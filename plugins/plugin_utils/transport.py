# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json
import os
import select
import subprocess
import time

from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.urls import open_url


class Transport(ABC):
    @abstractmethod
    def connect(self) -> None:
        """Connect to the MCP server.

        This is called before attempting to perform initialization.
        """
        pass

    @abstractmethod
    def notify(self, data: dict) -> None:
        """Send a notification message to the server.

        This sends a JSON-RPC payload to the server when no response is
        expected.

        Args:
            data: JSON-RPC payload.
        """
        pass

    @abstractmethod
    def request(self, data: dict) -> dict:
        """Send a request to the server.

        This sends a JSON-RPC payload to the server when a response is expected.

        Args:
            data: JSON-RPC payload.
        Returns:
            The JSON-RPC response from the server.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the server connection.

        This is called to perform any final actions to close and clean up the
        connection.
        """
        pass


class Stdio(Transport):
    def __init__(self, cmd: Union[list[str], str], env: Optional[dict] = None):
        """Initialize the stdio transport class.

        Args:
            cmd: Command used to run the MCP server.
            env: Environment variables to set for the MCP server process.
        """
        self._cmd = cmd
        self._env = env
        self._process: Optional[Any] = None

    def connect(self) -> None:
        """Spawn a local MCP server subprocess."""
        params: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "bufsize": 0,  # Unbuffered for real-time communication
        }

        if self._env:
            # Prepare environment for command
            env: dict[str, Any] = os.environ.copy()
            env.update(self._env)
            params.update({"env": env})

        try:
            cmd = self._cmd
            if isinstance(self._cmd, str):
                cmd = [self._cmd]
            self._process = subprocess.Popen(cmd, **params)

            # Give the server a moment to start
            time.sleep(0.1)

            # Check if process started successfully
            if self._process.poll() is not None:
                try:
                    stdout, stderr = self._process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", ""
                    pass
                raise AnsibleConnectionFailure(
                    f"MCP server exited immediately. stdout: {stdout}, stderr: {stderr}"
                )
        except AnsibleConnectionFailure:
            raise
        except Exception as e:
            raise AnsibleConnectionFailure(f"Failed to start MCP server: {str(e)}")

    def _stdout_read(self, wait_timeout: int = 5) -> dict:
        """Read response from MCP server with timeout.

        Args:
            wait_timeout: The wait timeout value, default: 5.
        Returns:
            A JSON-RPC response dictionary from the MCP server.
        """

        response = {}
        if self._process:
            rfd, wfd, efd = select.select([self._process.stdout], [], [], wait_timeout)
            if not (rfd or wfd or efd):
                # Process has timeout
                raise AnsibleConnectionFailure(
                    f"MCP server response timeout after {wait_timeout} seconds."
                )

            if self._process.stdout in rfd:
                response = json.loads(
                    os.read(self._process.stdout.fileno(), 4096).decode("utf-8").strip()
                )
        return response

    def _stdin_write(self, data: dict) -> None:
        """Write data to process standard input.

        Args:
            data: JSON-RPC payload.
        """
        data_json = json.dumps(data) + "\n"
        if self._process is not None:
            self._process.stdin.write(data_json)
            self._process.stdin.flush()

    def _ensure_server_started(func: Callable):  # type: ignore  # see https://github.com/python/mypy/issues/7778     # pylint: disable=no-self-argument
        """Decorator to ensure that the MCP server process is running before method execution."""

        @wraps(func)
        def wrapped(self, *args, **kwargs: dict[str, Any]):
            if self._process is None:
                raise AnsibleConnectionFailure("MCP server process not started.")
            if self._process.poll() is not None:
                stdout, stderr = self._process.communicate()
                raise AnsibleConnectionFailure(
                    f"MCP server process terminated unexpectedly. stdout: {stdout}, stderr: {stderr}"
                )
            return func(self, *args, **kwargs)

        return wrapped

    @_ensure_server_started
    def notify(self, data: dict) -> None:
        """Send a notification message to the server.

        This sends a JSON-RPC payload to the server when no response is
        expected.

        Args:
            data: JSON-RPC payload.
        """
        try:
            self._stdin_write(data)
        except Exception as e:
            raise AnsibleConnectionFailure(f"Error sending notification to MCP server: {str(e)}")

    @_ensure_server_started
    def request(self, data: dict) -> dict:
        """Send a request to the server.

        This sends a JSON-RPC payload to the server when a response is expected.

        Args:
            data: JSON-RPC payload.
        Returns:
            The JSON-RPC response from the server.
        """
        try:
            # Send request to the server
            self._stdin_write(data)
            # Read response
            return self._stdout_read()
        except Exception as e:
            raise AnsibleConnectionFailure(f"Error sending request to MCP server: {str(e)}")

    def close(self) -> None:
        """Close the server connection."""
        if self._process:
            try:
                # Try to terminate gracefully first
                self._process.terminate()

                # Wait for process to terminate
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                self._process.kill()
                self._process.wait()
            except Exception as e:
                raise AnsibleConnectionFailure(f"Error closing MCP process: {str(e)}")
            finally:
                self._process = None


class StreamableHTTP(Transport):
    def __init__(self, url: str, headers: Optional[dict] = None, validate_certs: bool = True):
        """Initialize the StreamableHTTP transport.

        Args:
            url: The MCP server URL endpoint
            headers: Optional headers to include with requests
            validate_certs: Whether to validate SSL certificates (default: True)
        """
        self.url = url
        self._headers: Dict[str, str] = headers.copy() if headers else {}
        self.validate_certs = validate_certs
        self._session_id = None

    def connect(self) -> None:
        """Connect to the MCP server.

        For HTTP transport, this is a no-op as connection is established
        per-request.
        """
        pass

    def notify(self, data: dict) -> None:
        """Send a notification message to the server.

        Args:
            data: JSON-RPC payload.
        """
        headers = self._build_headers()

        try:
            response = open_url(
                self.url,
                method="POST",
                data=json.dumps(data),
                headers=headers,
                validate_certs=self.validate_certs,
            )

            if response.getcode() != 202:
                raise Exception(f"Unexpected response code: {response.getcode()}")

            self._extract_session_id(response)

        except Exception as e:
            raise Exception(f"Failed to send notification: {str(e)}")

    def request(self, data: dict) -> dict:
        """Send a request to the server.

        Args:
            data: JSON-RPC payload.

        Returns:
            The JSON-RPC response from the server.
        """
        headers = self._build_headers()

        try:
            response = open_url(
                self.url,
                method="POST",
                data=json.dumps(data),
                headers=headers,
                validate_certs=self.validate_certs,
            )

            if response.getcode() != 200:
                raise Exception(f"Unexpected response code: {response.getcode()}")

            self._extract_session_id(response)

            response_data = response.read()

            # Parse JSON response
            try:
                return json.loads(response_data.decode("utf-8"))
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON response: {str(e)}")

        except Exception as e:
            raise Exception(f"Failed to send request: {str(e)}")

    def close(self) -> None:
        """Close the server connection.

        For HTTP transport, this is a no-op as connections are not persistent.
        """
        pass

    def _build_headers(self) -> dict:
        """Build headers for HTTP requests.

        Returns:
            Dictionary of headers to include in the request.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
        }

        # Add custom headers
        headers.update(self._headers)

        # Add session ID if available
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        return headers

    def _extract_session_id(self, response) -> None:
        """Extract session ID from response headers.

        Args:
            response: The HTTP response object
        """
        # Check for Mcp-Session-Id header in response
        session_header = response.headers.get("Mcp-Session-Id")
        if session_header is not None:
            self._session_id = session_header
