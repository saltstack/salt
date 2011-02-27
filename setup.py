#!/usr/bin/python2

from distutils.core import setup

setup(name='salt',
      version='0.1',
      description='Portable, distrubuted, remote execution system',
      author='Thomas S Hatch',
      author_email='thatch45@gmail.com',
      url='https://github.com/thatch45/salt',
      packages=['salt'],
      scripts=['scripts/salt-master',
               'scripts/salt-minion'],
    data_files=[('/etc/salt',
                    ['conf/master.conf',
                     'conf/minion.conf',
                    ]),
                ('/etc/rc.d/',
                    ['init/salt-minion',
                     'init/salt-master',
                    ]),
                 ],

     )
