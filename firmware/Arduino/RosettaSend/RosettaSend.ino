/* 
  Firmware for Arduino MKRWAN 1310
  Connects to Featherweight Raven in USB Host mode and Eggtimer Quantum as serial UART
  Copyright 2023 Jan T. Liphardt
  JTLiphardt@gmail.com
  No warranties, use at your own risk.
*/

#include <SPI.h>
#include <LoRa.h>
#include <cdcacm.h>
#include <usbhub.h>
#include "wiring_private.h"
#include <Arduino_MKRGPS.h>

#define SerialDebug Serial1

int counterMain = 0;

char buf[64];
uint16_t rcvd = 0;
uint8_t rcode;
uint32_t state;

bool haveNewRavData = false;
bool haveNewEggData = false;
bool haveNewGpsData = false;

char rav_dp[200]       = "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@";
char rav_dp_final[200] = "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@";

String EggData = "";
String RavData = "";
String GpsData = "";

long frequency   = 910700000; // change this to something quiet - e.g. this is Channel 42 (910.700 MHz)
byte myAddress   = 0xBC;  
byte destination = 0xE5;

class ACMAsyncOper : public CDCAsyncOper
{
  public:
    uint8_t OnInit(ACM *pacm);
};

uint8_t ACMAsyncOper::OnInit(ACM *pacm)
{

  uint8_t rcode = pacm->SetControlLineState(0); // Yup, "0" is the one

  if (rcode) {
    ErrorMessage<uint8_t>(PSTR("SetControlLineState"), rcode);
    return rcode;
  }

  LINE_CODING	lc;
  lc.dwDTERate	 = 57600;
  lc.bCharFormat = 0;
  lc.bParityType = 0;
  lc.bDataBits	 = 8;

  rcode = pacm->SetLineCoding(&lc);

  if (rcode)
    ErrorMessage<uint8_t>(PSTR("SetLineCoding"), rcode);

  return rcode;
}

USBHost      UsbH;
ACMAsyncOper AsyncOper;
ACM          AcmSerial(&UsbH, &AsyncOper);

void setup() {

  // initialize digital pin LED_BUILTIN as an output.
  pinMode(LED_BUILTIN, OUTPUT);

  SerialDebug.begin( 57600 ); 
  SerialDebug.println("SerialDebug is up");
  
  // The eggtimer uses Serial UART 9600
  Serial2.setTimeout( 50 ); 
  // timeout setting is critical otherwise the query loop will run very slowly for no reason
  Serial2.begin( 9600 );

  // Assign pins 0 and 1 SERCOM functionality
  pinPeripheral(0, PIO_SERCOM);
  pinPeripheral(1, PIO_SERCOM);

  if (UsbH.Init())
    SerialDebug.println("USB host FAILED to start");
  else   
    SerialDebug.println("USB host started");

  if (LoRa.begin(frequency)) { // US LoRa settings
    SerialDebug.println("LoRa started");
  } else {
    SerialDebug.println("LoRa FAILED to start");
  }

  LoRa.dumpRegisters(SerialDebug);

  // TX power in dB, defaults to 17 
  // 20 is the max, and you may not get it, depending...
  LoRa.setTxPower(20);

  // We want to increase data transmission reliability at the expense of data rate.
  // https://medium.com/home-wireless/testing-lora-radios-with-the-limesdr-mini-part-2-37fa481217ff
  // Lowest possible bandwidth
  // Highest possible Spreading Factor
  // Maximize coding rate

  // LoRa modulation has a total of six spreading factors (SF7 to SF12). 
  // The larger the spreading factor used, the farther the signal will be 
  // able to travel and still be received without errors by the RF receiver.
  LoRa.setSpreadingFactor(9); // 6 to 12, defaults to 7
  //  53 bytes SF9 125 kHz
  // 125 bytes SF8 125 kHz

  // https://lora-developers.semtech.com/documentation/tech-papers-and-guides/lora-and-lorawan/#:~:text=LoRa%20modulation%20has%20a%20total,errors%20by%20the%20RF%20receiver.
  // For a fixed SF, a narrower bandwidth will increase sensitivity as the bit rate is reduced.
  LoRa.setSignalBandwidth(125E3);
  // 7.8E3, 10.4E3, 15.6E3, 20.8E3, 31.25E3, 41.7E3, 62.5E3, 125E3, 250E3, and 500E3.
  // defaults to 125E3.

  // The Code Rate is the degree of redundancy implemented by the forward error correction (FEC) used to detect errors and correct them. 
  // Supported values are between 5 and 8, these correspond to coding rates of 4/5 and 4/8. The coding rate numerator is fixed at 4.
  // Coding Rate | CRC Rate | Overhead Ratio
  // ----------------------------------------
  // 1 | 4/5 | 1.25
  // 2 | 4/6 | 1.5
  // 3 | 4/7 | 1.75
  // 4 | 4/8 | 2
  LoRa.setCodingRate4(8);

  if (!GPS.begin()) {
    SerialDebug.println("Failed to initialize GPS!");
  } else {
    SerialDebug.println("GPS is up!");
  }
}

void loop() {

  SerialDebug.println("\nLoop: " + String(counterMain++));

  haveNewEggData = false;
  haveNewRavData = false;

  EggData = "";
  RavData = "";
  GpsData = "";

  digitalWrite(LED_BUILTIN, HIGH);

  delay(250);

  while (LoRa.beginPacket() == 0) {
    // doing anything else is pointless if the radio is not ready...
    //SerialDebug.println("Waiting for LoRa radio...");
    delay(100);
  }
  
  if(Serial2.available() > 0) {
    EggData = Serial2.readString();
    if(EggData.length() > 0) {
      EggData = "E" + EggData;
      haveNewEggData = true;
    }
  }
  
  if (GPS.available()) {
    SerialDebug.println("GPS has data");
  } else {
    SerialDebug.println("Waiting for GPS");
  }

  float latitude  = GPS.latitude();         // We are always on the Northern hemisphere
  float longitude = GPS.longitude() * -1.0; // We are always near -122 W

  SerialDebug.print("Location: ");
  SerialDebug.print(latitude);
  SerialDebug.print(" ");
  SerialDebug.println(longitude);

  // downsample alt to nearest 10 meters
  long altitude = long(GPS.altitude() / 10.0);

  // remove the degrees and sign and convert to a long
  // downsample to 5 decimal places aka 1.1 m accuracy 
  long latLocal = (latitude  - long(latitude )) * 100000L;
  long lonLocal = (longitude - long(longitude)) * 100000L;

  char gps[15];
  sprintf(gps, "G%d:%d:%d\0", latLocal, lonLocal, altitude);
  GpsData = String(gps);
  SerialDebug.print("Backup GPS: ");
  SerialDebug.println(gps);

  int satellites = GPS.satellites();
  SerialDebug.print("Number of satellites: ");
  SerialDebug.println(satellites);

  UsbH.Task();

  /*
    state = UsbH.getUsbTaskState();

    if ( state == USB_ATTACHED_SUBSTATE_SETTLE ) { //0x20 32
      SerialDebug.println("USB_ATTACHED_SUBSTATE_SETTLE");
    } else if ( state == USB_ATTACHED_SUBSTATE_RESET_DEVICE ) { //0x30 48
      SerialDebug.println("USB_ATTACHED_SUBSTATE_RESET_DEVICE");
    } else if ( state == USB_ATTACHED_SUBSTATE_WAIT_RESET_COMPLETE ) { //0x40 64
      SerialDebug.println("USB_ATTACHED_SUBSTATE_WAIT_RESET_COMPLETE");
    } else if (state == USB_ATTACHED_SUBSTATE_WAIT_SOF) { //0x50 80
      SerialDebug.println("USB_ATTACHED_SUBSTATE_WAIT_SOF");
    } else if (state == USB_STATE_DETACHED ) { //0x10 16
      SerialDebug.println("USB_STATE_DETACHED");
    } else if ( state == USB_ATTACHED_SUBSTATE_WAIT_RESET_COMPLETE ) { //0x40 64
      SerialDebug.println("USB_ATTACHED_SUBSTATE_WAIT_RESET_COMPLETE");
    } else if ( state == USB_STATE_ADDRESSING ) { // 0x70 112
      SerialDebug.println("USB_STATE_ADDRESSING");
    } else if ( state == USB_STATE_CONFIGURING ) { // 0x80 128
      SerialDebug.println("USB_STATE_CONFIGURING");
    } else if ( state == USB_STATE_RUNNING ) { // 0x90 144
      SerialDebug.println("USB_STATE_RUNNING");
    } else if ( state == USB_STATE_ERROR ) { // 0xa0 160
      SerialDebug.println("USB_STATE_ERROR");
    } else {
      SerialDebug.print("UNKNOWN USB task state: ");
      SerialDebug.println(state);
    }
  */

  if( AcmSerial.isReady() ) {

    int payloadLength = 0;
    bool haveRavData = false;
    int i, j;

    rcvd = 64; // always reset rcvd to max USB packet length
    rcode = AcmSerial.RcvData(&rcvd, (uint8_t *)buf);
    if (rcode && rcode != USB_ERRORFLOW)
      ErrorMessage<uint8_t>(PSTR("Ret"), rcode);

    if( rcvd > 0 ) {
      //SerialDebug.print("Raven Part 1: ");
      //SerialDebug.write(buf, rcvd);
      //SerialDebug.println("");

      // cut off the header and date
      if (buf[0] == '@' && buf[2] == 'B') {
        haveRavData = true;
        //int skip = 26; //skip @ BLR_STAT 189 2023 08 20 
        int j = 0;
        while (buf[j] != ':') j++;
        int start_parse = j + 1;
        for (i = 0, j = start_parse; j < rcvd; j++) {
          if (isAlpha(buf[j])) { 
            // skip letters
          } else if (buf[j] == ':') {
            // replace with a space 
            rav_dp[i++] = ' ';
          } else {
            rav_dp[i++] = buf[j];
          }
        }
        payloadLength = i;
      }
    }

    if( haveRavData ) {
      // get the second Raven USB packet
      rcvd = 64;
      rcode = AcmSerial.RcvData(&rcvd, (uint8_t *)buf);
      if (rcode && rcode != USB_ERRORFLOW)
        ErrorMessage<uint8_t>(PSTR("Ret"), rcode);

      if( rcvd > 0 ) {
        //SerialDebug.print("Raven Part 2: ");
        //SerialDebug.write(buf, rcvd);
        //SerialDebug.println("");

        for (i = payloadLength, j = 0; j < rcvd; j++) {
          if (isAlpha(buf[j])) { 
            // skip letters
          } else if (buf[j] == ':') {
            // replace with a space 
            rav_dp[i++] = ' ';
          } else {
            rav_dp[i++] = buf[j];
          }
        }

        payloadLength = i;
      }

      // get the third Raven USB packet
      rcvd = 64;
      rcode = AcmSerial.RcvData(&rcvd, (uint8_t *)buf);
      if (rcode && rcode != USB_ERRORFLOW)
        ErrorMessage<uint8_t>(PSTR("Ret"), rcode);

      if( rcvd > 0 ) {
        //SerialDebug.print("Raven Part 3: ");
        //SerialDebug.write(buf, rcvd);
        //SerialDebug.println("");

        for (i = payloadLength, j = 0; j < rcvd; j++) {
          if (isAlpha(buf[j])) { 
            // skip letters
          } else if (buf[j] == ':') {
            // replace with a space 
            rav_dp[i++] = ' ';
          } else {
            rav_dp[i++] = buf[j];
          }
        }

        payloadLength = i;

        // skip runs of whitespace
        for (i = 0, j = 0; j < payloadLength; j++) {
          if (rav_dp[j] == ' ' && rav_dp[j+1] == ' ') {
          } else {
            rav_dp_final[i++] = rav_dp[j];
          }
        }
        // chop off spurious junk from previous data
        // the last two characters are always 1310 aka CR and LF
        rav_dp_final[i-2] = '\0';

        // parse the string
        char *token;
        const char *delimiter = " ";
        int tN = 0;
        
        token = strtok(rav_dp_final, delimiter);
        int minutes = atoi(token);

        float seconds;
        int accel400;
        int accel16;
        int roll;
        int batt;
        int vel;
        int agl;

        while (token != NULL) {
          tN++;
          SerialDebug.print(tN);
          SerialDebug.println(token);
          token = strtok(NULL, delimiter);
          if (tN == 1) 
            seconds = atof(token);
          else if (tN == 2) 
            accel400 = atoi(token);
          else if (tN == 5) 
            accel16 = atoi(token);
          else if (tN == 10)
            // downsample the battery to one decimal point 
            batt = int(float(atoi(token))/100.0);
          else if (tN == 11) 
            roll = atoi(token);
          else if (tN == 16) 
            vel = atoi(token);
          else if (tN == 17) 
            // downsample the alt to nearest 10th
            agl = int(float(atoi(token))/10.0);
        }

        int time = (minutes * 60 + seconds) * 10.0; 
        // convert time to seconds * 10 to preserve 10th ms

        // construct the final data string
        char buffer[22];
        sprintf(buffer, "R%d:%d:%d:%d:%d:%d:%d\0", time, accel400, accel16, batt, roll, vel, agl);
        RavData = String(buffer);
        haveNewRavData = true;
      }

    } 

  } else {
    //SerialDebug.println("ACM NOT READY");
  }

  digitalWrite(LED_BUILTIN, LOW);

  if(haveNewRavData) {
    SerialDebug.println("Final Rav Data: " + RavData + " Length: " + RavData.length());
  }

  if(haveNewEggData) {
    SerialDebug.println("Final Egg Data: " + EggData + " Length: " + EggData.length());
  }

  SerialDebug.println("Final Gps Data: " + GpsData + " Length: " + GpsData.length());

  int LoRaState = LoRa.beginPacket();
  if (LoRaState == 1) {
    LoRa.write(destination);          
    if (haveNewRavData)
      LoRa.print(RavData);
    if (haveNewEggData)
      LoRa.print(EggData);
    LoRa.print(GpsData);
    LoRa.endPacket(true);
  } else if (LoRaState == 0) {
    SerialDebug.println("LORA DATA LOSS: Radio not ready");
  }


}