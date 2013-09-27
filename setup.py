#!/usr/bin/env python
'''
The setup script for salt
'''

import os
import sys
import urllib2
from distutils import log
from distutils.core import setup
from distutils.cmd import Command
from distutils.command.sdist import sdist as original_sdist

setup_kwargs = {}
USE_SETUPTOOLS = False
SALTCLOUD_SOURCE_DIR = os.path.abspath(os.path.dirname(__file__))

BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION = os.environ.get(
    # The user can provide a different bootstrap-script version.
    # ATTENTION: A tag for that version MUST exist
    'BOOTSTRAP_SCRIPT_VERSION',
    # If no bootstrap-script version was provided from the environment, let's
    # provide the one we define.
    'v1.5.8'
)

if 'USE_SETUPTOOLS' in os.environ:
    try:
        from setuptools import setup
        from setuptools.command.sdist import sdist as original_sdist
        USE_SETUPTOOLS = True
        saltcloud_reqs = os.path.join(SALTCLOUD_SOURCE_DIR, 'requirements.txt')
        requirements = ''
        with open(saltcloud_reqs) as f:
            requirements = f.read()

        setup_kwargs['install_requires'] = requirements
        setup_kwargs['dependency_links'] = [
            'https://github.com/saltstack/salt-testing/tarball/develop#egg=SaltTesting'
        ]
        setup_kwargs['tests_require'] = ['SaltTesting']
    except:
        USE_SETUPTOOLS = False


if USE_SETUPTOOLS is False:
    from distutils.core import setup

exec(
    compile(
        open('saltcloud/version.py').read(), 'saltcloud/version.py', 'exec'
    )
)


class sdist(original_sdist):
    user_options = original_sdist.user_options + [
        ('skip-bootstrap-download', None,
         'Skip downloading the bootstrap-salt.sh script. This can also be '
         'triggered by having `SKIP_BOOTSTRAP_DOWNLOAD=1` as an environment '
         'variable.')
    ]
    boolean_options = original_sdist.boolean_options + [
        'skip-bootstrap-download'
    ]

    def initialize_options(self):
        original_sdist.initialize_options(self)
        self.skip_bootstrap_download = False

    def finalize_options(self):
        original_sdist.finalize_options(self)
        if 'SKIP_BOOTSTRAP_DOWNLOAD' in os.environ:
            skip_bootstrap_download = os.environ.get(
                'SKIP_BOOTSTRAP_DOWNLOAD', '0'
            )
            self.skip_bootstrap_download = skip_bootstrap_download == '1'

    def run(self):
        if self.skip_bootstrap_download is False:
            # Let's update the bootstrap-script to the version defined to be
            # distributed. See BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION above.
            url = (
                'https://github.com/saltstack/salt-bootstrap/raw/{0}'
                '/bootstrap-salt.sh'.format(
                    BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION
                )
            )
            req = urllib2.urlopen(url)
            deploy_path = os.path.join(
                SALTCLOUD_SOURCE_DIR,
                'saltcloud',
                'deploy',
                'bootstrap-salt.sh'
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
                    'Failed to update the bootstrap-salt.sh script. HTTP '
                    'Error code: {0}'.format(
                        req.getcode()
                    )
                )

        # Let's the rest of the build command
        original_sdist.run(self)


class TestCommand(Command):
    description = 'Run tests'
    user_options = [
        ('runtests-opts=', 'R', 'Command line options to pass to runtests.py')
    ]

    def initialize_options(self):
        self.runtests_opts = None

    def finalize_options(self):
        pass

    def run(self):
        from subprocess import Popen
        self.run_command('build')
        build_cmd = self.get_finalized_command('build_ext')
        runner = os.path.abspath('tests/runtests.py')
        test_cmd = sys.executable + ' {0}'.format(runner)
        if self.runtests_opts:
            test_cmd += ' {0}'.format(self.runtests_opts)

        print('running test')
        test_process = Popen(
            test_cmd, shell=True,
            stdout=sys.stdout, stderr=sys.stderr,
            cwd=build_cmd.build_lib
        )
        test_process.communicate()
        sys.exit(test_process.returncode)


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
          'sdist': sdist,
          'test': TestCommand
      },
      **setup_kwargs
      )
