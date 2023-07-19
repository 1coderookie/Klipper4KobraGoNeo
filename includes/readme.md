Here you can find some example `.cfg` files which are referred to in the top section of my `printer.cfg` file for the Neo (the file named `NEO_1coderookie_printer.cfg`) , like the file `gcode.cfg`, which contains the commands for your start and end gcode you'll refer to from your slicer.  
These files contain e.g. scripts and macros and can be included in the `printer.cfg` using the syntax `[include gcode.cfg]` for example. This will load the defined file during the start. Adding these commands using an include file keeps the `printer.cfg` shorter and easier to read.  



*Attention:*  
- Every file you want to load by referring to it using the `[include xyz.cfg]` command needs to be existent! If you don't have that file and refer to it, the startup and initialisation will fail.  
- As other users might contribute and want to share their include files, I renamed the files by adding the GitHub username plus an underscore to the filename. So when activating that include in your `printer.cfg`, rename the belonging include file so that the naming is consistent.  
As an example: if you use a `printer.cfg` where there's an `[include gcode.cfg]` active and you use the file `1coderookie_gcode.cfg`, rename that file to `gcode.cfg` then. If you won't do so, you'll get an error message as the file you referred to in the `printer.cfg` isn't existent then.  
- The same must be taken into account when using additional hardware like a RaspberryPi Pico with an ADXL345 sensor attached to it for doing measurements for the Input Shaper functionality (resonance compenastion). If you have the command `[include adxl345Pico.cfg]` active in the `printer.cfg` and the file itself is existent, but the Pico isn't connected to the host and can't be found, then the start will fail as well.  
So keep this in mind when using these commands.  


