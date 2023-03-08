# Klipper4KobraGoNeo
Files for getting Klipper installed and running at the Anycubic Kobra Go &amp; Neo.  
***USE AT YOUR OWN RISK!***

Here you can download the compiled `klipper.bin` and `printer.cfg` for your Anycubic Kobra Go and Neo or at least find links to the belonging `printer.cfg` files of other users.  

Please read the chapter [Klipper (Mod)](https://1coderookie.github.io/KobraGoNeoInsights/firmware/fw_klipper/) of my comprehensive infopage about the Kobra Go and Neo: ["KobraGoNeo Insights"](https://1coderookie.github.io/KobraGoNeoInsights/).

# How to Setup & Flash
1. Download the files and rename the file `klipper.bin` to `firmware.bin`.
2. Copy the `.cfg` files to the home directory of the host where Mainsail/Fluidd/OctoPrint is running on (e.g. on a RaspberryPi it's `/home/pi/`).  
If you're using Mainsail/Fluidd, you can just upload them using the webinterface, if you're using OctoPrint you probably have to SSH into the host.  
3. Take a mSD card (FAT32 formatted), delete all files on it (you may want to do a backup of them if you're using the card that came with the printer, just in case you'd need them in case you wanna go back to the stock firmware and don't want to download the files from the internet) and copy the `firmware.bin` file onto the card.  
You have to put the file in the root directory, not in a subdirectory (in other words: just copy it directly onto the card without placing it in a subdirectory). 
4. Turn off the printer and insert the card. Then turn on the printer again and wait.  
You'll see the message "Updating firmware. Please wiat." (I'm not kidding, the typo comes for free with the printer ;) ) - this message *won't* dissapear after the flash procedure is done as the stock control unit isn't supported by Klipper yet. So just give the printer some time and let it sit for 10min.  
5. After that, turn off the printer, take out the card and connect the printer with your host (e.g. RaspberryPi) which is running Mainsail/Fluidd/Octoprint using an USB-C cable. 
6. After doing so, turn off the printer. It should now be recognized by Mainsail/Fluidd/OctoPrint. If an errorf message like "Can't connect to the MCU." occurs, either click on "restart the firmware" or turn your printer off and on again.  

**Now you have to adjust the settings in the `printer.cfg` file and proceed with the basic config checks mentioned in the official documentation of Klipper: https://www.klipper3d.org/Config_checks.html**


