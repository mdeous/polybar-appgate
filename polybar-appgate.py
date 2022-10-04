#!/usr/bin/python3
import os
import sys
from multiprocessing.connection import Client

MPC_HOST = "127.0.0.1"
MPC_PORT = 2345
MPC_KEY = b"polybar-appgate-mpc"
COMMANDS = [
    "status",
    "goodbye",
    "exit-service"
]

COLOR_CONNECTED = os.getenv("APPGATE_COLOR_CONNECTED", "55AA55")
COLOR_DISCONNECTED = os.getenv("APPGATE_COLOR_DISCONNECTED", "FF7070")
COLOR_CONNECTING = os.getenv("APPGATE_COLOR_CONNECTING", "F5A70A")
COLOR_ERROR = os.getenv("APPGATE_COLOR_ERROR", "FF7070")

ICON_CONNECTED = os.getenv("APPGATE_ICON_CONNECTED", "輦")
ICON_DISCONNECTED = os.getenv("APPGATE_ICON_DISCONNECTED", "聯")
ICON_CONNECTING = os.getenv("APPGATE_ICON_OK", "ﱾ")
ICON_ERROR = os.getenv("APPGATE_ICON_OK", "")

OUTPUT_CONNECTED = f"%{{F#{COLOR_CONNECTED}}}{ICON_CONNECTED}%{{F-}}"
OUTPUT_DISCONNECTED = f"%{{F#{COLOR_DISCONNECTED}}}{ICON_DISCONNECTED}%{{F-}}"
OUTPUT_CONNECTING = f"%{{F#{COLOR_CONNECTING}}}{ICON_CONNECTING}%{{F-}}"
OUTPUT_ERROR = f"%{{F#{COLOR_ERROR}}}{ICON_ERROR}%{{F-}}"

RESPONSES = {
    "login": OUTPUT_CONNECTING,
    "connecting": OUTPUT_CONNECTING,
    "connected": OUTPUT_CONNECTED,
    "error": OUTPUT_ERROR,
    "unknown": OUTPUT_ERROR
}


def main():
    try:
        conn = Client((MPC_HOST, MPC_PORT), authkey=MPC_KEY)
    except ConnectionRefusedError:
        print(OUTPUT_ERROR)
        return
    cmd = "status"

    if len(sys.argv) == 2:
        cmd = sys.argv[1]
        if cmd not in COMMANDS:
            print(f"invalid command: {cmd}")
            return

    conn.send(cmd)
    if cmd != "exit-service":
        resp = conn.recv()
        print(RESPONSES.get(resp, OUTPUT_DISCONNECTED))
        conn.send("goodbye")
        conn.close()


if __name__ == "__main__":
    main()
