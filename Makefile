BIN_PATH=${HOME}/.local/bin
SERVICE_PATH=${HOME}/.config/systemd/user/
CLIENT=appgate-client.py
SERVICE=appgate-client.service

all:

install:
	mkdir -p $(BIN_PATH)
	cp $(CLIENT) $(BIN_PATH)
	mkdir -p $(SERVICE_PATH)
	cp $(SERVICE) $(SERVICE_PATH)
	systemctl --user daemon-reload
	systemctl --user start appgate-client.service
	systemctl --user enable appgate-client.service
