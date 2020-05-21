# USBDO96

Module used to control an EasyDAQ USBDO96 card.

USBDO96 is a USB Digital Output card which can control 96 channels.
The datasheet for this device can be found
[here](https://www.easydaq.co.uk/datasheets/Data%20Sheet%2024%20%28USBDO96%20-%2096%20Channel%20Digital%20Output%20Card%29.pdf)

However the section explaining how to interact with the card contains some
errors. Below is a summary on how to setup your machine and control your card
(here DO refers to Digital Output):

The USBDO96 card has a FTDI FT232BL chip which is used as a USB <-> Serial 
interface. Depending on your platform you might need to install some drivers
which are all available on the
[FTDI page](https://www.ftdichip.com/Drivers/VCP.htm) (get the VCP drivers, not
 the D2XX):

Once the drivers are installed and the device connected, you will need to
install the `pyserial` python package:

```
$ pip install pyserial
```

The Serial port has 4 ports: Port A, Port B, Port C, and Port D.  
Only Port B, C, and D are used to control the DOs.

The 96 channels/DOs are split in 6 groups of 16 DOs each:

 * group 1: DO01-DO16
 * group 2: DO17-DO32
 * [...]
 * group 6: DO81-DO96

The 16 DOs per group are controlled with the Port C and D:

 * DO 1, 17, 33, [...], 81 are controlled by Bit 0 of Port C (C0).
 * DO 2, 18, 34, [...], 82 are controlled by Bit 1 of Port C (C1).
 * [...]
 * DO 16, 32, 48, [...], 96 are controlled by Bit 7 of Port D (D7).

Port B is used to control which group should be updated with the values of Port
C and D (so that you can control each DO individually):

 * B1 (Bit 1 of Port B) corresponds to group 1.
 * B2 <-> group 2
 * [...]
 * B6 <-> group 6

B7 is not used.

B0 is used as a switch to disable/turn off all the channels. If set to 0, then
all DOs are set to 0 (disable board).  
B0 should always be set to 1 after initialization (unless you want to turn off
all DOs).  
Note: setting B0 to 0 after setting some DOs to 1 will set them to 0, but will
keep all of the DOs' state in memory. When B0 is set back to 1, all the DOs will
return to their previous state (either 0 or 1).

Communication with the different ports is done by sending a simple text message
over the Serial Port.  
There are three commands for each port (B, C, and D):

 * Configure: used to configure each bit of the port as input/output.
 * Read: used to read the value of the given port.
 * Write: used to set the value of the given port.

Each message is composed of two bytes:

 * First byte: Command for a given port (an ASCII letter).
 * Second byte: the value for this command (used only for Configure and Write).

Here are the corresponding first byte for each command:

 * 'A' (0x41): Port B - Read
 * 'B' (0x42): Port B - Configure
 * 'C' (0x43): Port B - Write
 * 'D' (0x44): Port C - Read
 * 'E' (0x45): Port C - Configure
 * 'F' (0x46): Port C - Write
 * 'G' (0x47): Port D - Read
 * 'H' (0x48): Port D - Configure
 * 'J' (0x4A): Port D - Write (Warning, this is 'J' and not 'I' (0x49))

When configuring a port (using 'B', 'E', or 'H'), each bit of the value
(second byte) indicates the direction of the corresonding port bit: 1 for
input, 0 for output.
Here you have to set all the bits of each port as outputs (so value = 0x00).

Setting a new value to a DO is done by first writting the corresponding bytes
to both Ports C and D (all 16 DOs of a group are always updated together), and
then switching the corresponding bit on Port B from 0 to 1 (Note: B0 should
also be set to 1). The values present on Ports C and D are applied
simultaneously at that time. See example below.

Initialization is done the follwing way:

 * Configure all bits of all ports (B, C, and D) as outputs (see above).
 * Write 0x00 to all ports:
    * 0x00 to B: disable board and reset data latch for each group.
    * 0x00 to C and D: future value will be 0 for all bits.
 * Write 0xFF to B: enable board and set current value of C and D to all
   groups. This sets the 96 DOs to 0.
 * Write 0x01 to B: reset data latch for each group, but keep board enabled.

Example on how to set bits once the initialization is done (e.g. DO03, DO10 and
DO12; i.e. group 1, C2, D1 and D3):

 * Write 0x04 to C (C2 set to 1)
 * Write 0x0A to D (D1 and D3 set to 1)
 * Write 0x01 to B (reset data latch for each groups, but keep board anabled)
 * Write 0x03 to B (set current value of C and D to group 1)

You can act on multiple groups simultaneously if the same values for port C and
D should be applied to those groups. E.g. in the previous example, if you write
0x07 to B instead of 0x03 (last command), then you will set DO03, DO10, DO12,
but also DO19, DO26, and DO28 (group 2, C2, D1 and D3) to 1.

The class USBDO96 provided in this module handles all this logic so that you
can turn on/off one or more DO simply by proving their number (from 1 to 96).
It also automatically detects your device (if only one is connected to your
machine). If more than one device is connected to your machine, you will need
to provide the correspondig name.

Here is some code sample showing how to use the USBDO96 class:

```
>>> # Create a USBDO96 instance and detect the device automatically.
>>> device = USBDO96()
>>>
>>> # Set DO01 to 1
>>> device.turnOn(1)
>>>
>>> # Set DO03 and DO23 to 1 (DO01 will stay set to 1)
>>> # Note: this can't be done simultaneously as groups are updated separately,
>>> # so there will be a few 10s of ms between turning DO03 and DO23 on.
>>> device.turnOn([3, 23])
>>>
>>> # Set DO01 and DO23 to 0 (DO03 will stay set to 1)
>>> device.turnOff([1, 23])
>>>
>>> # Set DO40 and DO60 to 1 and DO03 to 0.
>>> device.setDOs([40, 60], 3)
>>> 
>>> # Reset all DOs to 0 simultaneously.
>>> device.resetDOs()
>>>
>>> # The DOs are reset and the Serial port is closed automatically when the
>>> # instance is destroyed. However you can still do it manually:
>>> device.closeSerial()
>>> # You can still use your instance afterwards, but you'll first have to
>>> # reinitialize it:
>>> device.initSerial()
```

Connector HDR1:

```
 5V  DO01 DO02 DO03 [...] DO23 DO24
 |    |    |    |          |    |
 49   47   45   43  [...]  3    1
 50   48   46   44  [...]  4    2
 |    |    |    |          |    |
GND  DO25 DO26 DO27 [...] DO47 DO48
```

Connector HDR1:

```
 5V  DO49 DO50 DO51 [...] DO71 DO72
 |    |    |    |          |    |
 49   47   45   43  [...]  3    1
 50   48   46   44  [...]  4    2
 |    |    |    |          |    |
GND  DO73 DO74 DO75 [...] DO95 DO96
```

Connector of a DO24MxP/S card (DI: Digital Input):

```
 5V  DI01 DI02 DI03 [...] DI23 DI24
 |    |    |    |          |    |
 49   47   45   43  [...]  3    1
 50   48   46   44  [...]  4    2
 |    |    |    |          |    |
GND  GND  GND  GND  [...] GND  GND
```
