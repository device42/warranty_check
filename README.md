#Warranty check

##About Device42
[Device42](http://www.device42.com) is a comprehensive data center inventory management and IP Address management software that integrates centralized password management, impact charts and applications mappings with IT asset management.

## Intro
This script checks warranty status for Dell, HP, IBM and Lenovo manufactured devices stored in Device42.

## Prerequisites
In order for this script to check warranty status of the device, the device must have hardware model and serial number entered in Device42. Dell Warranty Status API key must be acquired as well.
- Device42 Hardware model must have "Dell", "Hewlett Packard", "IBM" or "LENOVO" in it's manufacturer data.
- Device42 Serial number must be set to "Dell", "Hewlett Packard", "IBM" or "LENOVO" device serial number.
- Dell's API key can be obtained by filling the on-boarding form. Please, follow the instructions from this ppt file: http://en.community.dell.com/dell-groups/supportapisgroup/m/mediagallery/20428185
- HP's API key can be obtained by filling the on-boarding form. Please, follow the instructions from here: https://developers.hp.com/css-enroll

## New Changes
- Added section to also update systems which have had their serials numbers changed due to a life_cycle event.
- Using offset per 50 requests instead of 100. The Dell API seems to limit response to 80 serials. For every 100 requests no info came back for the last 20 serials.
- Added a service_level_group for dell equipment as that also has warranty contracts

## Changes
- Moved from just showing last date to showing all warranties and services found in the api call
- Comparison on existence of registration per purchase/support info (per line on the order) based on serial, line contract id and contract end date
- Moved from querying ALL devices to just querying the devices from the vendor itself (so skipping virtual machines and other manufacturers)
- Using offset per 100 requests instead of doing a full request of all devices
- Brief pause per api call to prevent blockage at the api request site (1 second pause per api call)
- Making a remark if the session for the api call is unauthorized (http code 401)

## Plans
- Include life_cycle event to register the purchase date. Unfortunately it can’t can done now, as I can’t easily compare purchases with the information found at dell. The life_cycle event doesn’t give back the serial, only the devicename. It would be nice if the serial_no could be added to the output of GET /api/1.0/lifecycle_event/

## Gotchas
If either hardware model or serial # is missing, warranty status won't be checked for device.
HP script unstable, may require retries.

## Usage
Set required parameters in warranty.cfg file and run warranty_dell.py script:

	python starter.py

## Compatibility
* Script runs on Linux and Windows
* Python 2.7
