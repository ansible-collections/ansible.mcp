#!/usr/bin/env bash

set -eux

# Change to the directory where this script is located
cd "$(dirname "$0")"

function cleanup() {
    rm -f ./inventory.yml
    exit 1
}

export ANSIBLE_ROLES_PATH="../"

trap 'cleanup'  ERR

# Configure test environment
ansible-playbook setup.yml -e '@../../integration_config.yml' "$@"

# Run tests
ansible-playbook test.yml -i inventory.yml "$@"

# Remove inventory file
rm -f ./inventory.yml
