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
#define SerialDebug Serial1

// CHANGE ME!!!
// change this to something quiet - e.g. this is Channel 42 (910.700 MHz)
// See this table for US Frequencies
// https://www.baranidesign.com/faq-articles/2019/4/23/lorawan-usa-frequencies-channels-and-sub-bands-for-iot-devices

long frequency   = 910700000; 
byte myAddress   = 0xBC;  
byte destination = 0xE5;

int counterRaven = 0;
int counterEgg = 0;
int counterMain = 0;

char buf[64];
uint16_t rcvd = 0;
uint8_t rcode;
uint32_t state;

bool haveNewRavenData = false;
bool haveNewEggData = false;

char raven_dp[200]       = "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@";
char raven_dp_final[200] = "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@";

String EggData = "";
String RavenData = "";

class ACMAsyncOper : public CDCAsyncOper
{
  public:
    uint8_t OnInit(ACM *pacm);
};

uint8_t ACMAsyncOper::OnInit(ACM *pacm)
{

  uint8_t rcode = pacm->SetControlLineState(0);
  // Yup, "0" is the one
  // Sigh - not documented...

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
    SerialDebug.println("USB host did not start");
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

}

void loop() {

  SerialDebug.print("\nLoop: ");
  SerialDebug.println(counterMain);
  counterMain++;

  haveNewEggData = false;
  haveNewRavenData = false;
  EggData = "";

  digitalWrite(LED_BUILTIN, HIGH);
  delay(250);

  digitalWrite(LED_BUILTIN, LOW);
  delay(250);

  while (LoRa.beginPacket() == 0) {
    // doing anything else is pointless if the radio is not ready...
    SerialDebug.println("Waiting for LoRa radio...");
    delay(100);
  }
  
  if(Serial2.available() > 0) {
    EggData = Serial2.readString();
    if(EggData.length() > 0) {
      counterEgg++;
      haveNewEggData = true;
      EggData = "EGG " + EggData;
    }
  }

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
    bool haveRavenData = false;
    int i, j;

    rcvd = 64; // always reset rcvd to max USB packet length
    rcode = AcmSerial.RcvData(&rcvd, (uint8_t *)buf);
    if (rcode && rcode != USB_ERRORFLOW)
      ErrorMessage<uint8_t>(PSTR("Ret"), rcode);

    if( rcvd > 0 ) {
      SerialDebug.print("Raven Part 1: ");
      SerialDebug.write(buf, rcvd);
      SerialDebug.println("");
      
      // get the first Raven USB packet
      if (buf[0] == '@' && buf[2] == 'B') {
        haveRavenData = true;
        int skip = 26;
        for (i = 0, j = skip; j < rcvd; j++) {
          if (isAlpha(buf[j]) || buf[j] == ':') { 
            // skip letters and :
          } else {
            raven_dp[i++] = buf[j];
          }
        }
        payloadLength = i;
      }

    }

    if( haveRavenData ) {
      // get the second Raven USB packet
      rcvd = 64;
      rcode = AcmSerial.RcvData(&rcvd, (uint8_t *)buf);
      if (rcode && rcode != USB_ERRORFLOW)
        ErrorMessage<uint8_t>(PSTR("Ret"), rcode);

      if( rcvd > 0 ) {
        SerialDebug.print("Raven Part 2: ");
        SerialDebug.write(buf, rcvd);
        SerialDebug.println("");

        for (i = payloadLength, j = 0; j < rcvd; j++) {
          if (isAlpha(buf[j]) || buf[j] == ':') {
            // skip letters and :
          } else {
            raven_dp[i++] = buf[j];
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
        SerialDebug.print("Raven Part 3: ");
        SerialDebug.write(buf, rcvd);
        SerialDebug.println("");

        for (i = payloadLength, j = 0; j < rcvd; j++) {
          if (buf[j] == 'C' && buf[j+1] == 'R') {
            j += 5;
            // copy the length 4 CRC
            raven_dp[i++] = buf[j++];
            raven_dp[i++] = buf[j++];
            raven_dp[i++] = buf[j++];
            raven_dp[i++] = buf[j++];
          } else if (isAlpha(buf[j]) || buf[j] == ':') {
            // skip letters and :
          } else {
            raven_dp[i++] = buf[j];
          }
        }

        payloadLength = i;

        for (i = 0, j = 0; j < payloadLength; j++) {
          if (raven_dp[j] == ' ' && raven_dp[j+1] == ' ') {
            // skip runs of whitespace
          } else {
            raven_dp_final[i++] = raven_dp[j];
          }
        }

        // the -1 chops off a spurious CR
        raven_dp_final[i-1] = '\0';

        RavenData = "RAV " + String(raven_dp_final);
        
        counterRaven++;
        haveNewRavenData = true;

      }

    } 

  } else {
    //SerialDebug.println("ACM NOT READY");
  }

  digitalWrite(LED_BUILTIN, LOW);

  if(haveNewRavenData) {
    SerialDebug.print("New Raven Data: ");
    SerialDebug.println(String(raven_dp_final));
  }

  if(haveNewEggData) {
    SerialDebug.print("New Eggtimer Data: ");
    SerialDebug.println(EggData);
  }
  
  if (LoRa.beginPacket() == 1 && (haveNewRavenData || haveNewEggData)) {
    SerialDebug.print("LORA: Sending packet: ");
    SerialDebug.println(counterRaven);
    
    // Each packet can contain up to 255 bytes.
    LoRa.beginPacket();
    LoRa.write(destination);    // write a destination char            
    LoRa.write(myAddress);      // my sender ID  
    if (haveNewRavenData) {
      LoRa.print(RavenData);
    }
    if (haveNewEggData) {
      LoRa.print(EggData);
    }
    LoRa.print(counterRaven); 
    LoRa.print(counterEgg); 
    LoRa.endPacket(true);       // true = async / non-blocking mode
  } else if (LoRa.beginPacket() == 0 && haveNewRavenData) {
    SerialDebug.println("LORA DATA LOSS: Radio not ready for Raven payload");
  }

}