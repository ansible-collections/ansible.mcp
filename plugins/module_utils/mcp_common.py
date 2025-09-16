# -*- coding: utf-8 -*-
# Copyright: (c) 2025, Ansible Project
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from ansible.module_utils._text import to_text
from ansible.module_utils.connection import Connection, ConnectionError


def get_connection(module):
    """Get the persistent MCP connection for the module."""
    try:
        connection = Connection(module._socket_path)
        return connection
    except ConnectionError as exc:
        module.fail_json(msg=to_text(exc, errors="surrogate_then_replace"))


def validate_tool_name(module, tool_name):
    """Validate that the tool name is a non-empty string."""
    if not tool_name:
        module.fail_json(msg="tool_name is required and cannot be empty")
    
    if not isinstance(tool_name, str):
        module.fail_json(msg="tool_name must be a string")


def format_tool_result(result):
    """Format tool execution result for Ansible output."""
    if not result:
        return {}
    
    # Handle different result formats from MCP servers
    if isinstance(result, dict):
        # Check for standard MCP tool response format
        if 'content' in result:
            content = result['content']
            if isinstance(content, list) and len(content) > 0:
                # Extract text content from first content item
                first_content = content[0]
                if isinstance(first_content, dict) and 'text' in first_content:
                    # Try to parse as JSON if possible
                    try:
                        parsed_content = json.loads(first_content['text'])
                        return {
                            'content': parsed_content,
                            'raw_content': first_content['text'],
                            'content_type': first_content.get('type', 'text'),
                            'is_error': result.get('isError', False)
                        }
                    except (json.JSONDecodeError, ValueError):
                        # Return as text if not valid JSON
                        return {
                            'content': first_content['text'],
                            'content_type': first_content.get('type', 'text'),
                            'is_error': result.get('isError', False)
                        }
                else:
                    # Return content item as-is
                    return {
                        'content': first_content,
                        'content_type': 'unknown',
                        'is_error': result.get('isError', False)
                    }
            else:
                # Empty or unexpected content format
                return {
                    'content': content,
                    'content_type': 'unknown',
                    'is_error': result.get('isError', False)
                }
        else:
            # Direct result format
            return result
    else:
        # Non-dict result
        return {'content': result}


def format_tool_info(tool):
    """Format tool information for display."""
    if not isinstance(tool, dict):
        return tool
    
    formatted = {
        'name': tool.get('name', 'Unknown'),
        'description': tool.get('description', 'No description available')
    }
    
    # Format input schema if present
    if 'inputSchema' in tool:
        input_schema = tool['inputSchema']
        formatted['input_schema'] = input_schema
        
        # Extract parameter information for easier access
        if isinstance(input_schema, dict) and 'properties' in input_schema:
            properties = input_schema['properties']
            required = input_schema.get('required', [])
            
            parameters = {}
            for param_name, param_info in properties.items():
                param_details = {
                    'type': param_info.get('type', 'unknown'),
                    'description': param_info.get('description', 'No description'),
                    'required': param_name in required
                }
                
                # Add additional schema details if present
                if 'enum' in param_info:
                    param_details['choices'] = param_info['enum']
                if 'default' in param_info:
                    param_details['default'] = param_info['default']
                if 'examples' in param_info:
                    param_details['examples'] = param_info['examples']
                
                parameters[param_name] = param_details
            
            formatted['parameters'] = parameters
    
    return formatted


def handle_connection_error(module, operation, error):
    """Handle connection errors with appropriate error messages."""
    error_msg = to_text(error, errors="surrogate_then_replace")
    
    if "timeout" in error_msg.lower():
        module.fail_json(
            msg=f"Timeout occurred during {operation}. "
                f"Consider increasing mcp_timeout setting. Error: {error_msg}"
        )
    elif "connection" in error_msg.lower():
        module.fail_json(
            msg=f"Connection error during {operation}. "
                f"Check MCP server configuration. Error: {error_msg}"
        )
    elif "not found" in error_msg.lower():
        module.fail_json(
            msg=f"MCP server or tool not found during {operation}. "
                f"Check server path and tool availability. Error: {error_msg}"
        )
    else:
        module.fail_json(
            msg=f"Error during {operation}: {error_msg}"
        )


def safe_json_loads(data, default=None):
    """Safely parse JSON data with fallback."""
    if not data:
        return default
    
    try:
        if isinstance(data, str):
            return json.loads(data)
        return data
    except (json.JSONDecodeError, ValueError, TypeError):
        return default
