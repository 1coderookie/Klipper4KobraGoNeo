Here you can find some example `.cfg` files which are referred to in the top section of the `printer.cfg` file, like the file `gcode.cfg`, which contains the commands for your start and end gcode you'll refer to from your slicer.  
These files contain e.g. scripts and macros and can be included in the `printer.cfg` using the syntax `[include gcode.cfg]` for example. This will load the defined file during the start. Adding these commands using an include file keeps the `printer.cfg` shorter and easier to read.  

*Attention:*  
Every file you want to load by referring to it using the `[include xyz.cfg]` command needs to be existent! If you don't have that file and refer to it, the startup and initialisation will fail.  
The same must be taken into account when using additional hardware like a RaspberryPi Pico with an ADXL345 sensor attached to it for doing measurements for the Input Shaper functionality (resonance compenastion). If you have the command `[include adxl345Pico.cfg]` active in the `printer.cfg` and the file itself is existent, but the Pico isn't connected to the host and can't be found, then the start will fail as well.  
So keep this in mind when using these commands.  
