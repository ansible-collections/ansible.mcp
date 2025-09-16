# AWS IAM MCP Server Integration with Ansible

This directory demonstrates the integration of AWS IAM MCP Server with Ansible using the generic MCP connection plugin.

## Overview

The AWS IAM MCP Server provides comprehensive AWS Identity and Access Management operations through the Model Context Protocol (MCP). This integration allows Ansible to manage AWS IAM resources using standardized MCP tools.

## Files

### Playbooks
- **`mcp_aws.yml`** - Main demonstration playbook showcasing AWS IAM operations
- **`mcp_aws_cleanup.yml`** - Cleanup playbook to remove demo resources
- **`cleanup_user.yml`** - Task file for individual user cleanup

### Configuration
- **`inventory.json`** - Updated inventory including both GitHub and AWS IAM MCP servers

## AWS IAM MCP Server Features

Based on the [AWS IAM MCP Server documentation](https://awslabs.github.io/mcp/servers/iam-mcp-server/), this integration provides:

### Core IAM Management
- **User Management**: Create, list, retrieve, and delete IAM users
- **Role Management**: Create, list, and manage IAM roles with trust policies
- **Group Management**: Create, list, retrieve, and delete IAM groups with member management
- **Policy Management**: List and manage IAM policies (managed and inline)
- **Inline Policy Management**: Full CRUD operations for user and role inline policies
- **Permission Management**: Attach/detach policies to users and roles
- **Access Key Management**: Create and delete access keys for users

### Security Features
- **Policy Simulation**: Test permissions without making changes using `simulate_principal_policy`
- **Force Delete**: Safely remove users with all associated resources
- **Permissions Boundary Support**: Set permission boundaries for enhanced security
- **Trust Policy Validation**: Validate JSON trust policies for roles

## Prerequisites

1. **AWS Credentials**: Configure AWS credentials using one of these methods:
   ```bash
   # Option 1: AWS Profile (recommended)
   export AWS_PROFILE=your-profile-name
   
   # Option 2: Environment Variables
   export AWS_ACCESS_KEY_ID=your-access-key
   export AWS_SECRET_ACCESS_KEY=your-secret-key
   export AWS_REGION=us-east-1
   
   # Option 3: IAM Roles (for EC2/Lambda)
   # Automatically used when running on AWS services
   ```

2. **Required IAM Permissions**: The AWS credentials need comprehensive IAM permissions including:
   - `iam:ListUsers`, `iam:CreateUser`, `iam:DeleteUser`
   - `iam:ListRoles`, `iam:CreateRole`, `iam:DeleteRole`
   - `iam:ListGroups`, `iam:CreateGroup`, `iam:DeleteGroup`
   - `iam:AttachUserPolicy`, `iam:DetachUserPolicy`
   - `iam:CreateAccessKey`, `iam:DeleteAccessKey`
   - `iam:SimulatePrincipalPolicy`
   - And many more (see full list in AWS documentation)

3. **Installed Components**:
   - AWS IAM MCP Server: `pip install awslabs.iam-mcp-server`
   - AWS CLI: `brew install awscli` (for credential configuration)
   - Ansible MCP Collection (already present)

## Usage

### Running the Demo

1. **Configure AWS Credentials**:
   ```bash
   aws configure
   # Or set environment variables as shown above
   ```

2. **Run the main demo playbook**:
   ```bash
   ansible-playbook -i inventory.json mcp_aws.yml -v
   ```

3. **Clean up demo resources** (important to avoid charges):
   ```bash
   ansible-playbook -i inventory.json mcp_aws_cleanup.yml
   ```

### What the Demo Does

The `mcp_aws.yml` playbook demonstrates:

1. **Tool Discovery**: Lists all available AWS IAM MCP tools
2. **User Management**: 
   - Lists existing users
   - Creates a new demo user with tags
   - Retrieves user details
3. **Policy Management**:
   - Creates an inline S3 read-only policy
   - Lists and retrieves user policies
4. **Security Testing**:
   - Simulates policy permissions using `simulate_principal_policy`
5. **Access Key Management**:
   - Creates access keys for the user
   - Lists access keys
6. **Group Management**:
   - Creates a demo group
   - Adds user to the group
7. **Resource Discovery**:
   - Lists existing roles and managed policies

### Available MCP Tools

The AWS IAM MCP server provides 93 tools including:

#### User Management
- `list_users` - List all IAM users
- `create_user` - Create a new IAM user
- `get_user` - Get details of a specific user
- `delete_user` - Delete an IAM user (with force option)

#### Role Management
- `list_roles` - List all IAM roles
- `create_role` - Create a new IAM role
- `get_role` - Get details of a specific role
- `delete_role` - Delete an IAM role

#### Group Management
- `list_groups` - List all IAM groups
- `create_group` - Create a new IAM group
- `get_group` - Get group details including members
- `delete_group` - Delete an IAM group
- `add_user_to_group` - Add user to a group
- `remove_user_from_group` - Remove user from a group

#### Policy Management
- `list_policies` - List IAM policies
- `attach_user_policy` - Attach managed policy to user
- `detach_user_policy` - Detach managed policy from user
- `put_user_policy` - Create/update inline policy for user
- `get_user_policy` - Retrieve inline policy for user
- `delete_user_policy` - Delete inline policy from user
- `list_user_policies` - List inline policies for user

#### Access Key Management
- `create_access_key` - Create access key for user
- `delete_access_key` - Delete access key
- `list_access_keys` - List access keys for user

#### Security Analysis
- `simulate_principal_policy` - Test policy permissions

## Security Best Practices

Following the [AWS IAM MCP Server security recommendations](https://awslabs.github.io/mcp/servers/iam-mcp-server/):

1. **Principle of Least Privilege**: Grant minimum necessary permissions
2. **Use Roles for Applications**: Prefer IAM roles over users for applications
3. **Regular Access Reviews**: Periodically review and clean up unused resources
4. **Access Key Rotation**: Regularly rotate access keys
5. **Enable MFA**: Use multi-factor authentication where possible
6. **Policy Simulation**: Test policies before applying them to production
7. **Prefer Managed Policies**: Use managed policies over inline policies for reusable permissions

## Error Handling

The integration provides comprehensive error handling:
- **Authentication Errors**: Clear messages for credential issues
- **Permission Errors**: Specific information about missing permissions
- **Resource Not Found**: Helpful messages when resources don't exist
- **Validation Errors**: Detailed feedback on invalid parameters

## Important Notes

⚠️ **WARNING**: This demo creates real AWS IAM resources that may incur charges. Always run the cleanup playbook after testing.

🔐 **SECURITY**: Access keys are shown in the demo output. In production:
- Store access keys securely (e.g., AWS Secrets Manager)
- Use IAM roles instead of access keys when possible
- Rotate access keys regularly
- Never commit access keys to version control

💰 **COST**: While IAM operations are generally free, some operations and resource storage may incur minimal charges.

## Troubleshooting

1. **Authentication Issues**: Ensure AWS credentials are properly configured
2. **Permission Denied**: Check that your AWS credentials have sufficient IAM permissions
3. **MCP Server Not Found**: Verify the server path in inventory.json
4. **Connection Timeout**: Check network connectivity and AWS service availability

## Integration Architecture

```
Ansible Playbook
       ↓
MCP Connection Plugin (ansible.mcp.mcp)
       ↓
AWS IAM MCP Server (awslabs.iam-mcp-server)
       ↓
AWS IAM API
```

This architecture provides a standardized way to interact with AWS IAM services through the Model Context Protocol, making it easy to integrate with other MCP-compatible tools and services.
