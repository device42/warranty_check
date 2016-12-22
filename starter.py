#!/usr/bin/env python
import sys
import time

from Files.shared import Config, Device42rest
from Files.warranty_dell import Dell


def get_hardware_models(vendor):

    # Getting the hardware models, so we specifically target the manufacturer systems registered
    hardware_models = d42_rest.get_hardware_models()
    models = []
    if hardware_models:
        for model in hardware_models['models']:
            manufacturer = model.get('manufacturer')
            if manufacturer and vendor not in manufacturer.lower():
                continue

            name = model.get('name')

            if name and name not in models:
                models.append(name)

    return ','.join(models)


def loader(vendor, cfg, d42_rest):

    current_cfg = cfg.get_config(vendor)

    if vendor == 'dell':
        dell_params = {
            'url': current_cfg['url'],
            'api_key': current_cfg['api_key'],
            'd42_rest': d42_rest
        }
        vendor_api = Dell(dell_params)


    # Locate the devices involved, based on the hardware models found, add offset with recursion
    offset = 0
    previous_batch = None
    while True:
        current_hardware_models = get_hardware_models(vendor)
        current_devices_batch = d42_rest.get_devices(offset, current_hardware_models)

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
                    d42_id, serial, vendor = item
                    print '[+] serial #: %s' % serial
                except ValueError as e:
                    print '\n[!] Error in item: "%s", msg : "%s"' % (item, e)
                else:
                    if 'dell' in vendor.lower():
                        # keep if statement in to prevent issues with vendors having choosen the same model names
                        # brief pause to let the API get a moment of rest and prevent 401 errors
                        time.sleep(1)
                        result = vendor_api.run_warranty_check(serial)
                        if result is not None:
                            vendor_api.process_result(result, serial, purchases)
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
                    line_contract_id = line_item.get('line_notes')

                    if devices:
                        for device in devices:
                            if 'serial_no' in device:
                                serial = device['serial_no']
                                hasher = serial + line_contract_id + end
                                if hasher not in purchases:
                                    purchases[serial + line_contract_id + end] = [start, end]

    '''
    For future implementation of registering the purchase date as a lifecycle event
    Can't be done now as life_cycle events give back the host name and not the serial_no.
    Therefore hard to compare data
    get life_cycle data from Device42
    lifecyclepurchase = d42.get_lifecycle()
    already_purchased = []

    if lifecyclepurchase:
       for purchase in lifecyclepurchase['lifecycle_events']:
           device = purchase.get('device')
    '''

    loader('dell', cfg, d42_rest)
    sys.exit()
