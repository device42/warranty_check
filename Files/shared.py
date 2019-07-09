import os
import sys
import base64
import time
import requests
import ConfigParser


APP_DIR = os.path.abspath(os.path.dirname(__file__))
CONFIGFILE = os.path.join(APP_DIR, 'warranty.cfg')
CC = ConfigParser.RawConfigParser()

# check file
if os.path.isfile(CONFIGFILE):
    CC.readfp(open(CONFIGFILE, "r"))
    DEBUG = CC.getboolean('other', 'debug')
    DOQL = CC.getboolean('other', 'doql')
    RETRY = int(CC.get('other', 'retry'))
    ORDER_NO_TYPE = CC.get('other', 'order_no_type')
else:
    print '\n[!] Cannot find config file!'
    print '\tDid you rename warranty.cfg.example to warranty.cfg ?'
    print '\tExiting...'
    sys.exit()


class Config:

    def __init__(self):
        self.cc = CC

    def get_config(self, source):
        # check params for licence issuer
        if source == 'd42':
            res = self.__get_d42_cfg()
        elif source == 'discover':
            res = self.__get_discover_cfg()
        elif source == 'dell':
            res = self.__get_dell_cfg()
        elif source == 'hp':
            res = self.__get_hp_cfg()
        elif source == 'cisco':
            res = self.__get_cisco_cfg()
        elif source == 'ibm':
            res = self.__get_ibm_cfg()
        elif source == 'lenovo':
            res = self.__get_lenovo_cfg()
        elif source == 'other':
            res = self.__get_other_cfg()
        else:
            print '\n[!] Error. Unknown source "%s".\n\tExiting...\n' % source
            sys.exit()

        return res

    def __get_d42_cfg(self):
        # Device42 -----------------------------------------
        d42_username = self.cc.get('device42', 'username')
        d42_password = self.cc.get('device42', 'password')
        d42_url = self.cc.get('device42', 'url')
        return {
            'username': d42_username,
            'password': d42_password,
            'url': d42_url
        }

    def __get_discover_cfg(self):
        # Discover -----------------------------------------
        dell = self.cc.getboolean('discover', 'dell')
        hp = self.cc.getboolean('discover', 'hp')
        ibm = self.cc.getboolean('discover', 'ibm')
        lenovo = self.cc.getboolean('discover', 'lenovo')
        forcedupdate = self.cc.getboolean('discover', 'forcedupdate')
        return {
            'dell': dell,
            'hp': hp,
            'ibm': ibm,
            'lenovo': lenovo,
            'forcedupdate': forcedupdate
        }

    def __get_dell_cfg(self):
        # Dell ---------------------------------------------
        dell_url = self.cc.get('dell', 'url')
        dell_api_key = self.cc.get('dell', 'api_key')
        return {
            'url': dell_url,
            'api_key': dell_api_key
        }

    def __get_hp_cfg(self):
        # HP   ---------------------------------------------
        hp_url = self.cc.get('hp', 'url')
        hp_api_key = self.cc.get('hp', 'api_key')
        hp_api_secret = self.cc.get('hp', 'api_secret')
        return {
            'url': hp_url,
            'api_key': hp_api_key,
            'api_secret': hp_api_secret
        }

    def __get_cisco_cfg(self):
        # Cisco --------------------------------------------
        cisco_url = self.cc.get('cisco', 'url')
        cisco_api_key = self.cc.get('cisco', 'api_key')
        cisco_api_secret = self.cc.get('cisco', 'api_secret')
        return {
            'url': cisco_url,
            'api_key': cisco_api_key,
            'api_secret': cisco_api_secret
        }

    def __get_ibm_cfg(self):
        # IBM  ---------------------------------------------
        ibm_url = self.cc.get('ibm', 'url')
        ibm_url2 = self.cc.get('ibm', 'url2')
        return {
            'url': ibm_url,
            'url2': ibm_url2
        }

    def __get_lenovo_cfg(self):
        # lenovo -------------------------------------------
        lenovo_url = self.cc.get('lenovo', 'url')
        lenovo_url2 = self.cc.get('lenovo', 'url2')
        return {
            'url': lenovo_url,
            'url2': lenovo_url2
        }

    def __get_other_cfg(self):
        # lenovo -------------------------------------------
        debug = self.cc.getboolean('other', 'debug')
        doql = self.cc.getboolean('other', 'doql')
        return {
            'debug': debug,
            'doql': doql
        }


class Device42rest:
    def __init__(self, params):
        self.username = params['username']
        self.password = params['password']
        self.url = params['url']

    def upload_data(self, data):
        path = '/api/1.0/purchases/'
        url = self.url + path
        payload = data
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(self.username + ':' + self.password),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        r = requests.post(url, data=payload, headers=headers, verify=False)

        if DEBUG:
            print '\t[+] Posting data: %s' % str(payload)
            print '\t[*] Status code: %d' % r.status_code
            print '\t[*] Response: %s' % str(r.text)
        return r.json()

    def upload_lifecycle(self, data):
        path = '/api/1.0/lifecycle_event/'
        url = self.url + path
        payload = data
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(self.username + ':' + self.password),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        r = requests.put(url, data=payload, headers=headers, verify=False)

        if DEBUG:
            print '\t[+] Posting data: %s' % str(payload)
            print '\t[*] Status code: %d' % r.status_code
            print '\t[*] Response: %s' % str(r.text)
        return r.json()

    def get_data(self, path):
        url = self.url + path
        for x in range(RETRY):
            try:
                r = requests.get(url, auth=(self.username, self.password), verify=False)
                return r.json()
            except requests.RequestException as e:
                msg = str(e)
                print '\n[!] HTTP error. Message was: %s' % msg

    def get_devices(self, offset, models):
        if DEBUG:
            print '\n[!] Fetching devices from Device42 with offset=' + str(offset)
        api_path = '/api/1.0/devices/all/'
        cols = '?include_cols=serial_no,device_id,manufacturer&limit=50&offset=' + str(offset) + '&hardware=' + models
        path = api_path + cols
        response = self.get_data(path)
        return response

    def get_purchases(self):
        if DEBUG:
            print '\n[!] Fetching order numbers from Device42'
        api_path = '/api/1.0/purchases/'
        response = self.get_data(api_path)
        return response

    def fetcher(self, url):
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(self.username + ':' + self.password),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        r = requests.get(url, headers=headers, verify=False)
        msg = 'Status code: %s' % str(r.status_code)
        return r.text

    def get_doqldata(self, query):
        if DEBUG:
            print '\n[!] DOQL: ', query
        api_path = '/services/data/v1.0/query/?query='
        url = self.url+'/services/data/v1.0/query/?query='+query
        response = self.fetcher(url)
        return response

    def get_lifecycle(self):
        if DEBUG:
            print '\n[!] Fetching life cycle purchase events from Device42'
        api_path = '/api/1.0/lifecycle_event/?type=Purchased'
        response = self.get_data(api_path)
        return response

    def get_hardware_models(self):
        if DEBUG:
            print '\n[!] Fetching hardware models from Device42'
        api_path = '/api/1.0/hardwares/'
        response = self.get_data(api_path)
        return response


def dates_are_the_same(dstart, dend, wstart, wend):
    if time.strptime(dstart, "%Y-%m-%d") == time.strptime(wstart, "%Y-%m-%d") and \
                    time.strptime(dend, "%Y-%m-%d") == time.strptime(wend, "%Y-%m-%d"):
        return True
    else:
        return False


def left(s, amount):
    return s[:amount]
