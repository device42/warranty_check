#!/usr/bin/env python
import sys

from Files.shared import Config, Device42rest
from Files.warranty_cisco import Cisco
from Files.warranty_dell import Dell
from Files.warranty_hp import Hp
from Files.warranty_ibm_lenovo import IbmLenovo
from Files.warranty_meraki import Meraki


def get_hardware_by_vendor(name):
    # Getting the hardware models, so we specifically target the manufacturer systems registered
    hardware_models = d42_rest.get_hardware_models()
    models = []
    if hardware_models:
        for model in hardware_models['models']:
            manufacturer = model.get('manufacturer')
            if manufacturer and name not in manufacturer.lower():
                continue

            model_name = model.get('name')
            if model_name and model_name not in models:
                models.append(model_name)

    return ','.join(models)


def get_vendor_api(name):

    current_cfg = cfg.get_config(name)
    api = None

    if vendor == 'cisco':
        cisco_params = {
            'url': current_cfg['url'],
            'client_id': current_cfg['client_id'],
            'client_secret': current_cfg['client_secret'],
            'd42_rest': d42_rest
        }
        api = Cisco(cisco_params)

    elif vendor == 'dell':
        dell_params = {
            'url': current_cfg['url'],
            'client_id': current_cfg['client_id'],
            'client_secret': current_cfg['client_secret'],
            'd42_rest': d42_rest
        }
        api = Dell(dell_params)

    elif vendor == 'hp':
        hp_params = {
            'url': current_cfg['url'],
            'api_key': current_cfg['api_key'],
            'api_secret': current_cfg['api_secret'],
            'd42_rest': d42_rest
        }
        api = Hp(hp_params)

    elif vendor == 'ibm' or vendor == 'lenovo':
        ibm_lenovo_params = {
            'url': current_cfg['url'],
            'client_id': current_cfg['client_id'],
            'd42_rest': d42_rest
        }
        api = IbmLenovo(vendor, ibm_lenovo_params)

    elif vendor == "meraki":
        meraki_params = {
            'url': current_cfg['url'],
            'api_key': current_cfg['api_key'],
            'd42_rest': d42_rest
        }
        api = Meraki(meraki_params)

    return api


def loader(name, api, d42):

    # Locate the devices involved, based on the hardware models found, add offset with recursion
    offset = 0
    previous_batch = None
    while True:
        serials = []
        current_hardware_models = get_hardware_by_vendor(name)
        current_devices_batch = d42.get_devices(offset, current_hardware_models)

        # If previous batch the same as current we finish
        if previous_batch is not None:
            if previous_batch == current_devices_batch:
                print '\n[!] Finished'
                break

        previous_batch = current_devices_batch
        if current_devices_batch and 'Devices' in current_devices_batch and len(current_devices_batch['Devices']) > 0:
            items = [[x['device_id'], x['serial_no'], x['manufacturer']] for x in
                     current_devices_batch['Devices'] if x['serial_no'] and x['manufacturer']]
            for item in items:
                try:
                    d42_id, d42_serial, d42_vendor = item
                    if name in d42_vendor.lower():
                        print '[+] %s serial #: %s' % (name.title(), d42_serial)
                        serials.append(d42_serial)
                except ValueError as e:
                    print '\n[!] Error in item: "%s", msg : "%s"' % (item, e)

            inline_serials = ','.join(serials)

            if len(serials) > 0:
                result = vendor_api.run_warranty_check(inline_serials)

                if result is not None:
                    api.process_result(result, purchases)

            offset += 50
        else:
            print '\n[!] Finished'
            break


if __name__ == '__main__':

    # get settings from config file
    cfg = Config()
    d42_cfg = cfg.get_config('d42')
    discover = cfg.get_config('discover')

    # init
    d42_params = {
        'username': d42_cfg['username'],
        'password': d42_cfg['password'],
        'url': d42_cfg['url']
    }
    d42_rest = Device42rest(d42_params)

    # get purchases data from Device42
    orders = d42_rest.get_purchases()
    purchases = {}

    if orders and 'purchases' in orders:
        for order in orders['purchases']:
            if 'line_items' in order:
                purchase_id = order.get('purchase_id')
                order_no = order.get('order_no')

                for line_item in order['line_items']:
                    line_no = line_item.get('line_no')
                    devices = line_item.get('devices')
                    contractid = line_item.get('line_notes')
                    # POs with no start and end dates will now be included and given a hasher key with date min and max
                    start = line_item.get('line_start_date')
                    end = line_item.get('line_end_date')

                    if start and end and devices:
                        for device in devices:
                            if 'serial_no' in device:
                                serial = device['serial_no']
                                hasher = serial + contractid + start + end
                                if hasher not in purchases:
                                    purchases[hasher] = [purchase_id, order_no, line_no, contractid, start, end, discover['forcedupdate']]

    APPS_ROW = []
    if discover['cisco']:
        APPS_ROW.append('cisco')
    if discover['dell']:
        APPS_ROW.append('dell')
    if discover['hp']:
        APPS_ROW.append('hp')
    if discover['ibm']:
        APPS_ROW.append('ibm')
    if discover['lenovo']:
        APPS_ROW.append('lenovo')
    if discover['meraki']:
        APPS_ROW.append('meraki')

    for vendor in APPS_ROW:
        print '\n[+] %s section' % vendor
        vendor_api = get_vendor_api(vendor)
        loader(vendor, vendor_api, d42_rest)

    sys.exit()
