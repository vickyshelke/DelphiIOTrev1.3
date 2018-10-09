# DelphiIotRev1.2
1.Data(machine pulses) from plc machines gathered on edge device when there is part produced at the factory shop.
Machine pulses:
-> machine cycle signal(ECP)
-> Qulaity signal (QSP)
The machine cycle signals are validated for time duration (2-4)and after verification data is sent to remote servers (Delphi Azure)
collectMachinedata.py is the main machine gathering process.
fetchConfigurationDev.py fetches initial configuration from NiFi for setting up machines input.
BUFFER,holds the buffered data which was not sent to Delphi remote servers(Azure) due to network issues or server downtime.
logConfig.py holds configuration information which used during setting up servers.
startup.sh is the process which starts as main process from container.
Dockerfile.template is the docker container which do the inital package,library setup and starts startup.sh sh as main process.
timestamp.txt hold the timestamp of latest and first ECP after latest reboot and for previous reboot. 
