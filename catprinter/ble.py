import asyncio
import contextlib
import uuid
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.scanner import AdvertisementData
from bleak.backends.device import BLEDevice
from catprinter import logger

# For some reason, bleak reports the 0xaf30 service on my macOS, while it reports
# 0xae30 (which I believe is correct) on my Raspberry Pi. This hacky workaround
# should cover both cases.

POSSIBLE_SERVICE_UUIDS = [
    '0000ae30-0000-1000-8000-00805f9b34fb',
    '0000af30-0000-1000-8000-00805f9b34fb',
]

TX_CHARACTERISTIC_UUID = '0000ae01-0000-1000-8000-00805f9b34fb'

SCAN_TIMEOUT_S = 10

# Wait time after sending each chunk of data through BLE.
WAIT_AFTER_EACH_CHUNK_S = 0.03

# This is a hacky solution so we don't terminate the BLE connection to the printer
# while it's still printing. A better solution is to subscribe to the RX characteristic
# and listen for printer events, so we know exactly when the printing is finished.
WAIT_AFTER_DATA_SENT_S = 30


async def scan(name: Optional[str], timeout: int):
    autodiscover = (not name)
    if autodiscover:
        logger.info('⏳ Trying to auto-discover a printer...')
    else:
        logger.info(f'⏳ Looking for a BLE device named {name}...')

    def filter_fn(device: BLEDevice, adv_data: AdvertisementData):
        if autodiscover:
            return any(uuid in adv_data.service_uuids
                       for uuid in POSSIBLE_SERVICE_UUIDS)
        else:
            return device.name == name

    device = await BleakScanner.find_device_by_filter(
        filter_fn, timeout=timeout,
    )
    if device is None:
        raise RuntimeError('Unable to find printer, make sure it is turned on and in range')
    logger.info(f'✅ Got it. Address: {device}')
    return device


def chunkify(data, chunk_size):
    return (
        data[i: i + chunk_size] for i in range(0, len(data), chunk_size)
    )


async def get_device_address(device: Optional[str]):
    # See if we were passed a string that smells like an UUID or MAC address.
    if device:
        with contextlib.suppress(ValueError):
            return str(uuid.UUID(device))
        if device.count(':') == 5 and device.replace(':', '').isalnum():
            return device

    return await scan(device, timeout=SCAN_TIMEOUT_S)


async def run_ble(
    data,
    device: Optional[str],
    chunk_size: Optional[int] = None,
    chunk_delay: Optional[float] = None,
    disconnect_delay: Optional[float] = None,
):
    try:
        address = await get_device_address(device)
    except RuntimeError as e:
        logger.error(f'🛑 {e}')
        return
    logger.info(f'⏳ Connecting to {address}...')
    async with BleakClient(address) as client:
        logger.info(
            f'✅ Connected: {client.is_connected}; MTU: {client.mtu_size}')
        
        # Calculate chunk size. On macOS, MTU size can negotiate to a very large value (e.g. 512),
        # which overflows the printer's RX buffer if sent in a single chunk. We cap the default
        # chunk size at 60 bytes (matching standard ~104 MTU on other platforms).
        if chunk_size is None:
            chunk_size = min(client.mtu_size - 3, 60)
        else:
            chunk_size = max(1, chunk_size)
            
        delay = chunk_delay if chunk_delay is not None else WAIT_AFTER_EACH_CHUNK_S
        disc_delay = disconnect_delay if disconnect_delay is not None else WAIT_AFTER_DATA_SENT_S

        logger.info(
            f'⏳ Sending {len(data)} bytes of data in chunks of {chunk_size} bytes with {delay}s delay...')
        for i, chunk in enumerate(chunkify(data, chunk_size)):
            await client.write_gatt_char(TX_CHARACTERISTIC_UUID, chunk)
            await asyncio.sleep(delay)
        logger.info(f'✅ Done. Waiting {disc_delay}s before disconnecting...')
        await asyncio.sleep(disc_delay)
