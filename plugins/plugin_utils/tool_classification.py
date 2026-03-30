# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import re

from typing import Any, Dict


# Read-only verb stems derived from empirical analysis of 130+ tools across
# AWS EC2, Cloud Control API, IAM, Azure, GCP Storage, GCP Observability,
# GCP BackupDR, and GitHub MCP servers.
READ_ONLY_VERBS = (
    "list",
    "get",
    "describe",
    "find",
    "check",
    "search",
    "show",
    "simulate",
    "read",
    "view",
)

# Matches a read-only verb at the start of the name or after a non-alphanumeric
# separator, followed by a non-alphanumeric character or end-of-string.
# Names are normalized to lowercase snake_case before matching, so this handles
# standard (list_instances), namespaced (github_list_issues), dot-separated
# (aws.ec2.describe_instances), and CamelCase (GetResource) conventions.
_READ_ONLY_PATTERN = re.compile(
    r"(?:^|(?<=[^a-z0-9]))(?:" + "|".join(READ_ONLY_VERBS) + r")(?=[^a-z0-9]|$)",
)

_CAMEL_BOUNDARY_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_BOUNDARY_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")


def _normalize_name(name: str) -> str:
    """Normalize a tool name to lowercase with separators at word boundaries.

    Inserts underscores at CamelCase boundaries and lowercases, so that
    ``GetResource`` becomes ``get_resource`` and ``ListInstances`` becomes
    ``list_instances``.  Names already in snake_case or using other separators
    are lowercased only.
    """
    s = _CAMEL_BOUNDARY_1.sub(r"\1_\2", name)
    s = _CAMEL_BOUNDARY_2.sub(r"\1_\2", s)
    return s.lower()


def classify_tool(tool_definition: Dict[str, Any]) -> Dict[str, Any]:
    """Classify an MCP tool as read-only or mutating for indirect node counting.

    Uses MCP ToolAnnotations (readOnlyHint / destructiveHint) when the server
    provides them (e.g. Azure MCP Server), and falls back to a verb-pattern
    heuristic on the tool name for servers that do not (e.g. AWS, GCP servers).

    The heuristic normalizes tool names to lowercase snake_case, then matches
    read-only verbs at word boundaries.  This handles standard names
    (list_instances), namespaced names (github_list_issues), dot-separated
    names (aws.ec2.describe_instances), and CamelCase (GetResource).

    Args:
        tool_definition: Tool definition dict from the MCP tools/list response.
            Expected keys: "name" (str), optional "annotations" (dict).

    Returns:
        Classification dict with:
            read_only: True if the tool only reads and does not modify state.
            source: "annotation" if classification came from MCP ToolAnnotations,
                    "heuristic" if inferred from the tool name.
            destructive: (annotation path only) Present when the server's
                destructiveHint annotation is provided.
    """
    annotations = tool_definition.get("annotations") or {}

    if "readOnlyHint" in annotations:
        read_only = bool(annotations["readOnlyHint"])
        result: Dict[str, Any] = {
            "read_only": read_only,
            "source": "annotation",
        }
        if "destructiveHint" in annotations:
            result["destructive"] = bool(annotations["destructiveHint"])
        return result

    name = _normalize_name(tool_definition.get("name", ""))
    read_only = bool(_READ_ONLY_PATTERN.search(name))

    return {
        "read_only": read_only,
        "source": "heuristic",
    }
