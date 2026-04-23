# SPDX-FileCopyrightText: Copyright (c) 2020 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: MIT

import time

import board

import adafruit_htu31d

i2c = board.I2C()  # uses board.SCL and board.SDA
# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
htu = adafruit_htu31d.HTU31D(i2c)
print("Found HTU31D with serial number", hex(htu.serial_number))

htu.heater = True
print("Heater is on?", htu.heater)
htu.heater = False
print("Heater is on?", htu.heater)

while True:
    temperature, relative_humidity = htu.measurements
    print(f"Temperature: {temperature:0.1f} C")
    print(f"Humidity: {relative_humidity:0.1f} %")
    print("")
    time.sleep(1)
