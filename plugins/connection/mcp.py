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
    mcp_server_transport:
        description:
            - The transport method to use for communicating with the MCP server.
        type: str
        choices: [ 'stdio', 'http' ]
        default: stdio
    mcp_server_path:
        description:
            - The name of the server binary when using stdio transport.
            - The URL to the server when using http transport.
        type: str
        required: true
    mcp_server_args:
        description:
            - Additional command line arguments to pass to the server when using stdio transport.
        type: list
        default: []
    mcp_server_env:
        description:
            - Additional environment variables to pass to the server when using stdio transport.
            - These are merged with the current environment.
            - Ignored when using http transport.
        type: dict
    mcp_bearer_token:
        description:
            - Bearer token for authenticating to the MCP server when using http transport.
            - Ignored when using stdio transport.
        type: str
    mcp_manifest_path:
        description:
            - Path to MCP manifest JSON file to resolve server executable paths for C(stdio).
            - This is optional and will look for TBD default locations if not specified.
        type: str
        default: null
    mcp_validate_certs:
        description:
            - Whether to validate SSL certificates when using C(http) transport.
        type: bool
        default: true
"""


EXAMPLES = r"""
# Example 1: Use STDIO transport to communicate with a local server binary
- name: Call a tool on a local MCP server
  ansible.mcp.mcp_tool:
    tool: file.readFile
    args:
      path: /etc/hosts
  vars:
    ansible_connection: mcp
    ansible_mcp_mcp_server_transport: stdio
    ansible_mcp_mcp_server_path: /usr/local/bin/my-mcp-server
    ansible_mcp_mcp_server_args: ["--mode", "stdio"]

# Example 2: Use Streamable HTTP transport with a bearer token
- name: List tools from a remote GitHub MCP endpoint
  ansible.mcp.mcp_tool:
    tool: tools/list
  vars:
    ansible_connection: mcp
    ansible_mcp_mcp_server_transport: http
    ansible_mcp_mcp_server_path: https://api.githubcopilot.com/mcp/
    ansible_mcp_mcp_bearer_token: "{{ github_pat_secret }}"
"""


from functools import wraps
import traceback
from typing import Optional, Any, Dict, List
from ansible.utils.plugins.plugin_utils.connection_base import PersistentConnectionBase
from ansible.errors import AnsibleConnectionFailure
from ansible.utils.display import Display

from ansible_collections.ansible.mcp.plugins.plugin_utils.mcp import (
    MCPClient, Stdio, StreamableHTTP, MCPError,
)

display = Display()


def ensure_connected(func):
    """Decorator ensuring that a connection is established before a method runs."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Check the connection status
        if not self.connected:
            display.vvv(f"MCP connection not established. Calling _connect() for method: {func.__name__}")
            # If not connected, establish the connection
            self._connect()
        # Call the original method
        return func(self, *args, **kwargs)
    return wrapper


class Connection(PersistentConnectionBase):
    """
    Ansible persistent connection plugin for the Model Context Protocol (MCP) server.
    """
    # Ansible connection type identifier
    transport = 'mcp'
    has_pipelining = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client: MCPClient | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        """Return True if connected to MCP server."""
        return bool(self._connected and self.client)

    def _connect(self):
        """
        Establishes the connection and performs the MCP initialization handshake.
        This runs only once per host/plugin instance.
        """
        if self._connected:
            return

        transport_type = self.get_option("mcp_server_transport")
        server_path = self.get_option("mcp_server_path")

        try:
            if transport_type == "stdio":
                # Retrieve STDIO specific options
                cmd = [server_path] + (self.get_option("mcp_server_args") or [])
                env = self.get_option("mcp_server_env") or {}
                display.vvv(f"[mcp] Starting stdio MCP server: {' '.join(cmd)}")
            
                # Initializes Stdio, which spawns the process
                transport = Stdio(cmd=cmd, env=env)
            elif transport_type == "http": 
                headers = {}
          
                # Retrieve HTTP specific options
                validate_certs = self.get_option("mcp_validate_certs")
                token = self.get_option("mcp_bearer_token")
                if token:
                    headers['Authorization'] = f'Bearer {token}'
                
                display.vvv(f"[mcp] Connecting to MCP server via HTTP: {server_path}")               
    
                # Initializes StreamableHTTP
                transport = StreamableHTTP(
                    url=server_path, 
                    headers=headers, 
                    validate_certs=validate_certs
                    )
            else:
                raise AnsibleConnectionFailure(f"Invalid MCP transport: {transport_type}")

            # Initialize MCP client
            self.client = MCPClient(transport)
            self.client.initialize()
            self._connected = True
            display.vvv("[mcp] Connection successfully initialized")

        except Exception as e:
            display.error(traceback.format_exc())
            raise AnsibleConnectionFailure(f"Failed to initialize MCP connection: {e}")

    def close(self) -> None:
        """Terminate the persistent connection."""
        display.vvv("[mcp] Closing MCP connection")
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                display.warning(f"[mcp] Error closing connection: {e}")
            finally:
                self._connected = False
                self.client = None

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
