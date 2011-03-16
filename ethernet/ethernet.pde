#include <Ethernet.h>
#include <string.h>

byte mac[] = {0x00, 0xDE, 0xCA, 0xFB, 0xAD, 0x00};
byte ip[] = {137, 110, 118, 251};
byte gw[] = { 137, 110, 118, 1 };
byte subnet[] = {255, 255, 255, 0};

byte mbp[] = { 137, 110, 111, 241 };

#include "Wire.h"
#include "BlinkM_funcs.h"

#include <avr/pgmspace.h>  // for progmem stuff

byte blinkm_addr = 0x09; // the default address of all BlinkMs
byte colors[3] = {0x00, 0x00, 0x00};
int idx = 0;

Server server(80);


void lookForBlinkM() 
{
  int a = BlinkM_findFirstI2CDevice();
  if( a != -1 ) 
  { 
    blinkm_addr = a;
  }
}

void setup()
{
  BlinkM_beginWithPower();
  lookForBlinkM();  
  BlinkM_stopScript(blinkm_addr);
  
  // R-G-B-W startup animation
  BlinkM_fadeToRGB(blinkm_addr, 0x20, 0x00, 0x00);  
  delay(500);
  BlinkM_fadeToRGB(blinkm_addr, 0x00, 0x20, 0x00);  
  delay(500);
  BlinkM_fadeToRGB(blinkm_addr, 0x00, 0x00, 0x20);  
  delay(500);
  BlinkM_fadeToRGB(blinkm_addr, 0x20, 0x20, 0x20);  
  delay(500);

  Ethernet.begin(mac, ip, gw, subnet);
  server.begin();

  // When light goes out, init is complete.
  BlinkM_fadeToRGB(blinkm_addr, 0x00, 0x00, 0x00);
}


void loop()
{
  Client client = server.available();
  if (client) 
  {
    BlinkM_fadeToRGB(blinkm_addr, 0x00, 0x00, 0x00);    
    delay(100);
    idx = 0;
    while (client.connected())
    {
      if (client.available()) 
      {
        // Data ready to read
        colors[idx] = client.read() - 'a';
        idx = idx + 1;
        if (idx > 2)
        {
          // Set color
          BlinkM_fadeToRGB(blinkm_addr, colors[0], colors[1], colors[2]);
          
          // Done reading - send sensors
          client.print(analogRead(0));
          client.print(" ");
          client.println(analogRead(1));
          delay(10);
          client.stop();
        }
      }
    }
  }
}

