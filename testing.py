import time
import machine
import uasyncio as asyncio

# MQ-9 Ro analog value: 132059, 0.641 V
LED = machine.Pin("LED", machine.Pin.OUT)
SENSOR = machine.ADC(machine.Pin(28))

def _blinkLED(led, seconds):
    for i in range(int(seconds * 10)):
        led.value(1)
        time.sleep_ms(50)
        led.value(0)
        time.sleep_ms(50)

def read_gas_sensor():
    analog_value = SENSOR.read_u16()  # Read the analog value (0 - 65535)
    voltage = analog_value * 3.3 / 65535.0
    return analog_value, voltage

while True:
    print(read_gas_sensor())
    time.sleep_ms(200)