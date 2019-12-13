import json
import sys
import time
import random
import requests
import datetime
from datetime import timedelta, datetime

from shared import DEBUG, RETRY, ORDER_NO_TYPE, left
from warranty_abstract import WarrantyBase

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class Dell(WarrantyBase, object):
    def __init__(self, params):
        super(Dell, self).__init__()
        self.url = params['url']
        self.client_id = params['client_id']
        self.client_secret = params['client_secret']
        self.debug = DEBUG
        self.retry = RETRY
        self.order_no = ORDER_NO_TYPE
        self.d42_rest = params['d42_rest']
        self.common = None

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()

        # OAuth 2.0
        self.expires_at = None
        self.access_token = None

    # OAth 2.0
    def get_access_token(self, client_id, client_secret):
        access_token_request_url = "https://apigtwb2c.us.dell.com/auth/oauth/v2/token"

        timeout = 10

        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials'
        }
        try:
            resp = requests.post(access_token_request_url, data=payload, timeout=timeout)

            msg = 'Status code: %s' % str(resp.status_code)

            if str(resp.status_code) == '400' or str(resp.status_code) == '401' or str(resp.status_code) == '404':
                print 'HTTP error. Message was: %s' % msg
            elif str(resp.status_code) == '500':
                print 'HTTP error. Message was: %s' % msg
                print 'token access services may be down, try again later...'
                print resp.text
            else:
                # assign access token and expiration to instance variables
                result = resp.json()
                self.access_token = "Bearer " + str(result['access_token'])
                self.expires_at = datetime.utcnow() + timedelta(seconds=int(result['expires_in']))
                if self.debug > 1:
                    print "Request Token Acquired"
        except requests.RequestException as e:
            self.error_msg(e)

    def run_warranty_check(self, inline_serials, retry=True):
        global full_serials
        full_serials = {}

        if self.debug:
            print '\t[+] Checking warranty info for "%s"' % inline_serials
        timeout = 10

        # making sure the warranty also gets updated if the serial has been changed by decom lifecycle process
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
        inline_serials = ','.join(inline_serials)

        if self.expires_at is None or self.expires_at is not None and self.expires_at <= datetime.utcnow():
            if self.debug:
                print 'attempting to acquire access_token'

            self.get_access_token(self.client_id, self.client_secret)

        if self.access_token is None:
            if self.debug:
                print 'unable to acquire access_token'
            return None

        payload = {
            'servicetags': inline_serials,
            'Method': 'GET',
        }

        headers = {
            'Accept': 'Application/json',
            'Authorization': self.access_token
        }

        try:
            resp = requests.get(self.url, params=payload, headers=headers, verify=True, timeout=timeout)
            msg = 'Status code: %s' % str(resp.status_code)
            if str(resp.status_code) == '401' or str(resp.status_code) == '404':
                print '\t[!] HTTP error. Message was: %s' % msg
                print '\t[!] waiting for 30 seconds to let the api server calm down'
                # suspecting blockage due to to many api calls. Put in a pause of 30 seconds and go on
                time.sleep(30)
                if retry:
                    print '\n[!] Retry'
                    self.run_warranty_check(inline_serials, False)
                else:
                    return None
            else:
                result = resp.json()
                return result
        except requests.RequestException as e:
            self.error_msg(e)
            return None

    def process_result(self, result, purchases):
        global full_serials
        data = {}

        for item in result:
            try:
                warranties = item['entitlements']
            except IndexError:
                if self.debug:
                    try:
                        msg = str(result['InvalidFormatAssets']['BadAssets'])
                        if msg:
                            print '\t\t[-] Error: Bad asset: %s' % msg
                    except Exception as e:
                        print e

            else:
                if self.order_no == 'common':
                    order_no = self.common
                else:
                    order_no = self.generate_random_order_no()

                serial = item['serviceTag']

                # We need check per warranty service item
                for sub_item in warranties:
                    data.clear()

                    try:
                        if 'shipDate' in item:
                            ship_date = item['shipDate'].split('T')[0]
                        else:
                            ship_date = None
                    except AttributeError:
                        ship_date = None

                    data.update({'order_no': order_no})

                    if ship_date:
                        data.update({'po_date': ship_date})

                    data.update({'completed': 'yes'})

                    data.update({'vendor': 'Dell Inc.'})
                    data.update({'line_device_serial_nos': full_serials[serial]})
                    data.update({'line_type': 'contract'})
                    data.update({'line_item_type': 'device'})
                    data.update({'line_completed': 'yes'})

                    line_contract_id = sub_item['itemNumber']

                    data.update({'line_notes': line_contract_id})
                    data.update({'line_contract_id': line_contract_id})

                    # Using notes as well as the Device42 API doesn't give back the line_contract_id,
                    # so notes is now used for identification
                    # Mention this to device42

                    contract_type = 'Service'  # default contract type

                    if 'serviceLevelDescription' in sub_item:
                        if sub_item['serviceLevelDescription'] is not None:
                            if 'Parts' in sub_item['serviceLevelDescription'] or 'Onsite' in sub_item['serviceLevelDescription']:
                                contract_type = 'Warranty'
                        else:  # service level description is null, continue to next entitlement item
                            continue
                    else:  # service level description not listed in entitlement, continue to next item
                        continue

                    data.update({'line_contract_type': contract_type})

                    try:
                        # There's a max 64 character limit on the line service type field in Device42 (version 13.1.0)
                        service_level_description = left(sub_item['serviceLevelDescription'], 64)
                        data.update({'line_service_type': service_level_description})
                    except KeyError:
                        pass

                    # start date and end date may be missing from payload so it is only posted when both have values
                    try:
                        start_date = sub_item['startDate'].split('T')[0]
                        end_date = sub_item['endDate'].split('T')[0]
                        data.update({'line_start_date': start_date})
                        data.update({'line_end_date': end_date})
                    except AttributeError:
                        if self.debug:
                            print('[Alert]: SN:', serial, ': Missing start and end date for a listed entitlement')
                            print(left(sub_item['serviceLevelDescription'], 64))
                        continue

                    # update or duplicate? Compare warranty dates by serial, contract_id, start date and end date
                    hasher = serial + line_contract_id + start_date + end_date

                    try:
                        d_purchase_id, d_order_no, d_line_no, d_contractid, d_start, d_end, forcedupdate = purchases[hasher]

                        if forcedupdate:
                            data['purchase_id'] = d_purchase_id
                            data.pop('order_no')
                            raise KeyError

                        # check for duplicate state
                        if d_contractid == line_contract_id and d_start == start_date and d_end == end_date:
                            print '\t[!] Duplicate found. Purchase ' \
                                  'for SKU "%s" and "%s" with end date "%s" ' \
                                  'order_id: %s and line_no: %s' % (serial, line_contract_id, end_date, d_purchase_id, d_line_no)

                    except KeyError:
                        self.d42_rest.upload_data(data)
                        data.clear()
