# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from ansible.errors import AnsibleConnectionFailure
from ansible.playbook.play_context import PlayContext

from ansible_collections.ansible.mcp.plugins.connection.mcp import Connection


@pytest.fixture
def manifest_file(tmp_path):
    """Create a temporary MCP manifest JSON file."""
    manifest_data = {
        "mcp-hello-world": {
            "type": "stdio",
            "command": "npx --prefix /opt/mcp/npm_installs mcp-hello-world",
            "args": [],
        },
        "aws-iam-mcp-server": {
            "type": "stdio",
            "command": "uvx awslabs.iam-mcp-server",
            "args": [],
            "package": "awslabs.iam-mcp-server",
        },
        "github-mcp-server": {
            "type": "stdio",
            "command": "/opt/mcp/bin/github-mcp-server",
            "args": ["stdio"],
            "description": "GitHub MCP Server - Access GitHub repositories, issues, and pull requests",
        },
        "remote": {"args": [], "type": "http", "url": "https://example.com/mcp"},
    }

    file_path = tmp_path / "mcpservers.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)
    yield file_path


@pytest.fixture(name="loaded_mcp_connection")
def fixture_loaded_mcp_connection(manifest_file):
    """
    Return a Connection instance with test options set.
    Network/stdio/http calls are mocked in the tests.
    """
    play_context = PlayContext()
    conn = Connection(play_context, StringIO())

    def get_option(key):
        return conn.test_options.get(key)

    # Provide a get_option helper
    conn.test_options = {
        "mcp_server_name": "remote",
        "mcp_server_args": ["--mock"],
        "mcp_server_env": {"FOO": "BAR"},
        "mcp_bearer_token": "token123",
        "mcp_validate_certs": True,
        "mcp_manifest_path": str(manifest_file),
    }
    conn.get_option = get_option

    yield conn


class TestMCPConnection:
    @patch(
        "ansible_collections.ansible.mcp.plugins.connection.mcp.MCPClient.initialize",
        return_value=None,
    )
    @patch(
        "ansible_collections.ansible.mcp.plugins.connection.mcp.Stdio",
        autospec=True,
    )
    def test_connect_stdio_transport(
        self, mock_stdio, mock_initialize, loaded_mcp_connection, manifest_file
    ):
        """Verify connection._connect() initializes stdio transport correctly."""
        conn = loaded_mcp_connection
        conn.test_options["mcp_server_name"] = "mcp-hello-world"
        conn._connected = False

        mock_transport = MagicMock()
        mock_stdio.return_value = mock_transport

        conn._connect()

        mock_stdio.assert_called_once()
        mock_initialize.assert_called_once()
        assert conn._connected is True
        assert conn._client is not None

    @patch("ansible_collections.ansible.mcp.plugins.connection.mcp.StreamableHTTP", autospec=True)
    def test_connect_http_transport(self, mock_http, loaded_mcp_connection):
        """Verify connection uses HTTP transport when configured."""
        loaded_mcp_connection._connected = False
        mock_transport = MagicMock()
        mock_http.return_value = mock_transport
        # Mock request for initialize
        mock_transport.request.return_value = {"result": {"server": "ok"}}

        loaded_mcp_connection._connect()

        mock_http.assert_called_once_with(
            url="https://example.com/mcp",
            headers={"Authorization": "Bearer token123"},
            validate_certs=True,
        )
        assert loaded_mcp_connection._connected is True
        assert loaded_mcp_connection._client is not None

    def test_connect_invalid_transport(self, loaded_mcp_connection):
        """Invalid transport type should raise."""
        """Unknown server_name should raise AnsibleConnectionFailure."""
        loaded_mcp_connection.test_options["mcp_server_name"] = "unknown-server"
        loaded_mcp_connection._connected = False
        with pytest.raises(AnsibleConnectionFailure):
            loaded_mcp_connection._connect()

    def test_list_tools_delegates_to_client(self, loaded_mcp_connection):
        """list_tools should call MCPClient.list_tools()."""
        loaded_mcp_connection._connect = MagicMock(name="_connect")
        mock_client = MagicMock()
        loaded_mcp_connection._client = mock_client
        mock_client.list_tools.return_value = {"tools": []}

        result = loaded_mcp_connection.list_tools()
        mock_client.list_tools.assert_called_once()
        assert result == {"tools": []}

    def test_close_resets_state(self, loaded_mcp_connection):
        """close() should reset client and connection state."""
        loaded_mcp_connection._connect = MagicMock(name="_connect")
        mock_client = MagicMock()
        loaded_mcp_connection._client = mock_client
        client_ref = loaded_mcp_connection._client

        loaded_mcp_connection.close()

        client_ref.close.assert_called_once()
        assert loaded_mcp_connection._connected is False
        assert loaded_mcp_connection._client is None
