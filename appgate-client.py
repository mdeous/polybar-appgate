#!/usr/bin/python3
#
# appgate-client.py - Background script that starts AppGate service and reports its status
#                     via a socket it listens on.
#
# Setup requirements:
# - this script should be started before polybar (e.g. in i3 config)
# - in AppGate GUI's advanced settings, automatic connection must be enabled
#
import json
import os
import socket
import time
from multiprocessing import Process
from multiprocessing.connection import Listener
from subprocess import Popen, PIPE, STDOUT
from typing import Optional, Any

DEBUG = False
RUN_DIR = f"/run/user/{os.getuid()}"
SOCK_FILE = os.path.join(RUN_DIR, "appgate.service.sock")
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
MPC_HOST = "127.0.0.1"
MPC_PORT = 2345
MPC_KEY = b"polybar-appgate-mpc"
IGNORED_ERROR_CODES = [
    -32602,
]
STATUS_CONNECTED = "connected"
STATUS_ERROR = "error"
STATUS_UNKNOWN = "unknown"


class AppGateService(Process):
    svc_bin: str = "/opt/appgate/service/appgateservice"
    log_file: str = os.path.join(
        CURRENT_DIR,
        "appgateservice.log"
    )
    sock_file: str = SOCK_FILE

    def __init__(self, debug: bool = False):
        self.debug: bool = debug
        super().__init__()

    @classmethod
    def exists(cls) -> bool:
        log("[service] checking if service is running")
        if process_exists(cls.svc_bin):
            return True
        log("[service] service is not running")
        if os.path.exists(cls.sock_file):
            log("[service] cleaning leftover")
            os.unlink(cls.sock_file)
        return False

    def run(self):
        cmd = [self.svc_bin]
        if self.debug:
            cmd += ["-l", "0"]
        process = Popen(
            cmd,
            stdout=PIPE,
            stderr=STDOUT
        )
        with open(self.log_file, "a") as outfile:
            try:
                for line in process.stdout:
                    line = line.decode("utf-8")
                    outfile.write(line)
                    outfile.flush()
            except KeyboardInterrupt:
                log("[service] underlying process killed")
                return
        log("[service] underlying process exited")


class AppGateClient:
    def __init__(self, socket_file: str, debug: bool):
        self.sock_file: str = socket_file
        self.debug: bool = debug
        self.connected: bool = False
        self.sock: socket.socket = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM
        )
        self.service: Optional[AppGateService] = None

    def start_service(self):
        if not AppGateService.exists():
            self.service = AppGateService(self.debug)
            self.service.start()

            while self.service.is_alive() and not os.path.exists(self.sock_file):
                time.sleep(0.2)
            if not self.service.is_alive():
                raise Exception("[client] service died during startup")
            log("[client] service started")
        else:
            log("[client] service already started")
        self.sock.connect(self.sock_file)
        self.connected = True
        log("[client] connected to unix socket")

    def send(self, method: str, params: Any = None, **kwargs) -> Any:
        if not self.connected:
            raise Exception("[client] service is not started")
        if params is None:
            params = kwargs
        call_id = int(time.time() * 100000)
        payload = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": method,
            "params": params
        }
        send_data = json.dumps(payload).encode() + b"\n"
        self.sock.sendall(send_data)
        if self.debug:
            log(f"[client] <<<\n{json.dumps(payload, indent=2)}")

        buf = self.recv()
        resp_data = json.loads(buf)
        if resp_data.get("error", None):
            if resp_data["error"]["code"] not in IGNORED_ERROR_CODES:
                log("[client] ERROR", resp_data["error"]["message"])
        else:
            if self.debug:
                log(f"[client] >>>\n{json.dumps(resp_data, indent=2)}")
        return resp_data

    def recv(self) -> bytes:
        if not self.connected:
            raise Exception("[client] service is not started")
        data = b""
        while not data.endswith(b"\r\n"):
            recv = self.sock.recv(1)
            if not recv:
                raise Exception("[client] connection closed unexpectedly")
            data += recv
        return data

    def saml_connect(self, saml_profile: int) -> str:
        resp = self.send("loginSaml", profile=saml_profile)
        if resp.get("error", None):
            if resp["error"]["code"] not in IGNORED_ERROR_CODES:
                log("[client] ERROR", resp["error"]["message"])
            return STATUS_ERROR
        if "params" not in resp:
            log(resp)
            return STATUS_UNKNOWN
        log("[main] saml status:", resp["params"]["view"])
        return resp["params"]["view"]


def log(*chunks: Any):
    with open(os.path.join(CURRENT_DIR, "appgateclient.log"), "a") as outfile:
        outfile.write(" ".join(map(str, chunks)) + "\n")
        outfile.flush()


def process_exists(target_exe: str) -> bool:
    for pid in os.listdir("/proc"):
        proc_path = os.path.join("/proc", pid)
        if pid.isnumeric() and os.path.isdir(proc_path):
            exe_path = os.path.join(proc_path, "exe")
            try:
                os.stat(exe_path)
            except PermissionError:
                continue
            real_exe = os.path.realpath(exe_path)
            if real_exe == target_exe:
                return True
    return False


def main():
    log("[main] begin")
    if AppGateService.exists():
        log("[main] service already started")
        return

    # start appgate service
    appgate = AppGateClient(SOCK_FILE, DEBUG)
    appgate.start_service()

    # read saml profile id
    data = appgate.recv()
    data = json.loads(data)
    saml_profile = data.get("params", {}) \
        .get("viewData", {}) \
        .get("setup", {}) \
        .get("selectedProfile", {}) \
        .get("id", None)
    if saml_profile is None:
        log("[main] saml profile id not found")
        return

    # start session and initiate SAML login
    appgate.send("ready", autoLogin=True)
    appgate.send("setLocale", locale="en")
    conn_result = appgate.saml_connect(saml_profile)
    appgate_connected = conn_result == STATUS_CONNECTED

    # listen for IPC connections
    listener = Listener((MPC_HOST, MPC_PORT), authkey=MPC_KEY)
    log("[main] mpc listener started")
    while appgate.service is None:
        time.sleep(1)
    assert appgate.service is not None
    while appgate.service.is_alive():
        # if socket file no longer exists, we can no longer proxy messages, let's exit
        if not os.path.exists(SOCK_FILE):
            log("[main] socket file not found")
            break

        # if appgate isn't connected yet, check status of SAML login
        if not appgate_connected:
            conn_result = appgate.saml_connect(saml_profile)
            appgate_connected = conn_result == STATUS_CONNECTED

        # wait for and reply to connections
        log("[main] waiting for mpc connections")
        conn = listener.accept()
        exit_service = False
        log("[main] mpc client connected")
        while True:
            msg = conn.recv()
            log(f"[main] received message: {msg}")
            if msg == "ping":
                log("[main] replying pong")
                conn.send("pong")
                continue
            elif msg == "status":
                conn.send(conn_result)
                continue
            elif msg == "goodbye":
                conn.send("goodbye")
                break
            elif msg == "exit-service":
                exit_service = True
                break
            else:
                log(f"[main] unknown message: {msg}")
                continue
        if exit_service:
            log("[main] stopping service")
            appgate.service.kill()
            break
    listener.close()
    log("[main] mpc listener and service ended")


if __name__ == "__main__":
    log("[__main__] starting appgate client")
    try:
        main()
    except KeyboardInterrupt:
        log("[__main__] appgate client exited")
