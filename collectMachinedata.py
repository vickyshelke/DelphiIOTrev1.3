
''' Software to gather Plc data from Delphi factory shops as a part of Delphi IOT '''


__author__     =      "Vikram Shelke"
__credits__    =      ["Wipro Team", "Delphi Team"]
__version__    =      "1.2"
__maintainer__ =      "Vikram Shelke"
__email__      =      "vikram.shelke@wipro.com"
__date__       =      "23/08/2018"
__status__     =      "Production" 


import RPi.GPIO as GPIO
import socket
import pytz
import time
import datetime
import urllib3
import logging
import urllib2
import sys
import ConfigParser
import uuid
import buffer
import Queue
#for python 2
import urllib
import threading
import re
from time import gmtime, strftime, sleep
from logging.handlers import RotatingFileHandler
from logging import handlers
import string
from  logConfig import *
#Check python version here and confirm if this code is reqiuired
#for python 3
#from urllib.parse import urlencode

http = urllib3.PoolManager()
q=Queue.Queue(maxsize=10) # que to hold messages temporary
queueLock = threading.Lock()
workque = []
threadlock=threading.Lock()  
#------------------global arrays to hold each machine information -------------------------------------------------- 

machineCycleSignal=[]                       # list to hold ECP  Signal
machineGoodbadPartSignal=[]                 #  list to hold QSP Signals  
machineName =[]                             #  this holds machine names  
machineobject=[]                            #  list to hold machine instances
machine_cycle_timestamp=[]                  # timestamp for each machine get stored in this list
finalmessage=[]                             #  whole message with timestamp + machine name + quality 
send_message=[]                             #  every machine has seprate send message for sending final message
machine_good_badpart_pinvalue=[]            #  this hold good/bad part pin values
machine_cycle_risingEdge_detected=[]        #   this hold Rising edges for ECP
machine_cycle_pinvalue=[]                   # this checks validity of machine cycle pulse  for each machine
messageinbuffer=0
buffered=False
thread_list = []
messagesSinceLastReboot=0
flaglist=[0,0,0,0,0,0,0,0,0,0]
#------------------------------------------------------------------------------------------------------------------



# ---------------------------------------Read Already updated machine configuration from fetchConfiguration.py  --------

config = ConfigParser.ConfigParser()
config.optionxform = str
config.readfp(open(r'machineConfig.txt'))
path_items = config.items( "machine-config" )
LOCATION=None
Logic=''
DeviceModel=''
DeviceType=''
PUD=''
DEVICENAME=''
for key, value in path_items:
        if 'DeviceName'in key:
                DEVICENAME = value
        if 'Facility'in key:
                LOCATION = value
        if 'Logic'in key:
                Logic = value
        if 'DeviceModel'in key:
                DeviceModel = value
        if 'DeviceType'in key:
                DeviceType = value
        if 'TotalMachines' in key:
                totalMachines=int(value)
        if 'PUD'  in key:
                PUD = value;
        if 'MACHINE' in key:
                machineName.append(value)
        if 'CYCLE' in key:
                machineCycleSignal.append(int (value))
        if '_Quality' in key:
                        if key == machineName[-1]+"_Quality":
                                if value !="NO":
                                        machineGoodbadPartSignal.append(int(value))
                                else:
                                        machineGoodbadPartSignal.append(0)

#Change Logic as per device

if Logic == 'Inverted': #For kristek and RPI
        VerificationLogic = 0
else : #For Iono PI siskon PI,din RPI
        VerificationLogic = 1

#----------------------------------------------------------------------------------------------------------------------


# --------------------------------initalization---------------------

for k in range (totalMachines):
        machine_good_badpart_pinvalue.append(0)
        machine_cycle_risingEdge_detected.append(0)
        machine_cycle_pinvalue.append(0)
        machine_cycle_timestamp.append("NODATA")
        finalmessage.append("NODATA")
        send_message.append("NODATA")


#---------------------------------------------------  log mechanism  configuration ------------------------------------

log = logging.getLogger('')
log.setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.ERROR)
if LOG_ENABLE == 'True':
        log.disabled = False
else :
        log.disabled=True


# write to console screen
#formatter_stdout = logging.Formatter("%(asctime)s %(levelname)s - %(message)s")
formatter_stdout = logging.Formatter("%(levelname)s - %(message)s")
log_stdout = logging.StreamHandler(sys.stdout)
log_stdout.setFormatter(formatter_stdout)
log.addHandler(log_stdout)
#use %(lineno)d for printnig line  no

# write logs to fileLOGFILE with rotating file handler which keeps file size limited 

formatter_file = logging.Formatter('%(asctime)s %(levelname)s %(message)s',"%Y-%m-%d %H:%M:%S")
#formatter_file = logging.Formatter("%(asctime)s %(levelname)s - %(message)s")
log_file = handlers.RotatingFileHandler(LOGFILE, maxBytes=(1000000), backupCount=3)
log_file.setFormatter(formatter_file)
log.addHandler(log_file)

#--------------------------------------------------------------------------------------------------------------------



#----------------------------------------------------   GPIO settings   -----------------------------------------------

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)


for setupPinAsInput in range(len(machineCycleSignal)):
        #log.debug( "setting  GPIO%d as input ",machineCycleSignal[setupPinAsInput])
        #comment out above line to check where gpio setting is done on required pin for ECP
        if PUD =='UP':                                   # check Device model as per table
                GPIO.setup(machineCycleSignal[setupPinAsInput], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        elif PUD == 'DOWN':
                GPIO.setup(machineCycleSignal[setupPinAsInput], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        else:
                GPIO.setup(machineCycleSignal[setupPinAsInput], GPIO.IN)

for setupPinAsInput in range(len(machineGoodbadPartSignal)):

        if machineGoodbadPartSignal[setupPinAsInput]!=0 :
                #log.debug( "setting GPIO%d as input ",machineGoodbadPartSignal[setupPinAsInput])
                # comment out above line to check gpio setting is done on required pin for QSP
                if PUD =='UP':
                        GPIO.setup(machineGoodbadPartSignal[setupPinAsInput], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                elif PUD =='DOWN':
                        GPIO.setup(machineGoodbadPartSignal[setupPinAsInput], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                else:
                        GPIO.setup(machineGoodbadPartSignal[setupPinAsInput], GPIO.IN)


#-------------------------------------------------------------------------------------------------------------------

log.debug('DeviceName:%s',DEVICENAME)
log.debug('Location:%s',LOCATION)
log.debug('Logic:%s',Logic)
log.debug('DeviceModel:%s',DeviceModel)
log.debug('DeviceType:%s',DeviceType)
log.debug('PUD:%s',PUD)
log.debug('machines connected   :%s',machineName)
log.debug('Machine cycle signal :%s',machineCycleSignal)
log.debug('Machine OK/NOTOK signals :%s',machineGoodbadPartSignal)


#Base Machine class

class Machine:
        'Common base class for all machines'
        MachineCount = 0
        def __init__(self, machine_cycle_rising_edge, machine_cycle_falling_edge, machine_cycle_pulse_time):
                self.machine_cycle_rising_edge = machine_cycle_rising_edge
                self.machine_cycle_falling_edge = machine_cycle_falling_edge
                self.machine_cycle_pulse_time = machine_cycle_pulse_time

        def machine_cycle_starttime(self):
                self.machine_cycle_rising_edge=time.time()

        def machine_cycle_stoptime(self):
                self.machine_cycle_falling_edge=time.time()

        def machine_cycle_cleartime(self):
                self.machine_cycle_rising_edge=0
                self.machine_cycle_falling_edge=0

        def machine_cycle_pulseTime(self,machinename):
                self.machinename=machinename
                self.machine_cycle_pulse_time=self.machine_cycle_falling_edge-self.machine_cycle_rising_edge
                log.debug ("Total Duration of MACHINE CYCLE SIGNAL for %s :%s ",machinename,str(self.machine_cycle_pulse_time))
                if self.machine_cycle_pulse_time >=2 and self.machine_cycle_pulse_time <= 4 :
                        return 1
                else:
                        return 0



# -------------------------------------------------------------------------------------------------------------------------------------------
'''
   get_mac function extract the mac address from system 

'''
#--------------------------------------------------------------------------------------------------------------------------------

def get_mac():
        mac = ':'.join(re.findall('..', '%012x' % uuid.getnode()))
        return mac

macAddress=str(get_mac())


#### form request 

fields1={'MAC':macAddress}
encoded_args = urllib.urlencode(fields1)
url = 'http://'+ HOST + ':' + PORT + '/'+ FETCHURL + '?' + encoded_args








'''------------------------------------------------------------------------------------------------
create backup of old data in timestamp.txt
now copy previous timestamp of messages (first and last)as old timestamp to make it old data 

----------------------------------------------------------------------------------------------------'''
with open('timestamp.txt', 'r') as f:
    # read a list of lines into data
    filedata = f.readlines()

# 
filedata[2]=filedata[0].replace('after latest','on previous')
filedata[3]=filedata[1].replace('after latest','on previous')
filedata[0]='TimeStamp of first ECP received after latest reboot:0120-00-00T00:00:00.300+00:00\n'
filedata[1]='TimeStamp of last ECP  received after latest reboot:0180-00-00T00:00:00.000+00:00\n'
# and write everything back
with open('timestamp.txt', 'w') as fd:
    fd.writelines( filedata )

#-------------------------------------------------------------------------------------------------------------------------------
'''
 send data function is used to send data to NiFi
 @param: timestamp
 @param:machinename
 @param:data ,is quality information

'''
#-------------------------------------------------------------------------------------------------------------------------------

def sendDataToDelphi(timestamp,machinename,data):
        data_send_from_machine_status=0
        global messageinbuffer
        fields={'ts':timestamp,'loc':LOCATION,'mach':machinename,'data':data}
        encoded_args = urllib.urlencode(fields)
        url = 'http://' + HOST + ':' + PORT + '/' + SENDURL +'?' + encoded_args
        try:
                r = http.request('GET', url,timeout=1.0)
                data_send_from_machine_status=r.status
        except urllib3.exceptions.MaxRetryError as e:
                data_send_from_machine_status=0
        if data_send_from_machine_status != 200 :
                if data_send_from_machine_status==0:
                        log.error(" Not able to send data to Delphi Azure: Connection Error")
                else:
                        log.debug("HTTP send status to Delphi : %d",data_send_from_machine_status)        
                buffer.push(timestamp+"||"+LOCATION+ "||" + machinename +"||"+data)
        else:        
            log.debug("HTTP send status to Delphi NiFi: %d",data_send_from_machine_status)


#---------------------------------------------------------------------------------------------------------------------------------------
'''
function to check network connectivity to Delphi NiFi

'''
#-----------------------------------------------------------------------------------------------------------------------------------------

def NiFiconnectionStatus_Delphi():
        
#        conn_url = 'http://' + HOST + ':' + PORT + '/' + SENDURL +'?'
        try:
                r = http.request('GET',url,timeout=2.0)    
                return str(r.status)
        except:
                return False




def detectedEvent(machineNo):
    global flaglist
    queueLock.acquire()
    event=''
    if (GPIO.input(machineCycleSignal[machineNo])!=VerificationLogic):
        if flaglist[machineNo]==1:
            event= 'Falling'
            machineobject[machineNo].machine_cycle_stoptime()
            flaglist[machineNo]=0
            workque[machineNo].put(event) 
    else:
        if flaglist[machineNo]==0:
            event= 'Rising'
            machineobject[machineNo].machine_cycle_starttime()
            flaglist[machineNo]=1
            workque[machineNo].put(event) 
    queueLock.release()





##plc machine 1 data collection
def plcMachine1(channel):
    
    detectedEvent(0)

##data collection machine 2
def plcMachine2(channel):
    detectedEvent(1)
def plcMachine3(channel):
    detectedEvent(2)

## data collection machine 4
def plcMachine4(channel):
    detectedEvent(3)
## data collection machine 5
def plcMachine5(channel):
    detectedEvent(4)
## data collection machine 6
def plcMachine6(channel):
    
    detectedEvent(5)
def plcMachine7(channel):
    detectedEvent(6)   
        
## data collection machine 8
def plcMachine8(channel):
    detectedEvent(7)   

def plcMachine9(channel):
    detectedEvent(8)
        
def plcMachine10(channel):
    detectedEvent(9)
        


#------------------------------------------------------------------------------------------------------------------------------

''' 
        process_machine_data function gathers Rising and Rising Edges, calculate pulse widh and quality of parts
        for respective machine 
        @param:  machineNo 
        @Return: none
'''
#------------------------------------------------------------------------------------------------------------------------------


def process_machine_data(machineNo):

        global q
        global workque
        global messagesSinceLastReboot
        log.debug("data collection started for %s",machineName[machineNo])
        while True:
            LOGIC= workque[machineNo].get()  
          
            if LOGIC=='Rising': # dry contact closed on machine cycle pin
                if machine_cycle_risingEdge_detected[machineNo] == 0:
                    machine_cycle_risingEdge_detected[machineNo] = 1
                    log.debug ("Rising edge : %s Cycle Signal ",machineName[machineNo])
                    #machineobject[machineNo].machine_cycle_starttime()
                    if machineGoodbadPartSignal[machineNo]==0:
                        machine_good_badpart_pinvalue[machineNo]=-1
                        #print "no goodbad part
                        #pass
                    else:
                        if (GPIO.input(machineGoodbadPartSignal[machineNo])==VerificationLogic): # check value of good_badpart_signal and set it to 1 if ok
                            machine_good_badpart_pinvalue[machineNo]=0
                        else: #good_badpart is not ok
                            machine_good_badpart_pinvalue[machineNo]=1
                else:
                        log.debug ("Multiple Rising Edge detected on %s", machineName[machineNo])
        
            else: # dry contact opend Rising edge detected for machine_cycle pin
                threadlock.acquire()
                if machine_cycle_risingEdge_detected[machineNo] == 1:
                        log.debug ("Falling edge : %s Cycle Signal ",machineName[machineNo])
                        
                        #machineobject[machineNo].machine_cycle_stoptime()
                        machine_cycle_risingEdge_detected[machineNo]=0
                        machine_cycle_timestamp[machineNo]=datetime.datetime.now(tz=pytz.UTC).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+"+00:00"
                        machine_cycle_pinvalue[machineNo]=machineobject[machineNo].machine_cycle_pulseTime(machineName[machineNo])
                        if machine_cycle_pinvalue[machineNo]==1:
                            if machineGoodbadPartSignal[machineNo]==0:
                                machine_good_badpart_pinvalue[machineNo]=-1   # "no goodbad part" set quality as -1
                                #pass
                            else:
                                if(GPIO.input(machineGoodbadPartSignal[machineNo])==VerificationLogic): # valid pulse
                                    machine_good_badpart_pinvalue[machineNo]=0            #good part
                                else:
                                    machine_good_badpart_pinvalue[machineNo]=1            # bad part
                                #try:
                               
                            finalmessage[machineNo]="Quality"+":"+str(machine_good_badpart_pinvalue[machineNo])
                            log.debug("%s ----> %s",machineName[machineNo],finalmessage[machineNo])
                            #send_message[machineNo]=machine_cycle_timestamp[machineNo]+"||"+machineName[machineNo]+"||"+finalmessage[machineNo]
                                #q.put(send_message[machineNo])
                                #q.task_done()
                            messagesSinceLastReboot= messagesSinceLastReboot+1
                            log.info(" machine Cycle signal received since last Reboot :%d",messagesSinceLastReboot)
                            with open("timestamp.txt", "r") as file: 
                                filedata=file.readlines() 
                                if messagesSinceLastReboot==1:        
                                        filedata[0]='timestamp of first ECP received after latest Reboot:'+ machine_cycle_timestamp[machineNo] +'\n'
                                else:
                      
                                        filedata[1]= 'timestamp of last ECP received after latest Reboot:'+ machine_cycle_timestamp[machineNo] +'\n'
                            with open('timestamp.txt', 'w') as file:
                                file.writelines( filedata )          

                            sendDataToDelphi(machine_cycle_timestamp[machineNo],machineName[machineNo],finalmessage[machineNo])
                                
                        else:
                                log.debug("%s cycle pulse width is invalid",machineName[machineNo])
                machineobject[machineNo].machine_cycle_cleartime()
                threadlock.release()    



#------------------------ create machine object and call function as per no of machine connected to device----------------------------------


plcMachine = lambda totalMachines: eval("plcMachine"+str(totalMachines))
for addDetectionOnPin in range (totalMachines):
        #log.debug( "added machine cycle detection on GPIO%d",machineCycleSignal[addDetectionOnPin])
        #comment out above line to check , interrupt is added for detection on pins which are reqiured for ECP  
        GPIO.add_event_detect(machineCycleSignal[addDetectionOnPin], GPIO.BOTH, callback=plcMachine(addDetectionOnPin+1),bouncetime=20)

for m in range (totalMachines):
        machineobject.append(Machine(0, 0, 0))
        m=Queue.Queue(maxsize=10)
        workque.append(m)

for d in range (totalMachines):
    t = threading.Thread(target=process_machine_data, args=(d,))
    thread_list.append(t)


for thread in thread_list:
    thread.start()


#------------------------------------------------------------------------------------------------------------------------------------------
'''
    below part starts thread and wait infinite loop it checks NiFi connection status on every 1 minute 
    it tries to send data available in buffer if any.

'''
#--------------------------------------------------------------------------------------------------------------------------------------------


#t = threading.Thread(name = "sendDataThread", target=machineData, args=(q,))

#t.start()
log.debug("Data collection started")
try:
        while True:
                if NiFiconnectionStatus_Delphi()=='200':
                        log.debug( "Connection status to Delphi NiFi for edge device[%s] : CONNECTED ",str(get_mac()))

                        while buffer.empty() !=-1 and NiFiconnectionStatus_Delphi()=='200':
                            data=buffer.pop().rstrip() 
                            #log.debug(data)   
                            dataTosend=data.split("||")
                           # log.debug(dataTosend)
                            if len(dataTosend)!= 0:                           
                                sendDataToDelphi(dataTosend[0],dataTosend[2],dataTosend[3])
                                time.sleep(1)    

                else:
                        log.error("Connection status to Delphi NiFi : NO NETWORK ")

                time.sleep(60)


except KeyboardInterrupt:
        log.debug(" Quit ")
        GPIO.cleanup()
