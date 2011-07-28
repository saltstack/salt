#!/usr/bin/python2
'''
The setup script for salt
'''
import os
import sys
import unittest
from distutils import log
from distutils.cmd import Command
from distutils.core import setup
from distutils.extension import Extension
from distutils.sysconfig import get_python_lib, PREFIX

NAME = 'salt'
VER = '0.8.9'
DESC = 'Portable, distrubuted, remote execution and configuration management system'

mod_path = os.path.join(get_python_lib(), 'salt/modules/')
doc_path = os.path.join(PREFIX, 'share/doc/', NAME + '-' + VER)
example_path = os.path.join(doc_path, 'examples')
template_path = os.path.join(example_path, 'templates')
if os.environ.has_key('SYSCONFDIR'):
    etc_path = os.environ['SYSCONFDIR']
else:
    etc_path = os.path.join(os.path.dirname(PREFIX), 'etc')

class UnitTest(Command):
    description = "run unit tests"
    user_options = []

    def initialize_options(self):
        self.test_dirs = None

    def finalize_options(self):
        if self.test_dirs is None:
            self.test_dirs = ["test"]

    def run(self):
        errors = 0
        failures = 0
        for path in self.test_dirs:
            for root, dirs, files in os.walk(path):
                for filename in files:
                    if filename.startswith("test_") and \
                            filename.endswith(".py"):
                        results = self._run_test(os.path.join(root, filename))
                        errors += results[0]
                        failures += results[1]
        self.announce(
            "unit test: {} errors and {} failures".format(errors, failures),
            level=log.INFO)

    def _run_test(self, path):
        self.announce("run tests in " + path, log.INFO)
        dirname, basename = os.path.split(path)
        sys.path.insert(0, dirname)
        try:
            modname = os.path.splitext(basename)[0]
            mod = __import__(modname)
            if hasattr(mod, "test_suite"):
                suite = mod.test_suite()
                runner = unittest.TextTestRunner(verbosity=2)
                results = runner.run(suite)
                return len(results.errors), len(results.failures)
            else:
                return (0, 0)
        finally:
            if sys.path[0] == dirname:
                del sys.path[0]

setup(name=NAME,
      version=VER,
      cmdclass={"test":UnitTest},
      description=DESC,
      author='Thomas S Hatch',
      author_email='thatch45@gmail.com',
      url='https://github.com/thatch45/salt',
      classifiers = [
          'Programming Language :: Python',
          'Programming Language :: Cython',
          'Programming Language :: Python :: 2.5',
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX :: Linux',
          'Topic :: System :: Monitoring',
          'Topic :: System :: Clustering',
          'Topic :: System :: Distributed Computing',
          ],
      packages=['salt',
                'salt.modules',
                'salt.cli',
                'salt.returners',
                'salt.renderers',
                'salt.runners',
                'salt.grains',
                'salt.states',
                ],
      scripts=['scripts/salt-master',
               'scripts/salt-minion',
               'scripts/salt-monitor',
               'scripts/salt-key',
               'scripts/salt-cp',
               'scripts/salt-call',
               'scripts/salt-run',
               'scripts/salt'],
      data_files=[(os.path.join(etc_path, 'salt'),
                    ['conf/master',
                     'conf/minion',
                     'conf/monitor',
                    ]),
                ('share/man/man1',
                    ['doc/man/salt-master.1',
                     'doc/man/salt-key.1',
                     'doc/man/salt.1',
                     'doc/man/salt-cp.1',
                     'doc/man/salt-run.1',
                     'doc/man/salt-minion.1',
                     'doc/man/salt-monitor.1',
                    ]),
                ('share/man/man7',
                    ['doc/man/salt.7',
                    ]),
                (mod_path,
                    ['salt/modules/cytest.pyx',
                    ]),
                (doc_path,
                    ['LICENSE'
                    ]),
                (template_path,
                    ['doc/example/templates/yaml-jinja.yml',
                     'doc/example/templates/yaml-mako.yml',
                     'doc/example/templates/yaml.yml',
                     'doc/example/templates/json-jinja.json',
                     'doc/example/templates/json-mako.json',
                     'doc/example/templates/json.json',
                    ]),
                 ],
     )
