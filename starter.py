#!/usr/bin/env python
import sys
import time

from Files.shared import Config, Device42rest
from Files.warranty_dell import Dell
from Files.warranty_hp import Hp
from Files.warranty_ibm_lenovo import IbmLenovo

APPS_ROW = ['dell', 'ibm', 'lenovo', 'hewlett packard']


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

    if vendor == 'dell':
        dell_params = {
            'url': current_cfg['url'],
            'api_key': current_cfg['api_key'],
            'd42_rest': d42_rest
        }
        api = Dell(dell_params)

    elif vendor == 'hewlett packard':
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
            'url2': current_cfg['url2'],
            'd42_rest': d42_rest
        }
        api = IbmLenovo(vendor, ibm_lenovo_params)

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
                        # keep if statement in to prevent issues with vendors having choosen the same model names
                        # brief pause to let the API get a moment of rest and prevent errors
                        #time.sleep(1)
                        serials.append(d42_serial.upper())
                except ValueError as e:
                    print '\n[!] Error in item: "%s", msg : "%s"' % (item, e)

            inline_serials = ','.join(serials)

            if len(serials) > 0:
                result = vendor_api.run_warranty_check(inline_serials)

                if result is not None:
                    api.process_result(result, purchases)

            offset += 100
        else:
            print '\n[!] Finished'
            break

if __name__ == '__main__':

    # get settings from config file
    cfg = Config()
    d42_cfg = cfg.get_config('d42')

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
                for line_item in order['line_items']:
                    end = line_item.get('line_end_date')
                    start = line_item.get('line_start_date')
                    devices = line_item.get('devices')

                    if devices:
                        for device in devices:
                            if 'serial_no' in device:
                                serial = device['serial_no']
                                hasher = serial + start + end
                                if hasher not in purchases:
                                    purchases[serial + start + end] = [start, end]

    for vendor in APPS_ROW:
        print '\n[+] %s section' % vendor
        vendor_api = get_vendor_api(vendor)
        loader(vendor, vendor_api, d42_rest)

    sys.exit()
