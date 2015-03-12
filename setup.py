#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
The setup script for salt
'''

# pylint: disable=C0111,E1101,E1103,F0401,W0611,W0201,W0232,R0201,R0902,R0903

# For Python 2.5.  A no-op on 2.6 and above.
from __future__ import print_function, with_statement

import os
import sys
import glob
import urllib2
from datetime import datetime
# pylint: disable=E0611
import distutils.dist
from distutils import log
from distutils.cmd import Command
from distutils.errors import DistutilsArgError
from distutils.command.build import build
from distutils.command.clean import clean
from distutils.command.sdist import sdist
from distutils.command.install_lib import install_lib
# pylint: enable=E0611

try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

# Change to salt source's directory prior to running any command
try:
    SETUP_DIRNAME = os.path.dirname(__file__)
except NameError:
    # We're most likely being frozen and __file__ triggered this NameError
    # Let's work around that
    SETUP_DIRNAME = os.path.dirname(sys.argv[0])

if SETUP_DIRNAME != '':
    os.chdir(SETUP_DIRNAME)

SETUP_DIRNAME = os.path.abspath(SETUP_DIRNAME)

BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION = os.environ.get(
    # The user can provide a different bootstrap-script version.
    # ATTENTION: A tag for that version MUST exist
    'BOOTSTRAP_SCRIPT_VERSION',
    # If no bootstrap-script version was provided from the environment, let's
    # provide the one we define.
    'v2014.06.21'
)

# Store a reference to the executing platform
IS_WINDOWS_PLATFORM = sys.platform.startswith('win')

# Use setuptools only if the user opts-in by setting the USE_SETUPTOOLS env var
# Or if setuptools was previously imported (which is the case when using
# 'distribute')
# This ensures consistent behavior but allows for advanced usage with
# virtualenv, buildout, and others.
WITH_SETUPTOOLS = False
if 'USE_SETUPTOOLS' in os.environ or 'setuptools' in sys.modules:
    try:
        from setuptools import setup
        from setuptools.command.install import install
        from setuptools.command.sdist import sdist
        from setuptools.command.egg_info import egg_info
        WITH_SETUPTOOLS = True
    except ImportError:
        WITH_SETUPTOOLS = False

if WITH_SETUPTOOLS is False:
    import warnings
    # pylint: disable=E0611
    from distutils.command.install import install
    from distutils.core import setup
    # pylint: enable=E0611
    warnings.filterwarnings(
        'ignore',
        'Unknown distribution option: \'(extras_require|tests_require|install_requires|zip_safe)\'',
        UserWarning,
        'distutils.dist'
    )

try:
    # Add the esky bdist target if the module is available
    # may require additional modules depending on platform
    from esky import bdist_esky
    # bbfreeze chosen for its tight integration with distutils
    import bbfreeze
    HAS_ESKY = True
except ImportError:
    HAS_ESKY = False

SALT_VERSION = os.path.join(os.path.abspath(SETUP_DIRNAME), 'salt', 'version.py')
SALT_VERSION_HARDCODED = os.path.join(os.path.abspath(SETUP_DIRNAME), 'salt', '_version.py')
SALT_REQS = os.path.join(os.path.abspath(SETUP_DIRNAME), '_requirements.txt')
SALT_ZEROMQ_REQS = os.path.join(os.path.abspath(SETUP_DIRNAME), 'zeromq-requirements.txt')
SALT_CLOUD_REQS = os.path.join(os.path.abspath(SETUP_DIRNAME), 'cloud-requirements.txt')
SALT_RAET_REQS = os.path.join(os.path.abspath(SETUP_DIRNAME), 'raet-requirements.txt')
SALT_SYSPATHS = os.path.join(os.path.abspath(SETUP_DIRNAME), 'salt', 'syspaths.py')

# Salt SSH Packaging Detection
PACKAGED_FOR_SALT_SSH_FILE = os.path.join(os.path.abspath(SETUP_DIRNAME), '.salt-ssh-package')
PACKAGED_FOR_SALT_SSH = os.path.isfile(PACKAGED_FOR_SALT_SSH_FILE)


# pylint: disable=W0122
exec(compile(open(SALT_VERSION).read(), SALT_VERSION, 'exec'))
exec(compile(open(SALT_SYSPATHS).read(), SALT_SYSPATHS, 'exec'))
# pylint: enable=W0122


# ----- Helper Functions -------------------------------------------------------------------------------------------->
def _parse_requirements_file(requirements_file):
    parsed_requirements = []
    with open(requirements_file) as rfh:
        for line in rfh.readlines():
            line = line.strip()
            if not line or line.startswith(('#', '-r')):
                continue
            if IS_WINDOWS_PLATFORM and 'libcloud' in line:
                continue
            parsed_requirements.append(line)
    return parsed_requirements
# <---- Helper Functions ---------------------------------------------------------------------------------------------


# ----- Custom Distutils/Setuptools Commands ------------------------------------------------------------------------>
class WriteSaltVersion(Command):

    description = 'Write salt\'s hardcoded version file'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if not os.path.exists(SALT_VERSION_HARDCODED):
            # Write the version file
            if getattr(self.distribution, 'salt_version_hardcoded_path', None) is None:
                print('This command is not meant to be called on it\'s own')
                exit(1)

            # pylint: disable=E0602
            open(self.distribution.salt_version_hardcoded_path, 'w').write(
                INSTALL_VERSION_TEMPLATE.format(
                    date=datetime.utcnow(),
                    full_version_info=__saltstack_version__.full_info
                )
            )
            # pylint: enable=E0602


class WriteSaltSshPackaingFile(Command):

    description = 'Write salt\'s ssh packaging file'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if not os.path.exists(PACKAGED_FOR_SALT_SSH_FILE):
            # Write the salt-ssh packaging file
            if getattr(self.distribution, 'salt_ssh_packaging_file', None) is None:
                print('This command is not meant to be called on it\'s own')
                exit(1)

            # pylint: disable=E0602
            open(self.distribution.salt_ssh_packaging_file, 'w').write('Packaged for Salt-SSH\n')
            # pylint: enable=E0602


class Sdist(sdist):

    def make_release_tree(self, base_dir, files):
        if self.distribution.ssh_packaging:
            self.distribution.salt_ssh_packaging_file = PACKAGED_FOR_SALT_SSH_FILE
            self.run_command('write-salt-ssh-packaging-file')
            self.filelist.files.append(os.path.basename(PACKAGED_FOR_SALT_SSH_FILE))

        sdist.make_release_tree(self, base_dir, files)

        # Let's generate salt/_version.py to include in the sdist tarball
        self.distribution.running_salt_sdist = True
        self.distribution.salt_version_hardcoded_path = os.path.join(
            base_dir, 'salt', '_version.py'
        )
        self.run_command('write-salt-version')

    def make_distribution(self):
        sdist.make_distribution(self)
        if self.distribution.ssh_packaging:
            os.unlink(PACKAGED_FOR_SALT_SSH_FILE)


class CloudSdist(Sdist):
    user_options = Sdist.user_options + [
        ('download-bootstrap-script', None,
         'Download the latest stable bootstrap-salt.sh script. This '
         'can also be triggered by having `DOWNLOAD_BOOTSTRAP_SCRIPT=1` as an '
         'environment variable.')

    ]
    boolean_options = Sdist.boolean_options + [
        'download-bootstrap-script'
    ]

    def initialize_options(self):
        Sdist.initialize_options(self)
        self.skip_bootstrap_download = True
        self.download_bootstrap_script = False

    def finalize_options(self):
        Sdist.finalize_options(self)
        if 'SKIP_BOOTSTRAP_DOWNLOAD' in os.environ:
            log('Please stop using \'SKIP_BOOTSTRAP_DOWNLOAD\' and use '
                '\'DOWNLOAD_BOOTSTRAP_SCRIPT\' instead')

        if 'DOWNLOAD_BOOTSTRAP_SCRIPT' in os.environ:
            download_bootstrap_script = os.environ.get(
                'DOWNLOAD_BOOTSTRAP_SCRIPT', '0'
            )
            self.download_bootstrap_script = download_bootstrap_script == '1'

    def run(self):
        if self.download_bootstrap_script is True:
            # Let's update the bootstrap-script to the version defined to be
            # distributed. See BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION above.
            url = (
                'https://github.com/saltstack/salt-bootstrap/raw/{0}'
                '/bootstrap-salt.sh'.format(
                    BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION
                )
            )
            deploy_path = os.path.join(
                SETUP_DIRNAME,
                'salt',
                'cloud',
                'deploy',
                'bootstrap-salt.sh'
            )
            log.info(
                'Updating bootstrap-salt.sh.'
                '\n\tSource:      {0}'
                '\n\tDestination: {1}'.format(
                    url,
                    deploy_path
                )
            )

            try:
                import requests
                req = requests.get(url)
                if req.status_code == 200:
                    script_contents = req.text.encode(req.encoding)
                else:
                    log.error(
                        'Failed to update the bootstrap-salt.sh script. HTTP '
                        'Error code: {0}'.format(
                            req.status_code
                        )
                    )
            except ImportError:
                req = urllib2.urlopen(url)

                if req.getcode() == 200:
                    script_contents = req.read()
                else:
                    log.error(
                        'Failed to update the bootstrap-salt.sh script. HTTP '
                        'Error code: {0}'.format(
                            req.getcode()
                        )
                    )
            try:
                with open(deploy_path, 'w') as fp_:
                    fp_.write(script_contents)
            except (OSError, IOError) as err:
                log.error(
                    'Failed to write the updated script: {0}'.format(err)
                )

        # Let's the rest of the build command
        Sdist.run(self)

    def write_manifest(self):
        # We only need to ship the scripts which are supposed to be installed
        dist_scripts = self.distribution.scripts
        for script in self.filelist.files[:]:
            if not script.startswith('scripts/'):
                continue
            if script not in dist_scripts:
                self.filelist.files.remove(script)
        return Sdist.write_manifest(self)


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


class Clean(clean):
    def run(self):
        clean.run(self)
        # Let's clean compiled *.py[c,o]
        for subdir in ('salt', 'tests', 'doc'):
            root = os.path.join(os.path.dirname(__file__), subdir)
            for dirname, _, _ in os.walk(root):
                for to_remove_filename in glob.glob('{0}/*.py[oc]'.format(dirname)):
                    os.remove(to_remove_filename)


INSTALL_VERSION_TEMPLATE = '''\
# This file was auto-generated by salt's setup on \
{date:%A, %d %B %Y @ %H:%m:%S UTC}.

from salt.version import SaltStackVersion

__saltstack_version__ = SaltStackVersion{full_version_info!r}
'''


INSTALL_SYSPATHS_TEMPLATE = '''\
# This file was auto-generated by salt's setup on \
{date:%A, %d %B %Y @ %H:%m:%S UTC}.

ROOT_DIR = {root_dir!r}
CONFIG_DIR = {config_dir!r}
CACHE_DIR = {cache_dir!r}
SOCK_DIR = {sock_dir!r}
SRV_ROOT_DIR= {srv_root_dir!r}
BASE_FILE_ROOTS_DIR = {base_file_roots_dir!r}
BASE_PILLAR_ROOTS_DIR = {base_pillar_roots_dir!r}
BASE_MASTER_ROOTS_DIR = {base_master_roots_dir!r}
LOGS_DIR = {logs_dir!r}
PIDFILE_DIR = {pidfile_dir!r}
'''


class Build(build):
    def run(self):
        # Run build.run function
        build.run(self)
        if getattr(self.distribution, 'running_salt_install', False):
            # If our install attribute is present and set to True, we'll go
            # ahead and write our install time python modules.

            # Write the hardcoded salt version module salt/_version.py
            self.run_command('write-salt-version')

            # Write the system paths file
            system_paths_file_path = os.path.join(
                self.build_lib, 'salt', '_syspaths.py'
            )
            open(system_paths_file_path, 'w').write(
                INSTALL_SYSPATHS_TEMPLATE.format(
                    date=datetime.utcnow(),
                    root_dir=self.distribution.salt_root_dir,
                    config_dir=self.distribution.salt_config_dir,
                    cache_dir=self.distribution.salt_cache_dir,
                    sock_dir=self.distribution.salt_sock_dir,
                    srv_root_dir=self.distribution.salt_srv_root_dir,
                    base_file_roots_dir=self.distribution.salt_base_file_roots_dir,
                    base_pillar_roots_dir=self.distribution.salt_base_pillar_roots_dir,
                    base_master_roots_dir=self.distribution.salt_base_master_roots_dir,
                    logs_dir=self.distribution.salt_logs_dir,
                    pidfile_dir=self.distribution.salt_pidfile_dir,
                )
            )


class Install(install):
    user_options = install.user_options + [
        ('salt-root-dir=', None,
         'Salt\'s pre-configured root directory'),
        ('salt-config-dir=', None,
         'Salt\'s pre-configured configuration directory'),
        ('salt-cache-dir=', None,
         'Salt\'s pre-configured cache directory'),
        ('salt-sock-dir=', None,
         'Salt\'s pre-configured socket directory'),
        ('salt-srv-root-dir=', None,
         'Salt\'s pre-configured service directory'),
        ('salt-base-file-roots-dir=', None,
         'Salt\'s pre-configured file roots directory'),
        ('salt-base-pillar-roots-dir=', None,
         'Salt\'s pre-configured pillar roots directory'),
        ('salt-base-master-roots-dir=', None,
         'Salt\'s pre-configured master roots directory'),
        ('salt-logs-dir=', None,
         'Salt\'s pre-configured logs directory'),
        ('salt-pidfile-dir=', None,
         'Salt\'s pre-configured pidfiles directory'),
    ]

    def initialize_options(self):
        install.initialize_options(self)
        # pylint: disable=undefined-variable
        self.salt_root_dir = ROOT_DIR
        self.salt_config_dir = CONFIG_DIR
        self.salt_cache_dir = CACHE_DIR
        self.salt_sock_dir = SOCK_DIR
        self.salt_srv_root_dir = SRV_ROOT_DIR
        self.salt_base_file_roots_dir = BASE_FILE_ROOTS_DIR
        self.salt_base_pillar_roots_dir = BASE_PILLAR_ROOTS_DIR
        self.salt_base_master_roots_dir = BASE_MASTER_ROOTS_DIR
        self.salt_logs_dir = LOGS_DIR
        self.salt_pidfile_dir = PIDFILE_DIR
        # pylint: enable=undefined-variable

    def finalize_options(self):
        install.finalize_options(self)

        for optname in ('root_dir', 'config_dir', 'cache_dir', 'sock_dir',
                        'srv_root_dir', 'base_file_roots_dir',
                        'base_pillar_roots_dir', 'base_master_roots_dir',
                        'logs_dir', 'pidfile_dir'):
            optvalue = getattr(self, 'salt_{0}'.format(optname))
            if not optvalue:
                raise DistutilsArgError(
                    'The value of --salt-{0} needs a proper path value'.format(
                        optname.replace('_', '-')
                    )
                )
            setattr(self.distribution, 'salt_{0}'.format(optname), optvalue)

    def run(self):
        # Let's set the running_salt_install attribute so we can add
        # _version.py in the build command
        self.distribution.running_salt_install = True
        self.distribution.salt_version_hardcoded_path = os.path.join(
            self.build_lib, 'salt', '_version.py'
        )
        # Run install.run
        install.run(self)


class InstallLib(install_lib):
    def run(self):
        executables = [
                'salt/templates/git/ssh-id-wrapper',
                'salt/templates/lxc/salt_tarball',
                ]
        install_lib.run(self)

        # input and outputs match 1-1
        inp = self.get_inputs()
        out = self.get_outputs()
        chmod = []

        for idx, inputfile in enumerate(inp):
            for executeable in executables:
                if inputfile.endswith(executeable):
                    chmod.append(idx)
        for idx in chmod:
            filename = out[idx]
            os.chmod(filename, 0755)
# <---- Custom Distutils/Setuptools Commands -------------------------------------------------------------------------


# ----- Custom Distribution Class ----------------------------------------------------------------------------------->
# We use this to override the package name in case --ssh-packaging is passed to
# setup.py or the special .salt-ssh-package is found
class SaltDistribution(distutils.dist.Distribution):
    '''
    Just so it's completely clear

    Under windows, the following scripts should be installed:

        * salt-call
        * salt-cp
        * salt-minion
        * salt-unity

    When packaged for salt-ssh, the following scripts should be installed:
        * salt-call
        * salt-run
        * salt-ssh
        * salt-cloud

        Under windows, the following scripts should be omitted from the salt-ssh package:
            * salt-cloud
            * salt-run

    Under *nix, all scripts should be installed
    '''
    global_options = distutils.dist.Distribution.global_options + [
        ('ssh-packaging', None, 'Run in SSH packaging mode'),
        ('salt-transport=', None, 'The transport to prepare salt for. Choices are \'zeromq\' '
                                  '\'raet\' or \'both\'. Defaults to \'zeromq\'', 'zeromq')
    ]

    def __init__(self, attrs=None):
        distutils.dist.Distribution.__init__(self, attrs)

        self.ssh_packaging = PACKAGED_FOR_SALT_SSH
        self.salt_transport = None

        self.salt_name = 'salt-ssh' if PACKAGED_FOR_SALT_SSH else 'salt'
        self.salt_version = __version__  # pylint: disable=undefined-variable
        self.salt_description = 'Portable, distributed, remote execution and configuration management system'
        self.salt_author = 'Thomas S Hatch'
        self.salt_author_email = 'thatch45@gmail.com'
        self.salt_url = 'http://saltstack.org'
        self.cmdclass.update({'test': TestCommand,
                              'clean': Clean,
                              'build': Build,
                              'sdist': Sdist,
                              'install': Install,
                              'write-salt-version': WriteSaltVersion,
                              'write-salt-ssh-packaging-file': WriteSaltSshPackaingFile})
        if not IS_WINDOWS_PLATFORM:
            self.cmdclass.update({'sdist': CloudSdist,
                                  'install_lib': InstallLib})

        self.license = 'Apache Software License 2.0'
        self.packages = self.discover_packages()
        self.zip_safe = False

        if HAS_ESKY:
            self.setup_esky()

        self.update_metadata()

    def update_metadata(self):
        for attrname in dir(self):
            attrvalue = getattr(self, attrname, None)
            if attrvalue == 0:
                continue
            if attrname.startswith('salt_'):
                attrname = attrname.split('salt_')[1]
            if hasattr(self.metadata, 'set_{0}'.format(attrname)):
                getattr(self.metadata, 'set_{0}'.format(attrname))(attrvalue)
            elif hasattr(self.metadata, attrname):
                setattr(self.metadata, attrname, attrvalue)

    def discover_packages(self):
        modules = []
        for root, _, files in os.walk(os.path.join(SETUP_DIRNAME, 'salt')):
            if '__init__.py' not in files:
                continue
            modules.append(os.path.relpath(root, SETUP_DIRNAME).replace(os.sep, '.'))
        return modules

    # ----- Static Data ---------------------------------------------------------------------------------------------
    @property
    def _property_classifiers(self):
        return ['Programming Language :: Python',
                'Programming Language :: Cython',
                'Programming Language :: Python :: 2.6',
                'Programming Language :: Python :: 2.7',
                'Development Status :: 5 - Production/Stable',
                'Environment :: Console',
                'Intended Audience :: Developers',
                'Intended Audience :: Information Technology',
                'Intended Audience :: System Administrators',
                'License :: OSI Approved :: Apache Software License',
                'Operating System :: POSIX :: Linux',
                'Topic :: System :: Clustering',
                'Topic :: System :: Distributed Computing']

    @property
    def _property_dependency_links(self):
        return ['https://github.com/saltstack/salt-testing/tarball/develop#egg=SaltTesting']

    @property
    def _property_tests_require(self):
        return ['SaltTesting']
    # <---- Static Data ----------------------------------------------------------------------------------------------

    # ----- Dynamic Data -------------------------------------------------------------------------------------------->
    @property
    def _property_package_data(self):
        package_data = {'salt.templates': ['rh_ip/*.jinja',
                                           'debian_ip/*.jinja',
                                           'virt/*.jinja',
                                           'git/*',
                                           'lxc/*',
                                          ]}
        if not IS_WINDOWS_PLATFORM:
            package_data['salt.cloud'] = ['deploy/*.sh']

        if not self.ssh_packaging and not PACKAGED_FOR_SALT_SSH:
            package_data['salt.daemons.flo'] = ['*.flo']
        return package_data

    @property
    def _property_data_files(self):
        # Data files common to all scenarios
        data_files = [
            ('share/man/man1', ['doc/man/salt-call.1']),
            ('share/man/man7', ['doc/man/salt.7'])
        ]
        if self.ssh_packaging or PACKAGED_FOR_SALT_SSH:
            data_files[0][1].append('doc/man/salt-ssh.1')
            if IS_WINDOWS_PLATFORM:
                return data_files
            data_files[0][1].extend(['doc/man/salt-run.1',
                                     'doc/man/salt-cloud.1'])
            return data_files

        if IS_WINDOWS_PLATFORM:
            data_files[0][1].extend(['doc/man/salt-cp.1',
                                     'doc/man/salt-minion.1',
                                     'doc/man/salt-unity.1'])
            return data_files

        # *nix, so, we need all man pages
        data_files[0][1].extend(['doc/man/salt-api.1',
                                 'doc/man/salt-cloud.1',
                                 'doc/man/salt-cp.1',
                                 'doc/man/salt-key.1',
                                 'doc/man/salt-master.1',
                                 'doc/man/salt-minion.1',
                                 'doc/man/salt-run.1',
                                 'doc/man/salt-ssh.1',
                                 'doc/man/salt-syndic.1',
                                 'doc/man/salt-unity.1'])
        return data_files

    @property
    def _property_install_requires(self):
        install_requires = _parse_requirements_file(SALT_REQS)

        if IS_WINDOWS_PLATFORM:
            install_requires.append('WMI')

        if self.salt_transport == 'zeromq':
            install_requires += _parse_requirements_file(SALT_ZEROMQ_REQS)
        elif self.salt_transport == 'raet':
            install_requires += _parse_requirements_file(SALT_RAET_REQS)
        return install_requires

    @property
    def _property_extras_require(self):
        if self.ssh_packaging:
            return {}
        return {'RAET': _parse_requirements_file(SALT_RAET_REQS),
                'Cloud': _parse_requirements_file(SALT_CLOUD_REQS)}

    @property
    def _property_scripts(self):
        # Scripts common to all scenarios
        scripts = ['scripts/salt-call']
        if self.ssh_packaging or PACKAGED_FOR_SALT_SSH:
            scripts.append('scripts/salt-ssh')
            if IS_WINDOWS_PLATFORM:
                return scripts
            scripts.extend(['scripts/salt-cloud', 'scripts/salt-run'])
            return scripts

        if IS_WINDOWS_PLATFORM:
            scripts.extend(['scripts/salt-cp',
                            'scripts/salt-minion',
                            'scripts/salt-unity'])
            return scripts

        # *nix, so, we need all scripts
        scripts.extend(['scripts/salt',
                        'scripts/salt-api',
                        'scripts/salt-cloud',
                        'scripts/salt-cp',
                        'scripts/salt-key',
                        'scripts/salt-master',
                        'scripts/salt-minion',
                        'scripts/salt-run',
                        'scripts/salt-ssh',
                        'scripts/salt-syndic',
                        'scripts/salt-unity'])
        return scripts

    @property
    def _property_entry_points(self):
        # console scripts common to all scenarios
        scripts = ['salt-call = salt.scripts:salt_call']
        if self.ssh_packaging or PACKAGED_FOR_SALT_SSH:
            scripts.append('salt-ssh = salt.scripts:salt_ssh')
            if IS_WINDOWS_PLATFORM:
                return {'console_scripts': scripts}
            scripts.extend(['salt-cloud = salt.scripts:salt_cloud',
                            'salt-run = salt.scripts:salt_run'])
            return {'console_scripts': scripts}

        if IS_WINDOWS_PLATFORM:
            scripts.extend(['salt-cp = salt.scripts:salt_cp',
                            'salt-minion = salt.scripts:salt_minion',
                            'salt-unity = salt.scripts:salt_unity'])
            return {'console_scripts': scripts}

        # *nix, so, we need all scripts
        scripts.extend(['salt = salt.scripts:salt_main',
                        'salt-api = salt.scripts:salt_api',
                        'salt-cloud = salt.scripts:salt_cloud',
                        'salt-cp = salt.scripts:salt_cp',
                        'salt-key = salt.scripts:salt_key',
                        'salt-master = salt.scripts:salt_master',
                        'salt-minion = salt.scripts:salt_minion',
                        'salt-run = salt.scripts:salt_run',
                        'salt-ssh = salt.scripts:salt_ssh',
                        'salt-syndic = salt.scripts:salt_syndic',
                        'salt-unity = salt.scripts:salt_unity'])
        return {'console_scripts': scripts}
    # <---- Dynamic Data ---------------------------------------------------------------------------------------------

    # ----- Esky Setup ---------------------------------------------------------------------------------------------->
    def setup_esky(self):
        opt_dict = self.get_option_dict('bdist_esky')
        opt_dict['freezer_module'] = ('setup script', 'bbfreeze')
        opt_dict['freezer_options'] = ('setup script', {'includes': self.get_esky_freezer_includes()})

    @property
    def _property_freezer_options(self):
        return {'includes': self.get_esky_freezer_includes()}

    def get_esky_freezer_includes(self):
        # Sometimes the auto module traversal doesn't find everything, so we
        # explicitly add it. The auto dependency tracking especially does not work for
        # imports occurring in salt.modules, as they are loaded at salt runtime.
        # Specifying includes that don't exist doesn't appear to cause a freezing
        # error.
        freezer_includes = [
            'zmq.core.*',
            'zmq.utils.*',
            'ast',
            'csv',
            'difflib',
            'distutils',
            'distutils.version',
            'numbers',
            'json',
            'M2Crypto',
            'Cookie',
            'asyncore',
            'fileinput',
            'sqlite3',
            'email',
            'email.mime.*',
            'requests',
            'sqlite3',
        ]
        if HAS_ZMQ and hasattr(zmq, 'pyzmq_version_info'):
            if HAS_ZMQ and zmq.pyzmq_version_info() >= (0, 14):
                # We're freezing, and when freezing ZMQ needs to be installed, so this
                # works fine
                if 'zmq.core.*' in freezer_includes:
                    # For PyZMQ >= 0.14, freezing does not need 'zmq.core.*'
                    freezer_includes.remove('zmq.core.*')

        if IS_WINDOWS_PLATFORM:
            freezer_includes.extend([
                'imp',
                'win32api',
                'win32file',
                'win32con',
                'win32com',
                'win32net',
                'win32netcon',
                'win32gui',
                'win32security',
                'ntsecuritycon',
                'pywintypes',
                'pythoncom',
                '_winreg',
                'wmi',
                'site',
                'psutil',
            ])
        elif sys.platform.startswith('linux'):
            freezer_includes.append('spwd')
            try:
                import yum  # pylint: disable=unused-variable
                freezer_includes.append('yum')
            except ImportError:
                pass
        elif sys.platform.startswith('sunos'):
            # (The sledgehammer approach)
            # Just try to include everything
            # (This may be a better way to generate freezer_includes generally)
            try:
                from bbfreeze.modulegraph.modulegraph import ModuleGraph
                mgraph = ModuleGraph(sys.path[:])
                for arg in glob.glob('salt/modules/*.py'):
                    mgraph.run_script(arg)
                for mod in mgraph.flatten():
                    if type(mod).__name__ != 'Script' and mod.filename:
                        freezer_includes.append(str(os.path.basename(mod.identifier)))
            except ImportError:
                pass
            # Include C extension that convinces esky to package up the libsodium C library
            # This is needed for ctypes to find it in libnacl which is in turn needed for raet
            # see pkg/smartos/esky/sodium_grabber{.c,_installer.py}
            freezer_includes.extend([
                'sodium_grabber',
                'ioflo',
                'raet',
                'libnacl',
            ])
        return freezer_includes
    # <---- Esky Setup -----------------------------------------------------------------------------------------------

    # ----- Overridden Methods -------------------------------------------------------------------------------------->
    def parse_command_line(self):
        args = distutils.dist.Distribution.parse_command_line(self)

        # Setup our property functions after class initialization and
        # after parsing the command line since most are set to None
        for funcname in dir(self):
            if not funcname.startswith('_property_'):
                continue
            property_name = funcname.split('_property_', 1)[-1]
            setattr(self, property_name, getattr(self, funcname))

        if not self.ssh_packaging and PACKAGED_FOR_SALT_SSH:
            self.ssh_packaging = 1

        if self.ssh_packaging:
            self.metadata.name = 'salt-ssh'
            self.salt_transport = 'ssh'
        elif self.salt_transport is None:
            self.salt_transport = 'zeromq'

        if self.salt_transport not in ('zeromq', 'raet', 'both', 'ssh', 'none'):
            raise DistutilsArgError(
                'The value of --salt-transport needs be \'zeromq\', '
                '\'raet\', \'both\', \'ssh\' or \'none\' not {0!r}'.format(
                    self.salt_transport
                )
            )

        return args
    # <---- Overridden Methods ---------------------------------------------------------------------------------------

# <---- Custom Distribution Class ------------------------------------------------------------------------------------


if __name__ == '__main__':
    setup(distclass=SaltDistribution)
