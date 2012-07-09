#!/usr/bin/env python2
'''
The setup script for salt
'''

# For Python 2.5.  A no-op on 2.6 and above.
from __future__ import with_statement

import os
import sys
from distutils.cmd import Command
from distutils.sysconfig import get_python_lib, PREFIX

# Use setuptools if available, else fallback to distutils.
# As an example, setuptools is available in virtualenvs and buildouts through
# Setuptools or Distribute.
with_setuptools = False
if 'SETUPTOOLS' in os.environ:
    try:
        from setuptools import setup
        with_setuptools = True
    except:
        with_setuptools = False

if with_setuptools is False:
    from distutils.core import setup

exec(compile(open("salt/version.py").read(), "salt/version.py", 'exec'))


class TestCommand(Command):
    description = 'Run tests'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from subprocess import Popen
        self.run_command('build')
        build_cmd = self.get_finalized_command('build_ext')
        runner = os.path.abspath('tests/runtests.py')
        test_cmd = 'python %s' % runner
        print("running test")
        test_process = Popen(
            test_cmd, shell=True,
            stdout=sys.stdout, stderr=sys.stderr,
            cwd=build_cmd.build_lib
        )
        test_process.communicate()
        sys.exit(test_process.returncode)

NAME = 'salt'
VER = __version__
DESC = ('Portable, distributed, remote execution and '
        'configuration management system')
mod_path = os.path.join(get_python_lib(), 'salt/modules')
doc_path = os.path.join(PREFIX, 'share/doc', NAME + '-' + VER)
example_path = os.path.join(doc_path, 'examples')
template_path = os.path.join(example_path, 'templates')

if 'SYSCONFDIR' in os.environ:
    etc_path = os.environ['SYSCONFDIR']
else:
    etc_path = os.path.join(os.path.dirname(PREFIX), 'etc')

libraries = ['ws2_32'] if sys.platform == 'win32' else []

requirements = ''
with open('requirements.txt') as f:
    requirements = f.read()


setup_kwargs = {'name': NAME,
                'version': VER,
                'description': DESC,
                'author': 'Thomas S Hatch',
                'author_email': 'thatch45@gmail.com',
                'url': 'http://saltstack.org',
                'cmdclass': {'test': TestCommand},
                'classifiers': ['Programming Language :: Python',
                                'Programming Language :: Cython',
                                'Programming Language :: Python :: 2.6',
                                'Programming Language :: Python :: 2.7',
                                'Development Status :: 5 - Production/Stable',
                                'Environment :: Console',
                                'Intended Audience :: Developers',
                                'Intended Audience :: Information Technology',
                                'Intended Audience :: System Administrators',
                                ('License :: OSI Approved ::'
                                 ' Apache Software License'),
                                'Operating System :: POSIX :: Linux',
                                'Topic :: System :: Clustering',
                                'Topic :: System :: Distributed Computing',
                                ],
                'packages': ['salt',
                             'salt.cli',
                             'salt.ext',
                             'salt.grains',
                             'salt.modules',
                             'salt.pillar',
                             'salt.renderers',
                             'salt.returners',
                             'salt.runners',
                             'salt.states',
                             'salt.utils',
                             ],
                'package_data': {'salt.modules': ['rh_ip/*.jinja']},
                'data_files': [('share/man/man1',
                                ['doc/man/salt-master.1',
                                 'doc/man/salt-key.1',
                                 'doc/man/salt.1',
                                 'doc/man/salt-cp.1',
                                 'doc/man/salt-call.1',
                                 'doc/man/salt-syndic.1',
                                 'doc/man/salt-run.1',
                                 'doc/man/salt-minion.1',
                                 ]),
                               ('share/man/man7', ['doc/man/salt.7']),
                               ],
                'install_requires': requirements,
                }

if with_setuptools:
    setup_kwargs['entry_points'] = {
        "console_scripts": ["salt-master = salt.scripts:salt_master",
                            "salt-minion = salt.scripts:salt_minion",
                            "salt-syndic = salt.scripts:salt_syndic",
                            "salt-key = salt.scripts:salt_key",
                            "salt-cp = salt.scripts:salt_cp",
                            "salt-call = salt.scripts:salt_call",
                            "salt-run = salt.scripts:salt_run",
                            "salt = salt.scripts:salt_main"
                            ],
    }
else:
    setup_kwargs['scripts'] = ['scripts/salt-master',
                               'scripts/salt-minion',
                               'scripts/salt-syndic',
                               'scripts/salt-key',
                               'scripts/salt-cp',
                               'scripts/salt-call',
                               'scripts/salt-run',
                               'scripts/salt']

setup(**setup_kwargs)
