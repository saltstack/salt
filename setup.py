#!/usr/bin/env python
'''
The setup script for salt
'''

# For Python 2.5.  A no-op on 2.6 and above.
from __future__ import with_statement

import os
import sys
from distutils.cmd import Command
from distutils.command.clean import clean
from distutils.sysconfig import get_python_lib, PREFIX

# Change to salt source's directory prior to running any command
setup_dirname = os.path.dirname(__file__)
if setup_dirname != '':
    os.chdir(setup_dirname)

# Use setuptools only if the user opts-in by setting the USE_SETUPTOOLS env var
# This ensures consistent behavior but allows for advanced usage with
# virtualenv, buildout, and others.
with_setuptools = False
if 'USE_SETUPTOOLS' in os.environ:
    try:
        from setuptools import setup
        with_setuptools = True
    except:
        with_setuptools = False

if with_setuptools is False:
    from distutils.core import setup

salt_version = os.path.join(os.path.abspath(
    os.path.dirname(__file__)), 'salt', 'version.py')

salt_reqs = os.path.join(os.path.abspath(
    os.path.dirname(__file__)), 'requirements.txt')

exec(compile(open(salt_version).read(), salt_version, 'exec'))


class TestCommand(Command):
    description = 'Run tests'
    user_options = [
        ('runtests-opts=', 'R', 'Command line options to pass to runtests.py')
    ]

    def initialize_options(self):
        self.runtests_opts = None

    def finalize_options(self):
        pass

    def run(self):
        from subprocess import Popen
        self.run_command('build')
        build_cmd = self.get_finalized_command('build_ext')
        runner = os.path.abspath('tests/runtests.py')
        test_cmd = 'python {0}'.format(runner)
        if self.runtests_opts:
            test_cmd += ' {0}'.format(self.runtests_opts)

        print("running test")
        test_process = Popen(
            test_cmd, shell=True,
            stdout=sys.stdout, stderr=sys.stderr,
            cwd=build_cmd.build_lib
        )
        test_process.communicate()
        sys.exit(test_process.returncode)


class Clean(clean):
    def run(self):
        clean.run(self)
        # Let's clean compiled *.py[c,o]
        remove_extensions = ('.pyc', '.pyo')
        for subdir in ('salt', 'tests'):
            root = os.path.join(os.path.dirname(__file__), subdir)
            for dirname, dirnames, filenames in os.walk(root):
                for filename in filenames:
                    for ext in remove_extensions:
                        if filename.endswith(ext):
                            os.remove(os.path.join(dirname, filename))
                            break


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

with open(salt_reqs) as f:
    lines = f.read().split('\n')
    requirements = [line for line in lines if line]


setup_kwargs = {'name': NAME,
                'version': VER,
                'description': DESC,
                'author': 'Thomas S Hatch',
                'author_email': 'thatch45@gmail.com',
                'url': 'http://saltstack.org',
                'cmdclass': {'test': TestCommand, 'clean': Clean},
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
                             'salt.auth',
                             'salt.wheel',
                             'salt.tops',
                             'salt.grains',
                             'salt.modules',
                             'salt.pillar',
                             'salt.renderers',
                             'salt.returners',
                             'salt.runners',
                             'salt.states',
                             'salt.fileserver',
                             'salt.search',
                             'salt.output',
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
                # The dynamic module loading in salt.modules makes this
                # package zip unsafe.
                'zip_safe': False
                }


# bbfreeze explicit includes
# Sometimes the auto module traversal doesn't find everything, so we
# explicitly add it. The auto dependency tracking especially does not work for
# imports occurring in salt.modules, as they are loaded at salt runtime.
# Specifying includes that don't exist doesn't appear to cause a freezing
# error.
freezer_includes = [
    'zmq.core.*',
    'zmq.utils.*',
    'ast',
    'difflib',
    'distutils',
    'distutils.version',
    'json',
]

if sys.platform.startswith('win'):
    freezer_includes.extend([
        'win32api',
        'win32file',
        'win32con',
        'win32security',
        'ntsecuritycon',
        '_winreg',
        'wmi',
    ])
    setup_kwargs['install_requires'] += '\nwmi'
elif sys.platform.startswith('linux'):
    freezer_includes.extend([
        'yum',
        'spwd',
    ])

if 'bdist_esky' in sys.argv:
    # Add the esky bdist target if the module is available
    # may require additional modules depending on platform
    from esky import bdist_esky
    # bbfreeze chosen for its tight integration with distutils
    import bbfreeze
    options = setup_kwargs.get('options', {})
    options['bdist_esky'] = {
        "freezer_module": "bbfreeze",
        "freezer_options": {
            "includes": freezer_includes
        }
    }
    setup_kwargs['options'] = options

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
    # Distutils does not know what these are and throws warnings.
    # Stop the warning.
    setup_kwargs.pop('install_requires')
    setup_kwargs.pop('zip_safe')

if __name__ == '__main__':
    setup(**setup_kwargs)
