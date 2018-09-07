# Dephirev1.2
1.Data(machine pulses) from plc machines gathered on edge device when there is part produced at the factory shop.
Machine pulses:
-> machine cycle signal(ECP)
-> Qulaity signal (QSP)
The machine cycle signals are validated for time duration (2-4)and after verification data is sent to remote servers (Delphi/WIPRO)
collectMachinedata.py is the main machine gathering process.
fetchConfiguration.py fetches initial configuration from NiFi for setting up machines input.
BUFFER,WIPROBUFFR holds the buffered data which was not sent to Delphi/Wipro remote servers(Azure) due to network issues or server downtime.
logConfig.txt holds configuration information which used during setting up servers.
startup.sh is the process which starts as main process from container.
Dockerfile.template is the docker container which do the inital package,library setup and starts startup.sh sh as main process.
