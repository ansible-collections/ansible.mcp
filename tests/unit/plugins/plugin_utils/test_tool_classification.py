# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function


__metaclass__ = type


import pytest

from ansible_collections.ansible.mcp.plugins.plugin_utils.tool_classification import (
    READ_ONLY_PREFIXES,
    classify_tool,
)


class TestAnnotationPath:
    """Tests for classification via MCP ToolAnnotations."""

    def test_read_only_annotation_true(self):
        tool_def = {
            "name": "create_vm",
            "annotations": {"readOnlyHint": True},
        }
        result = classify_tool(tool_def)
        assert result == {
            "read_only": True,
            "destructive": False,
            "source": "annotation",
        }

    def test_read_only_annotation_false(self):
        tool_def = {
            "name": "list_vms",
            "annotations": {"readOnlyHint": False},
        }
        result = classify_tool(tool_def)
        assert result == {
            "read_only": False,
            "destructive": True,
            "source": "annotation",
        }

    def test_annotation_with_explicit_destructive(self):
        tool_def = {
            "name": "update_vm",
            "annotations": {"readOnlyHint": False, "destructiveHint": False},
        }
        result = classify_tool(tool_def)
        assert result == {
            "read_only": False,
            "destructive": False,
            "source": "annotation",
        }

    def test_annotation_read_only_with_destructive_false(self):
        tool_def = {
            "name": "get_status",
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        }
        result = classify_tool(tool_def)
        assert result == {
            "read_only": True,
            "destructive": False,
            "source": "annotation",
        }

    def test_annotation_takes_priority_over_heuristic(self):
        """A tool named list_* but annotated as NOT read-only should use annotation."""
        tool_def = {
            "name": "list_things",
            "annotations": {"readOnlyHint": False},
        }
        result = classify_tool(tool_def)
        assert result["read_only"] is False
        assert result["source"] == "annotation"


class TestHeuristicPath:
    """Tests for classification via verb-prefix heuristic (no annotations)."""

    @pytest.mark.parametrize("prefix", READ_ONLY_PREFIXES)
    def test_read_only_prefixes(self, prefix):
        tool_def = {"name": f"{prefix}resources"}
        result = classify_tool(tool_def)
        assert result == {
            "read_only": True,
            "destructive": False,
            "source": "heuristic",
        }

    @pytest.mark.parametrize(
        "name",
        [
            "create_instance",
            "delete_role",
            "update_firewall",
            "attach_volume",
            "terminate_instance",
            "reboot_server",
            "run_command",
        ],
    )
    def test_mutating_tools(self, name):
        tool_def = {"name": name}
        result = classify_tool(tool_def)
        assert result == {
            "read_only": False,
            "destructive": True,
            "source": "heuristic",
        }

    def test_prefix_must_match_from_start(self):
        """A tool containing a read-only prefix in the middle should not match."""
        tool_def = {"name": "do_list_things"}
        result = classify_tool(tool_def)
        assert result["read_only"] is False


class TestEdgeCases:
    """Tests for edge cases and missing data."""

    def test_empty_name(self):
        tool_def = {"name": ""}
        result = classify_tool(tool_def)
        assert result["read_only"] is False
        assert result["source"] == "heuristic"

    def test_missing_name(self):
        tool_def = {}
        result = classify_tool(tool_def)
        assert result["read_only"] is False
        assert result["source"] == "heuristic"

    def test_annotations_none(self):
        tool_def = {"name": "list_things", "annotations": None}
        result = classify_tool(tool_def)
        assert result["read_only"] is True
        assert result["source"] == "heuristic"

    def test_annotations_empty(self):
        tool_def = {"name": "get_item", "annotations": {}}
        result = classify_tool(tool_def)
        assert result["read_only"] is True
        assert result["source"] == "heuristic"

    def test_annotations_without_read_only_hint(self):
        """Annotations present but readOnlyHint missing -> fall through to heuristic."""
        tool_def = {
            "name": "create_resource",
            "annotations": {"destructiveHint": True},
        }
        result = classify_tool(tool_def)
        assert result["read_only"] is False
        assert result["source"] == "heuristic"
