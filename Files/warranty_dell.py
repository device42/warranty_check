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
                msg = 'Status code: %s' % str(resp.status_code)
                if str(resp.status_code) == '401':
                    print '\t[!] HTTP error. Message was: %s' % msg
                    print '\t[!] waiting for 30 seconds to let the api server calm down :D'
                    time.sleep(30) # suspecting blockage due to to many api calls. Put in a pause of 30 seconds and go on
                else:
                    result  = resp.json()
                    data    = self.process_result(result, service_tag)
                    return data
            except requests.RequestException as e:
                msg     = str(e)
                print '\n[!] HTTP error. Message was: %s' % msg


    def process_result(self, result, service_tag):
        data = {}
        try:
            warranties  = result['AssetWarrantyResponse'][0]['AssetEntitlementData']
            asset       = result['AssetWarrantyResponse'][0]['AssetHeaderData']
            product     = result['AssetWarrantyResponse'][0]['ProductHeaderData']
        except IndexError:
            if self.debug:
                try:
                    msg = result['InvalidFormatAssets']['BadAssets']
                    if msg:
                        print '\t\t[-] Error: Bad asset: %s' % service_tag
                except Exception as e:
                    print e

        else:
            if self.order_no == 'vendor':
                order_no = asset['OrderNumber']
            elif self.order_no == 'common':
                order_no = self.common
            else:
                order_no = self.generate_random_order_no()

            serial = service_tag

            # For future implementation of registering the purchase date as a lifecycle event
            #Add a lifecycle event for the system
            #data.update({'date':shipdate})
            #data.update({'type':'Purchased'})
            #data.update({'serial_no':serial})
            #d42.upload_lifecycle(data)
            #data.clear()

            #we need check per warranty service item
            for item in warranties:
                data.clear()
                shipdate    = asset['ShipDate'].split('T')[0]
                ProductId   = product['ProductId']

                data.update({'order_no':order_no})
                if shipdate:
                    data.update({'po_date':shipdate})
                data.update({'completed':'yes'})

                data.update({'vendor':'Dell'})
                data.update({'line_device_serial_nos':service_tag})
                data.update({'line_type':'contract'})
                data.update({'line_item_type':'device'})
                data.update({'line_completed':'yes'})

                line_contract_id= item['ItemNumber']
                data.update({'line_notes':line_contract_id})
                data.update({'line_contract_id':line_contract_id})
                #using notes as well as the Device42 API doesn't give back the line_contract_id, so notes is now used for identification
                #mention this to device42

                servicelevelgroup= item['ServiceLevelGroup']
                if servicelevelgroup==-1 or servicelevelgroup==5 or servicelevelgroup==8:
                    contracttype='Warranty'
                elif servicelevelgroup==8 and 'compellent' in ProductId:
                    contracttype='Service'
                elif servicelevelgroup==11 and 'compellent' in ProductId:
                    contracttype='Warranty'
                else:
                    contracttype='Service'
                data.update({'line_contract_type':contracttype})
                if contracttype=='Service':
                    #Skipping the services, only want the warranties
                    continue

                try:
                    #There's a max 32 character limit on the line service type field in Device42 (version 10.2.1)
                    serviceleveldescription= left(item['ServiceLevelDescription'],32)
                    data.update({'line_service_type':serviceleveldescription})
                except:
                    pass

                start_date  = item['StartDate'].split('T')[0]
                end_date    = item['EndDate'].split('T')[0]

                wstart = start_date
                wend   = end_date

                data.update({'line_start_date':start_date})
                data.update({'line_end_date':end_date})

                # update or duplicate? Compare warranty dates by serial, contract_id and end date
                if serial+line_contract_id+wend in already_there:
                    try:
                        dstart, dend = dates[serial+line_contract_id+wend]
                        if dstart == wstart and dend == wend: # duplicate
                            print '\t[!] Duplicate found. Purchase for SKU "%s" and "%s" with end date "%s" is already uploaded' % (serial,line_contract_id,wend)
                        else:
                            # add new line_item
                            d42.upload_data(data)
                    except:
                        print '\t[!] KeyError. Purchase for SKU "%s" and "%s" with end data "%s" failed' % (serial,line_contract_id,wend)
                else:
                    # upload new warranty to 'already_there'
                    d42.upload_data(data)
                    already_there.append(serial+line_contract_id+wend)
                data.clear()


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

def left(s, amount):
    return s[:amount]

def right(s, amount):
    return s[-amount:]

def mid(s, offset, amount):
    return s[offset:offset+amount]

def getdevices(offset,models,previous):
    devices = d42.get_serials(offset,models)
    if devices == previous:
        print '\n\t[!] Breaking loop, duplicate information found after new offset'
        return

    if devices and devices.has_key('Devices') and int(len(devices['Devices'])) > 0:
        items = [[x['device_id'],x['serial_no'],x['manufacturer']] for x in devices['Devices'] if x['serial_no'] and  x['manufacturer']]
        for item in items:
            try:
                d42_id, serial, vendor = item
                print '[+] serial #: %s' % serial
            except ValueError as e:
                print '\n[!] Error in item: "%s"' % item
            else:
                if 'dell' in vendor.lower():
                    #keep if statement in to prevent issues with vendors having choosen the same model names
                    time.sleep(1) # brief pause to let the API get a moment of rest and prevent 401 errors
                    dell.run_warranty_check(serial)
        offset += 100
        getdevices(offset,models,devices)
    else:
        return

def main():
    global already_there,d42,dell,dates,models
    # get settings from config file
    d42_username, d42_password, d42_url,\
           dell_api_key, dell_url, debug, retry, order_no_type = config.get_config('dell')

    # init
    d42  = Device42(d42_username, d42_password, d42_url, debug, retry)
    dell = DELL(dell_url, dell_api_key, debug, retry, order_no_type)

    # get purchase data from Device42
    orders = d42.get_purchases()
    already_there = []
    dates   = {}

    if orders and orders.has_key('purchases'):
        for order in orders['purchases']:
            if order.has_key('line_items'):
                line_items =  order['line_items']
                for line_item in line_items:
                    end = line_item.get('line_end_date')
                    start = line_item.get('line_start_date')
                    devices = line_item.get('devices')
                    contracttype = line_item.get('line_contract_type')
                    line_contract_id = line_item.get('line_notes')

                    if devices:
                        for device in devices:
                            if device.has_key('serial_no'):
                                serial = device['serial_no']
                                if serial+line_contract_id+end not in already_there:
                                    already_there.append(serial+line_contract_id+end)
                                if start and end:
                                    dates.update({serial+line_contract_id+end: [start, end]})


    # For future implementation of registering the purchase date as a lifecycle event
    # Can't be done now as life_cycle events give back the host name and not the serial_no. Therefore hard to compare data
    # get life_cycle data from Device42
    #lifecyclepurchase = d42.get_lifecycle()
    #already_purchased = []
    #
    #if lifecyclepurchase:
    #    for purchase in lifecyclepurchase['lifecycle_events']:
    #        device = purchase.get('device')

    #Getting the hardware models, so we specifically target the manufacturer systems registered
    hardwaremodels  = d42.get_hardwaremodels('Dell')
    #print int(len(hardwaremodels['models']))
    models=''
    if hardwaremodels:
        for model in hardwaremodels['models']:
            name = model.get('name')
            if not name in models:
                models = models+name+','
        #print left(models,len(models)-1)

    #Locate the devices involved, based on the hardware models found
    offset = 0
    getdevices(offset,models,'none')



if __name__ == '__main__':
    main()
    sys.exit()
