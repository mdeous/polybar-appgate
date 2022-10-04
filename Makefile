SERVICE_PATH=${HOME}/.config/systemd/user/
SERVICE=appgate-client.service
PWD=$(shell pwd)

.PHONY: update install uninstall pull

update: pull install

install:
	mkdir -p $(SERVICE_PATH)
	cp $(SERVICE) $(SERVICE_PATH)
	sed -i -e 's:SCRIPT_PATH:$(PWD):' $(SERVICE_PATH)/$(SERVICE)
	systemctl --user daemon-reload
	systemctl --user start $(SERVICE)
	systemctl --user enable $(SERVICE)

uninstall:
	systemctl --user stop $(SERVICE)
	systemctl --user disable $(SERVICE)
	rm -rf $(SERVICE_PATH)
	systemctl --user daemon-reload

pull:
	git pull origin main
