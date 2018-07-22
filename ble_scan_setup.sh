#!/usr/bin/env bash

# Before running this make sure you set chmod +x ./ble_scan_setup.sh

sudo apt-get -y install bluez bluez-hcidump python3-dev libbluetooth-dev libcap2-bin

# Give python the required socket permissions
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))

pip install --upgrade pip
pip install wheel
pip install -r app/requirements.scan.txt
chmod +x ble_scan.sh
echo "To scan run:"
echo "-   ./ble_scan.sh"