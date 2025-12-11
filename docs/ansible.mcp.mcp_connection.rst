.. _ansible.mcp.mcp_connection:


***************
ansible.mcp.mcp
***************

**Persistent connection to an Model Context Protocol (MCP) server**


Version added: 1.0.0

.. contents::
   :local:
   :depth: 1


Synopsis
--------
- This connection plugin allows for a persistent connection to an Model Context Protocol (MCP) server.
- It is designed to run once per host for the duration of a playbook, allowing tasks to communicate with a single, long-lived server session.
- Both stdio and Streamable HTTP transport methods are supported.
- All tasks using this connection plugin are run on the Ansible control node.




Parameters
----------

.. raw:: html

    <table  border=0 cellpadding=0 class="documentation-table">
        <tr>
            <th colspan="1">Parameter</th>
            <th>Choices/<font color="blue">Defaults</font></th>
                <th>Configuration</th>
            <th width="100%">Comments</th>
        </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>bearer_token</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">string</span>
                    </div>
                </td>
                <td>
                </td>
                    <td>
                                <div>env:MCP_BEARER_TOKEN</div>
                                <div>var: ansible_mcp_bearer_token</div>
                    </td>
                <td>
                        <div>Bearer token for authenticating to the MCP server when using http transport.</div>
                        <div>Ignored when using stdio transport.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>manifest_path</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">string</span>
                    </div>
                </td>
                <td>
                        <b>Default:</b><br/><div style="color: blue">"/opt/mcp/mcpservers.json"</div>
                </td>
                    <td>
                                <div>var: ansible_mcp_manifest_path</div>
                    </td>
                <td>
                        <div>Path to MCP manifest JSON file to resolve server executable paths for stdio.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>persistent_command_timeout</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">integer</span>
                    </div>
                </td>
                <td>
                        <b>Default:</b><br/><div style="color: blue">30</div>
                </td>
                    <td>
                                <div>env:ANSIBLE_PERSISTENT_COMMAND_TIMEOUT</div>
                                <div>var: ansible_command_timeout</div>
                    </td>
                <td>
                        <div>Timeout for persistent connection commands in seconds.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>persistent_connect_timeout</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">integer</span>
                    </div>
                </td>
                <td>
                        <b>Default:</b><br/><div style="color: blue">30</div>
                </td>
                    <td>
                                <div>env:ANSIBLE_PERSISTENT_CONNECT_TIMEOUT</div>
                                <div>var: ansible_connect_timeout</div>
                    </td>
                <td>
                        <div>Timeout in seconds for initial connection to persistent transport.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>persistent_log_messages</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">boolean</span>
                    </div>
                </td>
                <td>
                        <b>Default:</b><br/><div style="color: blue">"no"</div>
                </td>
                    <td>
                                <div>env:ANSIBLE_PERSISTENT_LOG_MESSAGES</div>
                                <div>var: ansible_persistent_log_messages</div>
                    </td>
                <td>
                        <div>Enable logging of messages from persistent connection.</div>
                        <div>Be sure to fully understand the security implications of enabling this option as it could create a security vulnerability by logging sensitive information in log file.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>server_args</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">list</span>
                         / <span style="color: purple">elements=string</span>
                    </div>
                </td>
                <td>
                </td>
                    <td>
                                <div>var: ansible_mcp_server_args</div>
                    </td>
                <td>
                        <div>Additional command line arguments to pass to the server when using stdio transport.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>server_env</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">dictionary</span>
                    </div>
                </td>
                <td>
                </td>
                    <td>
                                <div>var: ansible_mcp_server_env</div>
                    </td>
                <td>
                        <div>Additional environment variables to pass to the server when using stdio transport.</div>
                        <div>These are merged with the current environment.</div>
                        <div>Ignored when using http transport.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>server_name</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">string</span>
                         / <span style="color: red">required</span>
                    </div>
                </td>
                <td>
                </td>
                    <td>
                                <div>var: ansible_mcp_server_name</div>
                    </td>
                <td>
                        <div>The name of the MCP server.</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="parameter-"></div>
                    <b>validate_certs</b>
                    <a class="ansibleOptionLink" href="#parameter-" title="Permalink to this option"></a>
                    <div style="font-size: small">
                        <span style="color: purple">boolean</span>
                    </div>
                </td>
                <td>
                        <ul style="margin: 0; padding: 0"><b>Choices:</b>
                                    <li>no</li>
                                    <li><div style="color: blue"><b>yes</b>&nbsp;&larr;</div></li>
                        </ul>
                </td>
                    <td>
                                <div>var: ansible_mcp_validate_certs</div>
                    </td>
                <td>
                        <div>Whether to validate SSL certificates when using http transport.</div>
                </td>
            </tr>
    </table>
    <br/>








Status
------


Authors
~~~~~~~

- Alina Buzachis (@alinabuzachis)


.. hint::
    Configuration entries for each entry type have a low to high priority order. For example, a variable that is lower in the list will override a variable that is higher up.
