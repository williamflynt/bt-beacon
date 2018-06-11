#!/usr/bin/env bash

sudo apt-get -y install bluez bluez-hcidump
sudo apt-get -y install python3-dev libbluetooth-dev libcap2-bin
# Give python the required socket permissions
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))
pip install -r app/requirements.scan.txt