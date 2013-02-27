#!/usr/bin/env python
'''
The setup script for salt
'''

import os
from distutils.core import setup

setup_kwargs = {}
USE_SETUPTOOLS = False
if 'USE_SETUPTOOLS' in os.environ:
    try:
        from setuptools import setup
        USE_SETUPTOOLS = True
        saltcloud_reqs = os.path.join(
            os.path.abspath(
                os.path.dirname(__file__)
            ),
            'requirements.txt'
        )
        requirements = ''
        with open(saltcloud_reqs) as f:
            requirements = f.read()

        setup_kwargs['install_requires'] = requirements
    except:
        USE_SETUPTOOLS = False


if USE_SETUPTOOLS is False:
    from distutils.core import setup

exec(
    compile(
        open("saltcloud/version.py").read(), "saltcloud/version.py", 'exec'
    )
)


NAME = 'salt-cloud'
VER = __version__
DESC = ('Generic cloud provisioning system with build in functions ')

setup(name=NAME,
      version=VER,
      description=DESC,
      author='Thomas S Hatch',
      author_email='thatch@saltstack.com',
      url='http://saltstack.org',
      classifiers=[
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Development Status :: 3 - Alpha',
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
      package_data={
          'saltcloud': ['deploy/*.sh'],
          },
      data_files=[('share/man/man1', ['doc/man/salt-cloud.1']),
                  ('share/man/man7', ['doc/man/salt-cloud.7'])
                  ],
      scripts=['scripts/salt-cloud'],
      **setup_kwargs
      )
