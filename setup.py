#!/usr/bin/env python
'''
The setup script for saltapi
'''

import os
from distutils.core import setup

if os.environ.get('VIRTUAL_ENV'):
    from setuptools import setup

exec(compile(
    open("saltapi/version.py").read(), "saltapi/version.py", 'exec')
    )

NAME = 'salt-api'
VER = __version__
DESC = ('Generic interface for providing external access apis to Salt')


setup(
      name=NAME,
      version=VER,
      description=DESC,
      author='Thomas S Hatch',
      author_email='thatch@saltstack.com',
      url='http://saltstack.org',
      classifiers=[
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Development Status :: 1 - Experimental',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX :: Linux',
          'Topic :: System :: Distributed Computing',
          ],
      packages=['saltapi',
                'saltapi/netapi',
                'saltapi/netauth',
                ],
      data_files=[('share/man/man1',
                     ['doc/man/salt-api.1']),
                     ('share/man/man7',
                     ['doc/man/salt-api.7'])],
      scripts=['scripts/salt-api'],
     )
