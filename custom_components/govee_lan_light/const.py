"""Constants for the Govee LAN Light integration."""

DOMAIN = "govee_lan_light"

# UDP Ports
PORT_SCAN = 4001
PORT_LISTEN = 4002
PORT_CONTROL = 4003

# Multicast address for discovery
MULTICAST_ADDRESS = "239.255.255.250"

# Timeouts (seconds)
TIMEOUT_DISCOVERY = 3.0
TIMEOUT_COMMAND = 2.0
TIMEOUT_STATUS = 2.0

# Polling interval (seconds)
POLL_INTERVAL = 30

# Retry settings
MAX_RETRIES = 3

# Color temperature range (Kelvin)
MIN_COLOR_TEMP_KELVIN = 2000
MAX_COLOR_TEMP_KELVIN = 9000

# Brightness range
MIN_BRIGHTNESS_GOVEE = 1
MAX_BRIGHTNESS_GOVEE = 100
