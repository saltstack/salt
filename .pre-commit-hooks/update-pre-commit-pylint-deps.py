#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Import Python libs
import os
import sys
import glob
import argparse

# Import 3rd-party libs
import ruamel.yaml
yaml = ruamel.yaml.YAML()
yaml.width = 200
yaml.default_flow_style = False
yaml.indent(sequence=4, offset=2)

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))

def collect_requirements():
    collected = set()
    for rfile in glob.glob(os.path.join(REPO_ROOT, 'requirements', '*.txt')):
        with open(rfile) as rfh:
            entries = rfh.read().splitlines()
            for entry in entries:
                if not entry:
                    continue
                if entry.startswith(('#', '-')):
                    continue
                if entry.startswith('ioflo'):
                    continue
                dep = entry.split('#', 1)[0]
                collected.add(dep)

    return collected


def rewrite_pre_commit_config(requirements):
    with open(os.path.join(REPO_ROOT, '.pre-commit-config.yaml')) as rfh:
        exising_config = yaml.load(rfh.read())
        for entry in exising_config['repos']:
            if entry['repo'] == 'https://github.com/pre-commit/mirrors-pylint':
                for hook in entry['hooks']:
                    hook['additional_dependencies'] = sorted(requirements)
        with open(os.path.join(REPO_ROOT, '.pre-commit-config.yaml'), 'w') as wfh:
            yaml.dump(exising_config, wfh)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+')
    opts = parser.parse_args()
    requirements = collect_requirements()
    rewrite_pre_commit_config(requirements)


if __name__ == '__main__':
    main()
