#!/usr/bin/env bash

# Before running this setup script: make sure you set chmod +x ./node_setup.sh"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"


echo "Installing required packages..."
# Install required packages
sudo apt-get update
sudo apt-get -y upgrade
sudo apt-get -y install libatlas-base-dev
sudo apt-get -y install bluez bluez-hcidump python3-dev libbluetooth-dev libcap2-bin blueman
sudo apt-get -y install python3-venv


echo "Creating required directories..."
# Make log dir, etc
mkdir ${DIR}/logs


echo "Setting up virtual environment"
# Create and activate our virtual environment
cd $DIR
python3 -m venv ${DIR}/venv
# Add to our PYTHONPATH for import consistency
PATHLINE="export PYTHONPATH=$DIR/app/src:$DIR/app:$DIR:$PYTHONPATH"
sed -i "\$a$PATHLINE" ${DIR}/venv/bin/activate
sed -i "\$a$PATHLINE" ~/.bashrc
source ${DIR}/venv/bin/activate


echo "Granting GPS dongle permissions at /dev/ttyACM0"
# Set permissions for GPS dongle
sudo chmod 666 /dev/ttyACM0


echo "Providing socket permissions to Python..."
# Give python the required socket permissions
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))


# Install Python packages
pip install --upgrade pip
pip install wheel
pip install -r app/requirements.txt


echo "Inserting Python executable path into node files..."
# Replace first line of run_node.py with correct interpreter for venv
VPYTHON=$(which python)
sed -i " 1 s@.*@&$VPYTHON@" run_node.py


# Allow Python script to run
echo "Setting run permissions for node files..."
chmod +x run_node.py


echo "Copying node.service ..."
# Create service for Node, awaiting registration
# On registration: node.service is enabled (thanks to sudo access for user pi)
EXEC="$DIR/run_node.py"
sed -i "s@ExecStart=.*@ExecStart=$EXEC@" $DIR/setup/node.service
sed -i "s@WorkingDirectory=.*@WorkingDirectory=$DIR@" $DIR/setup/node.service
sudo cp $DIR/setup/node.service /etc/systemd/system/node.service


echo "Copying node_registration.service ..."
# Run the NodeRegistration server
EXEC="$VPYTHON $DIR/app/src/node_register.py"
sed -i "s@ExecStart=.*@ExecStart=$EXEC@" $DIR/setup/node_register.service
sed -i "s@WorkingDirectory=.*@WorkingDirectory=$DIR@" $DIR/setup/node_register.service
sudo cp $DIR/setup/node_register.service /etc/systemd/system/node_register.service


echo "Enabling and starting Node Registration..."
# Start the service(s)
sudo systemctl daemon-reload
sudo systemctl start node_register.service
sudo systemctl enable node_register.service


echo "Node is ready to register."