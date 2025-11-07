Update the frist_get_com() function in position.py to be able run on MAC

Need install driver on MAC OS: 
https://www.wch-ic.com/downloads/CH341SER_MAC_ZIP.html

download -> setting -> general -> login & extention -> allow driver extention 

cmd to check the port number: 
ls /dev/cu.*

check data format, sometime it is unrecognize format

make sure use the hardware left port for power, right port uploads code

uncommend the anchor 4 in main function

create this python script into an app(.exe) using pyinstaller
1.pip install pyinstaller
2.pyinstaller --onefile --windowed app.py

note: run "pyinstaller --clean --onefile --windowed app.py" again if we modify/debug code "--clean" overwrite the privious version

if we have more than 1 file like seperated CSS, html, ...: use --add-data "<source>:<destination>", note: update function "def resource_path(relative_path)"
On MacOS/Linux: 
pyinstaller --onefile --windowed \
--add-data "templates:templates" \
--add-data "static:static" \
app.py

On Window: replace ":" to ";"

