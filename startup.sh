#!/bin/sh
SERVICE='snmpd'
 
if ps ax | grep -v grep | grep $SERVICE > /dev/null
then
   echo "$SERVICE service is running"
   /etc/init.d/snmpd stop
else
   echo "$SERVICE is not running"
fi
   
# copy snmpd.conf with appropriate setting to sefault location
cp snmpd.conf /etc/snmp/snmpd.conf

echo "starting SNMP Service"
/etc/init.d/snmpd restart

#echo 'Fetching configuration from NIFI'
python fetchConfiguration.py
if [ $? -eq 0 ]
then
  #echo 'Starting data collection from machine'
  python plc_collect.py

else
  echo "Problem in fetching configuration" 
  exit 1
fi

