#!/bin/bash -eu

# Script to run ansible galaxy unit tests

help()
{
    printf "Usage: run_unit_tests.sh [OPTION]\n"
    printf "\t-p\t\tThe python version to use (default: '%s').\n" "${PY_VERSION}"
    printf "\t-a\t\tThe ansible version to use (default: 'devel').\n"
}

PY_VERSION=$(python --version | cut -d '.' -f1,2 | cut -d ' ' -f2)
ANSIBLE_VERSION="devel"

while getopts ":ha:p:" option; do
    case $option in
        h)
            help
            exit;;
        p)
            PY_VERSION=$OPTARG;;
        a)
            ANSIBLE_VERSION=$OPTARG;;
        \?) # Invalid option
            echo "Error: Invalid option"
            exit;;
   esac
done

echo "ANSIBLE VERSION = ${ANSIBLE_VERSION}"
echo "PYTHON VERSION = ${PY_VERSION}"

echo "INSTALL tox-ansible"
python -m pip install tox-ansible
echo "RUN Unit tests"
python -m tox --ansible -e "unit-py${PY_VERSION}-${ANSIBLE_VERSION}" --conf tox-ansible.ini -v