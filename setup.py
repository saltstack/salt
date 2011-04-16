#!/usr/bin/python2
'''
The setup script for salt
'''
import os
from distutils.core import setup
from distutils.extension import Extension
from distutils.sysconfig import get_python_lib

mod_path = os.path.join(get_python_lib(), 'salt/modules/')

setup(name='salt',
      version='0.7.9',
      description='Portable, distrubuted, remote execution system',
      author='Thomas S Hatch',
      author_email='thatch45@gmail.com',
      url='https://github.com/thatch45/salt',
      packages=['salt',
                'salt.modules',
                'salt.cli',
                'salt.returners',
                ],
      scripts=['scripts/salt-master',
               'scripts/salt-minion',
               'scripts/saltkey',
               'scripts/salt-cp',
               'scripts/salt'],
      data_files=[('/etc/salt',
                    ['conf/master',
                     'conf/minion',
                    ]),
                ('share/man/man1',
                    ['man/salt-master.1',
                     'man/saltkey.1',
                     'man/salt.1',
                     'man/salt-minion.1',
                    ]),
                ('share/man/man7',
                    ['man/salt.7',
                    ]),
                (mod_path,
                    ['salt/modules/cytest.pyx',
                    ])
                 ],
     )
