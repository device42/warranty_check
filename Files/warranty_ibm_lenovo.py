import sys
import re
import time
import json
import copy
import random
import requests

from shared import DEBUG, RETRY, ORDER_NO_TYPE, left, Device42rest
from warranty_abstract import WarrantyBase

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class IbmLenovo(WarrantyBase, object):
    def __init__(self, vendor, params):
        super(IbmLenovo, self).__init__()
        self.url = params['url']
        self.client_id = params['client_id']
        self.debug = DEBUG
        self.retry = RETRY
        self.order_no = ORDER_NO_TYPE
        self.d42_rest = params['d42_rest']
        self.common = None
        self.requests = requests.session()
        self.vendor = vendor

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()

    def get_product_info(self, serials, retry=True):
        if self.debug:
            print '\t[+] Checking possible product "%s"' % serials

        timeout = 30

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'ClientID': self.client_id
        }

        params = {
            'Serial': serials
        }

        try:
            resp = self.requests.get(self.url, params=params, headers=headers, verify=True, timeout=timeout)
            msg = 'Status code: %s' % str(resp.status_code)
            if str(resp.status_code) == '401':
                print '\t[!] HTTP error. Message was: %s' % msg
                print '\t[!] waiting for 30 seconds to let the api server calm down'
                # suspecting blockage due to to many api calls. Put in a pause of 30 seconds and go on
                time.sleep(30)
                if retry:
                    print '\n[!] Retry'
                    self.get_product_info(serials, False)
                else:
                    return None
            else:
                if self.debug:
                    print
                    print resp.json()
                    print
                return resp.json()
        except requests.RequestException as e:
            self.error_msg(e)
            return None

    def run_warranty_check(self, inline_serials, retry=True):
        global full_serials
        full_serials = {}

        if self.debug:
            print '\t[+] Checking warranty "%s"' % inline_serials

        incoming_serials = inline_serials.split(',')
        inline_serials = []

        for d42_serial in incoming_serials:
            d42_serial = d42_serial.upper()
            if '_' in d42_serial:
                full_serials.update({d42_serial.split('_')[0]: d42_serial})
                d42_serial = d42_serial.split('_')[0]
            elif '(' in d42_serial:
                full_serials.update({d42_serial.split('(')[0]: d42_serial})
                d42_serial = d42_serial.split('(')[0]
            else:
                full_serials.update({d42_serial: d42_serial})
            inline_serials.append(d42_serial)

        result = self.get_product_info(inline_serials, retry)
        return result

    def process_result(self, result, purchases):
        global full_serials
        data = {}

        # The API returns results for single devices in a different format than multiple devices, this keeps everything
        # returned from the API in the same list format
        if 'Warranty' in result:
            result = [result]

        for item in result:
            # Warranties
            if 'Warranty' in item and len(item['Warranty']) > 0:
                warranties = item['Warranty']
            else:
                continue

            data.clear()
            serial = item['Serial']

            if self.order_no == 'common':
                order_no = self.common
            else:
                order_no = self.generate_random_order_no()

            data.update({'order_no': order_no})
            data.update({'completed': 'yes'})

            if self.vendor == 'ibm':
                data.update({'vendor': 'IBM'})
            else:
                data.update({'vendor': 'LENOVO'})

            data.update({'line_device_serial_nos': serial.split('.')[0]})
            data.update({'line_type': 'contract'})
            data.update({'line_item_type': 'device'})
            data.update({'line_completed': 'yes'})

            lines = []

            # process warranty line items for a device
            for warranty in warranties:
                try:
                    start_date = warranty['Start'].split('T')[0]
                    end_date = warranty['End'].split('T')[0]
                except (KeyError, AttributeError):
                    continue

                data.update({'line_start_date': start_date})
                data.update({'line_end_date': end_date})
                data.update({'line_contract_type': warranty['Type']})

                try:
                    # There's a max 64 character limit on the line service type field in Device42 (version 13.1.0)
                    service_level_description = left(warranty['Name'], 64)
                    data.update({'line_service_type': service_level_description})
                except:
                    pass

                # update or duplicate? Compare warranty dates by serial, contract_id and end date
                hasher = serial + start_date + end_date

                try:
                    d_purchase_id, d_order_no, d_line_no, d_contractid, d_start, d_end, forcedupdate = purchases[hasher]

                    if forcedupdate:
                        data['purchase_id'] = d_purchase_id
                        data.pop('order_no')
                        raise KeyError

                    # check for duplicate state
                    if d_start == start_date and d_end == end_date:
                        print '\t[!] Duplicate found. Purchase ' \
                              'for SKU "%s" with end date "%s" ' \
                              'is already uploaded' % (serial, end_date)
                except KeyError:
                    lines.append(copy.deepcopy(data))

            for line in lines:
                self.d42_rest.upload_data(line)
            data.clear()
