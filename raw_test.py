#!/usr/bin/python3
# -*- coding: utf-8 -*-
# raw_test.py	Empfang des PV-JSON Strings vom PI4, Ausgabe für APRS und SVX
# 04.04.2023	DL7ATA

import paho.mqtt.client as mqtt
import json
from datetime import datetime
import time
import sys

# ---------indiv. Anpassung-------------------ON----------------------
mqtt_broker = "pi4"
mqtt_topic = "7ata/wx/"
mqtt_rx = "raw"  	# Einlesen JSON aus rtl_433
# -------------------------------------------OFF----------------------

TOPIC = [
(mqtt_topic + mqtt_rx, 0)
]
pfad_tmp = "/tmp/Wetter/devel"
datei = pfad_tmp + "/mqtt_test.tmp"
farbe_gelb = '\033[33m'
farbe_aus = '\033[0m'

def on_connect(client, userdata, flags, rc):
    print("Connected to >" + mqtt_broker + "< [result code " + str(rc) + "]")
    client.subscribe(TOPIC)

def datei_schreiben(datei, inhalt):
    with open(datei, 'a') as output:
        output.write(inhalt)
        output.close()

def on_message(client, userdata, message):
    msg = str(message.payload.decode("utf-8"))
    topic = str(message.topic)
    data = json.loads(msg)
    time_stamp = str(datetime.fromtimestamp(int(time.time())))
    if 'rain_mm' in data:
        if data['rain_mm'] > 1000:
            text = time_stamp + " Fehler bei Regenwert:" + \
                  str(data['rain_mm']) + str(rain_start)
            datei_schreiben(datei, text)
            print(time_stamp, farbe_gelb, data['rain_mm'], farbe_aus)
        print(time_stamp, farbe_gelb, data['rain_mm'], farbe_aus, "   \r\b")

# START
print(datetime.now().strftime("%H:%M:%S"),
      "UTC. MQTT-Broker/Topic:", farbe_gelb, mqtt_broker, mqtt_topic,
      farbe_aus, "mit rx-ch", farbe_gelb, mqtt_rx, farbe_aus,
      "\nPfad /tmp:", farbe_gelb, pfad_tmp, farbe_aus, "\n")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(mqtt_broker, 1883)
client.loop_forever()
