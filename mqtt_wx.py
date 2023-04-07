#!/usr/bin/python3
# -*- coding: utf-8 -*-
# mqtt_wx.py	Empfang des PV-JSON Strings vom PI4, Ausgabe für APRS und SVX
# 05.03.2023	DL7ATA

""" ACHTUNG: Es erfolgt eine Umrechnung der Daten von metrisch/BRESSER nach US für APRS
    Doku APRS-format unter http://www.aprs.org/APRS-docs/PROTOCOL.TXT und .../WX.TXT
    sowie Details in APRS101.PDF, S. 74
  CSE/SPD is wind direction and sustained 1 minute speed
  txxx is in degrees F
  rxxx is Rain per last 60 minutes
  pxxx is precipitation per last 24 hours (sliding 24 hour window)
  Pxxx is precip per last 24 hours since midnight
  sxxx is snow
  bxxxxx is Baro in tenths of a mb
  hxx is humidity in percent.  00=100
  gxxx is Gust (peak winds in last 5 minutes)
  Lxxx is luminosity below 999
  lxxx is luminosity above 1000
  Fxxxx is flood water height in feet (to tenths ie: 20.1)
  fxxxx is flood height in meters (also to tenths)
  #xxx is the raw rain counter for remote WX stations. See notes on remotes
  %xxx.. 1st byte shows software type d=Dos, m=Mac, w=Win, etc
         remainder shows type of WX instrument

BRESSER 6in1 sendet regelmäßig zwei unterschiedliche Pakete aus:
I: {"time" : "2023-03-15 07:10:51", "model" : "Bresser-6in1", "id" : 339740226, "channel" : 0,
"battery_ok" : 1,"temperature_C" : 0.700, "humidity" : 84, "sensor_type" : 1,
"wind_max_m_s" : 0.000, "wind_avg_m_s" : 0.000, "wind_dir_deg" : 112,
"uv" : 0.000, "startup" : 1, "flags" : 0, "mic" : "CRC"}

II: {"time" : "2023-03-15 07:11:03", "model" : "Bresser-6in1", "id" : 339740226, "channel" : 0, "sensor_type" : 1,
"wind_max_m_s" : 0.600, "wind_avg_m_s" : 0.600, "wind_dir_deg" : 112,
"rain_mm" : 48.000, "startup" : 1, "flags" : 1, "mic" : "CRC"}
"""

import paho.mqtt.client as mqtt
import json
from datetime import datetime
import time
import pytz
import subprocess
import sys
import mqtt_set

Version = "230406.071"
mqtt_ch = "tgo"  	# Selbst erstellte JSON wird in "mqtt_topic/mqtt_ch" veröffentlicht  dev = develop, tgo = live!

TOPIC = [
(mqtt_set.mqtt_topic + mqtt_set.mqtt_rx, 0), \
(mqtt_set.mqtt_topic + mqtt_set.mqtt_bme280, 0) \
]
timing = (5 * 60)	  # Alle x Sek. (Angaben in Sek.) an APRS-Server senden
pfad_tmp = "/tmp/Wetter"
home_pfad = "/home/svxlink/Scripte/Wetter"
datei_svx = pfad_tmp + "/svx_akt_temp"
datei_aprs = pfad_tmp + "/aprs_WX"
datei_log = pfad_tmp + "/aprs_mqtt.tmp"
datei_json = pfad_tmp + "/Wetter.json"
datei_tag = pfad_tmp + "/Tagesstatistik.txt"
erster_durchlauf_rain = True
erster_durchlauf_wind = True
farbe_gelb = '\033[33m'
farbe_aus = '\033[0m'

# Counter Regen letzte 1h., letzte 24h, seit Mitternacht
aprs_timer, count_5m, count_10m, count_1h, count_24h, count_mn, rain_start, rain_mn = 0, 0, 0, 0, 0, 0, 0, 0
time_count_5m = 0
time_count_10m = 0

# Variable Regen
count_rain_5m = 0
count_rain_1h = 0
count_rain_24h = 0
rain_mm_1h = []
rain_mm_24h = []

# Indicees Wind Durchschnitt 10 Min., Gust 5 Min.
wind_10m_avg = []
wind_5m_max = []

# Tgl. maximal- und minimal Werte initialisieren
temp_max_tag, temp_min_tag, wind_max_tag = -99, 99, 0

# Zwischenfelder für Ausgabe
v_rain_1h, v_rain_24h, v_rain_mn = 0, 0, 0
v_temp, v_hum, v_wind_max, v_wind_avg, v_wind_dir, v_rain = '', '', '', '', '', ''

v_baro_Hpa = 0

def on_connect(client, userdata, flags, rc):
    print("Connected to >" + mqtt_set.mqtt_broker + "< [result code " + str(rc) + "]")
    client.subscribe(TOPIC)

def einlesen_JSON(datei):
    global rain_mm_1h, rain_mm_24h, rain_mn, mqtt_ch
    try:
        with open(datei) as json_file:
            data_tx = json.load(json_file)

    except FileNotFoundError:
        template_json = home_pfad + datei_json
        print("Wetter.JSON nicht gefunden, nehme ", template_json)
        try:
            with open(template_json) as json_file:
                data_tx = json.load(json_file)

        except FileNotFoundError:
            print("Wetter.JSON auch in ", home_pfad, " nicht gefunden. good bye..")
            sys.exit()

    if mqtt_ch == "dev":
        print("Einlesen JSON:",datei, "\n", data_tx, "\n")

    return(data_tx)

def datei_schreiben(datei, inhalt):
    with open(datei, 'w') as output:
        output.write(inhalt)
        output.close()

def schreiben_JSON(data):
    # schreibt JSON mit allen ermittelten Werten und sendet sie per mqtt auf ch "7ata/wx/<ch>"
    with open(datei_json, 'w') as outfile:
        json.dump(data, outfile)
    publ_data = json.dumps(data)
    client.publish(mqtt_set.mqtt_topic + mqtt_ch, str(publ_data))

def regen_ermitteln(data):
    global erster_durchlauf_rain
    global count_rain_5m, count_rain_1h, rain_mm_1h
    global count_rain_24h, rain_mm_24h
    global rain_1h, rain_24h, rain_mn, rain_start

    # Initialisierung
    if erster_durchlauf_rain:
        erster_durchlauf_rain = False
        rain_start = data['rain_mm']
        rain_mn = data_tx['Regen_mn']
        count_rain_5m = int(time.time()) - 300
        return(round(sum(rain_mm_1h),2), round(sum(rain_mm_24h),2), round(rain_mn,2))

    # Alle 5 Min. den Wert ermitteln
    if (int(time.time()) - count_rain_5m) > 300:
        count_rain_5m = int(time.time())
        # neue_menge: Diff. aus akt. Wert - Wert vor 5 Min.
        neue_menge = data['rain_mm'] - rain_start

        # Sect. I letzte Stunde. Wenn neuer Wert > ist als 0-Index/Ursprungswert, dann speichern
        try:
            rain_mm_1h[count_rain_1h] = neue_menge
        except IndexError:
            rain_mm_1h.append(neue_menge)
        count_rain_1h += 1
        # In 1h Stunde werden 12 Werte ermittelt, dann rolliert die Tabelle wieder
        if count_rain_1h == 12:
            count_rain_1h = 0

        # Sect. II letzte 24 Stunden
        try:
            rain_mm_24h[count_rain_24h] = neue_menge
        except IndexError:
            rain_mm_24h.append(neue_menge)
        count_rain_24h += 1
        # In 24h stunden werden 12 *24 Werte ermittelt, dann rolliert die Tabelle wieder
        if count_rain_24h == (12 * 24):
            count_rain_24h = 0

        # Sect. III seit Mitternacht
        rain_mn += neue_menge

        # Akt. Summenwert für nächsten Durchlauf merken
        rain_start = data['rain_mm']

        if mqtt_ch == "dev" and sum(rain_mm_1h) > 20:
            print(datetime.fromtimestamp(int(time.time())), " > 10mm in 1h, raw:", data['rain_mm'], " ,rain_mm_1h|24h/Count_rain_1h|24h/mn: ",\
                  sum(rain_mm_1h), count_rain_1h, "|", sum(rain_mm_24h), count_rain_24h, rain_mn)

    return(round(sum(rain_mm_1h),2), round(sum(rain_mm_24h),2), round(rain_mn,2))

def wind_ermitteln(data):
    global count_5m, count_10m, time_count_5m, time_count_10m, wind_5m_max, wind_10m_avg,  erster_durchlauf_wind
    # Windgeschwindigkeit - Mittelwert der jeweils letzten 10 Minuten. Initialisieren der Timer bei Start
    if erster_durchlauf_wind:
        erster_durchlauf_wind = False
        time_count_10m = int(time.time())
        time_count_5m = int(time.time())
        wind_max_tag = data['wind_max_m_s']

    try:
        wind_10m_avg[count_10m] = data['wind_avg_m_s']
    except IndexError:
        wind_10m_avg.append(data['wind_avg_m_s'])

    count_10m += 1
    wind_10m = round(sum(wind_10m_avg)/len(wind_10m_avg),1)
    time_diff = int(time.time()) - time_count_10m
    if time_diff > (60 * 10):
        #if mqtt_ch == "dev":
        #    print(datetime.fromtimestamp(int(time.time())), " Zeit 10m Diff/Count/Wind avg: ", time_diff, count_10m, wind_10m)
        count_10m = 0
        time_count_10m = int(time.time())

    # Windgeschwindigkeit - Spitze (= Maximalwert aus Tabelle) der jeweils letzten 5 Minuten
    try:
        wind_5m_max[count_5m] = data['wind_max_m_s']
    except IndexError:
        wind_5m_max.append(data['wind_max_m_s'])
    count_5m += 1

    # Workaround da nicht immer die selbe Anzahl an Elementen in der Tabelle vorhanden sein müssen
    if count_5m > 18:
        count_5m = 0
    if count_10m > 36:
        count_10m = 0

    wind_5m = round(max(wind_5m_max),1)
    time_diff = int(time.time()) - time_count_5m
    if time_diff > (60 * 5):
        #if mqtt_ch == "dev":
        #    print(datetime.fromtimestamp(int(time.time())), " Zeit 5m  TimeDiff/Count/Wind/max.Tab: ", time_diff, count_5m, wind_5m, wind_5m_max)
        count_5m = 0
        time_count_5m = int(time.time())

    return(wind_10m, wind_5m)

def meldung(data):
    global counter, aprs_timer, gestern, rain_mn, rain_start
    global temp_max_tag, temp_min_tag, wind_max_tag
    global v_temp, v_hum, v_wind_max, v_wind_avg, v_wind_dir, v_rain_1h, v_rain_24h, v_rain_mn
    global v_baro_Hpa

    # Zeitformat für APRS-Bake
    heute = datetime.now().strftime("%d")
    aprs_zeit = heute + str(datetime.now(tz=pytz.UTC).strftime("%H%M"))

    # BRESSER 6in1 sendet 2 unterscheidliche Pakete aus, zB. ein komplettes Wind-JSON
    if 'wind_avg_m_s' in data:
        data_tx['Wind_avg'], \
        data_tx['Wind_gust'] = wind_ermitteln(data)

        a_wind_avg = float(data_tx['Wind_avg']) * 2.23694
        v_wind_avg = int(round(a_wind_avg,0))

        a_wind_max = float(data_tx['Wind_gust']) * 2.23694
        v_wind_max = int(round(a_wind_max,0))

        if a_wind_avg > 0:
            v_wind_dir = data['wind_dir_deg']
            data_tx['Windrichtung'] = data['wind_dir_deg']
        else:
            v_wind_dir = 0

        if data['wind_max_m_s'] > wind_max_tag:
            wind_max_tag = data['wind_max_m_s']
    else:
        v_wind_dir, v_wind_avg , v_wind_max = 0, 0, 0

    if 'temperature_C' in data:
        a_temp = float(data['temperature_C'] * 9/5 + 32)
        v_temp = int(round(a_temp,0))
        data_tx['Temperatur'] = data['temperature_C']

        # Datei mit Temperatur für svxlink erzeugen
        svx_string = "set temp " + str(data['temperature_C'])
        datei_schreiben(datei_svx, svx_string)

        # Tgl. minimal- und maximal Werte speichern
        if data['temperature_C'] > temp_max_tag:
            temp_max_tag = data['temperature_C']
        if data['temperature_C'] < temp_min_tag:
            temp_min_tag = data['temperature_C']

    if 'rain_mm' in data:
        # Routine bis zum Bugfixing  r262465 p262465 P262465
        if data['rain_mm'] < 10000:
            data_tx['Regen_1h'],  \
            data_tx['Regen_24h'], \
            data_tx['Regen_mn'], = regen_ermitteln(data)

            a_rain_1h = float(data_tx['Regen_1h'] / 25.4 * 100)
            v_rain_1h = int(round(a_rain_1h,0))

            a_rain_24h = float(data_tx['Regen_24h'] / 25.4 * 100)
            v_rain_24h = int(round(a_rain_24h,0))

            a_rain_mn = float(data_tx['Regen_mn'] / 25.4 * 100)
            v_rain_mn = int(round(a_rain_mn,0))

    if 'humidity' in data:
        a_hum = float(data['humidity'])
        if a_hum == 100:
            v_hum = 0
        else:
             v_hum = int(round(a_hum,0))
        data_tx['Luftfeuchtigkeit'] = data['humidity']

    aprs_login = "user " + mqtt_set.aprs_call + " pass " + mqtt_set.aprs_pass +\
    "\n" + mqtt_set.aprs_call + "-12>APRS,TCPIP*:" + \
    "@" + aprs_zeit + "h" + mqtt_set.aprs_qth + "_"

    msg = str(v_wind_dir).zfill(3) + "/" + \
    str(v_wind_avg).zfill(3) + \
    "g" + str(v_wind_max).zfill(3) + \
    "t" + str(v_temp).zfill(3) + \
    "r" + str(v_rain_1h).zfill(3) + \
    "p" + str(v_rain_24h).zfill(3) + \
    "P" + str(v_rain_mn).zfill(3) + \
    "h" + str(v_hum).zfill(2) + \
    "b" + str(v_baro_Hpa).zfill(5) + \
    mqtt_set.aprs_remark

    # APRS Ausgabe nur alle x timing Min.
    aprs_diff = int(time.time()) - aprs_timer
    if aprs_diff > timing:
        aprs_timer = int(time.time())
        datei_schreiben(datei_aprs, aprs_login + msg)
        cmd = "nc -v -w 5 rotate.aprs2.net 14580 <" + datei_aprs

        #if mqtt_ch != "dev":			DEAKTIVIERT, daher nur Ausgabe via mqtt-aprs -> aprx, Ausgabe auf DB0TGO-14
        #    os.system(cmd)
        # print("CMD:", cmd, " \r\b")

    else:

        # Erstellen Rest vom JSON - String
        data_tx['Temp_max_tag'] = temp_max_tag
        data_tx['Temp_min_tag'] = temp_min_tag
        data_tx['Wind_max_tag'] = wind_max_tag
        data_tx['Luftdruck'] = v_baro_Hpa / 10
        data_tx['Stand'] = datetime.now().replace(microsecond=0).isoformat()
        data_tx['Station'] = "DB0TGO-14"
        data_tx['Version'] = Version
        schreiben_JSON(data_tx)
        datei_schreiben(datei_log, msg)
        if mqtt_ch != "dev":
            client.publish(mqtt_set.mqtt_topic + "aprs", msg)
        else:
            if 'temperature_C' in data:
                print(datetime.fromtimestamp(int(time.time())), " akt./max./min. Temperatur:",
                      data['temperature_C'], "/", temp_max_tag, "/", temp_min_tag,
                      "max. Windböen:", wind_max_tag,
                      "Rain 1h/24H/mn:", data_tx['Regen_1h'],
                      data_tx['Regen_24h'],
                      data_tx['Regen_mn'],
                      "HPa:", v_baro_Hpa, "     \r\b")

    # Tageswechsel
    if not gestern == heute:
        # Tagesstatistik schreiben im CSV Format
        tag_inhalt = str(datetime.fromtimestamp(int(time.time()))) + \
                     " max./min. Temperatur/Windböen/Regen seit 0h; " + \
                     str(temp_max_tag) + ";" + str(temp_min_tag) + \
                     ";" + str(wind_max_tag) + \
                     ";" + str(round(rain_mn,1)) + "\n"
        if mqtt_ch != "dev":
            with open(datei_tag, 'a') as output:
                output.write(tag_inhalt)
                output.close()
        else:
            print(tag_inhalt)

        # Rücksetzen div. Zähler
        gestern = heute
        rain_mn = 0
        temp_max_tag, temp_min_tag, wind_max_tag = -99, 99, 0

def on_message(client, userdata, message):
    global v_baro_Hpa
    msg = str(message.payload.decode("utf-8"))
    topic = str(message.topic)

    try:
        data = json.loads(msg)
    except ValueError as e:
        print(time.time.strftime("%H:%M:%S"),
              " Fehler bei JSON Dekodierung:", e, "\n", msg)
        return
    if topic == "7ata/wx/bme280":
        v_baro_Hpa = data['baro_Hpa']
    else:
        meldung(data)

# START
if mqtt_ch == "dev":
    pfad_tmp = pfad_tmp + "/devel"
datei_json = pfad_tmp + "/Wetter.json"

print(datetime.now().strftime("%H:%M:%S"),
      "UTC. MQTT-Broker/Topic:", farbe_gelb, mqtt_set.mqtt_broker, mqtt_set.mqtt_topic,
      farbe_aus, "mit rx-ch", farbe_gelb, mqtt_set.mqtt_rx, farbe_aus, "und tx-ch",
      farbe_gelb, mqtt_ch, farbe_aus,
      "\nCall/APRS-pass/QTH:", farbe_gelb,
      mqtt_set.aprs_call,
      mqtt_set.aprs_pass,
      mqtt_set.aprs_qth, farbe_aus,
      "\nPfad /tmp:", farbe_gelb, pfad_tmp, farbe_aus,
      "Version:", farbe_gelb, Version, farbe_aus, "\n")

data_tx = einlesen_JSON(datei_json)
gestern = datetime.now().strftime("%d")
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(mqtt_set.mqtt_broker, 1883)
client.loop_forever()
