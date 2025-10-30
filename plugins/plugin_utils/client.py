# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from typing import Any, Dict, Optional

from ansible_collections.ansible.mcp.plugins.plugin_utils.errors import MCPError
from ansible_collections.ansible.mcp.plugins.plugin_utils.transport import Transport


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

    def _build_request(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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

    def _handle_response(self, response: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Handle JSON-RPC response and extract result or raise appropriate error.

        Args:
            response: JSON-RPC response from server
            operation: Description of the operation being performed (for error messages)

        Returns:
            The result from the response

        Raises:
            MCPError: If the response contains an error
        """
        if "result" in response:
            return response["result"]
        else:
            raise MCPError(
                f"Failed to {operation}: {response.get('error', f'Error in {operation}')}"
            )

    def initialize(self) -> None:
        """Initialize the connection to the MCP server.

        Raises:
            MCPError: If initialization fails
        """
        if not self._connected:
            self.transport.connect()

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
        self._server_info = self._handle_response(response, "initialize")

        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        self.transport.notify(initialized_notification)

        # Mark as connected only after successful initialization
        self._connected = True

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

        self._tools_cache = self._handle_response(response, "list tools")
        return self._tools_cache

    def get_tool(self, tool: str) -> Dict[str, Any]:
        """Get the definition of a specific tool.

        Args:
            tool: Name of the tool to retrieve

        Returns:
            Dictionary containing the tool definition

        Raises:
            MCPError: If client is not initialized or if the tool is not found
        """
        if not self._connected or self._server_info is None:
            raise MCPError("Client not initialized. Call initialize() first.")

        tools_response = self.list_tools()
        tools = tools_response.get("tools", [])

        for tool_def in tools:
            if tool_def.get("name") == tool:
                return tool_def

        raise MCPError(f"Tool '{tool}' not found")

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

        return self._handle_response(response, f"call tool '{tool}'")

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

    def _validate_schema_type(self, tool: str, schema: Dict[str, Any]) -> None:
        """Validate that the schema type is supported.

        Args:
            tool: Name of the tool being validated
            schema: The input schema from the tool definition

        Raises:
            ValueError: If the schema type is not supported
        """
        schema_type = schema.get("type")
        if schema_type and schema_type != "object":
            raise ValueError(
                f"Tool '{tool}' has unsupported schema type '{schema_type}', expected 'object'"
            )

    def _validate_required_parameters(
        self, tool: str, kwargs: Dict[str, Any], required_parameters: list
    ) -> None:
        """Validate that all required parameters are provided.

        Args:
            tool: Name of the tool being validated
            kwargs: Arguments provided to the tool
            required_parameters: List of required parameter names

        Raises:
            ValueError: If required parameters are missing
        """
        missing_required = [param for param in required_parameters if param not in kwargs]
        if missing_required:
            raise ValueError(
                f"Tool '{tool}' missing required parameters: {', '.join(missing_required)}"
            )

    def _validate_unknown_parameters(
        self, tool: str, kwargs: Dict[str, Any], schema_properties: Dict[str, Any]
    ) -> None:
        """Validate that no unknown parameters are provided.

        Args:
            tool: Name of the tool being validated
            kwargs: Arguments provided to the tool
            schema_properties: Properties defined in the schema

        Raises:
            ValueError: If unknown parameters are provided
        """
        if schema_properties:
            unknown_parameters = [param for param in kwargs if param not in schema_properties]
            if unknown_parameters:
                raise ValueError(
                    f"Tool '{tool}' received unknown parameters: {', '.join(unknown_parameters)}"
                )

    def _validate_parameter_type(
        self, tool: str, parameter_name: str, parameter_value: Any, parameter_schema: Dict[str, Any]
    ) -> None:
        """Validate that a parameter value matches its expected type.

        Args:
            tool: Name of the tool being validated
            parameter_name: Name of the parameter being validated
            parameter_value: Value of the parameter
            parameter_schema: Schema definition for the parameter

        Raises:
            ValueError: If the parameter type is invalid
        """
        parameter_type_in_schema = parameter_schema.get("type")
        if not parameter_type_in_schema:
            return

        # Handle None values first
        if parameter_value is None:
            if parameter_type_in_schema != "null":
                raise ValueError(
                    f"Parameter '{parameter_name}' for tool '{tool}' cannot be None (expected type '{parameter_type_in_schema}')"
                )
            return

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

        if not isinstance(parameter_value, expected_type):  # type: ignore[arg-type]
            raise ValueError(
                f"Parameter '{parameter_name}' for tool '{tool}' should be of type "
                f"'{parameter_type_in_schema}', but got '{type(parameter_value).__name__}'"
            )

    def validate(self, tool: str, **kwargs: Any) -> None:
        """Validate that a tool call arguments match the tool's schema.

        Args:
            tool: Name of the tool to validate
            **kwargs: Arguments to validate against the tool schema

        Raises:
            MCPError: If the tool is not found
            ValueError: If validation fails (missing required parameters, etc.)
        """
        # Get tool definition and schema
        tool_definition = self.get_tool(tool)
        schema = tool_definition.get("inputSchema", {})

        # Extract schema components
        parameters_from_schema_properties = schema.get("properties", {})
        required_parameters = schema.get("required", [])

        # Perform validation
        self._validate_schema_type(tool, schema)
        self._validate_required_parameters(tool, kwargs, required_parameters)
        self._validate_unknown_parameters(tool, kwargs, parameters_from_schema_properties)

        # Validate parameter types
        for parameter_name, parameter_value in kwargs.items():
            if parameter_name in parameters_from_schema_properties:
                parameter_schema = parameters_from_schema_properties[parameter_name]
                self._validate_parameter_type(
                    tool, parameter_name, parameter_value, parameter_schema
                )

    def close(self) -> None:
        """Close the connection to the MCP server."""
        self.transport.close()
        self._connected = False
        self._server_info = None
        self._tools_cache = None
        self._request_id = 0
