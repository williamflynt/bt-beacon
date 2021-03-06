#!/usr/bin/env bash

# Before running this make sure you set chmod +x ./ble_scan_setup.sh

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
# Go to this DIR on login
echo "cd ${DIR}" >> /home/${USER}/.bashrc

echo "Installing required packages..."
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
echo "Activating virtual environment"
source ${DIR}/venv/bin/activate
# Activate venv on login to shell
echo "source ${DIR}/venv/bin/activate" >> /home/${USER}/.bashrc


echo "Providing socket permissions to Python..."
# Give python the required socket permissions
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))

echo "Installing required Python packages..."
pip install --upgrade pip
pip install wheel
pip install -r app/requirements.txt
chmod +x ble_scan.sh

# Set path to venv python as env var
echo "Getting virtual environment Python path..."
VPYTHON=$(which python)

echo "Inserting Python executable path into service Python files..."
# Replace first line of do_ble_scan.py with correct interpreter for venv
VPYTHON=$(which python)
sed -i " 1 s@.*@&$VPYTHON@" do_ble_scan.py

echo "Copying ble_scan.service ..."
# Create service for BLE scanner
EXEC="$VPYTHON $DIR/do_ble_scan.py"
sed -i "s@ExecStart=.*@ExecStart=$EXEC@" $DIR/setup/ble_scan.service
sed -i "s@WorkingDirectory=.*@WorkingDirectory=$DIR@" $DIR/setup/ble_scan.service
sudo cp $DIR/setup/ble_scan.service /etc/systemd/system/ble_scan.service

echo "Copying ble_placement.service ..."
# Run the BLE Placement server
EXEC="$VPYTHON $DIR/app/src/ble_placement.py"
sed -i "s@ExecStart=.*@ExecStart=$EXEC@" $DIR/setup/ble_placement.service
sed -i "s@WorkingDirectory=.*@WorkingDirectory=$DIR@" $DIR/setup/ble_placement.service
sudo cp $DIR/setup/ble_placement.service /etc/systemd/system/ble_placement.service

echo "Enabling and starting BLE Scan Service..."
# Start the service(s)
sudo systemctl daemon-reload
sudo systemctl start ble_scan.service
sudo systemctl enable ble_scan.service

echo "Enabling and starting BLE Placement Service..."
# Start the service(s)
sudo systemctl daemon-reload
sudo systemctl start ble_placement.service
sudo systemctl enable ble_placement.service

echo "Done. BLE scanning is active on boot."