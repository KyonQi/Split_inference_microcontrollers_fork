#!/bin/bash

#Enable errors
set -e

echo "This script will configure your teensy for inference"

read -p "Please specify the role of the device to be configured: " mcu_role

read -p "Please specify the id of the device to be configured: " mcu_id

if test -s MCU_code/testbed.json; then 
echo "Current testbed:"
cat MCU_code/testbed.json
echo ""
fi

read -p "Would you like to append $mcu_role $mcu_id to the testbed? (Yy/Nn)" append_to_testbed

export mcu_role
export mcu_id
export append_to_testbed

read -p "Is the device connected to the PC? (Y/N)" ynconn
case $ynconn in 
    [yY]*);;
    *) echo "Check connection and try again" 
        exit;;
esac

echo "configuring Teensy 4.1 as $mcu_role $mcu_id"

cd ./MCU_code/PlatformIO_code/download
~/.platformio/penv/bin/pio run --target upload
echo "Waiting for COM connection"
sleep 5 
wait

echo "Download coordinator weights..."
cd ../../
python3 ./write_into_mcus_prog.py /dev/ttyACM0 c $mcu_id
echo "Logging..."
sleep 10
echo "Download worker weights..."
python3 ./write_into_mcus_prog.py /dev/ttyACM0 w $mcu_id
echo "Logging..."
sleep 10

echo "Flashing worker code"
cd ./PlatformIO_code/worker_code
~/.platformio/penv/bin/pio run -e teensy41_autoconf --target upload
sleep 5 &
wait

echo "checking if the configuration was successful"
ip_last=$((124-$mcu_id))
ping -c 5 169.254.71.$ip_last
res=$?
if [[ $res -eq 0 ]]; then
    echo "----DONE setting up $mcu_role $mcu_id!----"
else
    echo "FAILED!"
    exit
fi
