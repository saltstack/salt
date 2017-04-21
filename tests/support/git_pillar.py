# -*- coding: utf-8 -*-
'''
Base classes for git_pillar integration tests
'''

# Import python libs
from __future__ import absolute_import
import errno
import logging
import os
import psutil
import random
import shutil
import string
import tempfile
import textwrap
import time
import yaml

# Import Salt libs
import salt.utils
from salt.pillar import git_pillar
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import LoaderModuleMockMixin, SaltReturnAssertsMixin
from tests.support.paths import FILES, TMP
from tests.support.helpers import (
    get_unused_localhost_port,
    requires_system_grains,
    Webserver,
)
from tests.support.mock import patch

log = logging.getLogger(__name__)


def _rand_key_name(length):
    return 'id_rsa_{0}'.format(
        ''.join(random.choice(string.ascii_letters) for _ in range(length))
    )


class GitPillarTestBase(ModuleCase,
                        LoaderModuleMockMixin,
                        SaltReturnAssertsMixin):
    '''
    Base class for all git_pillar tests
    '''
    case = port = bare_repo = admin_repo = None
    maxDiff = None
    git_opts = '-c user.name="Foo Bar" -c user.email=foo@bar.com'
    ext_opts = {}

    @requires_system_grains
    def setup_loader_modules(self, grains):  # pylint: disable=W0221
        return {
            git_pillar: {
                '__opts__': {
                    '__role': 'minion',
                    'environment': None,
                    'pillarenv': None,
                    'hash_type': 'sha256',
                    'file_roots': {},
                    'state_top': 'top.sls',
                    'state_top_saltenv': None,
                    'renderer': 'yaml_jinja',
                    'renderer_whitelist': [],
                    'renderer_blacklist': [],
                    'pillar_merge_lists': False,
                    'git_pillar_base': 'master',
                    'git_pillar_branch': 'master',
                    'git_pillar_env': '',
                    'git_pillar_root': '',
                    'git_pillar_ssl_verify': True,
                    'git_pillar_global_lock': True,
                    'git_pillar_user': '',
                    'git_pillar_password': '',
                    'git_pillar_insecure_auth': False,
                    'git_pillar_privkey': '',
                    'git_pillar_pubkey': '',
                    'git_pillar_passphrase': '',
                    'git_pillar_refspecs': [
                        '+refs/heads/*:refs/remotes/origin/*',
                        '+refs/tags/*:refs/tags/*',
                    ],
                    'git_pillar_includes': True,
                },
                '__grains__': grains,
            }
        }

    @classmethod
    def update_class(cls, case):
        '''
        Make the test class available to the tearDownClass. Note that this
        cannot be defined in a parent class and inherited, as this will cause
        the parent class to be modified.
        '''
        if getattr(cls, 'case') is None:
            setattr(cls, 'case', case)

    @classmethod
    def setUpClass(cls):
        cls.port = get_unused_localhost_port()

    def setUp(self):
        # Make the test class available to the tearDownClass so we can clean up
        # after ourselves. This (and the gated block below) prevent us from
        # needing to spend the extra time creating an ssh server and user and
        # then tear them down separately for each test.
        self.update_class(self)

    def get_pillar(self, ext_pillar_conf):
        '''
        Run git_pillar with the specified configuration
        '''
        cachedir = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, cachedir, ignore_errors=True)
        ext_pillar_opts = yaml.safe_load(
            ext_pillar_conf.format(
                cachedir=cachedir,
                extmods=os.path.join(cachedir, 'extmods'),
                **self.ext_opts
            )
        )
        with patch.dict(git_pillar.__opts__, ext_pillar_opts):
            return git_pillar.ext_pillar(
                'minion',
                ext_pillar_opts['ext_pillar'][0]['git'],
                {}
            )

    def make_repo(self, root_dir, user='root'):
        self.bare_repo = os.path.join(root_dir, 'repo.git')
        self.admin_repo = os.path.join(root_dir, 'admin')

        for dirname in (self.bare_repo, self.admin_repo):
            shutil.rmtree(dirname, ignore_errors=True)

        # Create bare repo
        self.run_function(
            'git.init',
            [self.bare_repo],
            user=user,
            bare=True)

        # Clone bare repo
        self.run_function(
            'git.clone',
            [self.admin_repo],
            url=self.bare_repo,
            user=user)

        def _push(branch, message):
            self.run_function(
                'git.add',
                [self.admin_repo, '.'],
                user=user)
            self.run_function(
                'git.commit',
                [self.admin_repo, message],
                user=user,
                git_opts=self.git_opts,
            )
            self.run_function(
                'git.push',
                [self.admin_repo],
                remote='origin',
                ref=branch,
                user=user,
            )

        with salt.utils.fopen(
                os.path.join(self.admin_repo, 'top.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            base:
              '*':
                - foo
            '''))
        with salt.utils.fopen(
                os.path.join(self.admin_repo, 'foo.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            branch: master
            mylist:
              - master
            mydict:
              master: True
              nested_list:
                - master
              nested_dict:
                master: True
            '''))
        # Add another file to be referenced using git_pillar_includes
        with salt.utils.fopen(
                os.path.join(self.admin_repo, 'bar.sls'), 'w') as fp_:
            fp_.write('included_pillar: True\n')
        _push('master', 'initial commit')

        # Do the same with different values for "dev" branch
        self.run_function(
            'git.checkout',
            [self.admin_repo],
            user=user,
            opts='-b dev')
        # The bar.sls shouldn't be in any branch but master
        self.run_function(
            'git.rm',
            [self.admin_repo, 'bar.sls'],
            user=user)
        with salt.utils.fopen(
                os.path.join(self.admin_repo, 'top.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            dev:
              '*':
                - foo
            '''))
        with salt.utils.fopen(
                os.path.join(self.admin_repo, 'foo.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            branch: dev
            mylist:
              - dev
            mydict:
              dev: True
              nested_list:
                - dev
              nested_dict:
                dev: True
            '''))
        _push('dev', 'add dev branch')

        # Create just a top file in a separate repo, to be mapped to the base
        # env and referenced using git_pillar_includes
        self.run_function(
            'git.checkout',
            [self.admin_repo],
            user=user,
            opts='-b top_only')
        # The top.sls should be the only file in this branch
        self.run_function(
            'git.rm',
            [self.admin_repo, 'foo.sls'],
            user=user)
        with salt.utils.fopen(
                os.path.join(self.admin_repo, 'top.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            base:
              '*':
                - bar
            '''))
        _push('top_only', 'add top_only branch')


class HTTPTestBase(GitPillarTestBase):
    '''
    Base class for GitPython and Pygit2 HTTP tests

    NOTE: root_dir must be overridden in a subclass
    '''
    goot_dir = None

    @classmethod
    def setUpClass(cls):
        '''
        Create start the webserver
        '''
        super(HTTPTestBase, cls).setUpClass()
        cls.webserver = cls.create_webserver()
        cls.webserver.start()
        cls.url = 'http://127.0.0.1:{port}/repo.git'.format(port=cls.port)
        cls.ext_opts = {
            'url': cls.url,
            'username': cls.username,
            'password': cls.password}

    @classmethod
    def tearDownClass(cls):
        '''
        Stop the webserver and cleanup the repo
        '''
        cls.webserver.stop()
        shutil.rmtree(cls.root_dir, ignore_errors=True)

    @classmethod
    def create_webserver(cls):
        '''
        Override this in a subclass with the handler argument to use a custom
        handler for HTTP Basic Authentication
        '''
        if cls.root_dir is None:
            raise Exception('root_dir not defined in test class')
        return Webserver(root=cls.root_dir, port=cls.port)

    def setUp(self):
        '''
        Create and start the webserver, and create the git repo
        '''
        super(HTTPTestBase, self).setUp()
        self.make_repo(self.root_dir)


class SSHTestBase(GitPillarTestBase):
    '''
    Base class for GitPython and Pygit2 SSH tests
    '''
    # Define a few variables and set to None so they're not culled in the
    # cleanup when the test function completes, and remain available to the
    # tearDownClass.
    sshd_proc = None
    # Creates random key names to (hopefully) ensure we're not overwriting an
    # existing key in /root/.ssh. Even though these are destructive tests, we
    # don't want to mess with something as important as ssh.
    id_rsa_nopass = _rand_key_name(8)
    id_rsa_withpass = _rand_key_name(8)
    sshd_wait = 10

    @classmethod
    def setUpClass(cls):
        super(SSHTestBase, cls).setUpClass()
        cls.url = 'ssh://{username}@127.0.0.1:{port}/~/repo.git'.format(
            username=cls.username,
            port=cls.port)
        home = '/root/.ssh'
        cls.ext_opts = {
            'url': cls.url,
            'privkey_nopass': os.path.join(home, cls.id_rsa_nopass),
            'pubkey_nopass': os.path.join(home, cls.id_rsa_nopass + '.pub'),
            'privkey_withpass': os.path.join(home, cls.id_rsa_withpass),
            'pubkey_withpass': os.path.join(home, cls.id_rsa_withpass + '.pub'),
            'passphrase': cls.passphrase}

    @classmethod
    def tearDownClass(cls):
        '''
        Stop the SSH server, remove the user, and clean up the config dir
        '''
        if cls.case.sshd_proc:
            try:
                cls.case.sshd_proc.kill()
            except psutil.NoSuchProcess:
                pass
        cls.case.run_state('user.absent', name=cls.username, purge=True)
        for dirname in (cls.sshd_config_dir, cls.case.admin_repo,
                        cls.case.bare_repo):
            if dirname is not None:
                shutil.rmtree(dirname, ignore_errors=True)
        ssh_dir = os.path.expanduser('~/.ssh')
        for filename in (cls.id_rsa_nopass, cls.id_rsa_withpass, cls.case.git_ssh):
            try:
                os.remove(os.path.join(ssh_dir, filename))
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise

    def setUp(self):
        '''
        Create the SSH server and user, and create the git repo
        '''
        super(SSHTestBase, self).setUp()
        sshd_config_file = os.path.join(self.sshd_config_dir, 'sshd_config')
        self.sshd_proc = self.find_sshd(sshd_config_file)
        self.sshd_bin = salt.utils.which('sshd')
        self.git_ssh = '/tmp/git_ssh'

        if self.sshd_proc is None:
            user_files = os.listdir(
                os.path.join(FILES, 'file/base/git_pillar/ssh/user/files')
            )
            ret = self.run_function(
                'state.apply',
                mods='git_pillar.ssh',
                pillar={'git_pillar': {'git_ssh': self.git_ssh,
                                       'id_rsa_nopass': self.id_rsa_nopass,
                                       'id_rsa_withpass': self.id_rsa_withpass,
                                       'sshd_bin': self.sshd_bin,
                                       'sshd_port': self.port,
                                       'sshd_config_dir': self.sshd_config_dir,
                                       'master_user': self.master_opts['user'],
                                       'user': self.username,
                                       'user_files': user_files}}
            )

            try:
                for idx in range(1, self.sshd_wait + 1):
                    self.sshd_proc = self.find_sshd(sshd_config_file)
                    if self.sshd_proc is not None:
                        break
                    else:
                        if idx != self.sshd_wait:
                            log.debug(
                                'Waiting for sshd process (%d of %d)',
                                idx, self.sshd_wait
                            )
                            time.sleep(1)
                        else:
                            log.debug(
                                'Failed fo find sshd process after %d seconds',
                                self.sshd_wait
                            )
                else:
                    raise Exception(
                        'Unable to find an sshd process running from temp '
                        'config file {0} using psutil. Check to see if an '
                        'instance of sshd from an earlier aborted run of '
                        'these tests is running, if so then manually kill '
                        'it and re-run test(s).'.format(sshd_config_file)
                    )
            finally:
                # Do the assert after we check for the PID so that we can track
                # it regardless of whether or not something else in the SLS
                # failed (but the SSH server still started).
                self.assertSaltTrueReturn(ret)

            known_hosts_ret = self.run_function(
                'ssh.set_known_host',
                user=self.master_opts['user'],
                hostname='127.0.0.1',
                port=self.port,
                enc='ssh-rsa',
                fingerprint='fd:6f:7f:5d:06:6b:f2:06:0d:26:93:9e:5a:b5:19:46',
                hash_known_hosts=False,
            )
            if 'error' in known_hosts_ret:
                raise Exception(
                    'Failed to add key to {0} user\'s known_hosts '
                    'file: {1}'.format(
                        self.master_opts['user'],
                        known_hosts_ret['error']
                    )
                )

        root_dir = os.path.expanduser('~{0}'.format(self.username))
        if root_dir.startswith('~'):
            self.fail(
                'Unable to resolve homedir for user \'{0}\''.format(
                    self.username
                )
            )
        self.make_repo(root_dir, user=self.username)

    def find_sshd(self, sshd_config_file):
        for proc in psutil.process_iter():
            if 'sshd' in proc.name():
                if sshd_config_file in proc.cmdline():
                    return proc
        return None
