# Continuous Integration (CI)

## MCP Collection Testing

GitHub Actions are used to run the CI for the ansible.mcp collection. The workflows used for the CI can be found in the [.github/workflows](.github/workflows) directory.

### PR Testing Workflows

The following tests run on every pull request:

| Job | Description | Python Versions | ansible-core Versions |
| --- | ----------- | --------------- | --------------------- |
| [Changelog](.github/workflows/changelog.yaml) | Checks for the presence of changelog fragments | 3.12 | devel |
| [Linters](.github/workflows/linters.yaml) | Runs `black`, `flake8`, `isort`, `mypy`, and `yamllint` on plugins and tests | 3.12 | devel |
| [Sanity](.github/workflows/tests.yaml) | Runs ansible sanity checks | 3.10, 3.11, 3.12 | 2.16 |
| [Unit tests](.github/workflows/tests.yaml) | Executes unit test cases | 3.10, 3.11, 3.12 | 2.16 |
| [Ansible-lint](.github/workflows/tests.yaml) | Runs ansible-lint validation | Latest | devel |
| [Build-import](.github/workflows/tests.yaml) | Validates collection build and import | Latest | devel |

### Python Version Compatibility by ansible-core Version

These are outlined in the collection's [tox.ini](tox.ini) file and GitHub Actions workflow configurations.

| ansible-core Version | Sanity Tests | Unit Tests |
| -------------------- | ------------ | ---------- |
| 2.16 | 3.10, 3.11, 3.12 | 3.10, 3.11, 3.12 |
