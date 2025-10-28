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


class MCPError(Exception):
    """Base exception class for MCP related errors.

    This exception is raised when MCP operations fail, such as initialization,
    tool listing, tool execution, or validation errors.
    """
    pass


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

class MCPClient:
    """Client for communicating with MCP (Model Context Protocol) servers.

    Attributes:
        transport: The transport layer for communication with the server
    """

    def __init__(self, transport: Transport) -> None:
        """Initialize the MCP client.

        Args:
            transport: Transport implementation for server communication
        """
        self.transport = transport
        self._connected = False
        self._server_info: Optional[Dict[str, Any]] = None
        self._tools_cache: Optional[Dict[str, Any]] = None
        self._request_id = 0

    def _get_next_id(self) -> int:
        """Generate the next request ID.

        Returns:
            Unique request ID
        """
        self._request_id += 1
        return self._request_id

    def _build_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Compose a JSON-RPC 2.0 request for MCP.

        Args:
            method: The JSON-RPC method name
            params: Optional parameters for the request

        Returns:
            Dictionary containing the JSON-RPC request
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": method,
        }
        if params is not None:
            request["params"] = params
        return request

    def initialize(self) -> None:
        """Initialize the connection to the MCP server.

        Raises:
            MCPError: If initialization fails
        """
        if not self._connected:
            self.transport.connect()
            self._connected = True

        # Send initialize request
        init_request = self._build_request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": {
                    "name": "ansible-mcp-client",
                    "version": "1.0.0",
                },
            },
        )

        response = self.transport.request(init_request)

        # Cache server info from response
        if "result" in response:
            self._server_info = response["result"]
        else:
            raise MCPError(
                f"Initialization failed: {response.get('error', 'Error in initialization')}"
            )

        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        self.transport.notify(initialized_notification)

    def list_tools(self) -> Dict[str, Any]:
        """List all available tools from the MCP server.

        Returns:
            Dictionary containing the tools list response

        Raises:
            MCPError: If the request fails
        """
        if not self._connected or self._server_info is None:
            raise MCPError("Client not initialized. Call initialize() first.")

        # Return cached result if available
        if self._tools_cache is not None:
            return self._tools_cache

        # Make request to server
        request = self._build_request("tools/list")

        response = self.transport.request(request)

        if "result" in response:
            self._tools_cache = response["result"]
            return self._tools_cache
        else:
            raise MCPError(
                f"Failed to list tools: {response.get('error', 'Error in listing tools')}"
            )

    def get_tool(self, tool: str) -> Dict[str, Any]:
        """Get the definition of a specific tool.

        Args:
            tool: Name of the tool to retrieve

        Returns:
            Dictionary containing the tool definition

        Raises:
            MCPError: If client is not initialized
            ValueError: If the tool is not found
        """
        if not self._connected or self._server_info is None:
            raise MCPError("Client not initialized. Call initialize() first.")

        tools_response = self.list_tools()
        tools = tools_response.get("tools", [])

        for tool_def in tools:
            if tool_def.get("name") == tool:
                return tool_def

        raise ValueError(f"Tool '{tool}' not found")

    def call_tool(self, tool: str, **kwargs: Any) -> Dict[str, Any]:
        """Call a tool on the MCP server with the provided arguments.

        Args:
            tool: Name of the tool to call
            **kwargs: Arguments to pass to the tool

        Returns:
            Dictionary containing the tool call response

        Raises:
            ValueError: If validation fails
            MCPError: If the tool call fails
        """
        if not self._connected or self._server_info is None:
            raise MCPError("Client not initialized. Call initialize() first.")

        # Validate parameters before making the request
        self.validate(tool, **kwargs)

        request = self._build_request(
            "tools/call",
            {
                "name": tool,
                "arguments": kwargs,
            },
        )

        response = self.transport.request(request)

        if "result" in response:
            return response["result"]
        else:
            raise MCPError(
                f"Failed to call tool '{tool}': {response.get('error', 'Error in tool call')}"
            )

    @property
    def server_info(self) -> Dict[str, Any]:
        """Return cached server information from initialization.

        Returns:
            Dictionary containing server information

        Raises:
            MCPError: If initialize() has not been called yet
        """
        if self._server_info is None:
            raise MCPError("Client not initialized. Call initialize() first.")
        return self._server_info

    def validate(self, tool: str, **kwargs: Any) -> None:
        """Validate that a tool call arguments match the tool's schema.

        Args:
            tool: Name of the tool to validate
            **kwargs: Arguments to validate against the tool schema

        Raises:
            ValueError: If the tool is not found
            ValueError: If validation fails (missing required parameters, etc.)
        """
        # Get tool definition and schema
        tool_definition = self.get_tool(tool)
        schema = tool_definition.get("inputSchema", {})

        # Extract schema components
        schema_type = schema.get("type")
        parameters_from_schema_properties = schema.get("properties", {})
        required_parameters = schema.get("required", [])

        # Validate schema supports object type
        if schema_type and schema_type != "object":
            raise ValueError(
                f"Tool '{tool}' has unsupported schema type '{schema_type}', expected 'object'"
            )

        # Check for missing required parameters
        missing_required = [param for param in required_parameters if param not in kwargs]
        if missing_required:
            raise ValueError(
                f"Tool '{tool}' missing required parameters: {', '.join(missing_required)}"
            )

        # Check for unknown parameters
        if parameters_from_schema_properties:
            unknown_parameters = [
                param for param in kwargs if param not in parameters_from_schema_properties
            ]
            if unknown_parameters:
                raise ValueError(
                    f"Tool '{tool}' received unknown parameters: {', '.join(unknown_parameters)}"
                )

        # Validate parameter types
        for parameter_name, parameter_value in kwargs.items():
            if parameter_name in parameters_from_schema_properties:
                parameter_schema = parameters_from_schema_properties[parameter_name]
                parameter_type_in_schema = parameter_schema.get("type")

                if parameter_type_in_schema:
                    # Handle None values first
                    if parameter_value is None:
                        if parameter_type_in_schema != "null":
                            raise ValueError(
                                f"Parameter '{parameter_name}' for tool '{tool}' cannot be None (expected type '{parameter_type_in_schema}')"
                            )
                        # None is valid for null type, continue to next parameter
                        continue

                    # Map JSON Schema types to their corresponding Python types
                    schema_type_to_python_type = {
                        "string": str,
                        "number": (int, float),
                        "integer": int,
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                        "null": type(None),
                    }

                    expected_type = schema_type_to_python_type.get(parameter_type_in_schema)
                    if expected_type is None:
                        raise ValueError(
                            f"Tool '{tool}' has unsupported parameter type '{parameter_type_in_schema}' for parameter '{parameter_name}'"
                        )

                    if not isinstance(parameter_value, expected_type):
                        raise ValueError(
                            f"Parameter '{parameter_name}' for tool '{tool}' should be of type '{parameter_type_in_schema}', but got '{type(parameter_value).__name__}'"
                        )

    def close(self) -> None:
        """Close the connection to the MCP server."""
        self.transport.close()
        self._connected = False
        self._server_info = None
        self._tools_cache = None
