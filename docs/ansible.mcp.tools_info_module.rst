.. _ansible.mcp.tools_info_module:


**********************
ansible.mcp.tools_info
**********************

**Retrieve a list of supported tools from an MCP server**


Version added: 1.0.0

.. contents::
   :local:
   :depth: 1


Synopsis
--------
- This module is used to discover available tools from an MCP server.
- The module sends a tools/list request to the server.







Examples
--------

.. code-block:: yaml

    - name: Retrieve list of supported tools from an MCP server.
      ansible.mcp.tools_info:



Return Values
-------------
Common return values are documented `here <https://docs.ansible.com/projects/ansible/latest/reference_appendices/common_return_values.html#common-return-values>`_, the following are the fields unique to this module:

.. raw:: html

    <table border=0 cellpadding=0 class="documentation-table">
        <tr>
            <th colspan="1">Key</th>
            <th>Returned</th>
            <th width="100%">Description</th>
        </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="return-"></div>
                    <b>server_name</b>
                    <a class="ansibleOptionLink" href="#return-" title="Permalink to this return value"></a>
                    <div style="font-size: small">
                      <span style="color: purple">string</span>
                    </div>
                    <div style="font-style: italic; font-size: small; color: darkgreen">added in 1.1.0</div>
                </td>
                <td>success</td>
                <td>
                            <div>Name of the MCP server.</div>
                    <br/>
                        <div style="font-size: smaller"><b>Sample:</b></div>
                        <div style="font-size: smaller; color: blue; word-wrap: break-word; word-break: break-all;">github-server</div>
                </td>
            </tr>
            <tr>
                <td colspan="1">
                    <div class="ansibleOptionAnchor" id="return-"></div>
                    <b>tools</b>
                    <a class="ansibleOptionLink" href="#return-" title="Permalink to this return value"></a>
                    <div style="font-size: small">
                      <span style="color: purple">list</span>
                       / <span style="color: purple">elements=dictionary</span>
                    </div>
                </td>
                <td>success</td>
                <td>
                            <div>List of supported tools.</div>
                    <br/>
                        <div style="font-size: smaller"><b>Sample:</b></div>
                        <div style="font-size: smaller; color: blue; word-wrap: break-word; word-break: break-all;">{&#x27;name&#x27;: &#x27;get_weather&#x27;, &#x27;title&#x27;: &#x27;Weather Information Provider&#x27;, &#x27;description&#x27;: &#x27;Get current weather information for a location&#x27;, &#x27;inputSchema&#x27;: {&#x27;type&#x27;: &#x27;object&#x27;, &#x27;properties&#x27;: {&#x27;location&#x27;: {&#x27;type&#x27;: &#x27;string&#x27;, &#x27;description&#x27;: &#x27;City name or zip code&#x27;}}, &#x27;required&#x27;: [&#x27;location&#x27;]}}</div>
                </td>
            </tr>
    </table>
    <br/><br/>


Status
------


Authors
~~~~~~~

- Aubin Bikouo (@abikouo)
