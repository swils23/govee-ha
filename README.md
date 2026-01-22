# Govee LAN Light Integration for Home Assistant

A Home Assistant custom integration for controlling Govee lights over LAN using the UDP protocol.

## Features

- **Manual IP Configuration**: Primary setup method that bypasses unreliable discovery
- **Auto Discovery**: Attempts to find Govee devices on your network (with sender-IP fallback for H60xx devices)
- **Full Light Control**:
  - On/Off
  - Brightness (0-100%)
  - RGB Color
  - Color Temperature (2000K-9000K)
- **State Polling**: Automatic state updates every 30 seconds

## Supported Devices

This integration supports Govee lights that implement the LAN UDP protocol, including:

- H607C Floor Lamp 2 (tested)
- Other H60xx series floor lamps
- Various Govee LED strips and bulbs with LAN control

**Note**: Newer H60xx floor lamps often omit the `ip` field in discovery responses. This integration handles this by falling back to the sender's IP address, or you can simply enter the IP manually.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Add"
6. Search for "Govee LAN Light" and install it
7. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/govee_lan_light` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Govee LAN Light"
4. The integration will attempt auto-discovery. If your device isn't found:
   - Enter the IP address manually
   - Give it a friendly name

### Finding Your Device's IP Address

If auto-discovery doesn't work (common with H60xx floor lamps):

1. Check your router's DHCP client list
2. Look for a device with MAC address starting with `5c:e7:53`
3. Use that IP address for manual configuration

## Device Requirements

- The Govee device must be connected to your local network
- LAN control must be enabled in the Govee Home app:
  1. Open Govee Home app
  2. Select your device
  3. Go to Settings (gear icon)
  4. Enable "LAN Control"
- The device and Home Assistant must be on the same network/subnet

## Ports Used

The integration uses the following UDP ports:

- **4001**: Discovery scan
- **4002**: Listen for responses
- **4003**: Control commands

Ensure these ports are not blocked by any firewall rules on your network.

## Troubleshooting

### Device not responding

1. Verify LAN Control is enabled in the Govee Home app
2. Ensure the device and Home Assistant are on the same network
3. Try restarting the Govee device
4. Check that UDP ports 4001-4003 are not blocked

### Discovery not finding devices

This is expected for some devices (especially H60xx floor lamps). Use manual IP entry instead.

### State not updating

- The integration polls every 30 seconds by default
- State updates immediately after sending commands
- If you control the light via the Govee app, HA will sync on the next poll cycle

## Technical Details

This integration communicates with Govee devices using their LAN UDP protocol:

- **Discovery**: Multicast to 239.255.255.250:4001
- **Commands**: Unicast to device:4003
- **Protocol**: JSON messages over UDP

### Command Examples

```json
// Turn on
{"msg":{"cmd":"turn","data":{"value":1}}}

// Set brightness to 50%
{"msg":{"cmd":"brightness","data":{"value":50}}}

// Set RGB color
{"msg":{"cmd":"colorwc","data":{"color":{"r":255,"g":128,"b":64},"colorTemInKelvin":0}}}

// Set color temperature
{"msg":{"cmd":"colorwc","data":{"color":{"r":0,"g":0,"b":0},"colorTemInKelvin":4000}}}

// Query status
{"msg":{"cmd":"devStatus","data":{}}}
```

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
