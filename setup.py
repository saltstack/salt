#!/usr/bin/python2
'''
The setup script for salt
'''

from distutils.core import setup

setup(name='salt',
      version='0.6.9',
      description='Portable, distrubuted, remote execution system',
      author='Thomas S Hatch',
      author_email='thatch45@gmail.com',
      url='https://github.com/thatch45/salt',
      packages=['salt', 'salt.modules', 'salt.cli'],
      scripts=['scripts/salt-master',
               'scripts/salt-minion',
               'scripts/saltkey',
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
                    ])
                ('share/man/man7',
                    ['salt.7',
                    ])
                 ],

     )
