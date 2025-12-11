====================================
Ansible MCP Collection Release Notes
====================================

.. contents:: Topics


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

Private
~~~~~~~

- run_tool - Call a specific tool on an MCP server
- server_info - Retrieve MCP server information
- tools_info - Retrieve a list of supported tools from an MCP server
