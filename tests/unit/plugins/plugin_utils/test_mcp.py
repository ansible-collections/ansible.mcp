# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest

from ansible_collections.ansible.mcp.plugins.plugin_utils.mcp import MCPClient, Transport


class MockTransport(Transport):
    def __init__(self):
        self.connected = False
        self.requests = []
        self.notifications = []

    def connect(self):
        self.connected = True

    def notify(self, data):
        self.notifications.append(data)

    def request(self, data):
        self.requests.append(data)
        method = data.get("method")
        request_id = data.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "serverInfo": {"name": "test-server", "version": "1.0.0"},
                },
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "test_tool",
                            "description": "Test tool",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"param": {"type": "string"}},
                                "required": ["param"],
                            },
                        }
                    ]
                },
            }
        elif method == "tools/call":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": "success"}]},
            }

        return {"jsonrpc": "2.0", "id": request_id, "error": {"message": "Unknown method"}}

    def close(self):
        self.connected = False


def test_client_initialization():
    """Test basic client initialization."""
    transport = MockTransport()
    client = MCPClient(transport)

    assert client.transport == transport
    assert client._connected is False
    assert client._server_info is None


def test_client_initialize():
    """Test client initialize method."""
    transport = MockTransport()
    client = MCPClient(transport)

    client.initialize()

    assert client._connected is True
    assert transport.connected is True
    assert client._server_info is not None
    assert len(transport.requests) == 1
    assert len(transport.notifications) == 1


def test_list_tools():
    """Test listing tools."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    tools = client.list_tools()

    assert "tools" in tools
    assert len(tools["tools"]) == 1
    assert tools["tools"][0]["name"] == "test_tool"


def test_get_tool():
    """Test getting specific tool."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    tool = client.get_tool("test_tool")

    assert tool["name"] == "test_tool"
    assert "inputSchema" in tool


def test_get_tool_not_found():
    """Test getting non-existent tool raises ValueError."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    with pytest.raises(ValueError, match="not found"):
        client.get_tool("nonexistent")


def test_call_tool():
    """Test calling a tool."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    result = client.call_tool("test_tool", param="value")

    assert "content" in result
    assert result["content"][0]["text"] == "success"


def test_validate_success():
    """Test successful validation."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    # Should not raise
    client.validate("test_tool", param="value")


def test_validate_missing_required():
    """Test validation with missing required parameter."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    with pytest.raises(ValueError, match="missing required parameters"):
        client.validate("test_tool")


def test_validate_wrong_type():
    """Test validation with wrong parameter type."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    with pytest.raises(ValueError, match="should be of type"):
        client.validate("test_tool", param=123)  # Should be string


def test_server_info():
    """Test getting server info."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    info = client.server_info()

    assert "serverInfo" in info
    assert info["serverInfo"]["name"] == "test-server"


def test_server_info_not_initialized():
    """Test getting server info before initialization raises error."""
    transport = MockTransport()
    client = MCPClient(transport)

    with pytest.raises(RuntimeError, match="not initialized"):
        client.server_info()


def test_close():
    """Test closing the client."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    client.close()

    assert transport.connected is False


def test_request_id_increments():
    """Test that request IDs increment."""
    transport = MockTransport()
    client = MCPClient(transport)

    id1 = client._get_next_id()
    id2 = client._get_next_id()
    id3 = client._get_next_id()

    assert id1 == 1
    assert id2 == 2
    assert id3 == 3


def test_build_request_without_params():
    """Test building a request without parameters."""
    transport = MockTransport()
    client = MCPClient(transport)

    request = client._build_request("test/method")

    assert request["jsonrpc"] == "2.0"
    assert request["method"] == "test/method"
    assert request["id"] == 1
    assert "params" not in request


def test_build_request_with_params():
    """Test building a request with parameters."""
    transport = MockTransport()
    client = MCPClient(transport)

    params = {"key": "value", "number": 42}
    request = client._build_request("test/method", params)

    assert request["jsonrpc"] == "2.0"
    assert request["method"] == "test/method"
    assert request["id"] == 1
    assert request["params"] == params


def test_tools_cache():
    """Test that tools list is cached."""
    transport = MockTransport()
    client = MCPClient(transport)
    client.initialize()

    # First call
    tools1 = client.list_tools()
    request_count = len(transport.requests)

    # Second call
    tools2 = client.list_tools()

    # Should not make another request
    assert len(transport.requests) == request_count
    assert tools1 is tools2
