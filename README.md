#Warranty check


##About Device42
[Device42](http://www.device42.com) is a comprehensive data center inventory management and IP Address management software that integrates centralized password management, impact charts and applications mappings with IT asset management.

##  Intro
This script checks warranty status for Dell, HP and IBM manufactured devices stored in Device42. 
Note: Currently works only for Dell

##Prerequisites
In order for this script to check warranty status of the device, the device must have hardware model and serial number entered in Device42. Dell Warranty Status API key must be acquired as well.
- Device42 Hardware model must have "Dell" in it's manufacturer data.
- Device42 Serial number must be set to Dell's device serial number.
- Dell's API key can be obtained by filling the on-boarding form. Please, follow the instructions from this ppt file: http://en.community.dell.com/dell-groups/supportapisgroup/m/mediagallery/20428185

##Gotchas
If either hardware model or serial # is missing, warranty status won't be checked for device.
IBM and HP warranty checks are not implemented yet.

## Usage
Set required parameters in warranty.cfg file and run warranty_dell.py script:

	python starter.py

## Compatibility
* Script runs on Linux and Windows
* Python 2.7





