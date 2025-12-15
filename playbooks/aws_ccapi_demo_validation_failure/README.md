# AWS CCAPI MCP Server - Validation Failure Demo

This directory contains a demonstration playbook that showcases how the Ansible MCP collection handles validation failures when calling tools with invalid arguments. The CCAPI MCP server allows you to create and manage AWS infrastructure resources programmatically via the Cloud Control API.

Reference: [AWS CCAPI MCP Server Documentation](https://awslabs.github.io/mcp/servers/ccapi-mcp-server)

## Overview

The AWS CCAPI MCP Server provides programmatic access to AWS resources via the Cloud Control API.

This demo demonstrates three types of validation failures that can occur when calling MCP tools:

1. **Missing Required Parameters**: Calling a tool without providing required arguments
2. **Invalid Parameter Types**: Providing arguments with incorrect data types
3. **Unknown Parameters**: Providing parameters that are not defined in the tool's schema

## Files

- **`demo.yml`** - Demonstration playbook showcasing validation failure scenarios
- **`inventory.yaml`** - Inventory configuration for the AWS CCAPI MCP server
- **`manifest.json`** - MCP server manifest defining connection details

## Prerequisites

### 1. Python and uvx

The AWS CCAPI MCP server requires  **Python 3.12+ ** and **uvx**:

```bash
# Check if uvx is installed
uvx --version

# Install uv (includes uvx) if needed
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or via pip:

```bash
pip install uv
```

### 2. AWS Credentials

Configure AWS credentials for creating infrastructure:

```bash
# Option 1: AWS Profile (recommended)
aws configure --profile default

# Option 2: Environment Variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
export SECURITY_SCANNING=enabled   # or 'disabled'
```

### 3. Ansible MCP Collection

Install the Ansible MCP collection:

```bash
ansible-galaxy collection install ansible.mcp
```

## Configuration

### manifest.json
Defines the stdio connection to the AWS Core MCP server:

```json
{
  "awslabs.ccapi-mcp-server": {
    "type": "stdio",
    "command": "uvx",
    "args": ["awslabs.ccapi-mcp-server@latest"],
    "description": "AWS CCAPI MCP Server - Manages AWS infrastructure via Cloud Control API"
  }
}
```

### inventory.yaml
Ansible inventory with role-based server configuration:

```yaml
all:
  children:
    mcp_servers:
      hosts:
        aws_ccapi_server:
          ansible_connection: ansible.mcp.mcp
          ansible_mcp_server_name: awslabs.ccapi-mcp-server
          ansible_mcp_server_args: []
          ansible_command_timeout: 3600
          ansible_mcp_manifest_path: "{{ playbook_dir }}/manifest.json"
          ansible_mcp_server_env:
            AWS_REGION: "{{ region }}"
            AWS_PROFILE: "{{ profile }}"
            FASTMCP_LOG_LEVEL: ERROR
```

### Key Configuration Parameters

- **ansible_mcp_server_name**: References the server in manifest.json (`awslabs.ccapi-mcp-server`)
- **ansible_mcp_server_env**: Environment variables including:
  - `AWS_REGION`: Your AWS region
  - `AWS_PROFILE`: AWS CLI profile name
  - `FASTMCP_LOG_LEVEL`: Log level (ERROR, INFO, DEBUG)


## Usage

### Running the Demo

```bash
ansible-playbook -i inventory.yaml demo.yml
```

### What the Demo Does

The playbook demonstrates:

1. **Server Connection**: Connects to AWS CC API MCP server via stdio transport using uvx
2. **Server Discovery**: Retrieves server information (name, version, protocol)
3. **Tool Discovery**: Lists all available tools.
4. **Validation Failure Examples**: Three scenarios that trigger validation errors:
   - Missing the required `environment_token` parameter for `get_aws_session_info`
   - Providing `environment_token` as a number instead of a string
   - Providing an unknown parameter `invalid_param` that doesn't exist in the tool schema

### Expected Output

The playbook will show validation error messages for each failed scenario. The errors will be caught before the tool call reaches the MCP server, demonstrating client-side validation.

Example validation error messages:
- `"Tool 'get_aws_session_info' missing required parameters: environment_token"`
- `Parameter 'environment_token' for tool 'get_aws_session_info' should be of type 'string', but got 'int'`
- `Tool 'get_aws_session_info' received unknown parameters: invalid_param`

## Validation Behavior

The Ansible MCP collection performs validation using the tool's schema definition:

- **Required Parameters**: All parameters marked as `required` in the tool schema must be provided
- **Parameter Types**: Each parameter must match its defined type (string, number, boolean, array, object)
- **Unknown Parameters**: Only parameters defined in the tool schema are allowed

This validation happens in the `MCPClient.validate()` method before any request is sent to the MCP server, providing fast feedback and preventing unnecessary network calls.
