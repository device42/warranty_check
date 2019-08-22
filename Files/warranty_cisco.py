from datetime import datetime, timedelta
import sys
import time
import random
import json
import requests

from shared import DEBUG, RETRY, ORDER_NO_TYPE, left
from warranty_abstract import WarrantyBase

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass

# resources
# https://github.com/meraki/automation-scripts/blob/master/merakilicensealert.py
# url_warranty = https://api.cisco.com/sn2info/v2/coverage/status/serial_numbers/{sr_no,sr_no,sr_no}


class Cisco(WarrantyBase, object):

    def __init__(self, params):
        super(Cisco, self).__init__()
        self.url = params['url']
        self.url2 = params['url2']
        self.client_id = params['client_id']
        self.client_secret = params['client_secret']
        self.meraki_key = params['meraki_api_key']
        self.use_cisco_api = False
        self.debug = DEBUG
        self.retry = RETRY
        self.order_no = ORDER_NO_TYPE
        self.d42_rest = params['d42_rest']
        self.common = None

        self.token = None
        self.token_type = None
        self.expiration = None

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()

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

        # ---------------------------------------- GET ACCESS TOKEN CISCO API ------------------------------------------
        # TODO: Serial to Information API requires Smart Net Total Care Access
        # https://developer.cisco.com/site/support-apis/
        if self.use_cisco_api:
            # if an access token expiration exists, if it does not gets an access token
            if self.expiration is None:
                if self.debug:
                    print "Access token does not exist, getting access token"
                self.get_oauth_token()

            # checks to see if the current time is past expiration, if it is renew access token
            if self.expiration is not None and self.expiration < datetime.now():
                if self.debug:
                    print "Access token expired, requesting new access token"
                self.renew_oauth_token()

            # headers required to make api requests with sn2info
            warranty_url = 'https://api.cisco.com/sn2info/v2/coverage/status/serial_numbers/'
            headers = {
                'Authorization': 'Bearer ' + self.token
            }

        else:
            # headers required to make meraki dashboard api request
            warranty_url = "https://api.meraki.com/api/v0/"
            headers = {
                'X-Cisco-Meraki-API-Key': self.meraki_key
            }
        # ---------------------------------------- START WARRANTY CHECK ------------------------------------------------
        # Once we have access to the cisco support API we can use this
        if self.use_cisco_api:
            # TODO: The EOX API requires you to have access to the Cisco support API. To get access to this API you have to be
            # TODO: a Cisco SMARTNet Customer or partner.
            payload = {
                'pageIndex': 50,
                'serialNumber': 'FOC1252W6EW'

            }

            eox_url = 'https://api.cisco.com/supporttools/eox/rest/5/EOXBySerialNumber/'

            # print warranty_url + ','.join(incoming_serials)

            # resp = requests.get(warranty_url, data=payload, headers=headers)
            # result = json.loads(resp.text)
            # print(result)

        # Integration with Meraki Dashboard API, alternative to not having cisco support api credentials
        else:
            # TODO: Setup test environment, Possible that the only devices detected are Cisco Meraki branded products
            # ------ Get a combined list of all organization IDs -------------------
            organizations_url = warranty_url + 'organizations'

            resp = requests.get(organizations_url, headers=headers)
            result = json.loads(resp.text)

            all_organization_ids = []

            for organization in result:
                if 'id' in organization:
                    all_organization_ids.append(organization['id'])

            if self.debug:
                print "        [+] Organization IDs:", all_organization_ids

            # ------ Get a combined list of all networks in each organization ------
            all_network_ids = []

            for organization_id in all_organization_ids:
                network_url = warranty_url + 'organizations/' + organization_id + '/networks'

                resp = requests.get(network_url, headers=headers)
                result = json.loads(resp.text)

                for network in result:
                    if 'id' in network:
                        all_network_ids.append(network['id'])

            if self.debug:
                print "        [+] Network IDs:", all_network_ids

            # ------ Get a combined list of all devices in each network ------------
            all_device_serials = []

            for network_id in all_network_ids:
                devices_url = warranty_url + 'networks/' + network_id + '/devices'

                resp = requests.get(devices_url, headers=headers)
                result = json.loads(resp.text)

                for device in result:
                    if 'serial' in device:
                        all_device_serials.append(device['serial'])

            if self.debug:
                print "        [+] Device Serial Numbers:", all_device_serials
                if len(all_device_serials) == 0:
                    print "            [!] There are no Cisco Meraki products in your organization"

    def renew_oauth_token(self):
        result = self.get_oauth_token()
        return result

    def get_oauth_token(self):
        timeout = 10

        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
            }

        try:
            # request access token
            resp = requests.post(self.url, data=payload, verify=True, timeout=timeout)
            result = json.loads(resp.text)

            # store access token information for reuse
            self.token = result['access_token']
            self.token_type = result['token_type']
            self.expiration = datetime.now() + timedelta(seconds=result['expires_in'])

            if self.debug:
                print
                print "access token: " + self.token
                print "token type: " + self.token_type
                print "expiration time: " + str(self.expiration)

        except KeyError:
            print "[!] Failed to retrieve access token from Cisco, did you enter the correct client_id and client_secret?"
            
        return result


