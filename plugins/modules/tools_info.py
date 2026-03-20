# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


DOCUMENTATION = """
module: tools_info
author: Aubin Bikouo (@abikouo)
short_description: Retrieve a list of supported tools from an MCP server
description:
    - This module is used to discover available tools from an MCP server.
    - The module sends a tools/list request to the server.
version_added: 1.0.0
options: {}
"""

EXAMPLES = """
- name: Retrieve list of supported tools from an MCP server.
  ansible.mcp.tools_info:
"""

RETURN = """
server_name:
    description: Name of the MCP server.
    returned: success
    type: str
    version_added: 1.1.0
    sample: "github-server"
tools:
    description: List of supported tools.
    returned: success
    type: list
    elements: dict
    sample: {
        "name": "get_weather",
        "title": "Weather Information Provider",
        "description": "Get current weather information for a location",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or zip code"
                }
            },
            "required": ["location"]
        }
    }
"""
