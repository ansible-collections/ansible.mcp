#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function


__metaclass__ = type


import datetime
import json
import os
import sys
import time


notifications = 0


def write(payload):
    """Write a single JSON message to stdout."""
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    data = json.loads(line)
    method = data.get("method")
    response = {}
    if method == "notify":
        notifications += 1
    elif method == "read_notifications":
        write(dict(id=data.get("id"), notifications=notifications))
    elif method == "hello":
        name = data.get("name")
        server_name = os.environ.get("MCP_SERVER_NAME")
        write(dict(id=data.get("id"), message=f"Hello {name} from {server_name}."))
    elif method == "date":
        today = datetime.datetime.now().strftime("%d%m%Y")
        write(dict(id=data.get("id"), date=f"The date of today is {today}"))
    elif method == "timeout":
        value = data.get("value")
        time.sleep(int(value) + 3)
    elif method == "notify_then_respond":
        # Mimics servers (e.g. the GitHub MCP server) that flush queued
        # notifications ahead of the response to the first list request.
        for index in range(int(data.get("count", 3))):
            write(
                dict(
                    jsonrpc="2.0",
                    method=f"notifications/{index}/list_changed",
                    params={},
                )
            )
        write(dict(jsonrpc="2.0", id=data.get("id"), result=dict(ok=True)))
    elif method == "stale_then_respond":
        # A late response to an earlier request must not be mistaken for the
        # response to the current one.
        write(dict(jsonrpc="2.0", id=data.get("id") - 1, result=dict(stale=True)))
        write(dict(jsonrpc="2.0", id=data.get("id"), result=dict(ok=True)))
    elif method == "noise_then_respond":
        # Servers that log to stdout emit lines that are not valid JSON.
        sys.stdout.write("this line is not json\n")
        sys.stdout.flush()
        write(dict(jsonrpc="2.0", id=data.get("id"), result=dict(ok=True)))
    elif method == "flood":
        # Never sends a response, only notifications, as fast as it can.
        while True:
            write(dict(jsonrpc="2.0", method="notifications/noise", params={}))
