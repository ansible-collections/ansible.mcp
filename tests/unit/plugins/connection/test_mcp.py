# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest
from unittest.mock import patch, MagicMock

from io import StringIO
from ansible.errors import AnsibleConnectionFailure
from ansible.playbook.play_context import PlayContext
from ansible.plugins.loader import connection_loader


@pytest.fixture(name="loaded_mcp_connection")
def fixture_loaded_mcp_connection():
    """Fixture to load the ansible.mcp connection plugin via the loader."""
    conn = connection_loader.get("ansible.mcp.mcp", PlayContext(), StringIO())

    # Mock the connection internals
    conn._connect = MagicMock()
    conn.client = MagicMock()
    conn._connected = True
    conn.test_options = {
        "mcp_server_transport": "stdio",
        "mcp_server_path": "/usr/bin/mcp-server",
        "mcp_server_args": ["--mock"],
        "mcp_server_env": {"FOO": "BAR"},
        "mcp_bearer_token": None,
    }
    conn.get_option = MagicMock(side_effect=conn.test_options.get)
    return conn


class TestMCPConnection:
    @patch(
        "ansible.mcp.plugins.connection.mcp.MCPClient.initialize",
        return_value=None,
    )
    @patch(
        "ansible.mcp.plugins.connection.mcp.Stdio",
        autospec=True,
    )
    def test_connect_stdio_transport(self, mock_stdio, mock_initialize, loaded_mcp_connection):
        """Verify connection._connect() initializes stdio transport correctly."""
        conn = loaded_mcp_connection
        conn._connected = False

        mock_transport = MagicMock()
        mock_stdio.return_value = mock_transport

        conn._connect()

        mock_stdio.assert_called_once()
        mock_initialize.assert_called_once()
        assert conn._connected is True

    @patch("ansible.mcp.plugins.connection.mcp.StreamableHTTP", autospec=True)
    def test_connect_http_transport(self, mock_http, loaded_mcp_connection):
        """Verify connection uses HTTP transport when configured."""
        conn = loaded_mcp_connection
        conn.test_options["mcp_server_transport"] = "http"
        conn.test_options["mcp_server_path"] = "https://example.org"
        conn.test_options["mcp_bearer_token"] = "token123"
        conn._connected = False

        mock_transport = MagicMock()
        mock_http.return_value = mock_transport
        conn.client = MagicMock()

        conn._connect()

        mock_http.assert_called_once_with(
            url="https://example.org",
            headers={"Authorization": "Bearer token123"},
        )

    def test_connect_invalid_transport(self, loaded_mcp_connection):
        """Invalid transport type should raise."""
        conn = loaded_mcp_connection
        conn.test_options["mcp_server_transport"] = "invalid"
        conn._connected = False

        with pytest.raises(AnsibleConnectionFailure):
            conn._connect()

    def test_list_tools_delegates_to_client(self, loaded_mcp_connection):
        """list_tools should call MCPClient.list_tools()."""
        conn = loaded_mcp_connection
        conn.client.list_tools.return_value = {"tools": []}

        result = conn.list_tools()
        conn.client.list_tools.assert_called_once()
        assert result == {"tools": []}

    def test_close_resets_state(self, loaded_mcp_connection):
        """close() should reset client and connection state."""
        conn = loaded_mcp_connection
        conn.client.close = MagicMock()
        conn._connected = True

        conn.close()

        conn.client.close.assert_called_once()
        assert conn._connected is False
        assert conn.client is None
