import sys

sys.path.append("")

from micropython import const
import uasyncio as asyncio
import aioble
import bluetooth
import machine
import RGB1602

# Enables logging to log.txt in root directory of Pico W
# For testing/debugging purposes only, will eventually fill the board's 2 MB flash memory
ENABLE_LOGGING = const(False)
# GPIO Pins used for sensors
# LCD: SDA is on GPIO4, and SCL is on GPIO5
MQ_9 = machine.Pin(2, machine.Pin.OUT)
MQ_135 = machine.Pin(3, machine.Pin.OUT)
#LCD = RGB1602.RGB1602(16, 2)

# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# Carbon Monoxide
_ENV_SENSE_CO_UUID = bluetooth.UUID("ef090000-2ec0-4cd4-8f5a-51de99e65ecb")
# Methane
_ENV_SENSE_CH4_UUID = bluetooth.UUID("ef090001-2ec0-4cd4-8f5a-51de99e65ecb")
# Data Receiving
_ENV_SENSE_RECV_UUID = bluetooth.UUID("ef090002-2ec0-4cd4-8f5a-51de99e65ecb")
# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_SENSOR = const(0x0540)
# How frequently to send advertising beacons in microseconds
_ADV_INTERVAL_US = const(250_000)

# Register GATT server.
env_service = aioble.Service(_ENV_SENSE_UUID)
co_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_CO_UUID, read=True, notify=True, initial="CO"
)
ch4_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_CH4_UUID, read=True, notify=True, initial="CH4"
)
recv_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_RECV_UUID, write=True, read=True, notify=True, capture=True, initial="RECEIVE"
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
def write_to_LCD(line1: str, line2: str, backlight: str):
    # Truncate strings to 16 characters - LCD is 16x2
    line1 = line1[:16]
    line2 = line2[:16]

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

async def transmit_data():
    while True:
        co_characteristic.write("test1")
        await asyncio.sleep_ms(50)
        ch4_characteristic.write("test2")
        await asyncio.sleep_ms(50)

async def receive_data():
    while True:
        connection, data = await recv_characteristic.written()
        await asyncio.sleep_ms(50)
        recv_characteristic.notify(connection, "Received!")
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
            await connection.disconnected()
            _logger("Device disconeccted:", connection.device)
            await asyncio.sleep_ms(100)

# Run tasks.
async def main():
    try:
        tasks = [
            asyncio.create_task(peripheral_task()),
            asyncio.create_task(transmit_data()),
            asyncio.create_task(receive_data()),
        ]
        await asyncio.gather(*tasks)

    except Exception as e:
        _logger('An error occurred: ' + str(e))
        _logger('Ending session and restarting...\n\n')
        if ENABLE_LOGGING:
            log_file.close()
        machine.reset()

asyncio.run(main())
