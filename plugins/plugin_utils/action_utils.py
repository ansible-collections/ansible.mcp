# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ParameterValidation:
    """Represents the result of parameter validation.

    Attributes:
        tool_name: The name of the tool (if validation succeeded).
        tool_args: The arguments for the tool (if validation succeeded).
        error: Error message if validation failed, empty string otherwise.
    """

    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    error: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if validation was successful."""
        return not self.error


@dataclass
class ActionResult:
    """Represents the result of an Ansible action plugin execution.

    Attributes:
        failed: Whether the action failed.
        changed: Whether the action made changes.
        msg: Optional message (typically for errors or important information).
        content: Optional content returned by the action.
        is_error: Optional flag indicating if an error occurred.
        structured_content: Optional structured content from the response.
    """

    failed: bool = False
    changed: bool = False
    msg: Optional[str] = None
    content: list = field(default_factory=list)
    is_error: Optional[bool] = None
    structured_content: Optional[Any] = None
    server_name: str = ""
    tool_name: str = ""

    def to_dict(self):
        """Convert the result to a dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


def validate_mcp_connection(play_context, action_name=None):
    """Validate that the connection type is MCP.

    Args:
        play_context: The Ansible play context containing connection information.
        action_name: Optional name of the action plugin for error messages.

    Returns:
        str or None: Error message if validation fails, None if validation succeeds.
    """
    if play_context.connection.split(".")[-1] != "mcp":
        action_ref = f" for {action_name}" if action_name else ""
        return (
            f"Connection type {play_context.connection} is not valid{action_ref}, "
            "please use fully qualified name of MCP connection type"
        )
    return None
