#!/usr/bin/env python3
"""
LOCAL-ONLY reproduction harness (NOT for PR).

Proves whether every record emitted by ansible.mcp's extensions/audit/event_query.yml
carries a non-null, non-empty TOP-LEVEL `name`.

The controller stores each emitted record in main_indirectmanagednodeaudit.name,
which is NOT NULL. A record with no top-level `name` (or a null one) raises an
IntegrityError that aborts the whole job's bulk_create -> every indirect node for
that job is silently lost (the job still reports success).

Fixtures below are taken verbatim from the collection's own integration tests
(tests/integration/targets/node_query/tasks/test_github.yml and test_aws.yml) so
the module result shapes are faithful, not invented.

Usage:  python3 verify_mcp_event_query_name.py [path-to-event_query.yml]
Exit 0 = every emitted record has a valid top-level name; nonzero = defect present.
"""
import json
import subprocess
import sys

import yaml


def parse_event_queries(path):
    # same extraction the collection's own test parser uses:
    # key like "ansible.mcp.run_tool" -> short name "run_tool"
    with open(path, "rb") as f:
        content = list(yaml.safe_load_all(f))
    return {k.split(".")[2]: v["query"] for k, v in content[0].items()}


# (module_short_name, fixture_description, fixture_json, expected_emitted_records)
FIXTURES = [
    (
        "run_tool",
        "MUTATING tool call (github create_issue) -- THE BILLABLE EVENT",
        {
            "server_name": "github-mcp-server",
            "tool_name": "create_issue",
            "content": [{"type": "text", "text": "Issue created"}],
            "tool_classification": {"read_only": False, "destructive": False, "source": "heuristic"},
        },
        1,
    ),
    (
        "run_tool",
        "READ-ONLY tool call (iam list_groups) -- should emit nothing",
        {
            "server_name": "awslabs.iam-mcp-server",
            "tool_name": "list_groups",
            "tool_classification": {"read_only": True, "source": "heuristic"},
        },
        0,
    ),
    (
        "server_info",
        "server_info (github-mcp-server)",
        {"server_info": {"serverInfo": {"name": "github-mcp-server", "version": "1.0"}}},
        1,
    ),
    (
        "tools_info",
        "tools_info (2 tools on github-mcp-server)",
        {"server_name": "github-mcp-server", "tools": [{"name": "search_repositories"}, {"name": "create_issue"}]},
        2,
    ),
]


def run_jq(program, fixture):
    proc = subprocess.run(
        ["jq", "-c", program],
        input=json.dumps(fixture),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"jq error: {proc.stderr.strip()}")
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "extensions/audit/event_query.yml"
    queries = parse_event_queries(path)
    print(f"Parsed {len(queries)} module queries from {path}\n")

    total_records = 0
    records_with_name = 0
    failures = []

    for module, desc, fixture, expected in FIXTURES:
        program = queries[module]
        records = run_jq(program, fixture)
        status_count = "ok" if len(records) == expected else f"UNEXPECTED (got {len(records)}, expected {expected})"
        print(f"[{module}] {desc}")
        print(f"    emitted {len(records)} record(s) [{status_count}]")
        for rec in records:
            total_records += 1
            name = rec.get("name")
            ok = isinstance(name, str) and name != ""
            if ok:
                records_with_name += 1
                print(f"      top-level name = {name!r}  -> OK")
            else:
                failures.append((module, desc, name))
                print(f"      top-level name = {name!r}  -> MISSING/NULL  *** would abort controller insert ***")
        print()

    print("=" * 70)
    print(f"Records emitted: {total_records}   with valid top-level name: {records_with_name}")
    if failures:
        print(f"RESULT: FAIL -- {len(failures)} record(s) have no usable top-level name.")
        print("Every such record raises NotNullViolation and silently drops the job's audit data.")
        return 1
    print("RESULT: PASS -- every emitted record has a non-null top-level name.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
