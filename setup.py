#!/usr/bin/env python
'''
The setup script for salt
'''

import os
from distutils.core import setup

if os.environ.get('VIRTUAL_ENV'):
    from setuptools import setup

exec(compile(
    open("saltcloud/version.py").read(),"saltcloud/version.py",'exec')
    )

NAME = 'saltcloud'
VER = __version__
DESC = ('Generic cloud provisioning system with build in functions ')


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
          'Development Status :: 2 - Pre-Alpha'
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX :: Linux',
          'Topic :: System :: Distributed Computing',
          ],
      packages=['saltcloud',
                'saltcloud/utils',
                'saltcloud/clouds',
                ],
      package_data = {
          'saltcloud': ['deploy/*'],
      },
      scripts=['scripts/salt-cloud'],
     )
