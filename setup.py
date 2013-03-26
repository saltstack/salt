#!/usr/bin/env python
'''
The setup script for salt
'''

import os
import urllib
from distutils import log
from distutils.core import setup
from distutils.command.build import build as distutils_build

setup_kwargs = {}
USE_SETUPTOOLS = False
SALTCLOUD_SOURCE_DIR = os.path.abspath(os.path.dirname(__file__))

BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION = os.environ.get(
    # The user can provide a different bootstrap-script version.
    # ATTENTION: A tag for that version MUST exist
    'BOOTSTRAP_SCRIPT_VERSION',
    # If no bootstrap-script version was provided from the environment, let's
    # provide the one we define.
    'v1.5.2'
)

if 'USE_SETUPTOOLS' in os.environ:
    try:
        from setuptools import setup
        USE_SETUPTOOLS = True
        saltcloud_reqs = os.path.join(SALTCLOUD_SOURCE_DIR, 'requirements.txt')
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
        open('saltcloud/version.py').read(), 'saltcloud/version.py', 'exec'
    )
)


class build(distutils_build):
    def run(self):
        # Let's update the bootstrap-script to the version defined to be
        # distributed. See BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION above.
        url = (
            'https://github.com/saltstack/salt-bootstrap/raw/{0}'
            '/bootstrap-salt.sh'.format(
                BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION
            )
        )
        req = urllib.urlopen(url)
        deploy_path = os.path.join(
            SALTCLOUD_SOURCE_DIR, 'saltcloud', 'deploy', 'bootstrap-salt.sh'
        )
        if req.getcode() == 200:
            try:
                log.info(
                    'Updating bootstrap-salt.sh.'
                    '\n\tSource:      {0}'
                    '\n\tDestination: {1}'.format(
                        url,
                        deploy_path
                    )
                )
                with open(deploy_path, 'w') as fp_:
                    fp_.write(req.read())
            except (OSError, IOError), err:
                log.error(
                    'Failed to write the updated script: {0}'.format(err)
                )
        else:
            log.error(
                'Failed to update the bootstrap-salt.sh script. HTTP Error '
                'code: {0}'.format(
                    req.getcode()
                )
            )

        # Let's the rest of the build command
        distutils_build.run(self)


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
      cmdclass={
          'build': build
      },
      **setup_kwargs
      )
