import sys
import json
import time
import random
import requests

from shared import DEBUG, RETRY, ORDER_NO_TYPE, left
from warranty_abstract import WarrantyBase

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class Hp(WarrantyBase, object):
    def __init__(self, params):
        super(Hp, self).__init__()
        self.url = params['url']
        self.api_key = params['api_key']
        self.api_secret = params['api_secret']
        self.debug = DEBUG
        self.retry = RETRY
        self.order_no = ORDER_NO_TYPE
        self.d42_rest = params['d42_rest']
        self.common = None

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()

        self.access_key = self.get_access_key()

    def get_access_key(self):
        if self.debug:
            print '\t[+] Getting HP access token'

        timeout = 10
        payload = {
            'apiKey': self.api_key,
            'apiSecret': self.api_secret,
            'grantType': 'client_credentials',
            'scope': 'warranty'
        }
        headers = {
            'Accept': 'application/json',
            'Content-type': 'application/x-www-form-urlencoded'
        }

        try:
            resp = requests.post(self.url + '/oauth/v1/token',
                                 data=payload, headers=headers, verify=True, timeout=timeout)
            result = json.loads(resp.text)
            return result['access_token']

        except requests.RequestException as e:
            self.error_msg(e)
            sys.exit()

    def prepare_job(self, inline_serials, retry=True):
        if self.debug:
            print '\t[+] Prepare API Job for "%s"' % inline_serials

        timeout = 5
        payload = [{'sn': x} for x in inline_serials.split(',')]
        headers = {
            'Authorization': 'Bearer %s' % self.access_key,
            'Content-type': 'application/json'
        }

        try:
            resp = requests.post(self.url + '/productWarranty/v1/jobs',
                                 json=payload, headers=headers, verify=True, timeout=timeout)
            result = json.loads(resp.text)
            if 'fault' not in result and 'error' not in resp.text:
                return result
            else:
                if retry:
                    # waiting for result
                    print '\t[+] HP API issue, trying again'
                    time.sleep(5)
                    print '\n[!] Retry'
                    self.prepare_job(inline_serials, False)
                else:
                    print '\n[!] Fail'
                    return None

        except requests.RequestException as e:
            if retry:
                # waiting for result
                print '\t[+] API issue, trying again'
                time.sleep(5)
                print '\t[!] Retry'
                self.prepare_job(inline_serials, False)
            else:
                print '\t[!] Fail, please try again later'
                return None

            self.error_msg(e)
            print '\t[!] API in beta and unstable version, please try again later'
            sys.exit()

    def check_job(self, job, retry=True):
        if self.debug:
            print '\t[+] Checking API Job "%s"' % job['jobId']

        timeout = 30
        headers = {
            'Authorization': 'Bearer %s' % self.access_key,
            'Content-type': 'application/json'
        }

        try:
            resp = requests.get(self.url + '/productWarranty/v1/jobs/' + job['jobId'],
                                headers=headers, verify=True, timeout=timeout)
            result = json.loads(resp.text)
            if result['status'] == 'completed':
                return result
            else:
                if retry:
                    # waiting for result
                    print '\t[+] Waiting 5 seconds before getting job result'
                    time.sleep(5)
                    print '\t[!] Retry'
                    self.check_job(job, False)
                else:
                    print '\t[!] Fail, please try again later'
                    return None

        except requests.RequestException as e:
            self.error_msg(e)
            return None

    def run_warranty_check(self, inline_serials, retry=True):
        # making sure the warranty also gets updated if the serial has been changed by decom lifecycle process
        global full_serials
        full_serials = {}

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

        if self.debug:
            print '\t[+] Checking warranty info for "%s"' % inline_serials
        timeout = 10
        headers = {
            'Authorization': 'Bearer %s' % self.access_key,
            'Content-type': 'application/json'
        }

        job = self.prepare_job(inline_serials)
        if self.debug:
            print '\t[+] Please wait... checking job status...'
        time.sleep(10)
        if self.check_job(job) is None:
            return None

        try:
            if self.debug:
                print '\t[+] Please wait... checking job result...'
            time.sleep(10)
            resp = requests.get(self.url + '/productWarranty/v1/jobs/' + job['jobId'] + '/results',
                                headers=headers, verify=True, timeout=timeout)
            result = resp.json()
            if 'fault' in result or ('message' in result and result['message'] == 'An error has occurred.'):
                if retry:
                    # waiting for result
                    print '\t[+] Waiting 5 seconds before getting job result'
                    time.sleep(5)
                    print '\t[!] Retry'
                    self.run_warranty_check(inline_serials, False)
                else:
                    print '\t[!] Fail, please try again later / or try to reproduce API call here : https://developers.hp.com/css/api/product-warranty-api-0, if you be able to get correct results, please create "issue" in the our repository. Thanks.'
                    return None
            else:
                return result

        except requests.RequestException as e:
            self.error_msg(e)
            return None

    def process_result(self, result, purchases):
        global full_serials
        data = {}

        for item in result:

            if item['type'] is None:
                print 'Skip serial #: %s ( no "warranty type", probably expired )' % item['sn']
                continue

            data.clear()
            serial = item['sn']

            if self.order_no == 'common':
                order_no = self.common
            else:
                order_no = self.generate_random_order_no()

            data.update({'order_no': order_no})
            data.update({'completed': 'yes'})
            data.update({'vendor': 'HP'})
            data.update({'line_device_serial_nos': full_serials[serial]})
            data.update({'line_type': 'contract'})
            data.update({'line_item_type': 'device'})
            data.update({'line_completed': 'yes'})

            start_date = item['startDate'].split('T')[0]
            end_date = item['endDate'].split('T')[0]

            data.update({'line_start_date': start_date})
            data.update({'line_end_date': end_date})
            data.update({'line_contract_type': item['type']})

            try:
                # There's a max 64 character limit on the line service type field in Device42 (version 13.1.0)
                service_level_description = left(sub_item['ServiceLevelDescription'], 64)
                data.update({'line_service_type': service_level_description})
            except:
                pass

            # update or duplicate? Compare warranty dates by serial, contract_id and end date
            hasher = serial.lower() + start_date + end_date

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
                self.d42_rest.upload_data(data)
                data.clear()
