# AWS CCAPI MCP Server Integration with Ansible

This directory contains files that demonstrate how to integrate the **AWS CCAPI MCP Server** with Ansible using the stdio transport. The CCAPI MCP server allows you to create and manage AWS infrastructure resources programmatically via the Cloud Control API.

This demo playbook creates a **VPC**, **Subnet**, **KeyPair** and **EC2 instance** using the MCP server, handling dependencies and dynamic resource properties automatically.

Reference: [AWS CCAPI MCP Server Documentation](https://awslabs.github.io/mcp/servers/ccapi-mcp-server)

---

## Overview

The AWS CCAPI MCP Server provides programmatic access to AWS resources via the Cloud Control API. This demo playbook showcases:
- Connecting to the MCP server using `stdio` transport via `uvx`
- Sequential creation of AWS resources with correct dependency handling:
    - VPC → Subnet → KeyPair → EC2
- Use of MCP tools for:
    - Resource code generation
    - Resource creation
    - Security scanning (Checkov)
    - Explanations of infrastructure and security findings
- Handling existing resources gracefully (AlreadyExists responses)
- Modular task structure with `tasks/process_resource.yml` to process any resource
- Conditional skipping of security scanning with `skip_security_check=True` if `SECURITY_SCANNING=disabled`

> **Note**: The CCAPI MCP server enforces a mandatory workflow and is interactive, some tools may prompt for confirmation during execution. Resources cannot be created without either running the security scan or explicitly allowing skipping with `skip_security_check=True`.

---

## Directory Structure

```bash
playbooks/aws_ccapi_demo
├── README.md                  # This documentation
├── demo.yml                   # Main Ansible playbook
├── group_vars
│   └── all.yml                # Variables for AWS, VPC, EC2, AMI, and KeyPair
├── inventory.yaml             # Inventory configuration for MCP server
├── manifest.json              # MCP server manifest for stdio connection
└── tasks
    └── process_resource.yml   # Task file that handles creating a single resource
```

---

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

### 4. AWS IAM Permissions

To run this playbook, the AWS credentials used must have valid IAM permissions to allow the MCP server to manage resources via the AWS Cloud Control API. 

The demo playbook only **creates resources** and reads their properties for processing. Therefore, the minimum required permissions are:
 
```bash
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudcontrol:GetResource",
        "cloudcontrol:CreateResource",
        "cloudformation:CreateGeneratedTemplate",
        "cloudformation:DescribeGeneratedTemplate",
        "cloudformation:GetGeneratedTemplate"
      ],
      "Resource": "*"
    }
  ]
}
```

For detailed information, see the [Cloud Control API IAM Permissions Documentation](https://awslabs.github.io/mcp/servers/ccapi-mcp-server#required-iam-permissions).


## Configuration

### manifest.json

Defines the stdio connection to the AWS CCAPI MCP 

```bash
{
  "server": {
    "awslabs.ccapi-mcp-server": {
      "type": "stdio",
      "command": "uvx",
      "args": ["awslabs.ccapi-mcp-server@latest"],
      "description": "AWS CCAPI MCP Server - Manages AWS infrastructure via Cloud Control API"
    }
  }
}
```

### inventory.yaml

Ansible inventory for MCP server:

```bash
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
            SECURITY_SCANNING: "{{ security_scanning }}"
```

Alternatively, instead of using ``AWS_PROFILE``, you may define ``AWS_ACCESS_KEY_ID`` and ``AWS_SECRET_ACCESS_KEY`` directly under ``ansible_mcp_server_env`` in the inventory.

### group_vars/all.yml

All key variables are defined in `group_vars/all.yml`:

```bash
# AWS Configuration
region: "{{ lookup('env', 'AWS_REGION') | default('us-east-1', true) }}"
profile: "{{ lookup('env', 'AWS_PROFILE') | default('default', true) }}"
security_scanning: "{{ lookup('env', 'SECURITY_SCANNING') | default('disabled', true) | lower }}"

# VPC Configuration
vpc_cidr: "10.1.0.0/16"
vpc_dns_support: true
vpc_dns_hostnames: true
vpc_tags:
  - Key: Name
    Value: "demo-vpc"

# Subnet Configuration
subnet_cidr: "10.1.1.0/24"
subnet_az: "{{ region }}a"
subnet_tags:
  - Key: Name
    Value: "demo-subnet"

# EC2 Configuration
ec2_instance_type: "t3.micro"
ec2_key_pair: "demo-key"
ec2_count: 1
ec2_tags:
  - Key: Name
    Value: "demo-ec2"

# AMI Configuration
ec2_ami_id: "ami-0156001f0548e90b1"
```
**NOTE**: The variable values in `group_vars/all.yml` (such as CIDR ranges, tags, AMI IDs, instance types, resource names, and security settings) are examples only. Before running the playbook, you must update all variables according to your own AWS environment and requirements. Failing to do so may cause resource creation errors or result in unintended configurations.

## Playbook Overview (demo.yml)

The playbook executes the following workflow:

1. Connect to MCP Server
    - Uses `ansible.mcp.server_info` to fetch MCP server information.
2. Check Environment and Get Token
    - Runs `check_environment_variables` to obtain an `environment_token`.
3. Initialize Resource Tracking
    - `resource_results` dictionary keeps track of created resources for dependency resolution.
4. Sequential Resource Creation Using `tasks/process_resource.yml`
   
   Each resource goes through a standardized workflow:
   - _Get AWS Session Info_: retrieves temporary, scoped credentials.
   - _Generate Infrastructure Code_: produces CCAPI-compliant JSON for the resource.
   - _Explain Code_: produces human-readable explanation and CloudFormation-like template.
   - _Security Scan_: Runs `run_checkov()` to validate code when enabled. If `security_scanning=disabled`, the playbook skips scanning and passes `skip_security_check=True` to `create_resource()`.
   - _Create Resource_: uses credentials and execution token (and Checkov token if scanned).
   - _Wait for Completion_: polls MCP server until resource creation succeeds.
   - _Store Output_: adds resource info to `resource_results` for later dependencies.

## Running the Demo

```bash
ansible-playbook -i playbooks/aws_ccapi_demo/inventory.yaml playbooks/aws_ccapi_demo/demo.yml
```

## Customization

You can customize variables in ``group_vars/all.yml``:

- **VPC settings**: ``vpc_cidr``, ``vpc_dns_support``, ``vpc_dns_hostnames``, ``vpc_tags``
- **Subnet**: ``subnet_cidr``, ``subnet_az``, ``subnet_tags``
- **EC2 settings**: ``ec2_instance_type``, ``ec2_count``, ``ec2_key_pair``, ``ec2_tags``
- **AWS region/profile**: ``AWS_REGION``, ``AWS_PROFILE``
- **Security scanning** is conditional on ``SECURITY_SCANNING`` variable.

_Example_: to create a larger VPC_

```bash
vpc_name: "custom-vpc"
vpc_cidr: "10.2.0.0/16"
ec2_instance_type: "t3.medium"
```

## Notes

- The CCAPI MCP server is designed for interactive sessions; certain tool actions may require manual confirmation.
- This playbook is intended for manual verification and demonstration purposes.
- Ensure your AWS credentials have sufficient IAM permissions for EC2 and VPC operations.
- Security scanning is optional but recommended. When disabled, skip_security_check=True is mandatory.
- All resources are automatically tagged with MCP management tags for auditability:
    - ``MANAGED_BY: CCAPI-MCP-SERVER``
    - ``MCP_SERVER_SOURCE_CODE``
    - ``MCP_SERVER_VERSION``
- The playbook handles existing resources gracefully using ``AlreadyExists`` responses.


### Security Scanning

The playbook optionally performs automated security validation using Checkov:

- When ``SECURITY_SCANNING`` is set to ``"enabled"``, all generated infrastructure code is scanned before resource creation. Any security findings are explained to the user, and the resource will only be created if validation passes.

- When ``SECURITY_SCANNING`` is set to ``"disabled"``, the security scan is skipped, and the playbook automatically sets ``skip_security_check=True`` for resource creation. A warning is displayed to inform users that resources will be created without automated security validation.

**Important:** Skipping security scanning does not bypass the MCP server workflow; it only bypasses automated Checkov validation. Ensure other security measures are in place when ``SECURITY_SCANNING`` is disabled, especially in production environments.