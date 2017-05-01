import sys
import re
import time
import json
import copy
import random
import requests

from shared import DEBUG, RETRY, ORDER_NO_TYPE, left
from warranty_abstract import WarrantyBase

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class IbmLenovo(WarrantyBase, object):
    def __init__(self, vendor, params):
        super(IbmLenovo, self).__init__()
        self.url = params['url']
        self.url2 = params['url2']
        self.debug = DEBUG
        self.retry = RETRY
        self.order_no = ORDER_NO_TYPE
        self.d42_rest = params['d42_rest']
        self.common = None
        self.requests = requests.session()
        self.vendor = vendor

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()

    def get_product_info(self, serial, retry=True):
        if self.debug:
            print '\t[+] Checking possible product "%s"' % serial
        timeout = 10
        try:
            resp = self.requests.get(self.url + '?productId=' + serial, verify=True, timeout=timeout)
            msg = 'Status code: %s' % str(resp.status_code)
            if str(resp.status_code) == '401':
                print '\t[!] HTTP error. Message was: %s' % msg
                print '\t[!] waiting for 30 seconds to let the api server calm down'
                # suspecting blockage due to to many api calls. Put in a pause of 30 seconds and go on
                time.sleep(30)
                if retry:
                    print '\n[!] Retry'
                    self.get_product_info(serial, False)
                else:
                    return None
            else:
                return resp.json()
        except requests.RequestException as e:
            self.error_msg(e)
            return None

    def run_warranty_check(self, inline_serials, retry=True):
        if self.debug:
            print '\t[+] Checking warranty "%s"' % inline_serials
        timeout = 10
        result = []

        for serial in inline_serials.split(','):
            product_info = self.get_product_info(serial)
            current_product = None

            if len(product_info) > 1:
                for product in product_info:
                    current_product = self.get_product_info(product['Name'])[0]
                    if current_product['Name'] is not None:
                        break
            else:
                try:
                    current_product = product_info[0]
                except IndexError:
                    print '\t[+] Unable to find "%s" orders' % serial
                    continue

            if current_product is not None:

                url = self.url2 + '/' + current_product['Id'] + '?tabName=Warranty&beta=false'

                resp = self.requests.post(
                    url,
                    data={'SERIALNUMBERKEY': current_product['Serial']},
                    verify=True,
                    timeout=timeout
                )

                # possible redirects
                if resp.url != url:
                    resp = self.requests.post(
                        resp.url,
                        data={'SERIALNUMBERKEY': current_product['Serial']},
                        verify=True,
                        timeout=timeout
                    )

                data_object = re.search(r"ds_warranties=(.*?});", resp.text)
                json_object = json.loads(data_object.group(1))
                result.append(json_object)

        return result

    def process_result(self, result, purchases):
        data = {}

        for item in result:

            if 'BaseWarranties' in item and len(item['BaseWarranties']) > 0:
                warranties = item['BaseWarranties']
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

            for warranty in warranties:

                start_date = warranty['Start']['UTC'].split('T')[0]
                end_date = warranty['End']['UTC'].split('T')[0]

                data.update({'line_start_date': start_date})
                data.update({'line_end_date': end_date})
                data.update({'line_contract_type': warranty['Origin']})

                try:
                    # There's a max 64 character limit on the line service type field in Device42 (version 13.1.0)
                    service_level_description = left(sub_item['ServiceLevelDescription'], 64)
                    data.update({'line_service_type': service_level_description})
                except:
                    pass

                # update or duplicate? Compare warranty dates by serial, contract_id and end date
                hasher = serial.split('.')[0] + start_date + end_date

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
