#!/usr/bin/python2
'''
The setup script for salt
'''
import os
import sys
from distutils import log
from distutils.cmd import Command
from distutils.core import setup
from distutils.extension import Extension
from distutils.sysconfig import get_python_lib, PREFIX
from Cython.Distutils import build_ext

NAME = 'salt'
VER = '0.9.2'
DESC = 'Portable, distrubuted, remote execution and configuration management system'

mod_path = os.path.join(get_python_lib(), 'salt/modules/')
doc_path = os.path.join(PREFIX, 'share/doc/', NAME + '-' + VER)
example_path = os.path.join(doc_path, 'examples')
template_path = os.path.join(example_path, 'templates')
if os.environ.has_key('SYSCONFDIR'):
    etc_path = os.environ['SYSCONFDIR']
else:
    etc_path = os.path.join(os.path.dirname(PREFIX), 'etc')

setup(
      name=NAME,
      version=VER,
      #ext_modules=[
      #    Extension('salt.modules.grains', ['salt/modules/grains.pyx']),
      #    Extension('salt.modules.cytest', ['salt/modules/cytest.pyx']),
      #    ],
      cmdclass={
          'build_ext': build_ext,
          },
      description=DESC,
      author='Thomas S Hatch',
      author_email='thatch45@gmail.com',
      url='https://github.com/thatch45/salt',
      classifiers = [
          'Programming Language :: Python',
          'Programming Language :: Cython',
          'Programming Language :: Python :: 2.5',
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX :: Linux',
          'Topic :: System :: Clustering',
          'Topic :: System :: Distributed Computing',
          ],
      packages=['salt',
                'salt.cli',
                'salt.ext',
                'salt.grains',
                'salt.modules',
                'salt.renderers',
                'salt.returners',
                'salt.runners',
                'salt.states',
                'salt.utils',
                ],
      scripts=['scripts/salt-master',
               'scripts/salt-minion',
               'scripts/salt-syndic',
               'scripts/salt-key',
               'scripts/salt-cp',
               'scripts/salt-call',
               'scripts/salt-run',
               'scripts/salt'],
      data_files=[(os.path.join(etc_path, 'salt'),
                    ['conf/master',
                     'conf/minion',
                    ]),
                ('share/man/man1',
                    ['doc/man/salt-master.1',
                     'doc/man/salt-key.1',
                     'doc/man/salt.1',
                     'doc/man/salt-cp.1',
                     'doc/man/salt-call.1',
                     'doc/man/salt-syndic.1',
                     'doc/man/salt-run.1',
                     'doc/man/salt-minion.1',
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
