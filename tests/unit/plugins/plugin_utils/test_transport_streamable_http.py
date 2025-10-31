# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function


__metaclass__ = type


import json

from unittest.mock import Mock, patch

import pytest

from ansible_collections.ansible.mcp.plugins.plugin_utils.transport import StreamableHTTP


@pytest.fixture
def streamable_http():
    url = "http://localhost:8080"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
    }
    return StreamableHTTP(url, headers, validate_certs=False)


@pytest.fixture
def mock_response():
    response = Mock()
    response.headers = {}
    response.getcode.return_value = 200
    response.read.return_value = b'{"result": "success"}'
    return response


@pytest.mark.parametrize(
    "url,headers,expected_headers",
    [
        (
            "https://example.com/mcp",
            {"Authorization": "Bearer token123"},
            {"Authorization": "Bearer token123"},
        ),
        ("https://example.com/mcp", None, {}),
        ("https://example.com/mcp", {}, {}),
    ],
)
def test_init(url, headers, expected_headers):
    """Test StreamableHTTP initialization with various header configurations."""
    client = StreamableHTTP(url, headers, validate_certs=False)

    assert client.url == url
    assert client._headers == expected_headers
    assert client._session_id is None


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_notify_success(mock_open_url, streamable_http, mock_response):
    mock_response.getcode.return_value = 202
    mock_open_url.return_value = mock_response

    data = {"jsonrpc": "2.0", "method": "test", "params": {}}

    # Should not raise any exceptions
    streamable_http.notify(data)

    # Verify open_url was called correctly
    mock_open_url.assert_called_once()
    call_args = mock_open_url.call_args
    assert call_args[0][0] == "http://localhost:8080"
    assert call_args[1]["method"] == "POST"
    assert json.loads(call_args[1]["data"]) == data
    assert call_args[1]["validate_certs"] is False


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_notify_with_session_id(mock_open_url, streamable_http, mock_response):
    mock_response.getcode.return_value = 202
    mock_response.headers = {"Mcp-Session-Id": "session123"}
    mock_open_url.return_value = mock_response

    data = {"jsonrpc": "2.0", "method": "test", "params": {}}

    streamable_http.notify(data)

    # Verify session ID was extracted
    assert streamable_http._session_id == "session123"


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_notify_http_error(mock_open_url, streamable_http):
    mock_open_url.side_effect = Exception("Connection failed")

    data = {"jsonrpc": "2.0", "method": "test", "params": {}}

    with pytest.raises(Exception, match="Failed to send notification: Connection failed"):
        streamable_http.notify(data)


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_request_success(mock_open_url, streamable_http, mock_response):
    expected_response = {"jsonrpc": "2.0", "result": "success", "id": 1}
    mock_response.read.return_value = json.dumps(expected_response).encode("utf-8")
    mock_open_url.return_value = mock_response

    data = {"jsonrpc": "2.0", "method": "test", "id": 1}

    result = streamable_http.request(data)

    assert result == expected_response

    # Verify open_url was called correctly
    mock_open_url.assert_called_once()
    call_args = mock_open_url.call_args
    assert call_args[0][0] == "http://localhost:8080"
    assert call_args[1]["method"] == "POST"
    assert json.loads(call_args[1]["data"]) == data


@pytest.mark.parametrize(
    "status_code,method_name",
    [
        (400, "notify"),
        (500, "request"),
    ],
)
@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_wrong_status_codes(
    mock_open_url, streamable_http, mock_response, status_code, method_name
):
    """Test handling of wrong HTTP status codes."""
    mock_response.getcode.return_value = status_code
    mock_open_url.return_value = mock_response

    data = {"jsonrpc": "2.0", "method": "test", "id": 1}

    with pytest.raises(Exception, match=f"Unexpected response code: {status_code}"):
        if method_name == "notify":
            streamable_http.notify(data)
        else:
            streamable_http.request(data)


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_request_invalid_json(mock_open_url, streamable_http, mock_response):
    mock_response.read.return_value = b"invalid json"
    mock_open_url.return_value = mock_response

    data = {"jsonrpc": "2.0", "method": "test", "id": 1}

    with pytest.raises(Exception, match="Invalid JSON response"):
        streamable_http.request(data)


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_request_with_session_id(mock_open_url, streamable_http, mock_response):
    expected_response = {"jsonrpc": "2.0", "result": "success", "id": 1}
    mock_response.read.return_value = json.dumps(expected_response).encode("utf-8")
    mock_response.headers = {"Mcp-Session-Id": "session456"}
    mock_open_url.return_value = mock_response

    data = {"jsonrpc": "2.0", "method": "test", "id": 1}

    result = streamable_http.request(data)

    assert result == expected_response
    assert streamable_http._session_id == "session456"


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_request_http_error(mock_open_url, streamable_http):
    mock_open_url.side_effect = Exception("Network error")

    data = {"jsonrpc": "2.0", "method": "test", "id": 1}

    with pytest.raises(Exception, match="Failed to send request: Network error"):
        streamable_http.request(data)


def test_build_headers_default():
    client = StreamableHTTP("http://localhost:8080")

    headers = client._build_headers()

    expected = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
    }
    assert headers == expected


def test_build_headers_with_custom_headers():
    custom_headers = {"Authorization": "Bearer token", "X-Custom": "value"}
    client = StreamableHTTP("http://localhost:8080", custom_headers)

    headers = client._build_headers()

    expected = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
        "Authorization": "Bearer token",
        "X-Custom": "value",
    }
    assert headers == expected


def test_build_headers_with_session_id():
    client = StreamableHTTP("http://localhost:8080")
    client._session_id = "session789"

    headers = client._build_headers()

    expected = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
        "Mcp-Session-Id": "session789",
    }
    assert headers == expected


def test_build_headers_custom_overrides_default():
    custom_headers = {"Content-Type": "application/xml"}
    client = StreamableHTTP("http://localhost:8080", custom_headers)

    headers = client._build_headers()

    assert headers["Content-Type"] == "application/xml"
    assert headers["Accept"] == "application/json, text/event-stream"
    assert headers["MCP-Protocol-Version"] == "2025-06-18"


@pytest.mark.parametrize(
    "headers,expected_session_id",
    [
        ({"Mcp-Session-Id": "session123"}, "session123"),
        ({}, None),
        ({"Mcp-Session-Id": ""}, ""),
    ],
)
def test_extract_session_id(streamable_http, headers, expected_session_id):
    """Test extracting session ID from various header configurations."""
    response = Mock()
    response.headers = headers

    streamable_http._extract_session_id(response)

    assert streamable_http._session_id == expected_session_id


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_session_id_persists_across_requests(mock_open_url, streamable_http):
    # First request - no session ID
    response1 = Mock()
    response1.getcode.return_value = 200
    response1.read.return_value = json.dumps({"result": "success"}).encode("utf-8")
    response1.headers = {"Mcp-Session-Id": "session123"}

    # Second request - should include session ID
    response2 = Mock()
    response2.getcode.return_value = 200
    response2.read.return_value = json.dumps({"result": "success2"}).encode("utf-8")
    response2.headers = {}

    mock_open_url.side_effect = [response1, response2]

    # First request
    data1 = {"jsonrpc": "2.0", "method": "test1", "id": 1}
    result1 = streamable_http.request(data1)

    assert result1 == {"result": "success"}
    assert streamable_http._session_id == "session123"

    # Second request
    data2 = {"jsonrpc": "2.0", "method": "test2", "id": 2}
    result2 = streamable_http.request(data2)

    assert result2 == {"result": "success2"}
    assert streamable_http._session_id == "session123"

    # Verify second request included session ID
    second_call_args = mock_open_url.call_args_list[1]
    headers = second_call_args[1]["headers"]
    assert headers["Mcp-Session-Id"] == "session123"


@patch("ansible_collections.ansible.mcp.plugins.plugin_utils.transport.open_url")
def test_session_id_updates_on_new_session(mock_open_url, streamable_http):
    # First request
    response1 = Mock()
    response1.getcode.return_value = 200
    response1.read.return_value = json.dumps({"result": "success"}).encode("utf-8")
    response1.headers = {"Mcp-Session-Id": "session123"}

    # Second request with new session ID
    response2 = Mock()
    response2.getcode.return_value = 200
    response2.read.return_value = json.dumps({"result": "success2"}).encode("utf-8")
    response2.headers = {"Mcp-Session-Id": "session456"}

    mock_open_url.side_effect = [response1, response2]

    # First request
    data1 = {"jsonrpc": "2.0", "method": "test1", "id": 1}
    streamable_http.request(data1)

    assert streamable_http._session_id == "session123"

    # Second request
    data2 = {"jsonrpc": "2.0", "method": "test2", "id": 2}
    streamable_http.request(data2)

    assert streamable_http._session_id == "session456"
