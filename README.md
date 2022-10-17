# polybar-appgate

This repository contains 2 scripts to integrate AppGate connection status in polybar:

* `appgate-client.py` - replaces the AppGate GUI: starts the AppGate service and handles interactions wih the polybar script
* `polybar-appgate.py` - the actual polybar script: outputs an icon depending on AppGate connection status

Status icons:

* connected: ![connected](images/icon-connected.png)
* disconnected: ![disconnected](images/icon-disconnected.png)
* connecting: ![disconnected](images/icon-connecting.png)
* error: ![error](images/icon-error.png)

Note: the client script is only able to handle SAML connection, there are no plans to implement more login methods.

## Setup

1. in AppGate GUI client's advanced settings, enable automatic login
1. clone this repository wherever you want
1. install the provided systemd service file by running `make install`, or run the `appgate-client.py` 
   script at startup (e.g. from your i3 config)
3. add the `polybar-appgate.py` script to your polybar config, as shown in the example below

```text
[module/appgate]
type = custom/script
exec = /path/to/polybar-appgate.py
interval = 5
```

## Configuration

The icons and colors used can be overridden by setting the environment variables described in the table below.

| Status       | Color                                            | Icon                        |
|--------------|--------------------------------------------------|-----------------------------|
| Connected    | `APPGATE_COLOR_CONNECTED` (default: `55AA55`)    | `APPGATE_ICON_CONNECTED`    |
| Disconnected | `APPGATE_COLOR_DISCONNECTED` (default: `FF7070`) | `APPGATE_ICON_DISCONNECTED` |
| Connecting   | `APPGATE_COLOR_CONNECTING` (default: `F5A70A`)   | `APPGATE_ICON_CONNECTING`   |
| Error        | `APPGATE_COLOR_ERROR` (default: `FF7070`)        | `APPGATE_ICON_ERROR`        |

## Known Issues

* TODO: implement icon click trigger to manually start login flow
