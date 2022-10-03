# polybar-appgate

This repository contains 2 scripts to integrate AppGate connection status in polybar:

* `appgate-client.py` - replaces the AppGate GUI: starts the AppGate service and handles interactions wih the polybar script
* `polybar-appgate.py` - the actual polybar script: outputs an icon depending on AppGate connection status

Status icons:

* connected: ![connected](images/icon-connected.png)
* connecting: ![disconnected](images/icon-connecting.png)
* error: ![error](images/icon-error.png)

Note: the client script is only able to handle SAML connection, there are no plans to implement more login methods.

## Setup

1. in AppGate GUI client's advanced settings, enable automatic login
1. clone this repository wherever you want
1. automatically start the `appgate-client.py` script in your i3 config
1. add the `polybar-appgate.py` script to your polybar config, as shown in the example below

```text
[module/appgate]
type = custom/script
exec = /path/to/polybar-appgate.py
interval = 5
```

## Known Issues

* AppGate service does not automatically restart if it crashes
* TODO: allow to customize colors
* TODO: allow to customize icons
* TODO: implement icon click trigger to manually start login flow
