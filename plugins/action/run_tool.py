# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from typing import Any, Dict, List, Optional

from ansible.module_utils.connection import Connection
from ansible.plugins.action import ActionBase

from ansible_collections.ansible.mcp.plugins.plugin_utils.action_utils import (
    ActionResult,
    ParameterValidation,
    validate_mcp_connection,
)


class ActionModule(ActionBase):
    """Action plugin for calling tools on an MCP server."""

    def run(self, task_vars: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the action plugin to call an MCP tool.

        Args:
            task_vars: Dictionary of task variables from Ansible context.

        Returns:
            Dictionary containing the result of the tool execution with keys:
                - failed: Whether the action failed
                - changed: Whether the action made changes
                - msg: Error message if failed
                - content: Tool response content
                - is_error: Whether an error occurred (if applicable)
                - structured_content: Structured response data (if applicable)
        """
        if task_vars is None:
            task_vars = {}

        result = super(ActionModule, self).run(task_vars=task_vars)
        action_result = ActionResult()

        # Validate connection
        if error := validate_mcp_connection(self._play_context, "run_tool"):
            action_result.failed = True
            action_result.msg = error
            result.update(action_result.to_dict())
            return result

        # Get and validate parameters
        param_validation = self._get_parameters()
        if not param_validation.is_valid:
            action_result.failed = True
            action_result.msg = param_validation.error
            result.update(action_result.to_dict())
            return result

        # Execute tool and populate result
        tool_name: str = param_validation.tool_name  # type: ignore[assignment]
        tool_args: Dict[str, Any] = param_validation.tool_args  # type: ignore[assignment]

        try:
            response = self._execute_tool(tool_name, tool_args)
            self._populate_result(action_result, response, tool_name)
            action_result.server_name = self._info["serverInfo"]["name"]
            action_result.tool_name = tool_name

        except Exception as e:
            action_result.failed = True
            action_result.msg = str(e)

        result.update(action_result.to_dict())
        return result

    def _get_parameters(self) -> ParameterValidation:
        """Extract and validate tool parameters from task arguments.

        Returns:
            ParameterValidation object containing:
                - tool_name: The name of the tool to execute
                - tool_args: Dictionary of arguments to pass to the tool
                - error: Error message if validation failed, empty string otherwise
        """
        tool_name = self._task.args.get("name")
        tool_args = self._task.args.get("args", {})

        if not tool_name:
            return ParameterValidation(error="Missing required parameter: 'name'")

        if not isinstance(tool_args, dict):
            return ParameterValidation(
                error=f"Parameter 'args' must be a dictionary, got {type(tool_args).__name__}"
            )

        return ParameterValidation(tool_name=tool_name, tool_args=tool_args)

    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool call via MCP connection.

        Args:
            tool_name: Name of the MCP tool to execute.
            tool_args: Dictionary of arguments to pass to the tool.

        Returns:
            Dictionary containing the MCP server response with tool execution results.

        Raises:
            Exception: If the tool execution fails at the connection level.
        """
        conn = Connection(self._connection.socket_path)
        self._info = conn.server_info()
        return conn.call_tool(tool_name, args=tool_args)

    def _populate_result(
        self, action_result: ActionResult, response: Dict[str, Any], tool_name: str
    ) -> None:
        """Populate ActionResult from MCP response.

        Args:
            action_result: ActionResult object to populate with response data.
            response: Dictionary containing the MCP server response.
            tool_name: Name of the tool that was executed (used for error messages).
        """
        content = response.get("content", [])
        is_error = response.get("isError", False)

        action_result.changed = False
        action_result.content = content

        if "structured_content" in response:
            action_result.structured_content = response["structured_content"]

        if is_error:
            action_result.is_error = is_error
            action_result.failed = True
            action_result.msg = self._extract_error_message(content, tool_name)

    def _extract_error_message(self, content: List[Dict[str, Any]], tool_name: str) -> str:
        """Extract error message from response content.

        Args:
            content: List of content items from the MCP response.
            tool_name: Name of the tool that was executed (used for fallback message).

        Returns:
            Combined error message from all text content items, or a default message
            if no text content is found.
        """
        error_messages = [item.get("text", "") for item in content if item.get("type") == "text"]
        return (
            " ".join(error_messages) if error_messages else f"Tool '{tool_name}' execution failed"
        )
