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
import logging
import logging.handlers
import os
import signal
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
STATUS_DISCONNECTED = "disconnected"
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
        svc_logger = logging.getLogger("appgateservice")
        svc_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        svc_logger.addHandler(svc_handler)
        try:
            for line in process.stdout:
                svc_logger.info(line.decode("utf-8").rstrip())
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
        self._next_id: int = 0
        self._recv_buf: bytes = b""

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

    def send(self, method: str, **kwargs):
        if not self.connected:
            raise Exception("[client] service is not started")
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
            "params": kwargs
        }
        self.sock.sendall(json.dumps(payload).encode() + b"\n")
        if self.debug:
            log(f"[client] <<< {method}")

    def recv_message(self, timeout: float = 10.0) -> Optional[dict]:
        self.sock.settimeout(timeout)
        max_size = 64 * 1024
        try:
            while b"\n" not in self._recv_buf:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise Exception("[client] connection closed unexpectedly")
                self._recv_buf += chunk
                if len(self._recv_buf) > max_size:
                    raise Exception("[client] message too large")
        except socket.timeout:
            return None
        line, self._recv_buf = self._recv_buf.split(b"\n", 1)
        msg = json.loads(line.rstrip(b"\r"))
        if self.debug:
            log(f"[client] >>> {msg.get('method', 'response')}")
        return msg

    def get_view(self, msg: dict) -> str:
        return msg.get("params", {}).get("view", "")


_logger = logging.getLogger("appgateclient")
_logger.setLevel(logging.DEBUG)
_handler = logging.handlers.RotatingFileHandler(
    os.path.join(CURRENT_DIR, "appgateclient.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
)
_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_logger.addHandler(_handler)

shutdown_requested = False


def log(*chunks: Any):
    _logger.info(" ".join(map(str, chunks)))


def sigterm_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True


def process_exists(target_exe: str) -> bool:
    for pid in os.listdir("/proc"):
        proc_path = os.path.join("/proc", pid)
        if pid.isnumeric() and os.path.isdir(proc_path):
            exe_path = os.path.join(proc_path, "exe")
            try:
                os.stat(exe_path)
            except (PermissionError, FileNotFoundError):
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

    # initiate session — client must speak first in v6.5+
    appgate.send(method="ready", autoLogin=True)
    appgate.send(method="setLocale", locale="en")

    # read setModel messages until we have connection status
    appgate_status = STATUS_UNKNOWN
    log("[main] waiting for service to initialize")
    for _ in range(60):
        msg = appgate.recv_message(timeout=2.0)
        if msg is None:
            continue
        view = appgate.get_view(msg)
        if view:
            appgate_status = view
            log(f"[main] status: {view}")
        if view in (STATUS_CONNECTED, "login"):
            break

    # listen for IPC connections
    listener = Listener((MPC_HOST, MPC_PORT), authkey=MPC_KEY)
    listener._listener._socket.settimeout(2.0)
    log("[main] mpc listener started")

    signal.signal(signal.SIGTERM, sigterm_handler)

    while appgate.service.is_alive() and not shutdown_requested:
        if not os.path.exists(SOCK_FILE):
            log("[main] socket file not found")
            break

        # read any pending setModel notifications to refresh status
        while True:
            msg = appgate.recv_message(timeout=0.1)
            if msg is None:
                break
            view = appgate.get_view(msg)
            if view:
                appgate_status = view
                log(f"[main] status update: {view}")

        # wait for and reply to IPC connections
        try:
            conn = listener.accept()
        except socket.timeout:
            continue
        exit_service = False
        log("[main] mpc client connected")
        while True:
            msg = conn.recv()
            log(f"[main] received message: {msg}")
            if msg == "status":
                conn.send(appgate_status)
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
    except (KeyboardInterrupt, SystemExit):
        log("[__main__] appgate client exited")
