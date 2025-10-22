# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function


__metaclass__ = type


import json
import random
import string

from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from ansible.errors import AnsibleConnectionFailure

from ansible_collections.ansible.mcp.plugins.plugin_utils.mcp import Stdio


@pytest.fixture
def mock_process():
    """Fixture providing a mock process."""
    process = MagicMock()
    process.terminate = MagicMock()
    process.wait = MagicMock()
    process.kill = MagicMock()
    process.stdin = MagicMock()
    process.stdin.write = MagicMock()
    process.stdin.flush = MagicMock()
    process.stdout = MagicMock()
    process.stdout.readline = MagicMock()
    process.poll = MagicMock()
    process.communicate = MagicMock()
    process.communicate.return_value = ("stdout value", "error output")
    return process


@patch("subprocess.Popen")
def test_connect_popen_exception(m_popen):
    cmd = MagicMock()
    stdio = Stdio(cmd=cmd)

    e_msg = "Popen failed!!"
    m_popen.side_effect = SystemError(e_msg)
    with pytest.raises(AnsibleConnectionFailure) as exc_info:
        stdio.connect()

    assert str(exc_info.value) == f"Failed to start MCP server: {e_msg}"


def test_connect_process_terminated(tmp_path):

    server_content = """
    #!/usr/bin/env bash
    exit 1
    """

    d = tmp_path / "server"
    d.mkdir()
    p = d / "server.sh"
    p.write_text(server_content)

    cmd = ["sh", str(p.resolve())]
    stdio = Stdio(cmd=cmd)
    with pytest.raises(AnsibleConnectionFailure) as exc_info:
        stdio.connect()
    assert str(exc_info.value).startswith("MCP server exited immediately.")


def test_connect_success(tmp_path):

    server_content = """
    #!/usr/bin/env bash
    sleep 5s
    """

    d = tmp_path / "server"
    d.mkdir()
    p = d / "server.sh"
    p.write_text(server_content)

    cmd = ["sh", str(p.resolve())]
    stdio = Stdio(cmd=cmd)
    stdio.connect()
    assert stdio._process is not None


def test_close_not_connected():

    cmd = MagicMock()
    stdio = Stdio(cmd=cmd)
    stdio.close()


def test_close_timeout(mock_process):

    cmd = MagicMock()
    stdio = Stdio(cmd=cmd)
    stdio._process = mock_process
    mock_process.terminate.side_effect = TimeoutExpired(cmd="ansible-test units", timeout=5)

    stdio.close()
    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_called_once()
    mock_process.wait.assert_called_once()
    assert stdio._process is None


def test_close_no_timeout(mock_process):

    cmd = MagicMock()
    stdio = Stdio(cmd=cmd)
    stdio._process = mock_process

    stdio.close()
    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_not_called()
    mock_process.wait.assert_called_once_with(timeout=5)
    assert stdio._process is None


def test_close_exception(mock_process):

    cmd = MagicMock()
    stdio = Stdio(cmd=cmd)
    stdio._process = mock_process
    mock_process.terminate.side_effect = SystemError("Failed to terminate process")

    with pytest.raises(AnsibleConnectionFailure) as exc_info:
        stdio.close()

    assert str(exc_info.value).startswith("Error closing MCP process")
    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_not_called()
    mock_process.wait.assert_not_called()
    assert stdio._process is None


def test_stdin_write(mock_process):
    cmd = MagicMock()
    stdio = Stdio(cmd=cmd)
    stdio._process = mock_process

    data = dict(foo="bar")
    stdio._stdin_write(data)

    mock_process.stdin.write.assert_called_once_with(json.dumps(data) + "\n")
    mock_process.stdin.flush.assert_called_once()


@patch("signal.signal")
@patch("signal.alarm")
def test_stdout_read_no_data(mock_signal_alarm, mock_signal_signal, mock_process):

    cmd = MagicMock()
    stdio = Stdio(cmd=cmd)
    stdio._process = mock_process

    mock_process.stdout.readline.return_value = None
    with pytest.raises(AnsibleConnectionFailure) as exc_info:
        stdio._stdout_read()
    assert str(exc_info.value) == "No response from MCP server"


@pytest.mark.parametrize(
    "stdout_line,data",
    [
        ('{"hello": "world"}', dict(hello="world")),
        ('{"foo": "bar"}\n', dict(foo="bar")),
    ],
)
@patch("signal.signal")
@patch("signal.alarm")
def test_stdout_read_with_data(
    mock_signal_alarm, mock_signal_signal, mock_process, stdout_line, data
):

    cmd = MagicMock()
    stdio = Stdio(cmd=cmd)
    stdio._process = mock_process

    mock_process.stdout.readline.return_value = stdout_line
    assert data == stdio._stdout_read()


@pytest.mark.parametrize("is_request", [True, False])
def test_request_or_notify_server_not_started(is_request):

    stdio = Stdio(cmd=MagicMock())
    stdio._stdin_write = MagicMock()
    stdio._stdout_read = MagicMock()
    data = MagicMock()
    with pytest.raises(AnsibleConnectionFailure) as exc_info:
        if is_request:
            stdio.request(data)
        else:
            stdio.notify(data)

    assert str(exc_info.value) == "MCP server process not started."
    stdio._stdin_write.assert_not_called()
    stdio._stdout_read.assert_not_called()


@pytest.mark.parametrize("is_request", [True, False])
def test_request_or_notify_server_terminated(mock_process, is_request):

    mock_process.poll.return_value = MagicMock()

    stdio = Stdio(cmd=MagicMock())
    stdio._process = mock_process
    stdio._stdin_write = MagicMock()
    stdio._stdout_read = MagicMock()
    data = MagicMock()
    with pytest.raises(AnsibleConnectionFailure) as exc_info:
        if not is_request:
            stdio.notify(data)
        else:
            stdio.request(data)

    assert str(exc_info.value).startswith("MCP server process terminated unexpectedly.")
    stdio._stdin_write.assert_not_called()
    stdio._stdout_read.assert_not_called()


@pytest.mark.parametrize("is_request", [True, False])
def test_request_or_notify_write_exception(mock_process, is_request):

    mock_process.poll.return_value = None

    stdio = Stdio(cmd=MagicMock())
    stdio._process = mock_process
    stdio._stdin_write = MagicMock()
    stdio._stdout_read = MagicMock()
    e_msg = "foo value error"
    stdio._stdin_write.side_effect = ValueError(e_msg)
    data = MagicMock()
    with pytest.raises(AnsibleConnectionFailure) as exc_info:
        if is_request:
            operation = "request"
            stdio.request(data)
        else:
            operation = "notification"
            stdio.notify(data)

    assert str(exc_info.value).startswith(f"Error sending {operation} to MCP server")
    assert e_msg in str(exc_info.value)
    stdio._stdin_write.assert_called_once_with(data)
    stdio._stdout_read.assert_not_called()


@pytest.mark.parametrize("is_request", [True, False])
def test_request_or_notify_success(mock_process, is_request):

    mock_process.poll.return_value = None

    stdio = Stdio(cmd=MagicMock())
    stdio._process = mock_process
    stdio._stdin_write = MagicMock()
    stdio._stdin_write.return_value = None
    stdout_value = MagicMock()
    stdio._stdout_read = MagicMock()
    stdio._stdout_read.return_value = stdout_value

    data = MagicMock()
    if not is_request:
        stdio.notify(data)
    else:
        assert stdio.request(data) == stdout_value
        stdio._stdout_read.assert_called_once_with()
    stdio._stdin_write.assert_called_once_with(data)


def test_with_mcp_server(tmp_path):

    mcp_server = """
import sys
import json
import datetime
import time
import os

notifications = 0

for line in sys.stdin:
    data = json.loads(line)
    method = data.get("method")
    response = {}
    if method == "notify":
        notifications += 1
    elif method == "read_notifications":
        result = json.dumps(dict(notifications=notifications)) + "\\n"
        sys.stdout.write(result)
        sys.stdout.flush()
    elif method == "hello":
        name = data.get("name")
        server_name = os.environ.get("MCP_SERVER_NAME")
        result = json.dumps(dict(message=f"Hello {name} from {server_name}.")) + "\\n"
        sys.stdout.write(result)
        sys.stdout.flush()
    elif method == "date":
        today = datetime.datetime.now().strftime("%d%m%Y")
        result = json.dumps(dict(date=f"The date of today is {today}")) + "\\n"
        sys.stdout.write(result)
        sys.stdout.flush()
    elif method == "timeout":
        value = data.get("value")
        time.sleep(int(value))
    """

    d = tmp_path / "server"
    d.mkdir()
    p = d / "mcp_server.py"
    p.write_text(mcp_server)

    cmd = ["python", str(p.resolve())]
    mcp_server_name = "mcp-server-" + "".join(
        [random.choice(string.ascii_lowercase + string.digits) for i in range(8)]
    )
    stdio = Stdio(cmd=cmd, env={"MCP_SERVER_NAME": mcp_server_name})

    # Validate connection
    stdio.connect()

    # Validate notifications
    number_notifications = 5
    for i in range(number_notifications):
        stdio.notify(dict(method="notify"))

    notifications = stdio.request(dict(method="read_notifications"))
    assert notifications["notifications"] == number_notifications

    # Validate requests
    hello = stdio.request(dict(method="hello", name="ansible"))
    assert hello["message"] == f"Hello ansible from {mcp_server_name}."

    date = stdio.request(dict(method="date"))
    assert date["date"].startswith("The date of today is")

    # request timeout
    with pytest.raises(AnsibleConnectionFailure) as exc_info:
        stdio.request(dict(method="timeout", value=6))
    assert "MCP server response timeout after" in str(exc_info.value)

    # terminate mcp server
    stdio.close()
