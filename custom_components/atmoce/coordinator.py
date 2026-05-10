from __future__ import annotations

import logging
import time
from datetime import timedelta

from pymodbus.client import AsyncModbusTcpClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .registers import SENSORS, AtmoceSensorDescription

_LOGGER = logging.getLogger(__name__)


def _count_for(data_type: str) -> int:
    return {
        "uint16": 1,
        "int16": 1,
        "uint32": 2,
        "int32": 2,
        "uint64": 4,
        "int64": 4,
    }[data_type]


def _decode_registers(registers: list[int], data_type: str) -> int:
    value = 0
    for reg in registers:
        value = (value << 16) | (reg & 0xFFFF)

    bits = 16 * len(registers)
    if data_type.startswith("int") and value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


class AtmoceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, float | int | None]]):
    """Coordinator that polls Atmoce MG100 registers via Modbus TCP.

    The coordinator wakes up every 3 seconds, but each sensor has its own
    scan_interval. Fast live power sensors are read every 3 seconds, while
    daily/total/static values are read less often.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave: int,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.host = host
        self.port = port
        self.slave = slave
        self._last_poll: dict[str, float] = {}

    async def _async_update_data(self) -> dict[str, float | int | None]:
        now = time.monotonic()
        data: dict[str, float | int | None] = dict(self.data or {})
        client = AsyncModbusTcpClient(self.host, port=self.port)

        try:
            connected = await client.connect()
            if not connected:
                raise UpdateFailed(f"Could not connect to Atmoce gateway at {self.host}:{self.port}")

            for desc in SENSORS:
                last_poll = self._last_poll.get(desc.key, 0.0)

                # On first refresh self.data is empty, so all sensors are read once.
                if self.data is not None and now - last_poll < desc.scan_interval:
                    continue

                try:
                    data[desc.key] = await self._read_sensor(client, desc)
                except Exception as err:  # noqa: BLE001 - keep other sensors updating
                    _LOGGER.warning(
                        "Error reading Atmoce sensor %s at address %s: %s",
                        desc.key,
                        desc.address,
                        err,
                    )
                    data.setdefault(desc.key, None)
                finally:
                    self._last_poll[desc.key] = now

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Atmoce gateway: {err}") from err
        finally:
            client.close()

        return data

    async def _read_sensor(
        self,
        client: AsyncModbusTcpClient,
        desc: AtmoceSensorDescription,
    ) -> float | int | None:
        count = _count_for(desc.data_type)
        result = await client.read_holding_registers(
            address=desc.address,
            count=count,
            device_id=self.slave,
        )
        if result.isError():
            _LOGGER.debug("Error reading %s at address %s: %s", desc.key, desc.address, result)
            return None

        raw = _decode_registers(result.registers, desc.data_type)
        value = raw * desc.scale

        if desc.precision is not None:
            value = round(value, desc.precision)

        return value
