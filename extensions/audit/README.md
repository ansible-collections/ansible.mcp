# Indirect Node Queries in Ansible Collections

## Overview

In the context of Ansible automation, **indirect node queries** refer to discovering or verifying the scope of what you automate **through controllers, APIs, and structured task results** -- rather than connecting directly to each workload (for example a cloud instance, database, repository, or bastion). The approach is **provider-agnostic**: any **Model Context Protocol (MCP) server** you use with **ansible.mcp** (for example **GitHub**, **AWS**, or other integrations) yields the same audit shape, you infer usage from **module JSON** (what server was used, which tools exist, which tools ran) instead of polling every node.

This collection implements that idea for MCP-driven flows in **`extensions/audit/event_query.yml`**: **jq** programs keyed by `ansible.mcp.server_info`, `ansible.mcp.tools_info`, and `ansible.mcp.run_tool` map each module's **result document** into audit events (`canonical_facts` and `facts`). If a `select(...)` guard fails, **jq emits nothing** and **no audit event** is produced.

This file explains:

- What indirect node queries are (including workloads reached via **any** MCP server in this collection, not a single cloud provider)
- Why they are required
- What they enable and their value
- How **`extensions/audit/event_query.yml`** implements the queries for this collection

## What Are Indirect Node Queries?

Rather than connecting directly to each node to assess automation scope (for example a **VM**, a managed **database**, a **GitHub** org or repo, or serverless workloads behind a provider API), **indirect node queries** use **management-layer or controller-visible data** - here, **JSON from ansible.mcp modules** after tasks talk to MCP servers (for example **GitHub**, **AWS**, or others used in this repository's playbooks).

In **ansible.mcp**, this involves:

- Using **MCP tools** (for example GitHub, cloud, or infrastructure helpers) so provider-facing work is driven through **documented tool calls** instead of ad hoc per-host sessions where that is not desired or possible
- **Deriving audit facts** from **`server_info`** (which MCP server), **`tools_info`** (which tools are available), and **`run_tool`** (which tool ran with `server_name` and `tool_name` on the result), as defined in **`extensions/audit/event_query.yml`**

## Why Are They Required?

Directly connecting to every node (or treating only classic inventory as the source of truth for scope):

- Is **inefficient** in large-scale or multi-account / multi-org environments
- May be **prohibited** due to network segmentation, security groups, or policy
- **Does not scale** across many regions, accounts, tenants, or ephemeral compute
- Often leads to **incomplete or stale data** compared to what automation actually invoked

Using indirect node queries via **ansible.mcp** module results and **`event_query.yml`**:

- Aligns audit signals with **what the playbook actually executed** against MCP, regardless of which MCP server (for example GitHub or a cloud provider) handled the work
- Works when assessment must stay at the **automation and API/tool layer** rather than on-instance access
- Yields **non-invasive**, repeatable facts (`canonical_facts` / `facts`) for guardrails and downstream systems

## What Does It Do?

In practical terms, for this collection:

- Enables **guardrails** to see which MCP **servers**, **tool catalog entries**, and **tool invocations** (`run_tool`) appear in task results, relevant for **any** provider or integration exposed through MCP (not only one cloud)
- Reduces operational risk and improves **predictability** by tying audit output to the same JSON Ansible records for those modules

## Implementation: `event_query.yml`

Every emitted object has:

- **`canonical_facts`**: correlation identifiers (see per-module rules below).
- **`facts`**: always includes `device_type` and `infra_bucket: "mcp"`.

### `ansible.mcp.run_tool`

| Step | jq behavior |
|------|----------------|
| Filter | `select(.server_name != null and .tool_name != null)` on the module result root. |
| Classification filter | `select(.tool_classification.read_only != true)` -- only mutating tool calls produce audit events. |
| `canonical_facts` | `server_name`, `tool_name`. |
| `facts` | `device_type: "resource"`, `infra_bucket: "mcp"`. |

#### Tool Classification for Indirect Node Counting

Each `run_tool` invocation includes a `tool_classification` field that indicates whether the tool is read-only (query) or mutating (manages a resource). The `event_query.yml` JQ query filters on this field so that **only mutating tool calls count as indirect nodes**.

The classification uses two strategies in priority order:

1. **MCP ToolAnnotations** (`readOnlyHint`): When the MCP server provides protocol-level annotations on its tool definitions (e.g. Azure MCP Server), these are used directly. The classification `source` is `"annotation"`.
2. **Verb-prefix heuristic**: When annotations are not available (e.g. AWS MCP servers), the tool name is matched against known read-only prefixes (`list_`, `get_`, `describe_`, `find_`, `check_`, `search_`, `show_`, `simulate_`). The classification `source` is `"heuristic"`.

This approach relies on the empirically verified pattern that **MCP tools are single-resource operators for mutations** -- each mutating tool invocation corresponds to exactly one managed entity. Read-only tools (listing, querying) are excluded from the node count.

The classification logic lives in `plugins/plugin_utils/tool_classification.py` and runs inside the persistent connection process using already-cached tool definitions (zero additional MCP server calls).

### `ansible.mcp.server_info`

| Step | jq behavior |
|------|----------------|
| Input | `.server_info`. |
| Filter | `select(.serverInfo.name != null)`. |
| `canonical_facts` | `server_name` from `.serverInfo.name` only (no `tool_name`). |
| `facts` | `device_type: "server"`, `infra_bucket: "mcp"`. |

### `ansible.mcp.tools_info`

| Step | jq behavior |
|------|----------------|
| Input | Binds top-level `.server_name` as `$sn`, then iterates `.tools[]`. |
| Filter | `select(.name != null)` per element. |
| `canonical_facts` | `server_name: $sn`, `tool_name: .name` -- one event per tool. |
| `facts` | `device_type: "tool"`, `infra_bucket: "mcp"`. |

## Why This Is a Good Practice

| Benefit | Description |
|--------|-------------|
| Scalable | Many tools per server; one row per catalog entry where `.name` is set |
| Secure | Uses task result JSON; avoids requiring broad direct node access for scope discovery |
| Efficient | No extra per-node polling; maps existing module output |
| Integrated | Fits **ansible.mcp** and provider-agnostic MCP usage in this collection (for example GitHub or cloud demos) |
| Reliable | Stable envelope (`canonical_facts` / `facts`) and behavior aligned with **`event_query.yml`** |

## Extending Tool Classification

To add new read-only verb prefixes, edit the `READ_ONLY_PREFIXES` tuple in `plugins/plugin_utils/tool_classification.py`. Prefixes are matched with `str.startswith()`, so each entry should end with an underscore (e.g. `"query_"`).

When an MCP server starts publishing `ToolAnnotations` (per the MCP 2025-06-18 spec), those annotations take priority over the heuristic automatically -- no code changes required.
