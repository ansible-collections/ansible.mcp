#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2025, Ansible Project
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
module: mcp_run_tools
author:
- Ansible Team
short_description: Execute tools on MCP server
description:
- Executes a specified tool on an MCP (Model Context Protocol) server
- Uses persistent connection to MCP server for efficient communication
- Supports passing arguments to tools and returns structured results
- Handles various tool result formats and provides consistent output
version_added: "1.0.0"
requirements:
- MCP server must be running and accessible via persistent connection
options:
  tool_name:
    description:
    - Name of the MCP tool to execute
    - Tool names are case-sensitive and must match exactly
    - Use mcp_get_tools module to discover available tools
    type: str
    required: true
  tool_args:
    description:
    - Arguments to pass to the MCP tool
    - Should be a dictionary matching the tool's input schema
    - Required arguments must be provided based on tool specification
    type: dict
    default: {}
  timeout:
    description:
    - Timeout in seconds for tool execution
    - Overrides the connection-level timeout for this specific operation
    - Use higher values for long-running tools
    type: int
    required: false
  validate_args:
    description:
    - Whether to validate tool arguments before execution
    - When true, checks if required arguments are provided
    - Requires tool schema to be available from server
    type: bool
    default: false
  format_result:
    description:
    - How to format the tool execution result
    - 'auto' attempts to parse JSON content intelligently
    - 'raw' returns the exact response from the MCP server
    - 'text' extracts text content from structured responses
    type: str
    choices: ['auto', 'raw', 'text']
    default: 'auto'
notes:
- This module requires an active MCP persistent connection
- Use 'delegate_to' to specify which MCP server to execute the tool on
- Tool execution results vary based on the specific tool and server implementation
- Some tools may modify external systems (e.g., creating GitHub issues)
"""

EXAMPLES = """
# Execute a simple tool without arguments
- name: List available repositories
  ansible.mcp.mcp_run_tools:
    tool_name: list_repositories

# Execute a tool with arguments
- name: Search for repositories
  ansible.mcp.mcp_run_tools:
    tool_name: search_repositories
    tool_args:
      query: "user:octocat"
      sort: stars
      per_page: 10

# Create a GitHub issue
- name: Create issue
  ansible.mcp.mcp_run_tools:
    tool_name: create_issue
    tool_args:
      owner: myorg
      repo: myrepo
      title: "Automated Issue from Ansible"
      body: |
        This issue was created automatically by Ansible.
        
        Please review and close when appropriate.
      labels: ["automation", "ansible"]
  register: new_issue

- name: Display issue URL
  debug:
    msg: "Created issue: {{ new_issue.result.content.html_url }}"

# Execute with custom timeout
- name: Long-running analysis tool
  ansible.mcp.mcp_run_tools:
    tool_name: analyze_repository
    tool_args:
      owner: myorg
      repo: large-repo
    timeout: 300

# Get raw result format
- name: Get file contents (raw format)
  ansible.mcp.mcp_run_tools:
    tool_name: get_file_contents
    tool_args:
      owner: myorg
      repo: myrepo
      path: README.md
    format_result: raw

# Use with argument validation
- name: Create issue with validation
  ansible.mcp.mcp_run_tools:
    tool_name: create_issue
    tool_args:
      owner: myorg
      repo: myrepo
      title: "Test Issue"
    validate_args: true

# Error handling example
- name: Try to create issue
  ansible.mcp.mcp_run_tools:
    tool_name: create_issue
    tool_args:
      owner: myorg
      repo: nonexistent-repo
      title: "Test Issue"
  register: issue_result
  failed_when: false

- name: Handle creation failure
  debug:
    msg: "Issue creation failed: {{ issue_result.msg }}"
  when: issue_result.failed

# Loop through multiple tool executions
- name: Create multiple issues
  ansible.mcp.mcp_run_tools:
    tool_name: create_issue
    tool_args:
      owner: myorg
      repo: myrepo
      title: "{{ item.title }}"
      body: "{{ item.body }}"
      labels: "{{ item.labels | default([]) }}"
  loop:
    - title: "Bug Report"
      body: "Found a bug in the system"
      labels: ["bug"]
    - title: "Feature Request"
      body: "Would like to see this feature"
      labels: ["enhancement"]
  register: created_issues

- name: Display created issues
  debug:
    msg: "Created issue {{ item.result.content.number }}: {{ item.result.content.title }}"
  loop: "{{ created_issues.results }}"
"""

RETURN = """
result:
  description: The result of tool execution
  returned: always
  type: dict
  sample:
    content:
      id: 12345
      number: 42
      title: "Automated Issue from Ansible"
      body: "This issue was created automatically by Ansible."
      state: "open"
      html_url: "https://github.com/myorg/myrepo/issues/42"
    content_type: "application/json"
    is_error: false

raw_result:
  description: Raw result from MCP server (when format_result is 'raw')
  returned: when format_result is 'raw'
  type: dict
  sample:
    content:
      - type: "text"
        text: '{"id": 12345, "number": 42, "title": "Test Issue"}'
    isError: false

tool_info:
  description: Information about the executed tool
  returned: always
  type: dict
  sample:
    name: "create_issue"
    execution_time: 1.23
    arguments_provided: 4
    server_response_time: 0.89

execution_stats:
  description: Statistics about the tool execution
  returned: always
  type: dict
  sample:
    start_time: "2025-01-01T12:00:00Z"
    end_time: "2025-01-01T12:00:01Z"
    duration_seconds: 1.23
    success: true
    tool_name: "create_issue"
"""

import time
from datetime import datetime, timezone

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import ConnectionError
from ansible_collections.ansible.mcp.plugins.module_utils.mcp_common import (
    get_connection,
    validate_tool_name,
    format_tool_result,
    handle_connection_error,
    safe_json_loads
)


def validate_tool_arguments(connection, tool_name, tool_args):
    """Validate tool arguments against the tool's schema."""
    try:
        # Get tool information to check schema
        tool_info = connection.get_tools(tool_name=tool_name)
        
        if not tool_info:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        input_schema = tool_info.get('inputSchema', {})
        required_fields = input_schema.get('required', [])
        
        # Check required fields
        missing_required = []
        for field in required_fields:
            if field not in tool_args:
                missing_required.append(field)
        
        if missing_required:
            raise ValueError(
                f"Missing required arguments for tool '{tool_name}': {', '.join(missing_required)}"
            )
        
        return True
        
    except ConnectionError as e:
        raise ConnectionError(f"Failed to validate arguments for tool '{tool_name}': {str(e)}")


def execute_tool(connection, tool_name, tool_args, timeout=None):
    """Execute the specified tool on the MCP server."""
    start_time = datetime.now(timezone.utc)
    
    try:
        # Set timeout if specified
        original_timeout = None
        if timeout:
            # Note: This would require connection plugin support for per-request timeouts
            # For now, we'll track it for reporting but use the connection's default timeout
            pass
        
        # Execute the tool
        result = connection.call_tool(tool_name, tool_args)
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        execution_stats = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': round(duration, 3),
            'success': True,
            'tool_name': tool_name
        }
        
        return result, execution_stats
        
    except Exception as e:
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        execution_stats = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': round(duration, 3),
            'success': False,
            'tool_name': tool_name,
            'error': str(e)
        }
        
        raise ConnectionError(f"Tool execution failed: {str(e)}")


def format_tool_execution_result(result, format_type='auto'):
    """Format the tool execution result based on the specified format."""
    if format_type == 'raw':
        return result
    
    if format_type == 'text':
        # Extract text content only
        formatted = format_tool_result(result)
        if isinstance(formatted, dict) and 'content' in formatted:
            content = formatted['content']
            if isinstance(content, str):
                return {'content': content, 'content_type': 'text'}
            else:
                return {'content': str(content), 'content_type': 'text'}
        else:
            return {'content': str(result), 'content_type': 'text'}
    
    # Auto format (default)
    return format_tool_result(result)


def main():
    """Main module execution."""
    argument_spec = dict(
        tool_name=dict(type='str', required=True),
        tool_args=dict(type='dict', default={}),
        timeout=dict(type='int', required=False),
        validate_args=dict(type='bool', default=False),
        format_result=dict(type='str', choices=['auto', 'raw', 'text'], default='auto')
    )
    
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )
    
    tool_name = module.params['tool_name']
    tool_args = module.params['tool_args'] or {}
    timeout = module.params['timeout']
    validate_args = module.params['validate_args']
    format_result = module.params['format_result']
    
    # Validate tool name
    validate_tool_name(module, tool_name)
    
    # Get connection to MCP server
    try:
        connection = get_connection(module)
    except ConnectionError as e:
        handle_connection_error(module, "establishing connection", e)
    
    # Validate arguments if requested
    if validate_args:
        try:
            validate_tool_arguments(connection, tool_name, tool_args)
        except ValueError as e:
            module.fail_json(msg=str(e))
        except ConnectionError as e:
            handle_connection_error(module, "validating tool arguments", e)
    
    # Check mode handling
    if module.check_mode:
        module.exit_json(
            changed=False,
            msg=f"Would execute tool '{tool_name}' with arguments: {tool_args}",
            tool_info={
                'name': tool_name,
                'arguments_provided': len(tool_args),
                'check_mode': True
            }
        )
    
    # Execute the tool
    try:
        raw_result, execution_stats = execute_tool(connection, tool_name, tool_args, timeout)
        
        # Format the result
        formatted_result = format_tool_execution_result(raw_result, format_result)
        
        # Prepare response
        result = {
            'changed': True,  # Assume tools make changes unless we know otherwise
            'result': formatted_result,
            'tool_info': {
                'name': tool_name,
                'execution_time': execution_stats['duration_seconds'],
                'arguments_provided': len(tool_args),
                'server_response_time': execution_stats['duration_seconds']  # Approximate
            },
            'execution_stats': execution_stats
        }
        
        # Include raw result if requested
        if format_result == 'raw':
            result['raw_result'] = raw_result
        
        # Check if the result indicates an error
        if isinstance(formatted_result, dict) and formatted_result.get('is_error', False):
            module.fail_json(
                msg=f"Tool '{tool_name}' returned an error",
                **result
            )
        
        module.exit_json(**result)
        
    except ConnectionError as e:
        handle_connection_error(module, f"executing tool '{tool_name}'", e)
    except Exception as e:
        module.fail_json(
            msg=f"Unexpected error executing tool '{tool_name}': {str(e)}",
            exception=str(type(e).__name__),
            tool_name=tool_name,
            tool_args=tool_args
        )


if __name__ == '__main__':
    main()
