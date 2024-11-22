import sys

sys.path.append("")

from micropython import const
import uasyncio as asyncio
import aioble
import bluetooth
from machine import Pin, ADC, reset
import math
import RGB1602
import struct

# Enables logging to log.txt in root directory of Pico W
# For testing/debugging purposes only, will eventually fill the board's 2 MB flash memory
ENABLE_LOGGING = const(False)

# GPIO Pins used for sensors
# LCD: SDA is on GPIO4, and SCL is on GPIO5
MQ_4 = ADC(Pin(28))
MQ_7 = ADC(Pin(27))
MQ_135 = ADC(Pin(26))
LCD = RGB1602.RGB1602(16, 2)

# Voltage Divider (used to convert sensor output from 5V to 3.3V)
# 1000 / (470 + 1000)
V_DIV = const(0.680272108843537)

# Parameters derived from calibration data
# -----------------------------------------
# Clean Air Ro values
MQ_4_RO = 94.94876
MQ_7_RO = 89.80074
MQ_135_RO = 73.23104
# -----------------------------------------
# Slope/intercept points for log(y) = m*log(x) + b
# where y = Rs / Ro, x = ppm
MQ_4_M = -0.248653271
MQ_4_B = 0.210873798
MQ_7_M = -0.035950986
MQ_7_B = -0.602351089
MQ_135_M = -0.21840921
MQ_135_B = -0.188441654

# BLE Constants
# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# Carbon Monoxide
_ENV_SENSE_CO_UUID = bluetooth.UUID("ef090000-2ec0-4cd4-8f5a-51de99e65ecb")
# Methane
_ENV_SENSE_CH4_UUID = bluetooth.UUID("ef090001-2ec0-4cd4-8f5a-51de99e65ecb")
# Carbon Dioxide
_ENV_SENSE_CO2_UUID = bluetooth.UUID("ef090002-2ec0-4cd4-8f5a-51de99e65ecb")
# Battery
_ENV_SENSE_BATT_UUID = bluetooth.UUID("ef090003-2ec0-4cd4-8f5a-51de99e65ecb")
# Data Receiving
_ENV_SENSE_RECV_UUID = bluetooth.UUID("ef090004-2ec0-4cd4-8f5a-51de99e65ecb")
# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_SENSOR = const(0x0540)
# How frequently to send advertising beacons in microseconds
_ADV_INTERVAL_US = const(250_000)
# Pico W MAC Address
# D8:3A:DD:73:5A:75
# Global Battery Percent Variable
batt_avg = 0

# Register GATT server.
env_service = aioble.Service(_ENV_SENSE_UUID)
co_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_CO_UUID, read=True, notify=True
)
ch4_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_CH4_UUID, read=True, notify=True
)
co2_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_CO2_UUID, read=True, notify=True
)
batt_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_BATT_UUID, read=True, notify=True
)
recv_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_RECV_UUID, write=True, read=True, notify=True, capture=True
)
aioble.register_services(env_service)

if ENABLE_LOGGING:
    log_file = open('log.txt', 'a')

def _logger(*args, **kwargs):
    data = ' '.join(str(arg) for arg in args)

    print(data)

    if ENABLE_LOGGING:
        log_file.write(data + '\n')
        log_file.flush()

# Write to LCD and set backlight
def write_to_LCD(line1: str, line2: str, backlight: str = "normal"):
    # Truncate strings to 16 characters - LCD is 16x2
    line1 = line1[:16]
    line2 = line2[:16]

    # Clear LCD
    LCD.clear()
    
    # Write both lines to LCD
    LCD.setCursor(0, 0)
    LCD.printout(line1)
    LCD.setCursor(0, 1)
    LCD.printout(line2)

    # Set backlight
    if (backlight == "normal"):
        LCD.setRGB(255, 255, 255)
    elif (backlight == "warning"):
        LCD.setRGB(255, 255, 0)
    elif (backlight == "alert"):
        LCD.setRGB(255, 0, 0)
    else:
        LCD.setRGB(255, 255, 255)

def read_gas_sensor(adc : ADC):
    # Read the analog value (0 - 65535)
    raw_adc = adc.read_u16()

    # Calculate voltage seen by ADC
    adc_voltage = raw_adc * 3.3 / 65535.0
    # Reverse voltage divider to find sensor voltage
    Vs = adc_voltage / V_DIV

    # Sensor resistance
    # R_L (sensor resistance) is omitted since it will cancel in the Rs/Ro ratio
    Rs = (5.0 - Vs) / Vs

    return Rs

def gas_ppm(Rs, Ro, MQ_m, MQ_b):
    # Rs/Ro ratio
    ratio = Rs / Ro

    # ppm calculation
    # Derived from log(y) = m*log(x) + b
    # where y = Rs / Ro, x = ppm
    ppm = math.pow(10, (math.log10(ratio) - MQ_b) / MQ_m)

    if (ppm < 0):
        return 0

    return round(ppm)

def warning_levels(ppm_CO, ppm_CH4, ppm_CO2):
    # Initialize Levels
    level_CO = "normal"
    level_CH4 = "normal"
    level_CO2 = "normal"

    # Check levels

    # CO Warning - OSHA PEL (permissible exposure limit)
    if (ppm_CO >= 50):
        level_CO = "warning"
    # CO Alert - NIOSH C (ceiling level)
    if (ppm_CO >= 200):
        level_CO = "alert"
    # CH4 Warning - Committee on Toxicology recommended long-term exposure limit
    if (ppm_CH4 >= 5000):
        level_CH4 = "warning"
    # CH4 Alert - concentration at which methane becomes flammable
    if (ppm_CH4 >= 50_000):
        level_CH4 = "alert"
    # CO2 Warning - OSHA PEL
    if (ppm_CO2 >= 5000):
        level_CO2 = "warning"
    # CO2 Alert - NIOSH ST (short term limit)
    if (ppm_CO2 >= 30_000):
        level_CO2 = "alert"

    return level_CO, level_CH4, level_CO2

# Measures battery voltage, returns charge percent
def measure_batt():
    Pin(25, Pin.OUT, value=1)
    Pin(29, Pin.IN, pull=None)
    batt_voltage = ADC(3).read_u16() * 9.9 / 65535.0
    Pin(25, Pin.OUT, value=0, pull=Pin.PULL_DOWN)
    Pin(29, Pin.ALT, pull=Pin.PULL_DOWN, alt=7)
    # 4.2V = 100%, 3.0V = 0%
    batt_percent = 83.333 * batt_voltage - 250
    return round(batt_percent)

def mean(values):
    return sum(values) / len(values) if values else 0

async def batt_rolling_avg():
    global batt_avg
    batt_values = []

    while True:
        batt = measure_batt()

        if len(batt_values) >= 40:
            batt_values.pop(0)

        batt_values.append(batt)

        batt_avg = round(mean(batt_values))
        if (batt_avg < 0):
            batt_avg = 0
        if (batt_avg > 100):
            batt_avg = 100

        await asyncio.sleep_ms(50)

async def lcd_task():
    while True:
        co_ppm = gas_ppm(read_gas_sensor(MQ_7), MQ_7_RO, MQ_7_M, MQ_7_B)
        ch4_ppm = gas_ppm(read_gas_sensor(MQ_4), MQ_4_RO, MQ_4_M, MQ_4_B)
        co2_ppm = gas_ppm(read_gas_sensor(MQ_135), MQ_135_RO, MQ_135_M, MQ_135_B) + 424
        batt = batt_avg

        level_CO, level_CH4, level_CO2 = warning_levels(co_ppm, ch4_ppm, co2_ppm)
        line1 = f"CO:{co_ppm} CH4:{ch4_ppm}"[:16]
        line2 = f"CO2:{co2_ppm} BAT:{batt}%"[:16]
        backlight = "normal"

        if any(level == "alert" for level in [level_CO, level_CH4, level_CO2]):
            backlight = "alert"
        if any(level == "warning" for level in [level_CO, level_CH4, level_CO2]):
            backlight = "warning"

        # Testing
        #line1 = f"CO:{level_CO[:1]},CO2:{level_CO2[:1]},{backlight[:1]}"[:16]
        #line2 = f"CH4:{level_CH4[:1]},BAT:{batt}%"[:16]

        write_to_LCD(line1, line2, backlight)
        await asyncio.sleep_ms(500)

async def transmit_data(connection):
    while True:
        co_ppm = gas_ppm(read_gas_sensor(MQ_7), MQ_7_RO, MQ_7_M, MQ_7_B)
        co_characteristic.write(struct.pack("<H", co_ppm))
        co_characteristic.notify(connection)
        await asyncio.sleep_ms(50)
        ch4_ppm = gas_ppm(read_gas_sensor(MQ_4), MQ_4_RO, MQ_4_M, MQ_4_B)
        ch4_characteristic.write(struct.pack("<H", ch4_ppm))
        ch4_characteristic.notify(connection)
        await asyncio.sleep_ms(50)
        co2_ppm = gas_ppm(read_gas_sensor(MQ_135), MQ_135_RO, MQ_135_M, MQ_135_B) + 424
        co2_characteristic.write(struct.pack("<H", co2_ppm))
        co2_characteristic.notify(connection)
        await asyncio.sleep_ms(50)
        batt = batt_avg
        batt_characteristic.write(struct.pack("<H", batt))
        batt_characteristic.notify(connection)
        await asyncio.sleep_ms(500)


async def receive_data(connection):
    while True:
        connection, data = await recv_characteristic.written()
        await asyncio.sleep_ms(50)
        recv_characteristic.notify(connection, b"Received!")
        await asyncio.sleep_ms(50)
        _logger("Data received:")
        _logger(data.decode())

# Serially wait for connections. Don't advertise while a central is
# connected.
async def peripheral_task():
    while True:
        async with await aioble.advertise(
            interval_us=_ADV_INTERVAL_US,
            name="Gas Sensor",
            services=[_ENV_SENSE_UUID],
            appearance=_ADV_APPEARANCE_GENERIC_SENSOR,
        ) as connection:
            _logger("Connection from:", connection.device)

            # Start data transmission and reception tasks
            asyncio.create_task(transmit_data(connection))
            asyncio.create_task(receive_data(connection))

            await connection.disconnected(timeout_ms=None)
            _logger("Device disconeccted:", connection.device)
            await asyncio.sleep_ms(100)

# Run tasks.
async def main():
    try:
        tasks = [
            asyncio.create_task(batt_rolling_avg()),
            asyncio.create_task(peripheral_task()),
            asyncio.create_task(lcd_task())
        ]
        await asyncio.gather(*tasks)

    except Exception as e:
        _logger('An error occurred: ' + str(e))
        _logger('Ending session and restarting...\n\n')
        if ENABLE_LOGGING:
            log_file.close()
        reset()

asyncio.run(main())
