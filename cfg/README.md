***USE AT YOUR OWN RISK!***

---

Choose the `printer.cfg` file for your specific model from the cfg folder here.  
The [`printer.cfg` file for the **Go**](https://github.com/Klipper3d/klipper/blob/master/config/printer-anycubic-kobra-go-2022.cfg) can be found in the official Klipper repo. 


Rename the specific config file to `printer.cfg` and copy the file to the home directory of the host where Mainsail/Fluidd/OctoPrint is running on (e.g. on a RaspberryPi it's `/home/pi/`).  
If you're using Mainsail/Fluidd, you can just upload them using the webinterface, if you're using OctoPrint you probably have to SSH into the host.

See the [main readme file](../README.md) and/or read the chapter [Klipper (Mod)](https://1coderookie.github.io/KobraGoNeoInsights/firmware/fw_klipper/) of [my comprehensive infopage about the Kobra Go and Neo](https://1coderookie.github.io/KobraGoNeoInsights/) for further instructions.

---

***ATTENTION***   

- *DON'T start trying to print right away!*    
- You have to adjust the settings in the `printer.cfg` file to your system and needs and proceed with the basic config checks mentioned in the official documentation of Klipper: https://www.klipper3d.org/Config_checks.html    
- Check all settings, there might be mistakes and wrong settings!

- *The file `regular-KOBRA_Sad_Kaleidoscope3286_printer.cfg` is for the ***regular KOBRA*** only!*  
  *Don't use it with the Kobra Go or Kobra Neo!*  
  *If you want to use Klipper on the regular Kobra, you need to resolder one SMD resistor (R65 to R66). Read here: https://klipper.discourse.group/t/support-for-hdsc-chips-hc32f460/2860/54 (look at the second image Steve Gotthardt posted there (December 18, 2022, 3:16pm)).* 


---  

*Note:*    
*I decided with a heavy heart that I had to remove cfg files for the Neo due to the fact that wrong and obsolete settings have been used and that the files weren't maintained by the users who contributed them.*  
*Users reached out to me reporting problems and due to limited time and the fact that the cfg files were pretty much the same anyway I decided to not further modify and maintain those files myself.*  
*So there's only the one example cfg file for the Neo available now which is my own.*     
*However, many thanks to those who contributed their files initially!*   

**Credits:**  
- *Thanks to @[mackmind](https://github.com/mackmind) for offering his `printer.cfg` for the **Creality SonicPad at the Neo** here as well!*  
- *Thanks to @[xpeng121](https://www.reddit.com/user/xpeng121/) for having added the example `printer.cfg` for the **Go** to the official Klipper repo!*   
- *Thanks to @[Joseph Montanez](https://github.com/joseph-montanez) for offering his `printer.cfg` for the **Go** and for the **BTT SKR Pico at the Go** here as well!*
- *Thanks to reddit user [Sad_Kaleidoscope3286](https://reddit.com/user/Sad_Kaleidoscope3286) for offering his `printer.cfg` for the **regular Kobra** here as well!*  

---

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/U6U5NPB51)  
