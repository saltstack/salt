#!/usr/bin/python2
'''
The setup script for salt
'''

from distutils.core import setup

setup(name='salt',
      version='0.6.0',
      description='Portable, distrubuted, remote execution system',
      author='Thomas S Hatch',
      author_email='thatch45@gmail.com',
      url='https://github.com/thatch45/salt',
      packages=['salt', 'salt.modules', 'salt.cli'],
      scripts=['scripts/salt-master',
               'scripts/salt-minion',
               'scripts/salt'],
      data_files=[('/etc/salt',
                    ['conf/master',
                     'conf/minion',
                    ]),
                ('/etc/rc.d/',
                    ['init/salt-minion',
                     'init/salt-master',
                    ]),
                 ],

     )
