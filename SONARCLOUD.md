# SonarQube Cloud in ansible.mcp

SonarQube Cloud (SonarCloud) is a Software-as-a-Service (SaaS) code analysis tool that helps maintain code quality by identifying issues related to maintainability, reliability, and security.

The **ansible.mcp** collection uses SonarQube Cloud to analyze the default branch and pull requests. **Unit test coverage** is produced in CI, uploaded as a `coverage` artifact, and passed to the scanner after the **`all_green`** workflow completes.

## Core concepts

1. **Clean as You Code**: New code is expected to meet the quality standards configured on the SonarCloud project.

2. **Clean Code Attributes**: Consistency, Intentionality, Adaptability, and Responsibility. See [Code analysis metrics](https://docs.sonarsource.com/sonarqube-cloud/digging-deeper/metric-definitions/).

3. **Software Quality**: SonarQube Cloud evaluates quality by flagging issues that violate clean code principles.

4. **Quality Standards**: Defined by a quality profile (rules) and a quality gate (conditions that must pass).

## Analysis method: CI-based analysis

The collection uses **CI-based analysis** with GitHub Actions:

- The **`all_green`** workflow (`.github/workflows/tests.yml`) runs linters, sanity, unit tests, and a dedicated **coverage** job.
- When **`all_green`** completes successfully, **SonarCloud** (`.github/workflows/sonarcloud.yml`) is triggered via **`workflow_run`**, downloads the **`coverage*`** artifact, and runs the SonarScanner with **`sonar.python.coverage.reportPaths`**.
- Configuration lives in **`sonar-project.properties`** at the repository root and the workflow files.

References:

- [CI-Based Analysis overview](https://docs.sonarsource.com/sonarqube-cloud/advanced-setup/ci-based-analysis/overview-of-integrated-cis/)
- [Test coverage in SonarCloud](https://docs.sonarsource.com/sonarqube-cloud/enriching/test-coverage/overview/)

## Configuration files

### `sonar-project.properties`

| Parameter | Value | Purpose |
|-----------|--------|---------|
| `sonar.projectKey` | `ansible-collections_ansible.mcp` | SonarCloud project identifier (must match the UI) |
| `sonar.organization` | `ansible-collections` | SonarCloud organization |
| `sonar.projectName` | `ansible.mcp` | Display name |
| `sonar.sources` | `.` | Root of analyzed source tree |
| `sonar.tests` | `tests/unit,tests/integration` | Test directories (test-aware analysis) |
| `sonar.exclusions` | `tests/**,.tox/**` | Paths excluded from main analysis |
| `sonar.python.coverage.reportPaths` | `coverage.xml` | Default coverage path; scanner may override via `-D` args |
| `sonar.python.version` | `3.12` | Python version for analysis (aligned with coverage job) |
| `sonar.newCode.referenceBranch` | `main` | Baseline branch for "new code" |

Full reference: [Analysis parameters](https://docs.sonarqube.org/latest/analysis/analysis-parameters/).

## GitHub Actions integration

### `tests.yml` (`name: all_green`)

- **Triggers**: `pull_request` and `push` to `main` / `stable-*`, plus `workflow_dispatch`.
- **Coverage job**: Checks out the collection under `ansible_collections/ansible/mcp`, installs **ansible.utils**, runs **`ansible-test units --coverage`** on ansible-core **stable-2.20** / Python **3.12**, rewrites paths in the Cobertura XML to be repo-relative, and uploads artifact **`coverage`**.
- **`all_green` gate**: Fails if build-import, sanity, unit-galaxy, ansible-lint, or coverage fail.

The workflow **`name:`** must be **`all_green`** so **`sonarcloud.yml`** `workflow_run.workflows` matches.

### `sonarcloud.yml`

- **Trigger**: `workflow_run` when **`all_green`** completes with **success**.
- **Permissions**: `contents: read`, `pull-requests: read`, **`actions: read`** (required to download artifacts from the triggering run).
- **Steps**: Checkout at **`workflow_run.head_sha`**, download **`coverage*`** artifacts, set **`sonar.python.coverage.reportPaths`**, optional PR metadata via **`gh`**, then **SonarCloud Scan** with **`ANSIBLE_COLLECTIONS_ORG_SONAR_TOKEN_CICD_BOT`**.

Using **`workflow_run`** runs Sonar in the **upstream** repository context so the org token is available even when the triggering PR came from a fork (after **`all_green`** succeeds).

### Prerequisites (org / admins)

1. A **SonarCloud project** exists for this GitHub repository and **`sonar.projectKey`** matches the UI exactly.
2. Org **Actions secret** **`ANSIBLE_COLLECTIONS_ORG_SONAR_TOKEN_CICD_BOT`** is available to workflows in the **ansible-collections** org.

## Coverage integration

1. **`coverage`** job in **`tests.yml`** produces Cobertura XML and uploads artifact **`coverage`**.
2. **`all_green`** depends on **`coverage`** completion.
3. **`sonarcloud.yml`** downloads the artifact for the same commit and passes paths to the scanner.

Dashboard: [ansible.mcp on SonarCloud](https://sonarcloud.io/project/overview?id=ansible-collections_ansible.mcp)

## Summary

| Item | Role |
|------|------|
| `sonar-project.properties` | Project key, org, sources, tests, exclusions, Python version, coverage path |
| `.github/workflows/tests.yml` | Aggregator **`all_green`**, coverage job, artifact upload |
| `.github/workflows/sonarcloud.yml` | Post-**`all_green`** scan with coverage via **`workflow_run`** |

## Debugging

1. Confirm the SonarCloud project exists and the **project key** matches `sonar-project.properties`.
2. If coverage is **0%** in Sonar but XML exists, check path rewriting in the coverage job (`sed` strips workspace and `ansible_collections/ansible/mcp/` prefixes).
3. If Sonar does not run, confirm **`all_green`** succeeded and the **`coverage`** artifact was uploaded.
4. Optional local run: install [SonarScanner CLI](https://docs.sonarsource.com/sonarqube-cloud/advanced-setup/ci-based-analysis/sonarscanner-cli/), set `SONAR_TOKEN` from [SonarCloud Security](https://sonarcloud.io/account/security), then from the repo root:

   ```sh
   sonar-scanner -Dsonar.projectBaseDir=. -Dsonar.host.url=https://sonarcloud.io
   ```

## References

- [SonarCloud Documentation](https://docs.sonarsource.com/sonarqube-cloud/)
- [GitHub Actions for SonarCloud](https://docs.sonarsource.com/sonarqube-cloud/advanced-setup/ci-based-analysis/github-actions-for-sonarcloud/)
- [workflow_run event](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#workflow_run)
- [Using secrets in GitHub Actions](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
- Related: [amazon.aws Sonar coverage PR #2871](https://github.com/ansible-collections/amazon.aws/pull/2871)
