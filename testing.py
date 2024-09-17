import time
import machine
import uasyncio as asyncio

# MQ-9 Ro analog value: 3904, 0.196585 V
# MQ-135 Ro analog value: 1056, 0.05317464 V
LED = machine.Pin("LED", machine.Pin.OUT)
MQ_9 = machine.ADC(machine.Pin(28))
MQ_135 = machine.ADC(machine.Pin(27))

def _blinkLED(led, seconds):
    for i in range(int(seconds * 10)):
        led.value(1)
        time.sleep_ms(50)
        led.value(0)
        time.sleep_ms(50)

def read_gas_sensor(sensor):
    analog_value = sensor.read_u16()  # Read the analog value (0 - 65535)
    voltage = analog_value * 3.3 / 65535.0
    return analog_value, voltage

while True:
    print(f"MQ-9: {read_gas_sensor(MQ_9)}\nMQ-135: {read_gas_sensor(MQ_135)}")
    time.sleep_ms(200)