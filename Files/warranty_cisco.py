import json
import sys
import time
import random
import requests
from datetime import datetime, timedelta

from shared import DEBUG, RETRY, ORDER_NO_TYPE, left
from warranty_abstract import WarrantyBase

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass

#https://cloudsso.cisco.com/as/token.oauth2


class Cisco(WarrantyBase, object):

    def __init__(self, params):
        super(Cisco, self).__init__()
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
        access_token_request_url = "https://cloudsso.cisco.com/as/token.oauth2"

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

        # check to see if the access token is expired, if it is get a new one, else, continue
        if self.expires_at is None or self.expires_at is not None and self.expires_at <= datetime.utcnow():
            if self.debug > 1:
                print 'attempting to acquire access_token'

            self.get_access_token(self.client_id, self.client_secret)

        if self.access_token is None:
            if self.debug > 1:
                print 'unable to acquire access_token'
            return None

        # get the device information using the requested access token




    def process_result(self, result, purchases):
        pass


