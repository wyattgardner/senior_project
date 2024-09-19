import machine

sdaPin = machine.Pin(4)
sclPin = machine.Pin(5)
i2c = machine.I2C(0, sda=sdaPin, scl=sclPin, freq=400000)

devices = i2c.scan()

if len(devices) == 0:
    print('No i2c device found!')
else:
    print('i2c device found', len(devices))

for device in devices:
    print("At address: ", hex(device))