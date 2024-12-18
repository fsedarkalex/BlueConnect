# Blue Connect Go

Home Assistant BLE Integration for the Blueriiot Blue Connect Go Pool Monitor

This integration is heavily based (basiscally started as a copy/paste) on the [Yinmik BLE-YC01 Integration](https://github.com/jdeath/BLE-YC01) by @jdeath.

For discussion, details on the BLE decoding and other integration alternatives, please refer to the
[Blue Connect pool measurements topic](https://community.home-assistant.io/t/blue-connect-pool-measurements/118901)
in the Home Assistant Community forum.

All the BLE decoding details that made this integration possible are full credit of many generous community members
on that thread including @vampcp, @JosePortillo, @rzulian and others.

# Installation

Install this repo in HACS, then add the Blue Connect Go integration. Restart Home Assistant. The device should be found automatically in a few minutes,
or you can add it manually via Settings > Devices and Services > + Add Integration
