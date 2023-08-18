/*

Firmware for Heltec Wireless Stick (LoRa)

Connects to Arduino MKRWAN 1310 and sends LoRa data to serial 

Copyright 2023 Jan T. Liphardt
JTLiphardt@gmail.com

No warranties, use at your own risk.

*/

#include "LoRaWan_APP.h"
#include "Arduino.h"
#include <Wire.h>  
#include "HT_SSD1306Wire.h"

// CHANGE ME!!!
#define RF_FREQUENCY                                910700000 // Hz
byte myAddress     = 0xE5;
byte correctSender = 0xBC;  

#define LORA_BANDWIDTH                              0         // [0: 125 kHz,
                                                              //  1: 250 kHz,
                                                              //  2: 500 kHz,
                                                              //  3: Reserved]

#define LORA_SPREADING_FACTOR                       7         // [SF7..SF12]

#define LORA_CODINGRATE                             1         // [1: 4/5,
                                                              //  2: 4/6,
                                                              //  3: 4/7,
                                                              //  4: 4/8]

#define LORA_PREAMBLE_LENGTH                        8
#define LORA_SYNCWORD                               0x12
#define LORA_SYMBOL_TIMEOUT                         0
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false
#define LORA_IQ_INVERSION_ON                        false
#define RX_TIMEOUT_VALUE                            1000
#define BUFFER_SIZE                                 256

char rxpacket[BUFFER_SIZE];

static RadioEvents_t RadioEvents;
void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr );

int16_t rxNumber;
int16_t Rssi,rxSize;
bool lora_idle = true;
String packet;

void VextON(void) {
  pinMode(Vext,OUTPUT);
  digitalWrite(Vext, LOW);  
}

SSD1306Wire  factory_display(0x3c, 500000, SDA_OLED, SCL_OLED, GEOMETRY_64_32, RST_OLED); // addr , freq , i2c group , resolution , rst

void setup() {
    
    Serial.begin(115200);
    Serial.println("Hello!");
    
    VextON();
	  delay(100);

    Mcu.begin();
    
    rxNumber = 0;
    Rssi = 0;
  
    RadioEvents.RxDone = OnRxDone;
    
    Radio.Init( &RadioEvents );
    
    Radio.SetChannel( RF_FREQUENCY );
    Radio.SetSyncWord( LORA_SYNCWORD );
    Radio.SetRxConfig( MODEM_LORA, LORA_BANDWIDTH, LORA_SPREADING_FACTOR,
      LORA_CODINGRATE, 0, LORA_PREAMBLE_LENGTH,
      LORA_SYMBOL_TIMEOUT, LORA_FIX_LENGTH_PAYLOAD_ON,
      0, true, 0, 0, LORA_IQ_INVERSION_ON, true );
    Radio.SetMaxPayloadLength( MODEM_LORA, 255 );

    factory_display.init();
    factory_display.clear();
    
    packet ="915MHz";
    factory_display.drawString(0, 0, packet);
    factory_display.display();
    delay(100);
    factory_display.clear();
	  
    pinMode(LED, OUTPUT);
	  digitalWrite(LED, LOW); 
}

void loop()
{
  Serial.println("RX");
  factory_display.drawString(0, 0, "Listening");
  factory_display.display();

  digitalWrite(LED, HIGH); 
  delay(100);
  digitalWrite(LED, LOW); 
  delay(100);

  if(lora_idle)
  {
    lora_idle = false;
    Radio.Rx(0);
  }

  Radio.IrqProcess();
}

void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr)
{
    Rssi = rssi;
    rxSize = size;
    
    // generate a nice string
    // char rxpacket[BUFFER_SIZE];
    memcpy(rxpacket, payload, size);
    rxpacket[size]='\0';

    Radio.Sleep();
    
    //Serial.printf("Header Bytes: %d %d\n",payload[0],payload[1]);
    
    if (payload[0] == myAddress && payload[1] == correctSender) {
      // this payload is for us
      Serial.printf("\"%s\" rssi %d, length %d, SNR: %d\n", rxpacket, Rssi, rxSize, snr);
      factory_display.clear();
      factory_display.drawString(0, 9, rxpacket);
      factory_display.display();
    } else {
      Serial.printf("This LoRa payload is not for us\n");
    }

    lora_idle = true;
}