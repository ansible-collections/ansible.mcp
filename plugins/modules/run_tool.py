# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function


__metaclass__ = type

DOCUMENTATION = r"""
---
module: run_tool
short_description: Call a specific tool on an MCP server
description:
    - Call a specific tool on an MCP server.
    - The plugin validates tool calls using the server's tools list.
    - Fails with an appropriate error message when there is a mismatch.
    - Uses the MCP connection plugin to communicate with the server.
version_added: "1.0.0"
options:
    name:
        description:
            - The name of the tool to call on the MCP server.
        required: true
        type: str
    args:
        description:
            - Arguments to pass to the tool.
            - The required arguments vary depending on the tool being called.
        type: dict
        default: {}
author:
    - Mandar Vijay Kulkarni (@mandar242)
notes:
    - This plugin requires an MCP connection to be established.
    - "Use C(connection: ansible.mcp.mcp) in your playbook."
    - See the MCP connection plugin documentation for configuration options.
"""


EXAMPLES = r"""
- name: Get weather information
  ansible.mcp.run_tool:
    name: get_weather
    args:
      location: Durham

- name: Search my-org repositories
  ansible.mcp.run_tool:
    name: search_repositories
    args:
      query: "org:my-org language:python"

- name: List IAM roles
  ansible.mcp.run_tool:
    name: list_roles
    args:
      max_items: 10
"""


RETURN = r"""
content:
    description: List of content objects representing unstructured result of the tool call.
    returned: success
    type: list
    elements: dict
    sample:
        - type: text
          text: Current weather in Durham is 72°F and partly cloudy.
is_error:
    description: Whether the tool call resulted in an error.
    type: bool
    returned: when MCP server reported an error in tool call
structured_content:
    description: Optional structured result of the tool call.
    returned: when provided by the MCP server
    type: dict
server_name:
    description: Name of the MCP server.
    returned: success
    type: str
    version_added: 1.1.0
    sample: "github-server"
tool_name:
    description: Name of the tool used.
    returned: success
    type: str
    version_added: 1.1.0
    sample: "search_repositories"
"""
