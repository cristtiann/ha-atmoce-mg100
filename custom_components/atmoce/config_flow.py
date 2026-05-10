from __future__ import annotations

import voluptuous as vol
from pymodbus.client import AsyncModbusTcpClient

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_SCAN_INTERVAL, CONF_SLAVE, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_SLAVE, DOMAIN

async def _validate_connection(host: str, port: int, slave: int) -> None:
    client = AsyncModbusTcpClient(host, port=port)
    try:
        connected = await client.connect()
        if not connected:
            raise CannotConnect
        result = await client.read_holding_registers(address=60010, count=1, device_id=slave)
        if result.isError():
            raise CannotConnect
    finally:
        client.close()

class AtmoceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Atmoce config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            slave = user_input[CONF_SLAVE]

            await self.async_set_unique_id(f"{host}:{port}:{slave}")
            self._abort_if_unique_id_configured()

            try:
                await _validate_connection(host, port, slave)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Atmoce MG100 ({host})",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_SLAVE, default=DEFAULT_SLAVE): int,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
