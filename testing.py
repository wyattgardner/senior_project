import time
import machine

LED = machine.Pin("LED", machine.Pin.OUT)

def _blinkLED(led, seconds):
    for i in range(int(seconds * 10)):
        led.value(1)
        time.sleep_ms(50)
        led.value(0)
        time.sleep_ms(50)

_blinkLED(LED, 5)