import time
import machine
from machine import Pin, ADC
import uasyncio as asyncio
import RGB1602
import math
import network

# Clean Air Ro values
# MQ-4: 94.94876
# MQ-7: 89.80074
# MQ-135: 73.23104

LED = machine.Pin("LED", machine.Pin.OUT)
# GPIO Pins used for sensors
# LCD: SDA is on GPIO4, and SCL is on GPIO5
# LCD I2C addresses: 0x3e, 0x60
MQ_4 = machine.ADC(machine.Pin(28))
MQ_7 = machine.ADC(machine.Pin(27))
MQ_135 = machine.ADC(machine.Pin(26))
#LCD = RGB1602.RGB1602(16, 2)
MQ_4_D = machine.Pin(machine.Pin(15), machine.Pin.IN)

# Voltage Divider (used to convert sensor output from 5V to 3.3V)
# 1000 / (470 + 1000)
V_DIV = const(0.680272108843537)

def _blinkLED(led, seconds):
    for i in range(int(seconds * 10)):
        led.value(1)
        time.sleep_ms(50)
        led.value(0)
        time.sleep_ms(50)

def mean(values):
    return sum(values) / len(values) if values else 0

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

def read_gas_sensor(adc : machine.ADC):
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

    return ppm

# prints average of the last n values of the gas sensors
def print_average(n : int):
    # Initialize lists to store the last 5 values for a, b, c
    a_values = []
    b_values = []
    c_values = []

    while True:
        a = read_gas_sensor(MQ_4)
        b = read_gas_sensor(MQ_7)
        c = read_gas_sensor(MQ_135)
        time.sleep_ms(200)

        # Update the value lists (keeping only the last n values)
        if len(a_values) >= n:
            a_values.pop(0)
        if len(b_values) >= n:
            b_values.pop(0)
        if len(c_values) >= n:
            c_values.pop(0)

        a_values.append(a)
        b_values.append(b)
        c_values.append(c)

        if len(a_values) == n:
            a_avg = mean(a_values)
            b_avg = mean(b_values)
            c_avg = mean(c_values)

            # Print the averages
            print(f"MQ-4: {a_avg}")
            print(f"MQ-7: {b_avg}")
            print(f"MQ-135: {c_avg}")

# Measures battery voltage
def measure_vsys():
    Pin(25, Pin.OUT, value=1)
    Pin(29, Pin.IN, pull=None)
    reading = ADC(3).read_u16() * 9.9 / 2**16
    Pin(25, Pin.OUT, value=0, pull=Pin.PULL_DOWN)
    Pin(29, Pin.ALT, pull=Pin.PULL_DOWN, alt=7)
    return reading

def display_mac():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    mac = wlan.config("mac")

    mac_address = ":".join("%02x" % b for b in mac)

    print("MAC Address:", mac_address)

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

#print_average(8)
#write_to_LCD("test1", "test2")
#display_mac()
level_CO, level_CH4, level_CO2 = warning_levels(100, 50, 40000)
print(level_CO, level_CH4, level_CO2)

"""
while True:
    print(f"MQ-4: {read_gas_sensor(MQ_4)}")
    print(f"MQ-7: {read_gas_sensor(MQ_7)}")
    print(f"MQ-135: {read_gas_sensor(MQ_135)}")
    print(f"MQ-4 (D): {MQ_4_D.IN.to_bytes}")
    time.sleep_ms(200)
"""

"""
write_to_LCD("testing1", "normal", "normal")
time.sleep(2)
write_to_LCD("testing2", "warning", "warning")
time.sleep(2)
write_to_LCD("testing3", "alert", "alert")
"""
