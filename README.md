# BRESSER-5in1-feed-APRS
Hardware:
  - Weather station BRESSER 5in1
  - Raspi 3b+ or newer with Raspbian OS
  - DVB-stick with Rafael Micro R820T tuner
  - BME280 Sensor
  Software:
  - rtl_433 (check on ggl)
  - python3 with some libraries (json, paho.mqtt.client, bme280)
  - mqtt (broker could be on same raspi)
  
  Step 1:    Install rtl_433 on raspi. Check it with a standard receive scan on 433 MHz. If you receive several signals, everything is fine for ...
  
  
  Step 2:    Running command
  rtl_433 -F log -F json -M iso -f 868M -R 172 -C si -Y squelch | mosquitto_pub -t 7ata/wx/raw -l  
  receives signal from weather sensor on 868 MHz, prepare data in ISO-format into a json-string and send it (command after piping) via mqtt.
  The guideline for preparing data in python script are "Positionless Weather Data" in APRS PROTOCOL REFERENCE Protocol Version 1.0 and wind is WMO calculated (avg. of 10 and 5 min. for gust).
  
  Step 3:   If you want to add air pressure, you need an extra sensor. A simple BME280 works fine and has to be connected on raspi via i2c (how to check on ggl).
  For that reason take wx_bme280.py - script from the repository.
  
  I know this is a quick & dirty description and dedicated to people, who have experience in raspi projects.
  
  Good luck & 73
