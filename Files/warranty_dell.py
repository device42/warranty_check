import sys
import time
import random
import requests

from shared import Config, Device42rest, DEBUG, RETRY, ORDER_NO_TYPE

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class DELL:
    def __init__(self, params):
        self.url = params['url']
        self.api_key = params['api_key']
        self.debug = DEBUG
        self.retry = RETRY
        self.order_no = ORDER_NO_TYPE
        self.d42_rest = params['d42_rest']
        self.common = None

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()

    def run_warranty_check(self, sku, retry=False):
        if self.debug:
            print '\t[+] Checking warranty info for Dell "%s"' % sku
        service_tag = sku
        timeout = 10
        payload = {'id': service_tag, 'apikey': self.api_key, 'accept': 'Application/json'}

        try:
            resp = requests.get(self.url, params=payload, verify=True, timeout=timeout)
            msg = 'Status code: %s' % str(resp.status_code)
            if str(resp.status_code) == '401':
                print '\t[!] HTTP error. Message was: %s' % msg
                print '\t[!] waiting for 30 seconds to let the api server calm down :D'
                # suspecting blockage due to to many api calls. Put in a pause of 30 seconds and go on
                time.sleep(30)
                if not retry:
                    print '\n[!] Retry'
                    self.run_warranty_check(sku, True)
                else:
                    return None
            else:
                result = resp.json()
                return result
        except requests.RequestException as e:
            msg = str(e)
            print '\n[!] HTTP error. Message was: %s' % msg
            return None

    def process_result(self, result, service_tag, purchases):
        data = {}

        try:
            warranties = result['AssetWarrantyResponse'][0]['AssetEntitlementData']
            asset = result['AssetWarrantyResponse'][0]['AssetHeaderData']
            product = result['AssetWarrantyResponse'][0]['ProductHeaderData']
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

            '''
            For future implementation of registering the purchase date as a lifecycle event
            Add a lifecycle event for the system
            data.update({'date':ship_date})
            data.update({'type':'Purchased'})
            data.update({'serial_no':serial})
            d42.upload_lifecycle(data)
            data.clear()
            '''

            # We need check per warranty service item
            for item in warranties:
                data.clear()
                ship_date = asset['ShipDate'].split('T')[0]
                product_id = product['ProductId']

                data.update({'order_no': order_no})
                if ship_date:
                    data.update({'po_date': ship_date})
                data.update({'completed': 'yes'})

                data.update({'vendor': 'Dell'})
                data.update({'line_device_serial_nos': service_tag})
                data.update({'line_type': 'contract'})
                data.update({'line_item_type': 'device'})
                data.update({'line_completed': 'yes'})

                line_contract_id = item['ItemNumber']
                data.update({'line_notes': line_contract_id})
                data.update({'line_contract_id': line_contract_id})

                # Using notes as well as the Device42 API doesn't give back the line_contract_id,
                # so notes is now used for identification
                # Mention this to device42

                service_level_group = item['ServiceLevelGroup']
                if service_level_group == -1 or service_level_group == 5 or service_level_group == 8:
                    contract_type = 'Warranty'
                elif service_level_group == 8 and 'compellent' in product_id:
                    contract_type = 'Service'
                elif service_level_group == 11 and 'compellent' in product_id:
                    contract_type = 'Warranty'
                else:
                    contract_type = 'Service'
                data.update({'line_contract_type': contract_type})
                if contract_type == 'Service':
                    # Skipping the services, only want the warranties
                    continue

                try:
                    # There's a max 32 character limit on the line service type field in Device42 (version 10.2.1)
                    service_level_description = left(item['ServiceLevelDescription'], 32)
                    data.update({'line_service_type': service_level_description})
                except:
                    pass

                start_date = item['StartDate'].split('T')[0]
                end_date = item['EndDate'].split('T')[0]

                data.update({'line_start_date': start_date})
                data.update({'line_end_date': end_date})

                item = serial + line_contract_id + end_date

                # update or duplicate? Compare warranty dates by serial, contract_id and end date
                if item not in purchases:
                    try:
                        dstart, dend = purchases[serial + line_contract_id + end_date]
                        # duplicate
                        if dstart == start_date and dend == end_date:
                            print '\t[!] Duplicate found. Purchase ' \
                                  'for SKU "%s" and "%s" with end date "%s" ' \
                                  'is already uploaded' % (serial, line_contract_id, end_date)
                        else:
                            # add new line_item
                            self.d42_rest.upload_data(data)
                    except:
                        print '\t[!] KeyError. Purchase for SKU "%s" and "%s" ' \
                              'with end data "%s" failed' % (serial, line_contract_id, end_date)
                else:
                    # upload new warranty for already purchased
                    self.d42_rest.upload_data(data)
                    purchases[item] = [start_date, end_date]

                data.clear()

    @staticmethod
    def generate_random_order_no():
        order_no = ''
        for index in range(9):
            order_no += str(random.randint(0, 9))
        return order_no


def dates_are_the_same(dstart, dend, wstart, wend):
    if time.strptime(dstart, "%Y-%m-%d") == time.strptime(wstart, "%Y-%m-%d") and \
                    time.strptime(dend, "%Y-%m-%d") == time.strptime(wend, "%Y-%m-%d"):
        return True
    else:
        return False


def left(s, amount):
    return s[:amount]


def right(s, amount):
    return s[-amount:]


def mid(s, offset, amount):
    return s[offset:offset+amount]


def main():

    # get settings from config file
    cfg = Config()
    d42_cfg = cfg.get_config('d42')
    dell_cfg = cfg.get_config('dell')

    # init
    d42_params = {
        'username': d42_cfg['username'],
        'password': d42_cfg['password'],
        'url': d42_cfg['url']
    }
    d42_rest = Device42rest(d42_params)

    dell_params = {
        'url': dell_cfg['url'],
        'api_key': dell_cfg['api_key'],
        'd42_rest': d42_rest
    }
    dell_api = DELL(dell_params)

    # get purchases data from Device42
    orders = d42_rest.get_purchases()
    purchases = {}

    if orders and 'purchases' in orders:
        for order in orders['purchases']:
            if 'line_items' in order:
                for line_item in order['line_items']:
                    end = line_item.get('line_end_date')
                    start = line_item.get('line_start_date')
                    devices = line_item.get('devices')
                    line_contract_id = line_item.get('line_notes')

                    if devices:
                        for device in devices:
                            if 'serial_no' in device:
                                serial = device['serial_no']
                                hash = serial + line_contract_id + end
                                if hash not in purchases:
                                    purchases[serial + line_contract_id + end] = [start, end]


    '''
    For future implementation of registering the purchase date as a lifecycle event
    Can't be done now as life_cycle events give back the host name and not the serial_no. Therefore hard to compare data
    get life_cycle data from Device42
    lifecyclepurchase = d42.get_lifecycle()
    already_purchased = []

    if lifecyclepurchase:
       for purchase in lifecyclepurchase['lifecycle_events']:
           device = purchase.get('device')
    '''

    # Getting the hardware models, so we specifically target the manufacturer systems registered
    hardware_models = d42_rest.get_hardwaremodels()
    models = ''
    if hardware_models:
        for model in hardware_models['models']:
            manufacturer = model.get('manufacturer')
            if manufacturer and 'dell' not in manufacturer.lower():
                continue

            name = model.get('name')
            if name not in models:
                models = models + name + ','

    # Locate the devices involved, based on the hardware models found, add offset with recursion
    offset = 0
    previous_batch = None
    while True:
        devices = d42_rest.get_serials(offset, models)

        # If previous batch the same as current we finish
        if previous_batch is not None:
            if previous_batch == devices:
                print '\n[!] Finished'
                break

        previous_batch = devices
        if devices and 'Devices' in devices and len(devices['Devices']) > 0:
            items = [[x['device_id'], x['serial_no'], x['manufacturer']] for x in
                     devices['Devices'] if x['serial_no'] and x['manufacturer']]
            for item in items:
                try:
                    d42_id, serial, vendor = item
                    print '[+] serial #: %s' % serial
                except ValueError as e:
                    print '\n[!] Error in item: "%s", msg : "%s"' % (item, e)
                else:
                    if 'dell' in vendor.lower():
                        # keep if statement in to prevent issues with vendors having choosen the same model names
                        # brief pause to let the API get a moment of rest and prevent 401 errors
                        time.sleep(1)
                        result = dell_api.run_warranty_check(serial)
                        if result is not None:
                            dell_api.process_result(result, serial, purchases)
            offset += 100
            print 'added offset'
            if offset == 500:
                break
        else:
            print '\n[!] Finished'
            break

if __name__ == '__main__':
    main()
    sys.exit()
