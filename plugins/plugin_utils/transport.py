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
    def __init__(
        self, cmd: Union[list[str], str], env: Optional[dict] = None, command_timeout: int = 5
    ):
        """Initialize the stdio transport class.

        Args:
            cmd: Command used to run the MCP server.
            env: Environment variables to set for the MCP server process.
            command_timeout: Wait timeout for command to execute.
        """
        self._cmd = cmd
        self._env = env
        self._process: Optional[Any] = None
        self._command_timeout = command_timeout
        # stdout is read in chunks, so a single read can return several
        # messages at once. Keep the leftovers for the next read.
        self._stdout_buffer = b""

    def connect(self) -> None:
        """Spawn a local MCP server subprocess."""
        # Bytes left over from a previous process belong to that process.
        self._stdout_buffer = b""

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

    def _stdout_read(self, timeout: Optional[float] = None) -> dict:
        """Read a single message from the MCP server with timeout.

        Args:
            timeout: Seconds to wait for a complete message. Defaults to the
                configured command timeout.

        Returns:
            A JSON-RPC message dictionary from the MCP server.
        """

        response: dict = {}
        if timeout is None:
            timeout = self._command_timeout

        if self._process:
            deadline = time.monotonic() + timeout
            while True:
                # An earlier read may have buffered more than one message.
                if b"\n" in self._stdout_buffer:
                    line, self._stdout_buffer = self._stdout_buffer.split(b"\n", 1)
                    try:
                        response = json.loads(line.decode("utf-8"))
                        break
                    except Exception:
                        # Discard the unparsable line only, so that any message
                        # already buffered behind it is still read.
                        continue

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AnsibleConnectionFailure(
                        f"MCP server response timeout after {timeout} seconds."
                    )

                rfd, wfd, efd = select.select([self._process.stdout], [], [], remaining)
                if self._process.stdout in rfd:
                    chunk = os.read(self._process.stdout.fileno(), 4096)
                    if not chunk:
                        raise AnsibleConnectionFailure(
                            "MCP server closed its output stream before sending a response."
                        )
                    self._stdout_buffer += chunk
                else:
                    # Process has timeout
                    raise AnsibleConnectionFailure(
                        f"MCP server response timeout after {self._command_timeout} seconds."
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

        A server may send notifications at any time, including between the
        request and its response, so messages are read until the one carrying
        the request ``id`` is found. The whole exchange is bounded by the
        command timeout so that a chatty server cannot block the caller
        indefinitely.

        Args:
            data: JSON-RPC payload. Must carry an ``id``.
        Returns:
            The JSON-RPC response matching the ``id`` of the request.
        """
        request_id = data.get("id")
        if request_id is None:
            # Without an id there is nothing to match the response against, and
            # every notification would compare equal to it. A payload with no id
            # is a notification by definition; send it with notify() instead.
            raise AnsibleConnectionFailure(
                "JSON-RPC request passed to request() must include an 'id'."
            )

        try:
            # Send request to the server
            self._stdin_write(data)
        except Exception as e:
            raise AnsibleConnectionFailure(f"Error sending request to MCP server: {str(e)}")

        deadline = time.monotonic() + self._command_timeout

        try:
            while True:
                message = self._stdout_read(timeout=max(deadline - time.monotonic(), 0))
                # Notifications carry no id, and a response to an earlier
                # request carries a different one. Neither is this reply.
                if message.get("id") == request_id:
                    return message
        except Exception as e:
            raise AnsibleConnectionFailure(f"Error reading server response: {str(e)}")

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
                self._stdout_buffer = b""


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

    def _extract_response(self, response: Any) -> dict:
        """Parse the MCP server response received as raw json or event stream.

        Args:
            response: object returned by the ansible open_url API.

        Returns:
            The JSON-RPC response from the server.
        """
        # raw_response = response.decode("utf-8")
        content_type = response.headers.get("Content-Type")
        raw_response = response.read().decode("utf-8")
        if content_type == "text/event-stream":
            for line in raw_response.split("\n"):
                if line.startswith("data:"):
                    raw_response = line.split(":", maxsplit=1)[1].lstrip()
                    break

        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {str(e)}")

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

            # Parse JSON response
            return self._extract_response(response)

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
