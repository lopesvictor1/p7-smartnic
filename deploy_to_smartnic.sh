#!/bin/bash

# Configuration
SMARTNIC_USER=ubuntu               # User on the SmartNIC
SMARTNIC_IP=192.168.102.2           # SmartNIC IP
REMOTE_PATH=/home/ubuntu/p7    # Path on SmartNIC where the folder should be placed
LOCAL_FOLDER=./p7         # Folder on the host to send

# Check if the folder exists on the SmartNIC
echo "Checking if the folder exists on SmartNIC..."
ssh ${SMARTNIC_USER}@${SMARTNIC_IP} "[ -d ${REMOTE_PATH} ]" && EXIST=1 || EXIST=0

if [ $EXIST -eq 1 ]; then
    echo "Folder exists. Removing contents..."
    ssh ${SMARTNIC_USER}@${SMARTNIC_IP} "sudo rm -rf ${REMOTE_PATH}/* && mkdir -p ${REMOTE_PATH}"
else
    echo "Folder does not exist. Creating it..."
    ssh ${SMARTNIC_USER}@${SMARTNIC_IP} "mkdir -p ${REMOTE_PATH}"
fi

# Copy the entire folder to the SmartNIC
echo "Transferring folder to SmartNIC..."
scp -r ${LOCAL_FOLDER}/* ${SMARTNIC_USER}@${SMARTNIC_IP}:${REMOTE_PATH}/

echo "Transfer complete!"

echo "Setting environment..."
ssh ${SMARTNIC_USER}@${SMARTNIC_IP} "sudo bash ${REMOTE_PATH}/restart_environment.sh"
echo "Environment set..."

echo "Running custom_topology..."
ssh ${SMARTNIC_USER}@${SMARTNIC_IP} "sudo python3 ${REMOTE_PATH}/custom_topology.py"
