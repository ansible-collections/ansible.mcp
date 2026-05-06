====================================
Ansible MCP Collection Release Notes
====================================

.. contents:: Topics

v1.1.0
======

Release Summary
---------------

This minor release adds new features and improvements to the ``run_tool``, ``tools_info`` module(s).

Minor Changes
-------------

- extensions/audit/event_query.yml - Added JQ query support for auditing MCP server events via indirect Node Query Count (https://github.com/ansible-collections/ansible.mcp/pull/36).
- playbook/aws_ccapi_demo_validation_failure - A playbook to showcase client-side validation failure with AWS CCAPI server (https://github.com/ansible-collections/ansible.mcp/pull/30).
- run_tool - Adds support for server_name and tool_name for node count query support and updates integration tests and relevant documentation (https://github.com/ansible-collections/ansible.mcp/pull/38).
- tools_info - Enhanced the action plugin to return the ``server_name`` metadata provided by the MCP server (https://github.com/ansible-collections/ansible.mcp/pull/36).

v1.0.0
======

Release Summary
---------------

This is the first release of the ``ansible.mcp`` collection, providing plugins and playbooks for Model Context Protocol (MCP) integration.

New Plugins
-----------

Connection
~~~~~~~~~~

- mcp - Persistent connection to an Model Context Protocol (MCP) server

New Modules
-----------

- run_tool - Call a specific tool on an MCP server
- server_info - Retrieve MCP server information
- tools_info - Retrieve a list of supported tools from an MCP server
