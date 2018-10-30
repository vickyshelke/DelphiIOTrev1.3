__credits__    =      ["Wipro Team", "Delphi Team"]
__version__    =      "1.2"
__maintainer__ =      "Vikram Shelke"
__email__      =      "vikram.shelke@wipro.com"
__date__       =      "25/10/2018"
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
#queueLock = threading.Lock()
workque = []
#threadlock=threading.Lock()  
#------------------global arrays to hold each machine information -------------------------------------------------- 

machineCycleSignal=[]                       # list to hold ECP  Signal
machineGoodbadPartSignal=[]                 #  list to hold QSP Signals  
machineName =[]                             #  this holds machine names  
machineobject=[]                            #  list to hold machine instances
machine_cycle_timestamp=[]                  # timestamp for each machine get stored in this list
finalmessage=[]                             #  whole message with timestamp + machine name + quality 
machine_good_badpart_pinvalue=[]            #  this hold good/bad part pin values
machine_cycle_risingEdge_detected=[]        #   this hold Rising edges for ECP
machine_cycle_pinvalue=[]                   # this checks validity of machine cycle pulse  for each machine
thread_list = []
#messagesSinceLastReboot=0
ECPofMachine=[]
machine_cycle_risingEdge_detected=[]
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
        ECPofMachine.append(0)

#---------------------------------------------------  log mechanism  configuration ------------------------------------

log = logging.getLogger('')
log.setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.WARNING)
if LOG_ENABLE == 'True':
        log.disabled = False
else :
        log.disabled=True


# write to console screen
#formatter_stdout = logging.Formatter("%(asctime)s %(levelname)s - %(message)s","%Y-%m-%d %H:%M:%S")
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
                self.machine_cycle_pulse_time=self.machine_cycle_falling_edge-(self.machine_cycle_rising_edge+0.2)
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




#### form request for heartbit message 
heartbits=12
fields1={'MAC':heartbits}
encoded_args = urllib.urlencode(fields1)
heartbitURL = 'http://'+ HOST + ':' + PORT + '/'+'nifi_heartbeat' + '?' + encoded_args
####form delphi Azure URL
urlazure= 'http://' + HOST + ':' + '7777' + '/' + 'simulator'+'?'          #check connectivity with azure
### form data sending URL
sendURL = 'http://' + HOST + ':' + PORT + '/' + SENDURL +'?'



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
        fields={'ts':timestamp,'loc':LOCATION,'mach':machinename,'data':data}
        encoded_args = urllib.urlencode(fields)
        error=''
        url= sendURL + encoded_args
       
        try:
                r = http.request('GET', url,retries=False,timeout=3.0)
                data_send_from_machine_status=r.status
        except urllib3.exceptions.MaxRetryError as e:
                error=e
                data_send_from_machine_status=0
        except urllib3.exceptions.ProtocolError as e:
                error=e
                data_send_from_machine_status=0
        except urllib3.exceptions.ConnectTimeoutError as e:
                error=e
                data_send_from_machine_status=0
        except urllib3.exceptions.ReadTimeoutError as e:
                error=e
                data_send_from_machine_status=0
        if data_send_from_machine_status != 200 :
                if data_send_from_machine_status==0:
                        log.error("Not able to send data to Nifi: %s",e)
                else:
                        log.debug("HTTP send status to Delphi : %d",data_send_from_machine_status)        
                buffer.push(timestamp+"||"+LOCATION+ "||" + machinename +"||"+data)
                status=0
                try:
                    azure=http.request('GET',urlazure,timeout=2.0,retries=False)
                    status=azure.status
                except urllib3.exceptions.ProtocolError as e: 
                    log.error(e)
                except urllib3.exceptions.MaxRetryError as e:
                    log.error(e)
                except urllib3.exceptions.ConnectTimeoutError as e:
                    log.error(e)    
                except urllib3.exceptions.ReadTimeoutError as e:
                    log.error(e)
                if  status==200:
                    log.debug("Delphi azure connection Status :%d OK",azure.status)
                else:
                    log.error("Delphi azure connection Status : Network Error")
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
            #log.debug("%s",heartbitURL)
            r = http.request('GET',heartbitURL,timeout=2.0,retries=False)    
            return str(r.status)
        except urllib3.exceptions.ProtocolError as e: 
            log.error(e)
            return False
        except urllib3.exceptions.MaxRetryError as e:
            log.error(e)
            return False
        except urllib3.exceptions.ConnectTimeoutError as e:
            log.error(e)
            return False
        except urllib3.exceptions.ReadTimeoutError as e:
            log.error(e)
            return False
    




def detectedEvent(machineNo):                       # only detect Rising Edges
    global machine_cycle_risingEdge_detected
    #queueLock.acquire()
    event='Rising'
    if machine_cycle_risingEdge_detected[machineNo]==0: #check wether last edge was falling
        machine_cycle_risingEdge_detected[machineNo]=1  
#       log.debug("TRANISITION To HIGH LEVEL")  
        workque[machineNo].put(event) 
 #   queueLock.release()


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

        global workque
        global machine_cycle_risingEdge_detected
        #global messagesSinceLastReboot
        global ECPofMachine
        while True:
                LOGIC= workque[machineNo].get()  
                machineobject[machineNo].machine_cycle_starttime()
                log.debug ("Rising edge : %s Cycle Signal ",machineName[machineNo])
                if machineGoodbadPartSignal[machineNo]==0:
                    machine_good_badpart_pinvalue[machineNo]=-1
                else:
                    if (GPIO.input(machineGoodbadPartSignal[machineNo])==VerificationLogic): # check value of good_badpart_signal and set it to 1 if ok
                        machine_good_badpart_pinvalue[machineNo]=0
                    else: #good_badpart is not ok
                        machine_good_badpart_pinvalue[machineNo]=1
                #else:
                 #       log.debug ("Multiple Rising Edge detected on %s", machineName[machineNo])
                time.sleep(2.5) ##########to avoid false trigger
                if(GPIO.input(machineCycleSignal[machineNo])==VerificationLogic):

                    time.sleep(0.7) ## specifically made 3.2 to avoid debouncing of relays happening at falling edges
                    while True:
                        if(GPIO.input(machineCycleSignal[machineNo])!=VerificationLogic):   #dry contact opend Rising edge detected for machine_cycle pin
                            break 
                    log.debug ("Falling edge : %s Cycle Signal ",machineName[machineNo])
                    machineobject[machineNo].machine_cycle_stoptime()
                    machine_cycle_timestamp[machineNo]=datetime.datetime.now(tz=pytz.UTC).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+"+00:00"
                    machine_cycle_pinvalue[machineNo]=machineobject[machineNo].machine_cycle_pulseTime(machineName[machineNo])
                    machine_cycle_risingEdge_detected[machineNo]=0                    
                    if machine_cycle_pinvalue[machineNo]==1:
                    #threadlock.acquire()
                        if machineGoodbadPartSignal[machineNo]==0:
                            machine_good_badpart_pinvalue[machineNo]=-1   # "no goodbad part" set quality as -1
                                #pass
                        else:
                            if(GPIO.input(machineGoodbadPartSignal[machineNo])==VerificationLogic): # valid pulse
                                machine_good_badpart_pinvalue[machineNo]=0            #good part set quality = 0
                            else:
                                machine_good_badpart_pinvalue[machineNo]=1            # bad part set quality = 1
                               
                        finalmessage[machineNo]="Quality"+":"+str(machine_good_badpart_pinvalue[machineNo])
                        log.debug("%s ----> %s",machineName[machineNo],finalmessage[machineNo])
                        ECPofMachine[machineNo]=ECPofMachine[machineNo]+1
                        log.info(" ECP received since last Reboot for %s : %d ",machineName[machineNo],ECPofMachine[machineNo])        
                        sendDataToDelphi(machine_cycle_timestamp[machineNo],machineName[machineNo],finalmessage[machineNo])    
                        #threadlock.release()        
                    else:
                        log.error("%s cycle pulse width is invalid",machineName[machineNo])
                else:
                    log.debug("False Trigger")        
                machineobject[machineNo].machine_cycle_cleartime()
                    



#------------------------ create machine object and call function as per no of machine connected to device----------------------------------


plcMachine = lambda totalMachines: eval("plcMachine"+str(totalMachines))
for addDetectionOnPin in range (totalMachines):
        #log.debug( "added machine cycle detection on GPIO%d",machineCycleSignal[addDetectionOnPin])
        #comment out above line to check , interrupt is added for detection on pins only Rising Edges which are reqiured for ECP  
        try:
            if VerificationLogic==1:
                    GPIO.add_event_detect(machineCycleSignal[addDetectionOnPin], GPIO.RISING, callback=plcMachine(addDetectionOnPin+1),bouncetime=200)
            else:
                    GPIO.add_event_detect(machineCycleSignal[addDetectionOnPin], GPIO.FALLING, callback=plcMachine(addDetectionOnPin+1),bouncetime=200)

        except RuntimeError as e:
            log.error(e)
            log.error(" Please reboot the device ......")
            time.sleep(60)
            GPIO.cleanup()
            sys.exit(1)
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

log.debug("Data collection started")
try:
        while True:
                if NiFiconnectionStatus_Delphi()=='200':
                        log.debug( "Connection status to Delphi NiFi for edge device[%s] : CONNECTED ",str(get_mac()))

                        while buffer.empty() !=-1 and NiFiconnectionStatus_Delphi()=='200':
                            data=buffer.pop().rstrip() 
                            log.debug("Sending buffered data : [%s]",data)   
                            dataTosend=data.split("||")
 #                           log.debug(dataTosend)
                            if len(dataTosend)== 4:                           
                                sendDataToDelphi(dataTosend[0],dataTosend[2],dataTosend[3])
                                time.sleep(5)    

                else:
                        log.error("Connection status to Delphi NiFi : NO NETWORK ")

                time.sleep(120)


except KeyboardInterrupt:
        log.debug(" Quit ")
        GPIO.cleanup()

