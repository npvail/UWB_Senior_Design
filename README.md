Update the frist_get_com() function in position.py to be able run on MAC

Need install driver on MAC OS: 
https://www.wch-ic.com/downloads/CH341SER_MAC_ZIP.html

download -> setting -> general -> login & extention -> allow driver extention 

cmd to check the port number: 
ls /dev/cu.*

check data format, sometime it is unrecognize format

make sure use the hardware left port for power, right port uploads code

uncommend the anchor 4 in main function
