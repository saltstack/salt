#! /bin/env python
from __future__ import print_function
import sys
import os
import tarfile
import argparse
from os.path import dirname, join, abspath
from shutil import copy
from subprocess import check_call

parser = argparse.ArgumentParser(
        description='Build salt rpms',
        )
parser.add_argument('buildid',
        help='The build id to use i.e. the bit after the salt version in the package name',
        )
args = parser.parse_args()

src = abspath(join(dirname(__file__), '../..'))

sys.path.append(src)

import salt.version

salt_version = salt.version.__saltstack_version__.string

rpmbuild = join(os.environ['HOME'], 'rpmbuild')
copy(join(src, 'pkg/rpm/salt.spec'), join(rpmbuild, 'SPECS'))
for f in os.listdir(join(src, 'pkg/rpm')):
    if f in ['salt.spec', 'build.py']:
        continue
    copy(join(src, 'pkg/rpm', f), join(rpmbuild, 'SOURCES'))


def srcfilter(ti):
    if '/.git' in ti.name:
        return None
    return ti

with tarfile.open(join(rpmbuild, 'SOURCES/salt-%s.tar.gz' % salt_version), 'w|gz') as tf:
    tf.add(src, arcname='salt-%s' % salt_version,
           filter=srcfilter)


cmd = ['rpmbuild', '-bb',
       '--define=salt_version %s' % salt_version,
       '--define=buildid %s' % args.buildid,
       'salt.spec']
print('Executing: %s' % ' '.join('"%s"' % c for c in cmd))
check_call(cmd, cwd=join(rpmbuild, 'SPECS'))
