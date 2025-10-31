# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


class MCPError(Exception):
    """Base exception class for MCP related errors.

    This exception is raised when MCP operations fail, such as initialization,
    tool listing, tool execution, or validation errors.
    """

    pass
