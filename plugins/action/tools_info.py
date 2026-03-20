# -*- coding: utf-8 -*-

# Copyright (c) 2025 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.module_utils.connection import Connection
from ansible.plugins.action import ActionBase

from ansible_collections.ansible.mcp.plugins.plugin_utils.utils import validate_connection_plugin


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):
        """Perform the process of the action plugin"""

        result = super(ActionModule, self).run(task_vars=task_vars)
        v_result = validate_connection_plugin(self._play_context, "tools_info")
        if v_result:
            result.update(v_result)
            return result

        conn = Connection(self._connection.socket_path)
        tools = conn.list_tools().get("tools", [])
        info = conn.server_info()
        server_name = info["serverInfo"]["name"]

        return dict(changed=False, server_name=server_name, tools=tools)
