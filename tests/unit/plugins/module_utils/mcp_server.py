#!/usr/bin/env python

import datetime
import json
import os
import sys
import time


notifications = 0


for line in sys.stdin:
    data = json.loads(line)
    method = data.get("method")
    response = {}
    if method == "notify":
        notifications += 1
    elif method == "read_notifications":
        result = json.dumps(dict(notifications=notifications)) + "\n"
        sys.stdout.write(result)
        sys.stdout.flush()
    elif method == "hello":
        name = data.get("name")
        server_name = os.environ.get("MCP_SERVER_NAME")
        result = json.dumps(dict(message=f"Hello {name} from {server_name}.")) + "\n"
        sys.stdout.write(result)
        sys.stdout.flush()
    elif method == "date":
        today = datetime.datetime.now().strftime("%d%m%Y")
        result = json.dumps(dict(date=f"The date of today is {today}")) + "\n"
        sys.stdout.write(result)
        sys.stdout.flush()
    elif method == "timeout":
        value = data.get("value")
        time.sleep(int(value) + 3)
