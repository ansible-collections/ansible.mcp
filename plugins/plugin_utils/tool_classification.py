# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from typing import Any, Dict

# Verb prefixes that indicate read-only (non-mutating) tools, derived from
# empirical analysis of 76+ tools across AWS EC2, Cloud Control API, IAM,
# and Azure MCP servers.
READ_ONLY_PREFIXES = (
    "list_",
    "get_",
    "describe_",
    "find_",
    "check_",
    "search_",
    "show_",
    "simulate_",
)


def classify_tool(tool_definition: Dict[str, Any]) -> Dict[str, Any]:
    """Classify an MCP tool as read-only or mutating for indirect node counting.

    Uses MCP ToolAnnotations (readOnlyHint / destructiveHint) when the server
    provides them (e.g. Azure MCP Server), and falls back to a verb-prefix
    heuristic on the tool name for servers that do not (e.g. AWS MCP servers).

    Args:
        tool_definition: Tool definition dict from the MCP tools/list response.
            Expected keys: "name" (str), optional "annotations" (dict).

    Returns:
        Classification dict with:
            read_only: True if the tool only reads and does not modify state.
            destructive: True if the tool may delete or destructively modify resources.
            source: "annotation" if classification came from MCP ToolAnnotations,
                    "heuristic" if inferred from the tool name.
    """
    annotations = tool_definition.get("annotations") or {}

    if "readOnlyHint" in annotations:
        read_only = bool(annotations["readOnlyHint"])
        destructive = bool(annotations.get("destructiveHint", not read_only))
        return {
            "read_only": read_only,
            "destructive": destructive,
            "source": "annotation",
        }

    name = tool_definition.get("name", "")
    read_only = name.startswith(READ_ONLY_PREFIXES)

    return {
        "read_only": read_only,
        "destructive": not read_only,
        "source": "heuristic",
    }
