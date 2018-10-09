#!/bin/sh

SERVICE='snmpd'
# copy snmpd.conf with appropriate setting to Default location
cp $SERVICE.conf /etc/snmp/$SERVICE.conf
#echo "starting $SERVICE service"
if [ $? -eq 0 ]; then
/etc/init.d/$SERVICE restart
if [ $? -eq 0 ]; then
echo "$SERVICE started successfully"
fi

fi
#echo 'Fetching configuration from NIFI'
python fetchConfigurationDev.py
if [ $? -eq 0 ]
then
#echo 'Starting data collection from machine'
python collectMachinedata.py
else
echo "Problem in fetching configuration"
exit 1
fi


