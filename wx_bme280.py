#!/usr/bin/python3
# Quelle: https://www.rustimation.eu/index.php/luftdruck-messen-aber-richtig/
# 28.03.2023	DL7ATA

import bme280 as bme280
import paho.mqtt.client as mqtt
import time
from datetime import datetime
import json

home_alt=40                         # Höhe des Standorts
TOPIC = "7ata/wx/bme280"
BROKER_ADDRESS = "pi4.fritz.box"
PORT = 1883
QOS = 1
log_datei = "/tmp/Wetter/bme280.json"
#-------------------------------------------------------

def bm280_lesen():
    data = {"baro_Hpa": 0, "temp_C": 0, "humi_P": 0, "Stand": ""}
    temperature,pressure,humidity = bme280.readBME280All()
    temperature_gradient = 0.0065        # Standard-Temperaturgradient
    temperatureK = temperature + 273.15  # Temperatur in Kelvin

    # barometrische Höhenformel
    compRelPress = round(pressure * (temperatureK / (temperatureK + home_alt * temperature_gradient)) ** -5.255 * 10, 0)
    data["baro_Hpa"] = int(compRelPress)
    data["baro_raw"] = int(pressure)
    data["temp_C"] = round(temperature,1)
    data["humi_P"] = round(humidity,1)
    data["Stand"] = datetime.now().replace(microsecond=0).isoformat()

    #print("complex reduced Pressure", compRelPress)
    #print("Temperature : ", round(temperature,1), "°C")
    #print("Pressure : ", round(pressure,1), "hPa")
    #print("Humidity : ", round(humidity,1), "%")

    data = json.dumps(data)
    publ_data = json.dumps(data)
    client.publish(TOPIC, data)

    with open(log_datei, 'w') as output:        # 'a' append
        output.write(data)
        output.close()

    return

if __name__ == "__main__":
    client = mqtt.Client("barometric_pressure")
    client.connect(BROKER_ADDRESS, PORT)
    print("Connected to MQTT Broker: " + BROKER_ADDRESS)
    client.loop()

    while True:
        bm280_lesen()
        time.sleep(60)
