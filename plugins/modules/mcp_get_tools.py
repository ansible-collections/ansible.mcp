#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2025, Ansible Project
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
module: mcp_get_tools
author:
- Ansible Team
short_description: Get available tools from MCP server
description:
- Retrieves the list of available tools from an MCP (Model Context Protocol) server
- Can return all tools or information about a specific tool
- Uses persistent connection to MCP server for efficient communication
- Returns structured information about tools including parameters and descriptions
version_added: "1.0.0"
requirements:
- MCP server must be running and accessible via persistent connection
options:
  tool_name:
    description:
    - Name of specific tool to get information about
    - If not specified, returns information about all available tools
    - Tool names are case-sensitive and must match exactly
    type: str
    required: false
  include_schema:
    description:
    - Whether to include detailed parameter schema information for tools
    - When true, returns full JSON schema for tool parameters
    - When false, returns simplified parameter information
    type: bool
    default: true
  format:
    description:
    - Output format for tool information
    - 'detailed' includes full schema and parameter information
    - 'summary' includes only basic tool information
    - 'raw' returns the raw response from MCP server
    type: str
    choices: ['detailed', 'summary', 'raw']
    default: 'detailed'
notes:
- This module requires an active MCP persistent connection
- Use 'delegate_to' to specify which MCP server to query
- Tool information is cached by the connection plugin for performance
"""

EXAMPLES = """
# Get all available tools with detailed information
- name: List all MCP tools
  ansible.mcp.mcp_get_tools:

# Get information about a specific tool
- name: Get search_repositories tool info
  ansible.mcp.mcp_get_tools:
    tool_name: search_repositories

# Get tool information in summary format
- name: List tools with summary information
  ansible.mcp.mcp_get_tools:
    format: summary

# Get raw tool information from server
- name: Get raw tool data
  ansible.mcp.mcp_get_tools:
    format: raw

# Use in a loop to process each tool
- name: Get all tools and process each one
  ansible.mcp.mcp_get_tools:
  register: mcp_tools

- name: Display each tool
  debug:
    msg: "Tool {{ item.name }}: {{ item.description }}"
  loop: "{{ mcp_tools.tools }}"

# Check if a specific tool exists
- name: Check if create_issue tool exists
  ansible.mcp.mcp_get_tools:
    tool_name: create_issue
  register: create_issue_tool
  failed_when: false

- name: Use tool if it exists
  ansible.mcp.mcp_run_tools:
    tool_name: create_issue
    tool_args:
      owner: myorg
      repo: myrepo
      title: "Automated Issue"
      body: "Created by Ansible"
  when: create_issue_tool.tool is defined
"""

RETURN = """
tools:
  description: List of available tools from the MCP server
  returned: when tool_name is not specified
  type: list
  elements: dict
  sample:
    - name: search_repositories
      description: Search for repositories on GitHub
      parameters:
        query:
          type: string
          description: Search query string
          required: true
        sort:
          type: string
          description: Sort order for results
          required: false
          choices: [stars, forks, updated]
      input_schema:
        type: object
        properties:
          query:
            type: string
            description: Search query string
          sort:
            type: string
            enum: [stars, forks, updated]
        required: [query]

tool:
  description: Information about the requested tool
  returned: when tool_name is specified and tool exists
  type: dict
  sample:
    name: create_issue
    description: Create a new issue in a GitHub repository
    parameters:
      owner:
        type: string
        description: Repository owner
        required: true
      repo:
        type: string
        description: Repository name
        required: true
      title:
        type: string
        description: Issue title
        required: true
      body:
        type: string
        description: Issue body content
        required: false
    input_schema:
      type: object
      properties:
        owner:
          type: string
        repo:
          type: string
        title:
          type: string
        body:
          type: string
      required: [owner, repo, title]

tool_count:
  description: Number of tools available on the MCP server
  returned: always
  type: int
  sample: 15

server_info:
  description: Information about the MCP server capabilities
  returned: always
  type: dict
  sample:
    has_tools: true
    tools_count: 15
    connection_status: connected
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import ConnectionError
from ansible_collections.ansible.mcp.plugins.module_utils.mcp_common import (
    get_connection,
    validate_tool_name,
    format_tool_info,
    handle_connection_error
)


def get_all_tools(connection, include_schema=True, format_type='detailed'):
    """Get all available tools from the MCP server."""
    try:
        # Use the connection's get_tools method
        tools_response = connection.get_tools()
        
        if format_type == 'raw':
            return tools_response
        
        if not isinstance(tools_response, list):
            raise ValueError("Expected list of tools from server")
        
        formatted_tools = []
        for tool in tools_response:
            if format_type == 'summary':
                # Return minimal information
                formatted_tools.append({
                    'name': tool.get('name', 'Unknown'),
                    'description': tool.get('description', 'No description available')
                })
            else:  # detailed format
                formatted_tool = format_tool_info(tool)
                if not include_schema and 'input_schema' in formatted_tool:
                    # Remove detailed schema but keep parameter summary
                    del formatted_tool['input_schema']
                formatted_tools.append(formatted_tool)
        
        return formatted_tools
        
    except ConnectionError as e:
        raise ConnectionError(f"Failed to retrieve tools from MCP server: {str(e)}")


def get_specific_tool(connection, tool_name, include_schema=True, format_type='detailed'):
    """Get information about a specific tool."""
    try:
        # Use the connection's get_tools method with tool name
        tool_response = connection.get_tools(tool_name=tool_name)
        
        if not tool_response:
            return None
        
        if format_type == 'raw':
            return tool_response
        
        if format_type == 'summary':
            return {
                'name': tool_response.get('name', 'Unknown'),
                'description': tool_response.get('description', 'No description available')
            }
        else:  # detailed format
            formatted_tool = format_tool_info(tool_response)
            if not include_schema and 'input_schema' in formatted_tool:
                del formatted_tool['input_schema']
            return formatted_tool
            
    except ConnectionError as e:
        raise ConnectionError(f"Failed to retrieve tool '{tool_name}' from MCP server: {str(e)}")


def main():
    """Main module execution."""
    argument_spec = dict(
        tool_name=dict(type='str', required=False),
        include_schema=dict(type='bool', default=True),
        format=dict(type='str', choices=['detailed', 'summary', 'raw'], default='detailed')
    )
    
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )
    
    tool_name = module.params['tool_name']
    include_schema = module.params['include_schema']
    format_type = module.params['format']
    
    # Validate tool name if provided
    if tool_name:
        validate_tool_name(module, tool_name)
    
    # Get connection to MCP server
    try:
        connection = get_connection(module)
    except ConnectionError as e:
        handle_connection_error(module, "establishing connection", e)
    
    result = {
        'changed': False,
        'server_info': {
            'connection_status': 'connected'
        }
    }
    
    try:
        if tool_name:
            # Get specific tool information
            tool_info = get_specific_tool(connection, tool_name, include_schema, format_type)
            
            if tool_info is None:
                module.fail_json(
                    msg=f"Tool '{tool_name}' not found on MCP server",
                    available_tools_hint="Use mcp_get_tools without tool_name to see available tools"
                )
            
            result['tool'] = tool_info
            result['tool_count'] = 1
            result['server_info']['has_tools'] = True
            result['server_info']['tools_count'] = 1
            
        else:
            # Get all tools
            tools = get_all_tools(connection, include_schema, format_type)
            
            result['tools'] = tools
            result['tool_count'] = len(tools)
            result['server_info']['has_tools'] = len(tools) > 0
            result['server_info']['tools_count'] = len(tools)
    
    except ConnectionError as e:
        handle_connection_error(module, "retrieving tools", e)
    except Exception as e:
        module.fail_json(
            msg=f"Unexpected error retrieving tools: {str(e)}",
            exception=str(type(e).__name__)
        )
    
    module.exit_json(**result)


if __name__ == '__main__':
    main()
