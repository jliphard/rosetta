# Rosetta

Rosetta is designed to move data from amateur rocket flight controllers and display those data in [Cosmos/OpenC3](https://openc3.com), a professional hardware command and control software.

Rosetta currently understands data from [Featherweight Raven](https://www.featherweightaltimeters.com/raven-altimeter.html) and [Eggtimer Quantum](http://eggtimerrocketry.com/eggtimer-quantum/) flight controllers as well as the [Featherweight GPS Tracker](https://www.featherweightaltimeters.com/featherweight-gps-tracker.html), but can easily be modified to transmit, receive, and display data from essentially all known flight computers provided they expose the data somehow. 

The system connects to the [Featherweight Raven](https://www.featherweightaltimeters.com/raven-altimeter.html) using an Arm Cortex-M0 32-bit SAMD21 [Arduino MKRWAN 1310](https://docs.arduino.cc/hardware/mkr-wan-1310) in USB host mode, and connects to the [Eggtimer Quantum](http://eggtimerrocketry.com/eggtimer-quantum/) via serial UART. The system also parses tracking/GPS data from the [Featherweight GPS Tracker](https://www.featherweightaltimeters.com/featherweight-gps-tracker.html).

Rosetta does not provide the ability to control or guide rockets and is strictly a one way real time telemetry system.  

![Dashboard](https://github.com/jliphard/rosetta/blob/main/images/dash.png)

## System Overview

Ok, so if you think building cubesats is fun and relaxing or it's you, Joe or Xyla, this will all be self explanatory - have fun. For many others, be advised, getting this all to run involves intermediate familiarity with LoRa, micro controllers, USB, RF, python, TCP sockets, Docker, and Cosmos/OpenC3.

### 1. Raven Telemetry 

The Raven streams telemetry through Bluetooth (before launch) and through USB (continuously - I hope/think) using essentially the default STM32 Usbmodem CDC_ACM. The data format is self-explanatory.

```c
// Raven USB settings
  lc.dwDTERate   = 57600;
  lc.bCharFormat = 0;
  lc.bParityType = 0;
  lc.bDataBits   = 8;
```

### 2. Raven->LoRa Transmission

An Arduino MKRWAN 1310 is configured to USB Host mode and connected to the Raven via a custom powered straight through USB cable. The 1310 talks to the Raven and re-transmits all data using a 20 dB LoRa down-link with sender/receiver IDs in the LoRa packet. To construct the cable, cut two USB cables and connect all four wires to their colors - do not cross the data lines - this is not a serial cable. Provide regulated +5V to the red (power) wire from your rocket's +5V power bus. Customize the LoRa frequency, sender, and destination addresses. Flash the Arduino MKRWAN 1310 with `firmware/Arduino/RosettaSend.ino`. 

```c
// RosettaSend.ino

// CHANGE ME!!!
// change this to something quiet - e.g. this is Channel 42 (910.700 MHz)
// See this table for US Frequencies
// https://www.baranidesign.com/faq-articles/2019/4/23/lorawan-usa-frequencies-channels-and-sub-bands-for-iot-devices

long frequency   = 910700000; 
byte myAddress   = 0xBC;  
byte destination = 0xE5;
```

**Important**

If you want to stream data from other flight controllers such as the Eggtimer, modify the SAMD21's Arduino drivers (`variant.cpp` and `variant.h`) to remap the SAMD21 Serial2/Sercom3 to digital pins 0 and 1:

```c
// variant.cpp
Uart Serial2(&sercom3, PIN_SERIAL2_RX, PIN_SERIAL2_TX, PAD_SERIAL2_RX, PAD_SERIAL2_TX);

void SERCOM3_Handler()
{
  Serial2.IrqHandler();
}
```

```c
// variant.h
extern Uart Serial2;
#define PIN_SERIAL2_RX (1ul)
#define PIN_SERIAL2_TX (0ul)
#define PAD_SERIAL2_TX (UART_TX_PAD_0)
#define PAD_SERIAL2_RX (SERCOM_RX_PAD_1)
```

### 3. Eggtimer->LoRa Transmission

The Eggtimer Quantum streams telemetry through serial UART. The data format is [well documented](http://eggtimerrocketry.com/wp-content/uploads/2021/05/Eggtimer-Telemetry-Data-Format.pdf). The 1310 receives serial on pins 0 and 1 and re-transmits everything to ground.

**Fun fact**: Interestingly, the Quantum switches serial data rate after initialization to 9600 baud. Also, the Quantum does not need to be armed to transmit data. 

### 4. Ground Station to Serial

The LoRa telemetry is received by a [Heltec Wireless Stick v3](https://heltec.org/project/wireless-stick-v3/) - current cost is $17.90. It has LoRa and a small display for showing debug information. Flash the Wireless Stick with `firmware/Arduino/RosettaReceive.ino`.

### 5. Ground Station Data to TCP

Sadly, Docker makes it very hard to access local serial/USB data and COSMOS/OpenC3 uses Docker. Yes, it _is_ possible but that's a whole other project. So, Rosetta collects the data from serial using a simple python script, clean up the data, and pushes them to a web socket at `127.0.0.1:23200`. 

To run the serial->TCP stream:

```shell
$ python3 StreamToTCP.py
```

You will need to set your ports based on `ls /dev/cu.usb*`:

```python
ser1 = serial.Serial('/dev/cu.usbserial-D201105P', baudrate=115200)
print (ser1.name)

ser2 = serial.Serial('/dev/cu.usbserial-0001', baudrate=115200)
print (ser2.name)
```

### 6. TCP to COSMOS/OpenC3

Start Docker and:

```shell
$ ./openc3.sh run
```

The dashboard is at:

```shell
http://localhost:2900/tools/admin
```

As always for COSMOS, the connector is defined in `/plugin.txt`

```
VARIABLE data_target_name M

TARGET HUB <%= data_target_name %>

INTERFACE <%= data_target_name %>_TCP tcpip_client_interface.rb host.docker.internal 23200 23200 10.0 10.0

MAP_TARGET <%= data_target_name %>
```

## Useful commands

To generate/rebuild OpenC3 plugins:

```shell
$ ./openc3.sh cli generate plugin HUB
$ cd openc3-cosmos-hub  
$ ../openc3.sh cli generate target HUB
$ ../openc3.sh cli rake build VERSION=1.0.0
```
