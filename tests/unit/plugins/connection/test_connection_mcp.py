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


@pytest.fixture
def empty_manifest_file(tmp_path):
    """Create a temporary empty MCP manifest JSON file."""
    file_path = tmp_path / "empty.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({}, f)
    yield file_path


@pytest.fixture
def malformed_manifest_file(tmp_path):
    """Create a temporary malformed MCP manifest JSON file."""
    file_path = tmp_path / "malformed.json"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("{invalid json")
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
        "server_name": "remote",
        "server_args": ["--mock"],
        "server_env": {"FOO": "BAR"},
        "bearer_token": "token123",
        "validate_certs": True,
        "manifest_path": str(manifest_file),
        "persistent_connect_timeout": 15,
        "persistent_command_timeout": 15,
        "persistent_log_messages": False,
    }
    conn.get_option = get_option

    yield conn


class TestMCPConnection:
    def test_load_server_from_manifest_success(self, loaded_mcp_connection, manifest_file):
        """Should successfully load server info for a known server."""
        server_name = "github-mcp-server"
        expected_info = {
            "type": "stdio",
            "command": "/opt/mcp/bin/github-mcp-server",
            "args": ["stdio"],
            "description": "GitHub MCP Server - Access GitHub repositories, issues, and pull requests",
        }

        info = loaded_mcp_connection._load_server_from_manifest(server_name, str(manifest_file))
        assert info == expected_info

    def test_load_server_from_manifest_file_not_found(self, loaded_mcp_connection):
        """Should raise AnsibleConnectionFailure if manifest file is not found."""
        with pytest.raises(AnsibleConnectionFailure, match="MCP manifest not found"):
            loaded_mcp_connection._load_server_from_manifest(
                "any-server", "/nonexistent/manifest.json"
            )

    def test_load_server_from_manifest_server_not_found(self, loaded_mcp_connection, manifest_file):
        """Should raise AnsibleConnectionFailure if the server is not in the manifest."""
        server_name = "non-existent-server"
        with pytest.raises(
            AnsibleConnectionFailure, match=f"MCP server '{server_name}' not found in manifest"
        ):
            loaded_mcp_connection._load_server_from_manifest(server_name, str(manifest_file))

    def test_create_transport_stdio_missing_command(self, loaded_mcp_connection):
        """Should raise AnsibleConnectionFailure if stdio manifest entry is missing 'command'."""
        server_name = "invalid_stdio"
        server_info = {"type": "stdio"}
        with pytest.raises(
            AnsibleConnectionFailure, match=f"Manifest for '{server_name}' missing 'command'"
        ):
            loaded_mcp_connection._create_transport(server_name, server_info)

    @patch("ansible_collections.ansible.mcp.plugins.connection.mcp.StreamableHTTP", autospec=True)
    def test_create_transport_http_success_no_token(self, mock_http, loaded_mcp_connection):
        """Should correctly create an HTTP transport without a bearer token."""
        server_name = "remote"
        server_info = {"type": "http", "url": "https://example.com/mcp"}

        loaded_mcp_connection.test_options["bearer_token"] = None  # No token

        loaded_mcp_connection._create_transport(server_name, server_info)

        mock_http.assert_called_once_with(
            url="https://example.com/mcp",
            headers={},
            validate_certs=True,
        )

    def test_load_server_from_manifest_json_decode_error(
        self, loaded_mcp_connection, malformed_manifest_file
    ):
        """Should raise AnsibleConnectionFailure for a malformed JSON file."""
        with pytest.raises(AnsibleConnectionFailure, match="Failed to parse MCP manifest JSON"):
            loaded_mcp_connection._load_server_from_manifest(
                "any-server", str(malformed_manifest_file)
            )

    @patch("ansible_collections.ansible.mcp.plugins.connection.mcp.Stdio", autospec=True)
    def test_create_transport_stdio_success(self, mock_stdio, loaded_mcp_connection):
        """Should correctly create a Stdio transport for a stdio server."""
        server_name = "github-mcp-server"
        server_info = {
            "type": "stdio",
            "command": "/opt/mcp/bin/github-mcp-server",
            "args": ["stdio"],
        }

        loaded_mcp_connection.test_options["server_args"] = ["--verbose"]
        loaded_mcp_connection.test_options["server_env"] = {"DEBUG": "1"}

        loaded_mcp_connection._create_transport(server_name, server_info)

        expected_cmd = [
            "/opt/mcp/bin/github-mcp-server",
            "stdio",
            "--verbose",
        ]
        mock_stdio.assert_called_once_with(
            cmd=expected_cmd,
            env={"DEBUG": "1"},
        )

    @patch("ansible_collections.ansible.mcp.plugins.connection.mcp.StreamableHTTP", autospec=True)
    def test_create_transport_http_success_with_token(self, mock_http, loaded_mcp_connection):
        """Should correctly create an HTTP transport with a bearer token and validation."""
        server_name = "remote"
        server_info = {"type": "http", "url": "https://example.com/mcp"}

        loaded_mcp_connection.test_options["bearer_token"] = "test-token"
        loaded_mcp_connection.test_options["validate_certs"] = False

        loaded_mcp_connection._create_transport(server_name, server_info)

        mock_http.assert_called_once_with(
            url="https://example.com/mcp",
            headers={"Authorization": "Bearer test-token"},
            validate_certs=False,
        )

    def test_create_transport_http_missing_url(self, loaded_mcp_connection):
        """Should raise AnsibleConnectionFailure if http manifest entry is missing 'url'."""
        server_name = "invalid_http"
        server_info = {"type": "http"}
        with pytest.raises(
            AnsibleConnectionFailure, match=f"Manifest for '{server_name}' missing 'url'"
        ):
            loaded_mcp_connection._create_transport(server_name, server_info)

    def test_create_transport_unknown_transport_type(self, loaded_mcp_connection):
        """Should raise AnsibleConnectionFailure for an unknown transport type."""
        server_name = "unknown_transport"
        server_info = {"type": "ftp"}
        with pytest.raises(
            AnsibleConnectionFailure,
            match=f"Invalid transport type 'ftp' for server '{server_name}'",
        ):
            loaded_mcp_connection._create_transport(server_name, server_info)

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
        conn.test_options["server_name"] = "mcp-hello-world"

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
        loaded_mcp_connection.test_options["server_name"] = "unknown-server"
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
