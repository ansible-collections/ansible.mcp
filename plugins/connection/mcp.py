# -*- coding: utf-8 -*-
# Copyright: (c) 2025, Ansible Project
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import subprocess
import time
import signal
from functools import wraps

from ansible.errors import AnsibleConnectionFailure, AnsibleError
from ansible.utils.display import Display
from ansible_collections.ansible.utils.plugins.plugin_utils.connection_base import PersistentConnectionBase

DOCUMENTATION = """
author:
- Ansible Team
name: mcp
short_description: Generic persistent connection plugin for MCP (Model Context Protocol) servers
description:
- This connection plugin provides a persistent connection to MCP servers using the Model Context Protocol
- Maintains a long-running MCP server process for the duration of the playbook run
- Supports JSON-RPC communication with MCP servers for tool execution
- Generic implementation that works with any MCP server that follows the protocol
version_added: "1.0.0"
requirements:
- MCP server binary must be available and executable
extends_documentation_fragment:
- ansible.netcommon.connection_persistent
options:
  mcp_server_path:
    description:
    - Path to the MCP server binary that will be executed
    - The server must support stdio transport for JSON-RPC communication
    type: str
    required: true
    vars:
    - name: ansible_mcp_server_path
    env:
    - name: ANSIBLE_MCP_SERVER_PATH
  mcp_server_args:
    description:
    - Additional command-line arguments to pass to the MCP server
    - Common arguments include transport type (e.g., 'stdio')
    type: list
    elements: str
    default: ['stdio']
    vars:
    - name: ansible_mcp_server_args
    env:
    - name: ANSIBLE_MCP_SERVER_ARGS
  mcp_server_env:
    description:
    - Environment variables to set for the MCP server process
    - Use this to pass authentication tokens, API keys, etc.
    type: dict
    default: {}
    vars:
    - name: ansible_mcp_server_env
  mcp_client_info:
    description:
    - Client information to send during MCP initialization
    - Contains name and version of the client
    type: dict
    default:
      name: "ansible-mcp-client"
      version: "1.0.0"
    vars:
    - name: ansible_mcp_client_info
  mcp_protocol_version:
    description:
    - MCP protocol version to use for communication
    type: str
    default: "2024-11-05"
    vars:
    - name: ansible_mcp_protocol_version
  mcp_timeout:
    description:
    - Timeout in seconds for MCP server operations
    type: int
    default: 30
    vars:
    - name: ansible_mcp_timeout
  mcp_retries:
    description:
    - Number of retry attempts for MCP server communication
    type: int
    default: 3
    vars:
    - name: ansible_mcp_retries
"""

EXAMPLES = """
# Example inventory configuration
[mcp_servers]
github_server ansible_connection=ansible.mcp.mcp ansible_mcp_server_path=/usr/local/bin/github-mcp-server
openai_server ansible_connection=ansible.mcp.mcp ansible_mcp_server_path=/usr/local/bin/openai-mcp-server

# Example playbook task using the connection
- name: Get tools from MCP server
  ansible.mcp.mcp_get_tools:
  delegate_to: github_server

- name: Run MCP tool
  ansible.mcp.mcp_run_tools:
    tool_name: search_repositories
    tool_args:
      query: "user:octocat"
  delegate_to: github_server
"""

display = Display()


def ensure_connected(func):
    """Decorator to ensure MCP connection is established before method execution."""
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        if not self._connected:
            self._connect()
        return func(self, *args, **kwargs)
    return wrapped


class Connection(PersistentConnectionBase):
    """MCP (Model Context Protocol) persistent connection plugin."""

    transport = "ansible.mcp.mcp"
    has_pipelining = False

    def __init__(self, play_context, new_stdin, *args, **kwargs):
        super(Connection, self).__init__(play_context, new_stdin, *args, **kwargs)
        
        self._mcp_process = None
        self._mcp_initialized = False
        self._tools_cache = None
        self._request_id_counter = 0
        
        # Connection state
        self._connected = False
        self._socket_path = None

    def _connect(self):
        """Establish connection to MCP server."""
        if self._connected:
            return self

        display.vvv("Starting MCP server connection", host=self._play_context.remote_addr)
        
        try:
            self._start_mcp_server()
            self._initialize_mcp_protocol()
            self._connected = True
            display.vvv("MCP server connection established", host=self._play_context.remote_addr)
            return self
        except Exception as e:
            self.close()
            raise AnsibleConnectionFailure(f"Failed to connect to MCP server: {str(e)}")

    def _start_mcp_server(self):
        """Start the MCP server process."""
        mcp_server_path = self.get_option('mcp_server_path')
        mcp_server_args = self.get_option('mcp_server_args') or ['stdio']
        mcp_server_env = self.get_option('mcp_server_env') or {}
        
        if not mcp_server_path:
            raise AnsibleConnectionFailure("mcp_server_path is required but not specified")
        
        if not os.path.isfile(mcp_server_path):
            raise AnsibleConnectionFailure(f"MCP server binary not found at: {mcp_server_path}")
        
        if not os.access(mcp_server_path, os.X_OK):
            raise AnsibleConnectionFailure(f"MCP server binary is not executable: {mcp_server_path}")
        
        # Prepare command and environment
        cmd = [mcp_server_path] + mcp_server_args
        env = os.environ.copy()
        env.update(mcp_server_env)
        
        display.vvvv(f"Starting MCP server: {' '.join(cmd)}", host=self._play_context.remote_addr)
        
        try:
            self._mcp_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=0  # Unbuffered for real-time communication
            )
            
            # Give the server a moment to start
            time.sleep(0.1)
            
            # Check if process started successfully
            if self._mcp_process.poll() is not None:
                stdout, stderr = self._mcp_process.communicate()
                raise AnsibleConnectionFailure(
                    f"MCP server exited immediately. stdout: {stdout}, stderr: {stderr}"
                )
                
        except Exception as e:
            raise AnsibleConnectionFailure(f"Failed to start MCP server: {str(e)}")

    def _initialize_mcp_protocol(self):
        """Initialize MCP protocol with the server."""
        client_info = self.get_option('mcp_client_info') or {
            "name": "ansible-mcp-client",
            "version": "1.0.0"
        }
        protocol_version = self.get_option('mcp_protocol_version') or "2024-11-05"
        
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": self._get_next_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": client_info
            }
        }
        
        display.vvvv("Sending MCP initialize request", host=self._play_context.remote_addr)
        response = self._send_mcp_request(init_request)
        
        if 'error' in response:
            error = response['error']
            raise AnsibleConnectionFailure(
                f"MCP initialization failed: {error.get('message', 'Unknown error')} "
                f"(code: {error.get('code', 'unknown')})"
            )
        
        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        self._send_mcp_notification(initialized_notification)
        self._mcp_initialized = True
        display.vvvv("MCP protocol initialized successfully", host=self._play_context.remote_addr)

    def _get_next_request_id(self):
        """Generate next request ID for JSON-RPC."""
        self._request_id_counter += 1
        return str(self._request_id_counter)

    def _send_mcp_request(self, request):
        """Send JSON-RPC request to MCP server and return response."""
        if not self._mcp_process:
            raise AnsibleConnectionFailure("MCP server process not started")
        
        timeout = self.get_option('mcp_timeout') or 30
        request_json = json.dumps(request) + "\n"
        
        display.vvvv(f"Sending MCP request: {request_json.strip()}", host=self._play_context.remote_addr)
        
        try:
            # Send request
            self._mcp_process.stdin.write(request_json)
            self._mcp_process.stdin.flush()
            
            # Read response with timeout
            response_line = self._read_mcp_response_with_timeout(timeout)
            response = json.loads(response_line)
            
            display.vvvv(f"Received MCP response: {json.dumps(response)}", host=self._play_context.remote_addr)
            return response
            
        except json.JSONDecodeError as e:
            raise AnsibleConnectionFailure(f"Invalid JSON response from MCP server: {str(e)}")
        except Exception as e:
            raise AnsibleConnectionFailure(f"Error communicating with MCP server: {str(e)}")

    def _send_mcp_notification(self, notification):
        """Send JSON-RPC notification to MCP server (no response expected)."""
        if not self._mcp_process:
            raise AnsibleConnectionFailure("MCP server process not started")
        
        notification_json = json.dumps(notification) + "\n"
        display.vvvv(f"Sending MCP notification: {notification_json.strip()}", host=self._play_context.remote_addr)
        
        try:
            self._mcp_process.stdin.write(notification_json)
            self._mcp_process.stdin.flush()
        except Exception as e:
            raise AnsibleConnectionFailure(f"Error sending notification to MCP server: {str(e)}")

    def _read_mcp_response_with_timeout(self, timeout):
        """Read response from MCP server with timeout."""
        def timeout_handler(signum, frame):
            raise AnsibleConnectionFailure(f"MCP server response timeout after {timeout} seconds")
        
        # Set up timeout
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        try:
            response_line = self._mcp_process.stdout.readline()
            if not response_line:
                # Check if process has terminated
                if self._mcp_process.poll() is not None:
                    stdout, stderr = self._mcp_process.communicate()
                    raise AnsibleConnectionFailure(
                        f"MCP server process terminated unexpectedly. stderr: {stderr}"
                    )
                raise AnsibleConnectionFailure("No response from MCP server")
            return response_line.strip()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    @ensure_connected
    def get_tools(self, tool_name=None):
        """Get available tools from MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_request_id(),
            "method": "tools/list"
        }
        
        response = self._send_mcp_request(request)
        
        if 'error' in response:
            error = response['error']
            raise AnsibleError(
                f"Failed to get tools from MCP server: {error.get('message', 'Unknown error')} "
                f"(code: {error.get('code', 'unknown')})"
            )
        
        tools = response.get('result', {}).get('tools', [])
        
        # Cache tools for future use
        self._tools_cache = {tool['name']: tool for tool in tools}
        
        if tool_name:
            # Return specific tool if requested
            return self._tools_cache.get(tool_name)
        
        return tools

    @ensure_connected
    def call_tool(self, tool_name, tool_arguments=None):
        """Execute a tool on the MCP server."""
        if tool_arguments is None:
            tool_arguments = {}
        
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_arguments
            }
        }
        
        response = self._send_mcp_request(request)
        
        if 'error' in response:
            error = response['error']
            raise AnsibleError(
                f"MCP tool '{tool_name}' failed: {error.get('message', 'Unknown error')} "
                f"(code: {error.get('code', 'unknown')})"
            )
        
        return response.get('result', {})

    def close(self):
        """Close the MCP connection and cleanup."""
        display.vvv("Closing MCP server connection", host=self._play_context.remote_addr)
        
        if self._mcp_process:
            try:
                # Try to terminate gracefully first
                self._mcp_process.terminate()
                
                # Wait for process to terminate
                try:
                    self._mcp_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    display.vvv("Force killing MCP server process", host=self._play_context.remote_addr)
                    self._mcp_process.kill()
                    self._mcp_process.wait()
                
            except Exception as e:
                display.vvv(f"Error closing MCP process: {str(e)}", host=self._play_context.remote_addr)
            
            finally:
                self._mcp_process = None
        
        self._connected = False
        self._mcp_initialized = False
        self._tools_cache = None
        
        super(Connection, self).close()

    @property
    def connected(self):
        """Return connection status."""
        return self._connected and self._mcp_process and self._mcp_process.poll() is None
