import urllib3
http = urllib3.PoolManager()
import sys
# from urllib.parse import urlencode
import urllib
import uuid
import re
import logging
from logging.handlers import RotatingFileHandler
from logging import handlers
from logConfig import *
import json

log = logging.getLogger('')
log.setLevel(logging.DEBUG)
formatterstdout = logging.Formatter('%(levelname)s : %(message)s')
#formatterstdout = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
stdoutlog = logging.StreamHandler(sys.stdout)
stdoutlog.setFormatter(formatterstdout)
log.addHandler(stdoutlog)


formatterfile = logging.Formatter('%(asctime)s %(levelname)s %(message)s',"%Y-%m-%d %H:%M:%S")
#formatterfile = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
logfile = handlers.RotatingFileHandler(LOGFILE, maxBytes=(1000000), backupCount=3)
logfile.setFormatter(formatterfile)
log.addHandler(logfile)

# get mac address of device
def get_mac():
        mac = ':'.join(re.findall('..', '%012x' % uuid.getnode()))
        return str(mac)
macAddress=get_mac()

log.debug('Fetching configuration from NiFi for Edge device:[%s]',macAddress)
fields1={'MAC':macAddress}
encoded_args = urllib.urlencode(fields1)
#url = 'http://'+ HOST + ':5558/'+ FETCHURL + '?' + encoded_args
url = 'http://'+ HOST + ':' + PORT + '/'+ FETCHURL + '?' + encoded_args

try:
        r = http.request('GET', url)
        log.debug('HTTP Send Status: %d',r.status)
        log.debug(r.data)
except urllib3.exceptions.MaxRetryError as e:
        log.debug(e)
        sys.exit(1)           #return non zero return code to startup.sh to tell problem in fetching configuration.

#parsed_data = r.data.replace('null','"NoData"')
#config_data=eval(parsed_data)
config_data=json.loads(r.data)
machine_data=[]
for machine in config_data:
        machine_data.append(machine['machine'])
machineCount = list(set(machine_data))

#create configuration file which can store configuration in machineConfig.txt
writeTomachineConfig=""
with open("machineConfig.txt", "w+") as myfile:
        myfile.write("[machine-config]\n")
        if any("devicename" in d for d in config_data):
                writeTomachineConfig = writeTomachineConfig + "DeviceName              = "+ config_data[0]['devicename']+"\n"
        if any("facility" in d for d in config_data):
                writeTomachineConfig = writeTomachineConfig + "Facility              = "+ config_data[0]['facility']+"\n"
        if any("logic" in d for d in config_data):
                writeTomachineConfig = writeTomachineConfig + "Logic                 = "+ config_data[0]['logic']+"\n"
        if any("devicemodel" in d for d in config_data):
                writeTomachineConfig = writeTomachineConfig + "DeviceModel           = "+ config_data[0]['devicemodel']+"\n"
        if any("devicetype" in d for d in config_data):
                writeTomachineConfig = writeTomachineConfig + "DeviceType            = "+ config_data[0]['devicetype']+"\n"
        if any("pud" in d for d in config_data):
                writeTomachineConfig = writeTomachineConfig + "PUD                   = "+ str(config_data[0]['pud'])+"\n"
        for maxpart in config_data:                         # this to extract max part per cycle for ECP
                        if maxpart['signalid']=='ECP':
                                        data=maxpart['maxpartpercycle']
                                        writeTomachineConfig = writeTomachineConfig + "MaxPartPerCycle       = "+ str(data)+"\n"
					break
        writeTomachineConfig = writeTomachineConfig + "TotalMachines         = " +str(len(machineCount))+"\n"
        myfile.write(writeTomachineConfig)
        for x in range(int(len(machineCount))):
                data="MACHINE"+str(x+1)+"_NAME         = "+machineCount[x]+"\n"
                myfile.write(data)
                
                #Parse Digital Inputs
                goodbadPresent=0
                for machine in config_data:
                        if machine['machine']==machineCount[x]:
                                if machine['signalid']=='ECP':
                                        data= machineCount[x]+"_CYCLE        = "+machine['pin']+"\n"
                                        myfile.write(data)
                                if machine['signalid']=='QSP':
                                        data= machineCount[x]+"_Quality      = "+machine['pin']+"\n"
                                        myfile.write(data)
                                        goodbadPresent=1
                if goodbadPresent==0:
                        data= machineCount[x]+"_Quality      = NO\n"
                        myfile.write(data)
log.debug("Configuration fetched")
