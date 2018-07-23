#!/usr/bin/env bash

# Before running this setup script: make sure you set chmod +x ./node_setup.sh"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"


echo "Installing required packages..."
# Install required packages
sudo apt-get update
sudo apt-get -y upgrade
sudo apt-get -y install bluez bluez-hcidump python3-dev libbluetooth-dev libcap2-bin
sudo apt-get -y install python3-venv


# Create and activate our virtual environment
cd $DIR
python3 -m venv .
source $DIR/bin/activate


# Set permissions for GPS dongle
sudo chmod 666 /dev/ttyACM0


# Give python the required socket permissions
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))


# Install Python packages
pip install --upgrade pip
pip install wheel
pip install -r app/requirements.txt


# Replace first line of run_node.py with correct interpreter for venv
VPYTHON=$(which python)
sed -i "1s/.*/$VPYTHON/" run_node.py


# Allow Python script to run
chmod +x run_node.py


# Create service for Node, awaiting registration
# On registration: node.service is enabled (thanks to sudo access for user pi)
EXEC="$DIR/run_node.py"
sed -i 's/ExecStart=.*/ExecStart=$EXEC/' $DIR/setup/node.service
sed -i 's/WorkingDirectory=.*/$DIR/' $DIR/setup/node.service
sudo cp $DIR/setup/node.service /etc/systemd/system/node.service


# Run the NodeRegistration server
EXEC="$VPYTHON $DIR/app/src/node_register.py"
sed -i 's/ExecStart=.*/ExecStart=$EXEC/' $DIR/setup/node_register.service
sed -i 's/WorkingDirectory=.*/$DIR/' $DIR/setup/node_register.service
sudo cp $DIR/setup/node.service /etc/systemd/system/node_register.service
sudo systemctl start node_register.service
sudo systemctl enable node_register.service