# Klipper4KobraGoNeo
Files for getting Klipper installed and running on Anycubic's Kobra Go and Kobra Neo.  
  
***USE AT YOUR OWN RISK!***

Here you can download the compiled `klipper.bin` and preconfigured `printer.cfg` files for your Anycubic Kobra Go and Neo or at least find links to the belonging `printer.cfg` files of other users.  

Please read the chapter [Klipper (Mod)](https://1coderookie.github.io/KobraGoNeoInsights/firmware/fw_klipper/) of my comprehensive infopage about the Kobra Go and Neo: ["KobraGoNeo Insights"](https://1coderookie.github.io/KobraGoNeoInsights/).

***Before attempting the installation process, please read the official [Klipper installation documentation](https://www.klipper3d.org/Installation.html)!***  

# How to Setup & Flash
1. **Download all files by clicking on the green "Code" button, then click "Download ZIP".**  
2. Unzip the downloaded folder and rename the file `klipper.bin` in the "bin" folder to `firmware.bin`. <br> *This is the file you'll need to flash your printer with later.*  
3. Choose the cfg-file in the "cfg" folder you want to use for your printer and rename it to `printer.cfg`. Then copy it to the home directory of the host where Mainsail/Fluidd/OctoPrint is running on (e.g. on a RaspberryPi it's `/home/pi/`). <br> *This is the file that contains the printer specific settings which you'd have to adjust later.* <br> Note: If you're using Mainsail/Fluidd, you can just upload them using the webinterface, if you're using OctoPrint you probably have to SSH into the host.  
4. Take a microSD card (FAT32 formatted!), delete all files on it (you may want to do a backup of them if you're using the card that came with the printer, just in case you'd need them in case you wanna go back to the stock firmware and don't want to download the files from the internet) and copy the `firmware.bin` file onto the card. <br> You have to put the file in the root directory, not in a subdirectory (in other words: just copy it directly onto the card without placing it in a subdirectory). 
5. Turn off the printer and insert the card. Then turn on the printer again and wait. <br> You'll see the message "Updating firmware. Please wait." - this message *won't* dissapear after the flash procedure is done as the stock control unit isn't supported by Klipper yet. So just give the printer some time and let it sit for 10min.  
6. After that, turn off the printer, take out the card and connect the printer with your host (e.g. RaspberryPi) which is running Mainsail/Fluidd/Octoprint using an USB-C cable. 
7. After doing so, turn off the printer. It should now be recognized by Mainsail/Fluidd/OctoPrint. If an error message like "Can't connect to the MCU." occurs, either click on "restart the firmware" or turn your printer off and on again. <br> If it still can't connect, you'd have to determine the serial port of your host where the printer is connected to (see the official [Klipper installation documentation](https://www.klipper3d.org/Installation.html) for further information) and adjust the setting in the `printer.cfg` accordingly. This is the belonging section: <br> 
   ```[mcu]
   serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
   restart_method: command
   ``` 


**Now you have to adjust the settings in the `printer.cfg` file and proceed with the basic config checks mentioned in the official documentation of Klipper: https://www.klipper3d.org/Config_checks.html - don't skip these steps!**


