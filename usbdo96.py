"""
Module used to control an EasyDAQ USBDO96 card.

USBDO96 is a USB Digital Output card which can control 96 channels.
The datasheet for this device can be found here:
https://www.easydaq.co.uk/datasheets/Data%20Sheet%2024%20(USBDO96%20-%2096%20Channel%20Digital%20Output%20Card).pdf

However the section explaining how to interact with the card contains some
errors. Below is a summary on how to setup your machine and control your card
(here DO refers to Digital Output):

The USBDO96 card has a FTDI FT232BL chip which is used as a USB <-> Serial 
interface. Depending on your platform you might need to install some drivers
which are all available on the FTDI page (get the VCP drivers, not the D2XX):
https://www.ftdichip.com/Drivers/VCP.htm

Once the drivers are installed and the device connected, you will need to
install the pyserial python package:
pip install pyserial

The Serial port has 4 ports: Port A, Port B, Port C, and Port D.
Only Port B, C, and D are used to control the DOs.

The 96 channels/DOs are split in 6 groups of 16 DOs each:
group 1: DO01-DO16
group 2: DO17-DO32
[...]
group 6: DO81-DO96

The 16 DOs per group are controlled with the Port C and D:
DO 1, 17, 33, [...], 81 are controlled by Bit 0 of Port C (C0).
DO 2, 18, 34, [...], 82 are controlled by Bit 1 of Port C (C1).
[...]
DO 16, 32, 48, [...], 96 are controlled by Bit 7 of Port D (D7).

Port B is used to control which group should be updated with the values of Port
C and D (so that you can control each DO individually):
B1 (Bit 1 of Port B) corresponds to group 1.
B2 <-> group 2
[...]
B6 <-> group 6

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
  0x00 to B: disable board and reset data latch for each group.
  0x00 to C and D: future value will be 0 for all bits.
* Write 0xFF to B: enable board and set current value of C and D to all groups.
                   This sets the 96 DOs to 0.
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

> # Create a USBDO96 instance and detect the device automatically.
> device = USBDO96()
>
> # Set DO01 to 1
> device.turnOn(1)
>
> # Set DO03 and DO23 to 1 (DO01 will stay set to 1)
> # Note: this can't be done simultaneously as groups are updated separately,
> # so there will be a few 10s of ms between turning DO03 and DO23 on.
> device.turnOn([3, 23])
>
> # Set DO01 and DO23 to 0 (DO03 will stay set to 1)
> device.turnOff([1, 23])
>
> # Set DO40 and DO60 to 1 and DO03 to 0.
> device.setDOs([40, 60], 3)
> 
> # Reset all DOs to 0 simultaneously.
> device.resetDOs()
>
> # The DOs are reset and the Serial port is closed automatically when the
> # instance is destroyed. However you can still do it manually:
> device.closeSerial()
> # You can still use your instance afterwards, but you'll first have to
> # reinitialize it:
> device.initSerial()


Connector HDR1:

 5V  DO01 DO02 DO03 [...] DO23 DO24
 |    |    |    |          |    |
 49   47   45   43         3    1
 50   48   46   44         4    2
 |    |    |    |          |    |
GND  DO25 DO26 DO27       DO47 DO48


Connector HDR1:

 5V  DO49 DO50 DO51 [...] DO71 DO72
 |    |    |    |          |    |
 49   47   45   43         3    1
 50   48   46   44         4    2
 |    |    |    |          |    |
GND  DO73 DO74 DO75       DO95 DO96


Connector of a DO24MxP/S card (DI: Digital Input):

 5V  DI01 DI02 DI03 [...] DI23 DI24
 |    |    |    |          |    |
 49   47   45   43         3    1
 50   48   46   44         4    2
 |    |    |    |          |    |
GND  GND  GND  GND        GND  GND
"""

import serial
from serial.tools import list_ports
import time

# Read/write timeouts for the serial port.
READ_TIMEOUT_SEC = 1
WRITE_TIMEOUT_SEC = 1

# IDs use to detect the connected device.
# The USBDO96 card uses the FTDI USB chip FT232B.
FTDI_VID = 0x0403  # Vendor ID for FTID.
FT232B_PID = 0x6001  # Product ID for the FT232B/FT232BL chips.

class USBDO96Exception(Exception):
  """Exception class used by USBDO96."""

class USBDO96(object):
  """Class controlling an EasyDAQ USBDO96 device.
  
  See the module docstring for more details.
  """

  _PORT_B = 1
  _PORT_C = 2
  _PORT_D = 3

  _CMD_READ = 0
  _CMD_CONFIGURE = 1
  _CMD_WRITE = 2
  
  def __init__(self, device_name=None, read_timeout=READ_TIMEOUT_SEC,
               write_timeout=WRITE_TIMEOUT_SEC, reset_on_exit=True):
    """Initialize the USBDO96 device and set all DOs to 0.

    Args:
      device_name: Name of the device (default set to None). Set to None to
                   Automatically detect the connected device.
      read_timeout: timeout in seconds used to read from the serial port.
                    Default set to 1 sec.
      write_timeout: timeout in seconds used to write to the serial port.
                     Default set to 1 sec.
      reset_on_exit: If True, then all the DOs will be reset on exit (either
                     when the instance is killed, or when exiting a
                     with-statement). Default set to True.            
    """
    device_name = device_name or self._DetectDevice()
    self.serial = serial.Serial(device_name, timeout=read_timeout,
                                write_timeout=write_timeout)
    self.reset_on_exit = reset_on_exit
    self.dos_enabled = False
    # current_values: array of 6 ints (one per group) use to keep track of the
    # DOs values.
    # The first 16 bits of each int represent the value of port C and D for the
    # given group.
    # Bit 0 <-> C0
    # Bit 15 <-> D7
    self.current_values = [0] * 6
    self.initSerial()
    
  def __del__(self):
    """Make sure the Serial Port is closed and maybe reset the DOs."""
    self.closeSerial(self.reset_on_exit)
    
  def __enter__(self):
    """Called when entering a with-statement context."""
    return self
    
  def __exit__(self, unused_exc_type, unused_exc_value, unused_traceback):
    """Called when exiting a with-statement context."""
    self.closeSerial(self.reset_on_exit)
    
  def _DetectDevice(cls):
    """Detect the connected device."""
    devices = list_ports.comports()
    ftdi_devices = set()
    for device in devices:
      if device.vid == FTDI_VID and device.pid == FT232B_PID:
        ftdi_devices.add(device.device.replace('/cu', '/tty'))
    if not ftdi_devices:
      raise USBDO96Exception('Did not find any connected devices.')
    if len(ftdi_devices) > 1:
      raise USBDO96Exception(
          'Found more than one connected device: {}'.format(ftdi_devices))
    return ftdi_devices.pop()
    
  def _DOToGPB(cls, do):
    """Convert the given Digital Output to Group/Port/Bit.
    
    Args:
      do: Digital Output (1-based).
    
    Returns: a tuple (group, port, bit), where group is the corresponding
      group (1-based), port is either PORT_C or PORT_D, and bit is the bit
      number (0-based).
    """
    if do <=0 or do > 96:
      raise USBDO96Exception('Invalid Digital Output: {}'.format(do))
    do -= 1  # make DO 0-based
    group = int(do / 16)  # 0-based for now
    port = int((do - 16 * group) / 8)  # 0 <-> Port C, 1 <-> Port D
    bit = do - 16 * group - 8 * port
    return (group + 1, port and cls._PORT_D or cls._PORT_C, bit)
    
  def _GPBToDO(cls, group, port, bit):
    """Convert the given Group/Port/Bit to a Digital Output.
    
    Args:
      group: the group for this DO (1-based).
      port: the port for this DO (either PORT_C or PORT_D).
      bit: the bit number (0-based).
    
    Returns: the corresponding Digital Output (1-based).
    """
    if group <=0 or group > 6:
      raise USBDO96Exception('Invalid group: {}'.format(group))
    group -= 1  # make it 0-based.
    if port == cls._PORT_C:
      port = 0
    elif port == cls._PORT_D:
      port = 1
    else:
      raise USBDO96Exception('Invalid port: {}'.format(port))
    if bit < 0 or bit > 8:
      raise USBDO96Exception('Invalid bit number: {}'.format(bit))
    return 16 * group + 8 * port + bit + 1
    
  def _WriteByte(self, port, command, value=0x00):
    """Send a command to the given port.
    
    Args:
      port: Port to send the command to. One of _PORT_B, _PORT_C, or PORT_D.
      command: Command to execute. One of _CMD_READ, _CMD_CONFIGURE, or 
               _CMD_WRITE.
      value: Argument for the command. Ignored for _CMD_READ.
    """
    if not self.serial.is_open:
      raise USBDO96Exception(
          'Unexpected status: serial {} is closed!'.format(self.serial.name))
    if port == self._PORT_D and command == self._CMD_WRITE:
        command += 1
    message = chr(65 + (port - 1) * 3 + command) + chr(value)
    self.serial.write(message)
    time.sleep(0.01)  # How much time is really needed here, and why?
    if command == self._CMD_READ:
        return int(self.serial.read(1).encode('hex'), 16)
    else:
        return None
    
  def initSerial(self):
    """Initialize the three ports (B, C, and D) and set all 96 DOs to 0."""
    if not self.serial.is_open:
      self.serial.open()
    # Configure all bits as outputs.
    self._WriteByte(self._PORT_B, self._CMD_CONFIGURE, 0x00)
    self._WriteByte(self._PORT_C, self._CMD_CONFIGURE, 0x00)
    self._WriteByte(self._PORT_D, self._CMD_CONFIGURE, 0x00)
    self.disableDOs()
    # C=0x00 and D=0x00 -> future values of the 16 DOs will be 0.
    self._WriteByte(self._PORT_C, self._CMD_WRITE, 0x00)  
    self._WriteByte(self._PORT_D, self._CMD_WRITE, 0x00)
    # Latching the status of each group of 16 to apply the values on Port C
    # and D (and so setting all DOs to 0).
    self._WriteByte(self._PORT_B, self._CMD_WRITE, 0x7E)
    # Enable the DOs, which also returns data latch signal to logic 0 for
    # each group.
    self.enableDOs()
    self.current_values = [0] * 6
  
  def closeSerial(self, reset_dos=True):
    """Reset all DOs to 0 and close the Serial Port.
    
    Args:
      reset_dos: reset the DOs before closing the serial (default to True).
    """
    if not self.serial.is_open:
      return
    # reset all outputs to 0 and disable the board
    if reset_dos:
      self.resetDOs()
      self.disableDOs()
    self.serial.close()
    
  def enableDOs(self):
    """Enable all the Digiatl Outputs.
    
    Enable all the DOs. If they were previously disabled with disableDOs, then
    their previous states will be reapplied.
    If the DOs states were changed while being disabled (e.g. with setDOs,
    turnOn, or turnOff) then the new states will be applied.
    """
    self._WriteByte(self._PORT_B, self._CMD_WRITE, 0x01)
    self.dos_enabled = True
    
  def disableDOs(self):
    """Disable all the Digital Outputs.
    
    All the DOs are set to 0, however their states are kept in memory and will
    be set back with enableDOs.
    The DOs states can be modified with setDOs, turnOn, and turnOff while being
    disabled. The new states will be applied with enableDOs. 
    """
    self._WriteByte(self._PORT_B, self._CMD_WRITE, 0x00)
    self.dos_enabled = False

  def resetDOs(self):
    """Set all 96 DOs to 0 simultaneously."""
    port_b_value = self.dos_enabled and 0x01 or 0x00 
    self._WriteByte(self._PORT_C, self._CMD_WRITE, 0x00)
    self._WriteByte(self._PORT_D, self._CMD_WRITE, 0x00)
    self._WriteByte(self._PORT_B, self._CMD_WRITE, port_b_value)
    self._WriteByte(self._PORT_B, self._CMD_WRITE, port_b_value | 0x7E)
    self._WriteByte(self._PORT_B, self._CMD_WRITE, port_b_value)
    self.current_values = [0] * 6
    
  def setAllDOs(self):
    """Set all 96 DOs to 1 simultaneously."""
    port_b_value = self.dos_enabled and 0x01 or 0x00 
    self._WriteByte(self._PORT_C, self._CMD_WRITE, 0xFF)
    self._WriteByte(self._PORT_D, self._CMD_WRITE, 0xFF)
    self._WriteByte(self._PORT_B, self._CMD_WRITE, port_b_value)
    self._WriteByte(self._PORT_B, self._CMD_WRITE, port_b_value | 0x7E)
    self._WriteByte(self._PORT_B, self._CMD_WRITE, port_b_value)
    self.current_values = [0xFFFF] * 6
        
  def setDOs(self, dos_on, dos_off):
    """Set the given Digital Output(s) to the given state.
    
    If the same DO is given in both dos_on and dos_off, then it will be turned
    on (set to 1).
    
    Args:
      dos_on: Digital Output(s) to turn on (set to 1). Either an int or an
              array of ints. DOs are 1-based.
      dos_off: Digital Output(s) to turn off (set to 0). Either an int or an
               array of ints. DOs are 1-based.
    """
    # Make sure dos_on and dos_off are sets.
    dos_on = dos_on or set()
    dos_on = type(dos_on) == int and set([dos_on]) or set(dos_on)
    dos_off = dos_off or set()
    dos_off = type(dos_off) == int and set([dos_off]) or set(dos_off)
    
    groups = {}  # will contain tuples of (port, bit, state)
    for do in dos_on.union(dos_off):
      group, port, bit = self._DOToGPB(do)
      if group not in groups:
        groups[group] = []
      state = int(do in dos_on)
      groups[group].append((port, bit, state))
    port_b_value = self.dos_enabled and 0x01 or 0x00
    self._WriteByte(self._PORT_B, self._CMD_WRITE, port_b_value)
    for group, pbs in groups.iteritems():
      current_c_value = self.current_values[group-1] & 0xFF
      current_d_value = (self.current_values[group-1] >> 8) & 0xFF
      new_c_value = current_c_value
      new_d_value = current_d_value
      for port, bit, state in pbs:
        if port == self._PORT_C:
          if state:
            new_c_value |= 1 << bit
          else:
            new_c_value &= 0xFF ^ (1 << bit)
        elif port == self._PORT_D:
          if state:
            new_d_value |= 1 << bit
          else:
            new_d_value &= 0xFF ^ (1 << bit)
        else:
          raise USBDO96Exception('Invalid port: {}'.format(port))
      if new_c_value != current_c_value or new_d_value != current_d_value:
        # Need to write on both ports even if change is only on one port
        # as the current ports' value might not be correct and both will
        # be updated.
        # Could also check if the new values are the same for other groups
        # in which case we could update them together. However, not sure this
        # happens very often in real scenarios, so I'm not adding more logic
        # here and just update the groups one by one.
        self._WriteByte(self._PORT_C, self._CMD_WRITE, new_c_value)
        self._WriteByte(self._PORT_D, self._CMD_WRITE, new_d_value)
        self._WriteByte(self._PORT_B, self._CMD_WRITE,
                        port_b_value | (1 << group))
        self.current_values[group-1] = new_c_value | (new_d_value << 8)
            
  def turnOn(self, dos):
    """Turn on the given Digital Output(s) (set to 1).
    
    Args:
      dos: Digital Output(s) to turn on (set to 1). Either an int or an array
           of ints. DOs are 1-based.
    """
    self.setDOs(dos, None)
    
  def turnOff(self, dos):
    """Turn off the given Digital Output(s) (set to 0).
    
    Args:
      dos: Digital Output(s) to turn on (set to 1). Either an int or an array
           of ints. DOs are 1-based.
    """
    self.setDOs(None, dos)

