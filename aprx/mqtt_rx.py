#!/usr/bin/python3
# -*- coding: utf-8 -*-
# mqtt_rx.py	Empfang des WX-JSON Strings vom Broker
# Aufbereitung als APRS-String für aprx
#
# Version 24.12.23	aprs_qth angepasst
# 06.03.2023, WX-JSON ergänzt
# 12.06.2022	DL7ATA

import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
from datetime import date
import pytz

# ANPASSEN
datei_wx = "/tmp/aprs/wx_TgO.aprs"
aprs_qth = "52xx.18N/013xx.92E"
broker = "pi4"

mqtt_topic = [("7ata/wx/aprs",0)]
counter_parse = 0
counter_noparse = 0
ausg1 = ""
ausg2 = ""

def on_connect(client, userdata, flags, rc):
    print(time.strftime("%H:%M:%S"), "Connected with result code " + str(rc))
    client.subscribe(mqtt_topic)

def on_message(client, userdata, message):
    global ausg1, ausg2
    msg = str(message.payload.decode("utf-8"))
    topic = str(message.topic)
    akt_zeit= time.strftime("%H:%M:%S")

    # Format: @201841h5234.15N/01313.88E_000/000g000t048r000p000P000h83b.....wDIY
    utc_zeit = datetime.now(tz=pytz.UTC).strftime("%H%M")
    heute = date.today()
    aprs_tag = heute.strftime("%d")
    aprs_bake  = "@" + aprs_tag + str(utc_zeit) + "h" + \
    aprs_qth + "_" + msg

    print(aprs_bake)

    """with open(datei_wx, 'w') as output:
        output.write(aprs_bake)
        output.close()"""

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, 1883)
client.loop_forever()
