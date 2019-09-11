import copy
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

# https://api.cisco.com/sn2info/v2/coverage/status/serial_numbers/{sr_no,sr_no,sr_no}


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

        # API Endpoints
        self.organization_endpoint = "/sn2info/v2/coverage/status/serial_numbers/"

        def run_warranty_check(self, inline_serials, retry=True):
            print("Coming Soon...")


