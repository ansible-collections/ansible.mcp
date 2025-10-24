# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


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


class MCPClient:
    """Client for communicating with MCP (Model Context Protocol) servers.

    Attributes:
        transport: The transport layer for communication with the server
        connected: Whether the client is currently connected
    """

    def __init__(self, transport: Transport) -> None:
        """Initialize the MCP client.

        Args:
            transport: Transport implementation for server communication
        """
        self.transport = transport
        self.connected = False
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

    def initialize(self) -> None:
        """Initialize the connection to the MCP server.

        Raises:
            Exception: If initialization fails
        """
        if not self.connected:
            self.transport.connect()
            self.connected = True

        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "initialize",
            "params": {
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
        }

        response = self.transport.request(init_request)

        # Cache server info from response
        if "result" in response:
            self._server_info = response["result"]
        else:
            raise Exception(
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
            Exception: If the request fails
        """
        # Return cached result if available
        if self._tools_cache is not None:
            return self._tools_cache

        # Make request to server
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "tools/list",
        }

        response = self.transport.request(request)

        if "result" in response:
            self._tools_cache = response["result"]
            return self._tools_cache
        else:
            raise Exception(
                f"Failed to list tools: {response.get('error', 'Error in listing tools')}"
            )

    def get_tool(self, tool: str) -> Dict[str, Any]:
        """Get the definition of a specific tool.

        Args:
            tool: Name of the tool to retrieve

        Returns:
            Dictionary containing the tool definition

        Raises:
            ValueError: If the tool is not found
        """
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
            Exception: If the tool call fails
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": kwargs,
            },
        }

        response = self.transport.request(request)

        if "result" in response:
            return response["result"]
        else:
            raise Exception(
                f"Failed to call tool '{tool}': {response.get('error', 'Error in tool call')}"
            )

    def server_info(self) -> Dict[str, Any]:
        """Return cached server information from initialization.

        Returns:
            Dictionary containing server information

        Raises:
            RuntimeError: If initialize() has not been called yet
        """
        if self._server_info is None:
            raise RuntimeError("Client not initialized. Call initialize() first.")
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
                    # Map JSON Schema types to their corresponding Python types
                    schema_type_to_python_type = {
                        "string": str,
                        "number": (int, float),
                        "integer": int,
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                    }

                    expected_type = schema_type_to_python_type.get(parameter_type_in_schema)
                    if not isinstance(parameter_value, expected_type):
                        raise ValueError(
                            f"Parameter '{parameter_name}' for tool '{tool}' should be of type '{parameter_type_in_schema}', but got '{type(parameter_value).__name__}'"
                        )

    def close(self) -> None:
        """Close the connection to the MCP server."""
        self.transport.close()
