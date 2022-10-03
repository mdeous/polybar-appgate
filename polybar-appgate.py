#!/usr/bin/python3
import sys
from multiprocessing.connection import Client

MPC_HOST = "127.0.0.1"
MPC_PORT = 2345
MPC_KEY = b"polybar-appgate-mpc"
COMMANDS = [
    "ping",
    "status",
    "goodbye",
    "exit-service"
]
CONNECTION_OK = "%{F#55AA55}輦%{F-}"
CONNECTION_KO = "%{F#FF7070}聯%{F-}"
CONNECTION_CONNECTING = "%{F#F5A70A}ﱾ%{F-}"
ERROR = "%{F#FF7070}%{F-}"
RESPONSES = {
    "login": CONNECTION_CONNECTING,
    "connecting": CONNECTION_CONNECTING,
    "connected": CONNECTION_OK,
    "error": ERROR,
    "unknown": ERROR
}


def main():
    try:
        conn = Client((MPC_HOST, MPC_PORT), authkey=MPC_KEY)
    except ConnectionRefusedError:
        print(ERROR)
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
        print(RESPONSES.get(resp, CONNECTION_KO))
        conn.send("goodbye")
        conn.close()


if __name__ == "__main__":
    main()
