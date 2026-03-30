# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function


__metaclass__ = type


import pytest

from ansible_collections.ansible.mcp.plugins.plugin_utils.tool_classification import (
    READ_ONLY_VERBS,
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
        assert result == {"read_only": True, "source": "annotation"}

    def test_read_only_annotation_false(self):
        tool_def = {
            "name": "list_vms",
            "annotations": {"readOnlyHint": False},
        }
        result = classify_tool(tool_def)
        assert result == {"read_only": False, "source": "annotation"}

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

    def test_annotation_destructive_hint_only_when_present(self):
        """destructive key should only appear when destructiveHint is in annotations."""
        tool_def = {
            "name": "create_vm",
            "annotations": {"readOnlyHint": False},
        }
        result = classify_tool(tool_def)
        assert "destructive" not in result

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
    """Tests for classification via verb-pattern heuristic (no annotations)."""

    @pytest.mark.parametrize("verb", READ_ONLY_VERBS)
    def test_read_only_verbs(self, verb):
        tool_def = {"name": f"{verb}_resources"}
        result = classify_tool(tool_def)
        assert result == {"read_only": True, "source": "heuristic"}

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
        assert result == {"read_only": False, "source": "heuristic"}

    def test_heuristic_has_no_destructive_key(self):
        """Heuristic path should not include a destructive field."""
        tool_def = {"name": "create_instance"}
        result = classify_tool(tool_def)
        assert "destructive" not in result


class TestNamespacedNames:
    """Tests for tool names with namespace prefixes or separators."""

    @pytest.mark.parametrize(
        "name",
        [
            "github_list_issues",
            "aws_get_instance",
            "csql_list_backups",
            "my_prefix_describe_resources",
        ],
    )
    def test_namespaced_read_only(self, name):
        result = classify_tool({"name": name})
        assert result["read_only"] is True
        assert result["source"] == "heuristic"

    @pytest.mark.parametrize(
        "name",
        [
            "csql_restore",
            "github_create_issue",
            "aws_delete_instance",
            "my_prefix_terminate_vm",
        ],
    )
    def test_namespaced_mutating(self, name):
        result = classify_tool({"name": name})
        assert result["read_only"] is False

    def test_dot_separated_namespace(self):
        result = classify_tool({"name": "aws.ec2.describe_instances"})
        assert result["read_only"] is True

    def test_dot_separated_mutating(self):
        result = classify_tool({"name": "aws.ec2.terminate_instance"})
        assert result["read_only"] is False

    def test_hyphen_separated_namespace(self):
        result = classify_tool({"name": "my-server-list-things"})
        assert result["read_only"] is True


class TestCaseInsensitive:
    """Tests for CamelCase and mixed-case tool names."""

    @pytest.mark.parametrize(
        "name",
        [
            "GetResource",
            "ListInstances",
            "DescribeVolumes",
            "SearchUsers",
            "ReadObjectContent",
            "ViewIamPolicy",
        ],
    )
    def test_camel_case_read_only(self, name):
        result = classify_tool({"name": name})
        assert result["read_only"] is True

    @pytest.mark.parametrize(
        "name",
        [
            "CreateInstance",
            "DeleteRole",
            "TerminateInstance",
            "UpdateFirewall",
        ],
    )
    def test_camel_case_mutating(self, name):
        result = classify_tool({"name": name})
        assert result["read_only"] is False

    def test_all_uppercase(self):
        result = classify_tool({"name": "LIST_INSTANCES"})
        assert result["read_only"] is True

    def test_mixed_case_namespaced(self):
        result = classify_tool({"name": "AWS_Get_Instance"})
        assert result["read_only"] is True


class TestGCPPrefixes:
    """Tests for GCP-specific read-only prefixes (read_, view_)."""

    def test_read_prefix(self):
        result = classify_tool({"name": "read_object_content"})
        assert result["read_only"] is True

    def test_view_prefix(self):
        result = classify_tool({"name": "view_iam_policy"})
        assert result["read_only"] is True

    def test_read_not_substring(self):
        """'read' inside a longer word should not match."""
        result = classify_tool({"name": "spread_resources"})
        assert result["read_only"] is False

    def test_view_not_substring(self):
        """'view' inside a longer word should not match."""
        result = classify_tool({"name": "review_code"})
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

    def test_verb_only_name(self):
        """A tool named exactly a read-only verb with no suffix."""
        result = classify_tool({"name": "list"})
        assert result["read_only"] is True

    def test_verb_as_substring_not_matched(self):
        """A verb embedded in a larger word should not match."""
        result = classify_tool({"name": "checklist_items"})
        assert result["read_only"] is False
