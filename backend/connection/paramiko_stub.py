"""
connection/paramiko_stub.py — Paramiko SSH-based connection implementation.

Provides actual SSH connection and execution logic.
"""

from __future__ import annotations

import logging
import shlex
import paramiko
from connection.interface import DeviceConnection

logger = logging.getLogger(__name__)


class ParamikoConnection(DeviceConnection):
    """
    SSH connection using Paramiko.
    """

    def __init__(self, host: str, port: int = 22,
                 username: str = "", password: str = "",
                 remote_command_template: str | None = None) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._remote_command_template = remote_command_template
        self._ssh: paramiko.SSHClient | None = None

    def connect(self) -> None:
        logger.info("Connecting to SSH %s@%s:%d", self._username, self._host, self._port)
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(
            hostname=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            timeout=10
        )

    def execute(self, command: str) -> str:
        if not self._ssh:
            raise RuntimeError("Not connected — call connect() first")
        
        logger.debug("SSH executing command on %s: %s", self._host, command)
        if self._remote_command_template:
            remote_command = self._remote_command_template.format(
                command=shlex.quote(command)
            )
        else:
            remote_command = command

        stdin, stdout, stderr = self._ssh.exec_command(remote_command, timeout=10)
        
        # Read raw output and error streams
        out_bytes = stdout.read()
        err_bytes = stderr.read()
        
        out = out_bytes.decode("utf-8")
        err = err_bytes.decode("utf-8")
        
        # Fetch exit status
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            logger.warning(
                "SSH command exit code %d on %s. Stderr: %r", 
                exit_status, self._host, err
            )
            # If stdout is empty but stderr has content, return stderr
            if not out.strip() and err.strip():
                return err
        
        return out

    def disconnect(self) -> None:
        if self._ssh:
            self._ssh.close()
            self._ssh = None
            logger.info("Disconnected from SSH %s", self._host)
