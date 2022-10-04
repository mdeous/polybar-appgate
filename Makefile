SERVICE_PATH=${HOME}/.config/systemd/user/
SERVICE=appgate-client.service
PWD=$(shell pwd)

all:

install_service:
	mkdir -p $(SERVICE_PATH)
	cp $(SERVICE) $(SERVICE_PATH)
	sed -i -e 's:SCRIPT_PATH:$(PWD):' $(SERVICE_PATH)/$(SERVICE)
	systemctl --user daemon-reload
	systemctl --user start $(SERVICE)
	systemctl --user enable $(SERVICE)
