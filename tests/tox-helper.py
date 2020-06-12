#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This script exists so that path handling when running tox works for both Linux and Windows

# Import Python Libs
from __future__ import absolute_import, unicode_literals
import os
import shutil
import argparse
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--rootdir',
        default=os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    )
    subparsers = parser.add_subparsers(help='sub-command help', dest='subparser')

    subparsers.add_parser('create-dirs')
    subparsers.add_parser('move-artifacts')

    options = parser.parse_args()
    if options.subparser == 'create-dirs':
        for dirname in ('logs', 'coverage', 'xml-unittests-output'):
            path = os.path.join(options.rootdir, 'artifacts', dirname)
            if not os.path.exists(path):
                os.makedirs(path)

    if options.subparser == 'move-artifacts':
        tmp_artifacts_dir = os.path.join(tempfile.gettempdir(), 'artifacts')
        if not os.path.exists(tmp_artifacts_dir):
            os.makedirs(tmp_artifacts_dir)

        for dirname in ('logs', 'coverage', 'xml-unittests-output'):
            src = os.path.join(options.rootdir, 'artifacts', dirname)
            dst = os.path.join(tmp_artifacts_dir, dirname)
            shutil.copytree(src, dst)


if __name__ == '__main__':
    main()
