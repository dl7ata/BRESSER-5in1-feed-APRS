#!/usr/bin/python3
# -*- coding: utf-8 -*-
# raw_test.py   Empfang des Regenwertes, Ausgabe bei Fehler in Datei
# 04.04.2023	DL7ATA

import paho.mqtt.client as mqtt
import json
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
    time_stamp = time.strftime("%H:%M:%S")
    mic = data['mic']
    sid = data['id']
    if 'rain_mm' in data:
        if data['rain_mm'] > 1000:
            text = time_stamp + " Fehler bei Regenwert:" + \
                  str(data['rain_mm']) + "\n"
            datei_schreiben(datei, text)
            print(time_stamp, farbe_gelb, data['rain_mm'], sid, farbe_aus, mic, " "*55)
        print(time_stamp, farbe_gelb, data['rain_mm'], ", ID:", sid, farbe_aus, mic, "  \r\b")

# START
print(time.strftime("%H:%M:%S"),
      " MQTT-Broker/Topic:", farbe_gelb, mqtt_broker, mqtt_topic,
      farbe_aus, "mit rx-ch", farbe_gelb, mqtt_rx, farbe_aus,
      "\nPfad /tmp:", farbe_gelb, pfad_tmp, farbe_aus, " "*66, "\n")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(mqtt_broker, 1883)
client.loop_forever()
