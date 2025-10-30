# -*- coding: utf-8 -*-
# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


DOCUMENTATION = r"""
name: mcp
author:
    - Alina Buzachis (@alinabuzachis)
version_added: 1.0.0
short_description: Persistent connection to an Model Context Protocol (MCP) server
description:
    - This connection plugin allows for a persistent connection to an Model Context Protocol (MCP) server.
    - It is designed to run once per host for the duration of a playbook, allowing tasks to communicate with a single, long-lived server session.
    - Both stdio and Streamable HTTP transport methods are supported.
    - All tasks using this connection plugin are run on the Ansible control node.
options:
    mcp_server_name:
        description:
            - The name of the MCP server.
        type: str
        required: true
        vars:
            - name: ansible_mcp_mcp_server_name
    mcp_server_args:
        description:
            - Additional command line arguments to pass to the server when using stdio transport.
        type: list
        elements: str
        vars:
            - name: ansible_mcp_mcp_server_args
    mcp_server_env:
        description:
            - Additional environment variables to pass to the server when using stdio transport.
            - These are merged with the current environment.
            - Ignored when using http transport.
        type: dict
        vars:
            - name: ansible_mcp_mcp_server_env
    mcp_bearer_token:
        description:
            - Bearer token for authenticating to the MCP server when using http transport.
            - Ignored when using stdio transport.
        type: str
        vars:
            - name: ansible_mcp_mcp_bearer_token
    mcp_manifest_path:
        description:
            - Path to MCP manifest JSON file to resolve server executable paths for stdio.
        type: str
        default: "/opt/mcp/mcpservers.json"
        vars:
            - name: ansible_mcp_mcp_manifest_path
    mcp_validate_certs:
        description:
            - Whether to validate SSL certificates when using http transport.
        type: bool
        default: true
        vars:
            - name: ansible_mcp_mcp_validate_certs
"""


import json
import os

from functools import wraps
from typing import Any, Dict

from ansible.errors import AnsibleConnectionFailure
from ansible.utils.display import Display
from ansible_collections.ansible.utils.plugins.plugin_utils.connection_base import (
    PersistentConnectionBase,
)

from ansible_collections.ansible.mcp.plugins.plugin_utils.mcp import (
    MCPClient,
    Stdio,
    StreamableHTTP,
)


display = Display()


def ensure_connected(func):
    """Decorator ensuring that a connection is established before a method runs."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Check the connection status
        if not self.connected:
            display.vvv(
                f"MCP connection not established. Calling _connect() for method: {func.__name__}"
            )
            # If not connected, establish the connection
            try:
                self._connect()
            except Exception as e:
                raise AnsibleConnectionFailure(f"Failed to connect to MCP server: {e}")
        # Call the original method
        return func(self, *args, **kwargs)

    return wrapper


class Connection(PersistentConnectionBase):
    """
    Ansible persistent connection plugin for the Model Context Protocol (MCP) server.
    """

    transport = "ansible.mcp.mcp"
    has_pipelining = False

    def __init__(self, play_context, new_stdin, *args, **kwargs):
        super(Connection, self).__init__(play_context, new_stdin, *args, **kwargs)
        self._client: MCPClient | None = None
        self._connected = False
        self._transport_type: str | None = None

    @property
    def connected(self) -> bool:
        """Return True if connected to MCP server."""
        return not self._conn_closed and self._connected and self._client is not None

    def _connect(self):
        """
        Establishes the connection and performs the MCP initialization handshake.
        This runs only once per host/plugin instance.
        """
        if self.connected:
            display.vvv("[mcp] Already connected, skipping _connect()")
            return

        server_name = self.get_option("mcp_server_name")
        manifest_path = self.get_option("mcp_manifest_path") or "/opt/mcp/mcpservers.json"

        server_info = self._load_server_from_manifest(server_name, manifest_path)
        transport = self._create_transport(server_name, server_info)

        # Initialize MCP client
        self._client = MCPClient(transport)
        try:
            self._client.initialize()
        except Exception as e:
            raise AnsibleConnectionFailure(f"[mcp] MCP client initialization failed: {e}")

        self._connected = True
        display.vvv(f"[mcp] Connection to '{server_name}' successfully initialized")

    def _load_server_from_manifest(self, server_name: str, manifest_path: str) -> dict:
        """Load the MCP server info from manifest JSON."""
        if not os.path.exists(manifest_path):
            raise AnsibleConnectionFailure(f"MCP manifest not found at {manifest_path}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise AnsibleConnectionFailure(f"[mcp] Failed to parse MCP manifest JSON: {e}")

        if server_name not in manifest:
            raise AnsibleConnectionFailure(f"MCP server '{server_name}' not found in manifest")

        return manifest[server_name]

    def _create_transport(self, server_name: str, server_info: dict):
        """Create the appropriate transport based on manifest server info."""
        transport_type = server_info.get("type")

        if transport_type == "stdio":
            if "command" not in server_info:
                raise AnsibleConnectionFailure(
                    f"[mcp] Manifest for '{server_name}' missing 'command' for stdio transport"
                )
            manifest_args = server_info.get("args", [])
            plugin_args = self.get_option("mcp_server_args") or []
            cmd = [server_info["command"]] + manifest_args + plugin_args
            env = self.get_option("mcp_server_env") or {}
            display.vvv(f"[mcp] Starting stdio MCP server '{server_name}': {' '.join(cmd)}")
            return Stdio(cmd=cmd, env=env)

        elif transport_type == "http":
            url = server_info.get("url")
            if not url:
                raise AnsibleConnectionFailure(
                    f"[mcp] Manifest for '{server_name}' missing 'url' for http transport"
                )

            headers = {}
            token = self.get_option("mcp_bearer_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            display.vvv(f"[mcp] Connecting to HTTP MCP server '{server_name}': {url}")
            return StreamableHTTP(
                url=url, headers=headers, validate_certs=self.get_option("mcp_validate_certs")
            )

        else:
            raise AnsibleConnectionFailure(
                f"Invalid transport type '{transport_type}' for server '{server_name}'"
            )

    def close(self) -> None:
        """Terminate the persistent connection and reset state."""
        display.vvv("[mcp] Closing MCP connection")

        self._close_client()
        super().close()  # sets _conn_closed, _connected

    def _close_client(self) -> None:
        """Close the MCPClient if it exists and reset the reference."""
        if not self._client:
            display.vvv("[mcp] No MCP client to close")
            return

        try:
            self._client.close()
            display.vvv("[mcp] MCP client successfully closed")
        except Exception as e:
            display.warning(f"[mcp] Error closing MCP client: {e}")
        finally:
            self._client = None

    @ensure_connected
    def list_tools(self) -> Dict[str, Any]:
        """Retrieves the list of tools from the MCP server."""
        return self._client.list_tools()

    @ensure_connected
    def call_tool(self, tool: str, **kwargs: Any) -> Dict[str, Any]:
        """Calls a specific tool on the MCP server."""
        return self._client.call_tool(tool, **kwargs)

    @ensure_connected
    def validate(self, tool: str, **kwargs: Any) -> None:
        """Validates arguments against a tool's schema (client-side validation)."""
        return self._client.validate(tool, **kwargs)

    @ensure_connected
    def server_info(self) -> Dict[str, Any]:
        """Returns the cached server information from the initialization step."""
        return self._client.server_info()
