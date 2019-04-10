# Warranty check

## About Device42
[Device42](http://www.device42.com) is a comprehensive data center inventory management and IP Address management software that integrates centralized password management, impact charts and applications mappings with IT asset management.

## Intro
This script checks warranty status for Dell, HP, IBM and Lenovo manufactured devices stored in Device42.

## Prerequisites
In order for this script to check warranty status of the device, the device must have hardware model and serial number entered in Device42. Dell Warranty Status API key must be acquired as well.
- Device42 Hardware model must have "Dell", "Hewlett Packard", "IBM" or "LENOVO" in it's manufacturer data.
- Device42 Serial number must be set to "Dell", "Hewlett Packard", "IBM" or "LENOVO" device serial number.
- Dell's API key can be obtained by filling the on-boarding form. New and existing API users will need to register an account with TechDirect. Please check: http://en.community.dell.com/dell-groups/supportapisgroup/
- HP's API key can be obtained by filling the on-boarding form. Please, follow the instructions from here: https://developers.hp.com/css-enroll

## Plans
- Include life_cycle event to register the purchase date. Unfortunately it can’t can done now, as I can’t easily compare purchases with the information found at dell. The life_cycle event doesn’t give back the serial, only the devicename. It would be nice if the serial_no could be added to the output of GET /api/1.0/lifecycle_event/

## Gotchas
- If either hardware model or serial # is missing, warranty status won't be checked for device.
- IBM script points to warranty info not related to the SKU, serial given

## Change Log
- Please check `CHANGELOG.md`


## Usage
- Set required parameters in warranty.cfg file and run warranty_dell.py script:

## Linux Usage
- Install pip depend on your distro.
- Run `pip install requests`
- Run `python starter.py`

## Windows Usage
- Download the pip installer: [https://bootstrap.pypa.io/get-pip.py](https://bootstrap.pypa.io/get-pip.py)
- Open a console in the download folder as Admin and run `get-pip.py`.
- Add the path to your environment : "%PythonFolder%\Scripts"
- Run `pip install requests`
- Run `python starter.py`

## Compatibility
* requests module required
* Script runs on Linux and Windows
* Python 2.7