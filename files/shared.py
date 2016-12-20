import os
import sys
import ConfigParser


APP_DIR = os.path.abspath(os.path.dirname(__file__))
CONFIGFILE = os.path.join(APP_DIR, 'warranty.cfg')


def get_config(source):
    cc = ConfigParser.RawConfigParser()
    if os.path.isfile(CONFIGFILE):
        cc.readfp(open(CONFIGFILE, "r"))
    else:
        print '\n[!] Cannot find config file!'
        print '\tDid you rename warranty.cfg.example to warranty.cfg ?'
        print '\tExiting...'

        sys.exit()

    # Device42 -----------------------------------------
    d42_username = cc.get('device42', 'username')
    d42_password = cc.get('device42', 'password')
    d42_url = cc.get('device42', 'url')

    # Dell ---------------------------------------------
    dell_url = cc.get('dell', 'url')
    dell_api_key = cc.get('dell', 'api_key')

    # IBM  ---------------------------------------------
    ibm_url = cc.get('ibm', 'url')

    # HP   ---------------------------------------------
    hp_url = cc.get('hp', 'url')

    # Other ----------------------------------------------
    debug = cc.getboolean('other', 'debug')
    retry = cc.get('other', 'retry')
    order_no_type = cc.get('other', 'order_no_type')

    if source == 'dell':
        return d42_username, d42_password, d42_url, dell_api_key, dell_url, debug, int(retry), order_no_type
    elif source == 'ibm':
        return d42_username, d42_password, d42_url, ibm_url, debug, int(retry), order_no_type
    elif source == 'hp':
        return d42_username, d42_password, d42_url, hp_url, debug, int(retry), order_no_type
    else:
        print '\n[!] Error. Unknown source "%s".\n\tExiting...\n' % source
        sys.exit()
