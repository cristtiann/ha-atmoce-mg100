from homeassistant.const import Platform

DOMAIN = "atmoce"

DEFAULT_NAME = "Atmoce"
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 3

CONF_SLAVE = "slave"
CONF_SCAN_INTERVAL = "scan_interval"

PLATFORMS: list[Platform] = [Platform.SENSOR]
