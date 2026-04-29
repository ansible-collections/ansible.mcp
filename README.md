# Ansible MCP Collection

This collection includes a variety of Ansible content to help automate interactions with Model Context Protocol (MCP) servers. This collection is maintained by the Ansible Cloud Content team.

## Contents

- [Ansible MCP Collection](#ansible-mcp-collection)
  - [Contents](#contents)
  - [Description](#description)
  - [Requirements](#requirements)
    - [Ansible version compatibility](#ansible-version-compatibility)
    - [Python version compatibility](#python-version-compatibility)
    - [Collection dependencies](#collection-dependencies)
    - [External requirements](#external-requirements)
  - [Included content](#included-content)
    - [Connection Plugins](#connection-plugins)
    - [Modules](#modules)
  - [Testing](#testing)
  - [Installation](#installation)
  - [Support](#support)
  - [Release notes](#release-notes)
  - [More information](#more-information)
  - [License Information](#license-information)

## Description

This collection enables Ansible users to interact with [MCP](https://modelcontextprotocol.io/) servers through automation. MCP is a standardized protocol for communication between AI systems and external tools or data sources.

The collection provides modules to query server information, discover available tools, and execute tool calls on MCP servers within Ansible playbooks and Execution Environments.

## Requirements

### Ansible version compatibility

The collection supports ansible-core versions based on the `requires_ansible` value in [meta/runtime.yml](meta/runtime.yml):
- Tested with ansible-core 2.16.0 and later, and the current development version of Ansible. Ansible Core versions prior to 2.16.0 are not supported.

### Python version compatibility

This collection requires Python 3.10 or greater.

### Collection dependencies

This collection depends on the following collections:
- `ansible.utils`

### External requirements

Some modules and plugins require external libraries. Please check the
requirements for each plugin or module you use in the documentation to find out
which requirements are needed.

## Included content

<!--start collection content-->
### Connection Plugins
Name | Description
--- | ---
[ansible.mcp.mcp](https://github.com/ansible-collections/ansible.mcp/blob/main/docs/ansible.mcp.mcp_connection.rst)|Persistent connection to an Model Context Protocol (MCP) server

### Modules
Name | Description
--- | ---
[ansible.mcp.run_tool](https://github.com/ansible-collections/ansible.mcp/blob/main/docs/ansible.mcp.run_tool_module.rst)|Call a specific tool on an MCP server
[ansible.mcp.server_info](https://github.com/ansible-collections/ansible.mcp/blob/main/docs/ansible.mcp.server_info_module.rst)|Retrieve MCP server information
[ansible.mcp.tools_info](https://github.com/ansible-collections/ansible.mcp/blob/main/docs/ansible.mcp.tools_info_module.rst)|Retrieve a list of supported tools from an MCP server

<!--end collection content-->

## Testing

This collection is tested using GitHub Actions. To learn more about testing, refer to [CI.md](https://github.com/ansible-collections/ansible.mcp/blob/main/CI.md).

## Installation

```bash
    ansible-galaxy collection install ansible.mcp
```

You can also include it in a `requirements.yml` file and install it via
`ansible-galaxy collection install -r requirements.yml` using the format:

```yaml
collections:
  - name: ansible.mcp
```

To upgrade the collection to the latest available version, run the following
command:

```bash
ansible-galaxy collection install ansible.mcp --upgrade
```

You can also install a specific version of the collection, for example, if you
need to downgrade when something is broken in the latest version (please report
an issue in this repository). Use the following syntax where `X.Y.Z` can be any
[available version](https://galaxy.ansible.com/ansible/mcp):

```bash
ansible-galaxy collection install ansible.mcp:==X.Y.Z
```

See
[Ansible Using Collections](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html)
for more details.

## Support

For support and questions about this collection:

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/ansible-collections/ansible.mcp/issues)
- **Community Help**: Available on the [Ansible Forum](https://forum.ansible.com/)
- **Discussions**: Join the [Ansible collection development forum](https://forum.ansible.com/c/project/collection-development/27)

## Release notes

See the
[changelog](https://github.com/ansible-collections/ansible.mcp/tree/main/CHANGELOG.rst).

## More information

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Ansible Collection overview](https://github.com/ansible-collections/overview)
- [Ansible collection development forum](https://forum.ansible.com/c/project/collection-development/27)
- [Ansible User guide](https://docs.ansible.com/ansible/devel/user_guide/index.html)
- [Ansible Developer guide](https://docs.ansible.com/ansible/devel/dev_guide/index.html)
- [Ansible Collections Checklist](https://docs.ansible.com/ansible/devel/community/collection_contributors/collection_requirements.html)
- [Ansible Community code of conduct](https://docs.ansible.com/ansible/devel/community/code_of_conduct.html)
- [The Bullhorn (the Ansible Contributor newsletter)](https://docs.ansible.com/ansible/devel/community/communication.html#the-bullhorn)
- [News for Maintainers](https://forum.ansible.com/tag/news-for-maintainers)

## License Information

GNU General Public License v3.0 or later.

See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.txt) to see the full text.
