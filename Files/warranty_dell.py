import sys
import time
import random
import requests

import shared as config
from uploader import Device42

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class DELL():
    def __init__(self, url, api_key, debug, retry, order_no):
        self.url        = url
        self.api_key    = api_key
        self.debug      = debug
        self.retry      = retry
        self.order_no   = order_no
        self.common     = None

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()


    def run_warranty_check(self, sku):
        if self.debug:
            print '\t[+] Checking warranty info for Dell "%s"' % sku
        service_tag     = sku
        timeout         = 10
        payload         = {'id': service_tag, 'apikey': self.api_key, 'accept':'Application/json'}
        for x in range(self.retry):
            try:
                resp    = requests.get(self.url, params=payload, verify=True, timeout=timeout)
                result  = resp.json()
                data    = self.process_result(result, service_tag)
                return data
            except requests.RequestException as e:
                msg     = str(e)
                print '\n[!] HTTP error. Message was: %s' % e


    def process_result(self, result, service_tag):
        data = {}
        try:
            warranties  = result['AssetWarrantyResponse'][0]['AssetEntitlementData']
            asset       = result['AssetWarrantyResponse'][0]['AssetHeaderData']
        except IndexError:
            if self.debug:
                try:
                    msg = result['InvalidFormatAssets']['BadAssets']
                    if msg:
                        print '\t\t[-] Error: Bad asset: %s' % service_tag
                except Exception as ex:
                    print ex

        else:
            if self.order_no == 'vendor':
                order_no = asset['OrderNumber']
            elif self.order_no == 'common':
                order_no = self.common
            else:
                order_no = self.generate_random_order_no()

            data.update({'order_no':order_no})
            data.update({'vendor':'Dell'})
            data.update({'line_device_serial_nos':service_tag})
            data.update({'line_type':'contract'})
            data.update({'line_item_type':'device'})

            # we need longest/last warranty
            timestamps = {}
            ts         = time.strptime("0001-01-01","%Y-%m-%d")
            for item in warranties:
                start_date  = item['StartDate'].split('T')[0]
                end_date    = item['EndDate'].split('T')[0]
                end_ts      = time.strptime(end_date,"%Y-%m-%d")
                if end_ts   > ts:
                    ts      = end_ts
                    timestamps.update({'line_start_date':start_date})
                    timestamps.update({'line_end_date':end_date})
            data.update(timestamps)
            timestamps.clear()
        return data

    def generate_random_order_no(self):
        order_no = ''
        for index in range(9):
            order_no += str(random.randint(0,9))
        return order_no


def dates_are_the_same(dstart, dend, wstart, wend):
    if time.strptime(dstart,"%Y-%m-%d") == time.strptime(wstart,"%Y-%m-%d") and \
                    time.strptime(dend,"%Y-%m-%d") == time.strptime(wend,"%Y-%m-%d"):
        return True
    else:
        return False


def main():
    # get settings from config file
    d42_username, d42_password, d42_url,\
           dell_api_key, dell_url, debug, retry, order_no_type = config.get_config('dell')

    # init
    d42  = Device42(d42_username, d42_password, d42_url, debug, retry)
    dell = DELL(dell_url, dell_api_key, debug, retry, order_no_type)

    # get data from Device42
    orders = d42.get_purchases()
    already_there = []
    dates   = {}
    if orders:
        for order in orders['purchases']:
            line_items =  order['line_items']
            for line_item in line_items:
		end   = line_item.get('line_end_date')
		start = line_item.get('line_start_date')
		devices = line_item.get('devices')
		if devices:
		  for device in devices:
		    serial = device['serial_no']
		    dates.update({serial:[start,end]})
		    if serial not in already_there:
			already_there.append(serial)

    devices = d42.get_serials()
    items = [[x['device_id'],x['serial_no'],x['manufacturer']] for x in devices['Devices'] if x['serial_no'] and  x['manufacturer']]
    for item in items:
        d42_id, serial, vendor = item
        print '\t[+] DELL serial #: %s' % serial
        if 'dell' in vendor.lower():
            #if len(serial) <= 7: # testing only original DELL...remove this
            warranty = dell.run_warranty_check(serial)
            if warranty:
                wend   = warranty.get('line_end_date')
                wstart = warranty.get('line_start_date')

                # update or duplicate? Compare warranty dates by serial
                if serial in already_there:
                    dstart, dend = dates[serial]
                    if dstart == wstart and dend == wend: # duplicate
                        print '[!] Duplicate found. Purchase for SKU "%s" is already uploaded' % serial
                    else:
                        # add new line_item
                        d42.upload_data(warranty)
                else:
                    # upload new warranty and add it's serial to 'already_there'
                    d42.upload_data(warranty)
                    already_there.append(serial)



if __name__ == '__main__':
    main()
    sys.exit()


