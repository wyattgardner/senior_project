import sys

sys.path.append("")

from micropython import const

import uasyncio as asyncio
import aioble
import bluetooth

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
    env_service, _ENV_SENSE_CO_UUID, read=True, notify=True
)
ch4_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_CH4_UUID, read=True, notify=True
)
recv_characteristic = aioble.Characteristic(
    env_service, _ENV_SENSE_RECV_UUID, write=True, read=True, notify=True, capture=True
)
aioble.register_services(env_service)

async def transmit_data():
    while True:
        co_characteristic.write("test1")
        ch4_characteristic.write("test2")
        await asyncio.sleep_ms(250)

async def receive_data():
    while True:
        connection, data = await recv_characteristic.written()
        recv_characteristic.notify(connection, "Received!")
        print("Data received:")
        print(data.decode())

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
            print("Connection from", connection.device)
            await connection.disconnected()


# Run both tasks.
async def main():
    asyncio.create_task(transmit_data())
    asyncio.create_task(peripheral_task())
    asyncio.create_task(receive_data())
    while True:
        await asyncio.sleep(1)


asyncio.run(main())
