# Scripts

## Mullvad Random Relay Rotator
This script continuously manages your Mullvad VPN connection by performing the following actions in an infinite loop:

- Disconnects from the current VPN connection.
- Selects a random Mullvad server.
- Reconnects to the VPN.
- Waits for 10 minutes before repeating the process.

Each step is logged with a timestamp, with colored output displayed on the terminal and detailed logs saved to a file.

## Usage

```./mullvad_random_relay_rotator.sh```
