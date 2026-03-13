# Indirect Node Queries for AWS Resources

## Overview

In the context of Ansible automation, **indirect node queries** refer to the practice of discovering or verifying the inventory and state of AWS resources **through AWS APIs and control-plane services**, rather than connecting directly to each node (e.g., EC2 instance, RDS database). This approach is especially useful in complex, multi-account, or network-restricted AWS environments.

This file explains:
- What indirect node queries are
- Why they are required
- What they enable
- Their value

## What Are Indirect Node Queries?

Rather than connecting directly to each node to assess its state of automation (e.g., EC2 instance, RDS DB, Lambda function, etc.), **indirect node queries** leverage **AWS APIs** (such as EC2 DescribeInstances, RDS DescribeDBInstances, or resource-group and tag APIs) or other management layers to obtain usage and inventory information.

In an Ansible role or collection, this might involve:
- Querying AWS APIs for the list of EC2 instances, RDS instances, or other resources and their status or whether they are in scope for automation

## Why Are They Required?

Directly connecting to every node:
- Is **inefficient** in large-scale AWS environments (many regions and accounts)
- May be **prohibited** due to security groups, VPC design, or organizational policy
- **Doesn't scale** across multiple regions or AWS accounts
- Often leads to **incomplete or stale data**

Using indirect node queries via AWS APIs:
- Enables **centralized insight** into resource usage across accounts and regions
- Works well in **managed or disconnected environments** (e.g., read-only IAM roles)
- Allows **non-invasive** assessment (e.g., describe-only API access without SSH or RDP)

## What Does It Do?

In practical terms, using indirect node queries in an Ansible collection:
- Enables **guardrails** to verify what you are automating before running playbooks
- Reduces operational risk and improves **predictability** of automation workflows against AWS resources

## Why This Is a Good Practice

| Benefit | Description |
|--------|-------------|
| Scalable | Works across many regions and AWS accounts |
| Secure | Limits direct access to instances; uses IAM and API-only access |
| Efficient | Avoids per-node polling, uses AWS APIs and cached or aggregated data |
| Integrated | Leverages existing Certified and Validated collections (e.g., amazon.aws) |
| Reliable | Provides a consistent data source for automation decisions |
