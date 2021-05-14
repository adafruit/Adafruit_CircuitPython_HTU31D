# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2021 ladyada for Adafruit
#
# SPDX-License-Identifier: MIT
"""
`adafruit_htu31d`
================================================================================

Python library for TE HTU31D temperature and humidity sensors


* Author(s): ladyada, Jose D. Montoya.

Implementation Notes
--------------------

**Hardware:**

* `Adafruit HTU31 Temperature & Humidity Sensor Breakout Board
  <https://www.adafruit.com/product/4832>`_ (Product ID: 4832)


**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library:
  https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

"""

import time
import struct
import adafruit_bus_device.i2c_device as i2c_device
from micropython import const

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_HTU31D.git"

_HTU31D_DEFAULT_ADDR = const(0x40)  # HTU31D default I2C Address

_HTU31D_READSERIAL = const(0x0A)  # Read Out of Serial Register
_HTU31D_SOFTRESET = const(0x1E)  # Soft Reset
_HTU31D_HEATERON = const(0x04)  # Enable heater
_HTU31D_HEATEROFF = const(0x02)  # Disable heater
_HTU31D_CONVERSION = const(0x40)  # Start a conversion
_HTU31D_READTEMPHUM = const(0x00)  # Read the conversion values

_HTU31D_HUMIDITY_RES = ("0.020%", "0.014%", "0.010%", "0.007%")
_HTU31D_TEMP_RES = ("0.040", "0.025", "0.016", "0.012")


class HTU31D:
    """
    A driver for the HTU31D temperature and humidity sensor.

    :param ~busio.I2C i2c_bus: The `busio.I2C` object to use. This is the only required parameter.

    **Quickstart: Importing and using the device**

        Here is an example of using the :class:`HTU31D` class.
        First you will need to import the libraries to use the sensor

        .. code-block:: python

            import board
            import adafruit_htu31d

        Once this is done you can define your `board.I2C` object and define your sensor object

        .. code-block:: python

            i2c = board.I2C()  # uses board.SCL and board.SDA
            htu = adafruit_htu31d.HTU31D(i2c)


        Now you have access to the :attr:`temperature` and :attr:`relative_humidity`
        attributes

        .. code-block:: python

            temperature = htu.temperature
            relative_humidity = htu.relative_humidity


    """

    def __init__(self, i2c_bus):
        self.i2c_device = i2c_device.I2CDevice(i2c_bus, _HTU31D_DEFAULT_ADDR)
        self._conversion_command = _HTU31D_CONVERSION
        self._buffer = bytearray(6)
        self.reset()

    @property
    def serial_number(self):
        """The unique 32-bit serial number"""
        self._buffer[0] = _HTU31D_READSERIAL
        with self.i2c_device as i2c:
            i2c.write_then_readinto(self._buffer, self._buffer, out_end=1, in_end=4)
        ser = struct.unpack(">I", self._buffer[0:4])
        return ser

    def reset(self):
        """Perform a soft reset of the sensor, resetting all settings to their power-on defaults"""
        self._conversion_command = _HTU31D_CONVERSION
        self._buffer[0] = _HTU31D_SOFTRESET
        with self.i2c_device as i2c:
            i2c.write(self._buffer, end=1)
        time.sleep(0.015)

    @property
    def heater(self):
        """The current sensor heater mode"""
        return self._heater

    @heater.setter
    def heater(self, new_mode):
        # check its a boolean
        if not new_mode in (True, False):
            raise AttributeError("Heater mode must be boolean")
        # cache the mode
        self._heater = new_mode
        # decide the command!
        if new_mode:
            self._buffer[0] = _HTU31D_HEATERON
        else:
            self._buffer[0] = _HTU31D_HEATEROFF
        with self.i2c_device as i2c:
            i2c.write(self._buffer, end=1)

    @property
    def relative_humidity(self):
        """The current relative humidity in % rH"""
        return self.measurements[1]

    @property
    def temperature(self):
        """The current temperature in degrees Celsius"""
        return self.measurements[0]

    @property
    def measurements(self):
        """both `temperature` and `relative_humidity`, read simultaneously"""

        temperature = None
        humidity = None

        self._buffer[0] = self._conversion_command
        with self.i2c_device as i2c:
            i2c.write(self._buffer, end=1)

        # wait conversion time
        time.sleep(0.02)

        self._buffer[0] = _HTU31D_READTEMPHUM
        with self.i2c_device as i2c:
            i2c.write_then_readinto(self._buffer, self._buffer, out_end=1)

        # separate the read data
        temperature, temp_crc, humidity, humidity_crc = struct.unpack_from(
            ">HBHB", self._buffer
        )

        # check CRC of bytes
        if temp_crc != self._crc(temperature) or humidity_crc != self._crc(humidity):
            raise RuntimeError("Invalid CRC calculated")

        # decode data into human values:
        # convert bytes into 16-bit signed integer
        # convert the LSB value to a human value according to the datasheet
        temperature = -40.0 + 165.0 * temperature / 65535.0

        # repeat above steps for humidity data
        humidity = 100 * humidity / 65535.0
        humidity = max(min(humidity, 100), 0)

        return (temperature, humidity)

    @property
    def humidity_resolution(self):
        """The current relative humidity resolution in % rH.

        Possibles values:

            * "0.020%"
            * "0.014%"
            * "0.010%"
            * "0.007%"

        """

        return _HTU31D_HUMIDITY_RES[self._conversion_command >> 4 & 3]

    @humidity_resolution.setter
    def humidity_resolution(self, value):
        if value not in _HTU31D_HUMIDITY_RES:
            raise ValueError(
                "Humidity resolution must be one of: {}".format(_HTU31D_HUMIDITY_RES)
            )
        register = self._conversion_command & 0xCF
        hum_res = _HTU31D_HUMIDITY_RES.index(value)
        self._conversion_command = register | hum_res << 4

    @property
    def temp_resolution(self):
        """The current temperature resolution in Celsius.

        Possibles values:

            * "0.040"
            * "0.025"
            * "0.016"
            * "0.012"

        """

        return _HTU31D_TEMP_RES[self._conversion_command >> 2 & 3]

    @temp_resolution.setter
    def temp_resolution(self, value):
        if value not in _HTU31D_TEMP_RES:
            raise ValueError(
                "Temperature resolution must be one of: {}".format(_HTU31D_TEMP_RES)
            )
        register = self._conversion_command & 0xF3
        temp_res = _HTU31D_TEMP_RES.index(value)
        self._conversion_command = register | temp_res << 2

    @staticmethod
    def _crc(value):
        polynom = 0x988000  # x^8 + x^5 + x^4 + 1
        msb = 0x800000
        mask = 0xFF8000
        result = value << 8  # Pad with zeros as specified in spec

        while msb != 0x80:
            # Check if msb of current value is 1 and apply XOR mask
            if result & msb:
                result = ((result ^ polynom) & mask) | (result & ~mask)
            # Shift by one
            msb >>= 1
            mask >>= 1
            polynom >>= 1

        return result
