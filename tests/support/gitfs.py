# -*- coding: utf-8 -*-
'''
Base classes for gitfs/git_pillar integration tests
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import errno
import logging
import os
import psutil
import shutil
import signal
import tempfile
import textwrap
import time

# Import Salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.yaml
from salt.fileserver import gitfs
from salt.pillar import git_pillar
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import LoaderModuleMockMixin, SaltReturnAssertsMixin
from tests.support.paths import TMP
from tests.support.helpers import (
    get_unused_localhost_port,
    requires_system_grains,
)
from tests.support.mock import patch

log = logging.getLogger(__name__)

USERNAME = 'gitpillaruser'
PASSWORD = 'saltrules'

_OPTS = {
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
}
PROC_TIMEOUT = 10
NOTSET = object()


class ProcessManager(object):
    '''
    Functions used both to set up self-contained SSH/HTTP servers for testing
    '''
    wait = 10

    def find_proc(self, name=None, search=None):
        def _search(proc):
            return any([search in x for x in proc.cmdline()])
        if name is None and search is None:
            raise ValueError('one of name or search is required')
        for proc in psutil.process_iter():
            if name is not None:
                if search is None:
                    if name in proc.name():
                        return proc
                elif name in proc.name() and _search(proc):
                    return proc
            else:
                if _search(proc):
                    return proc
        return None

    def wait_proc(self, name=None, search=None, timeout=PROC_TIMEOUT):
        for idx in range(1, self.wait + 1):
            proc = self.find_proc(name=name, search=search)
            if proc is not None:
                return proc
            else:
                if idx != self.wait:
                    log.debug(
                        'Waiting for %s process (%d of %d)',
                        name, idx, self.wait
                    )
                    time.sleep(1)
                else:
                    log.debug(
                        'Failed fo find %s process after %d seconds',
                        name, self.wait
                    )
        raise Exception(
            'Unable to find {0} process running from temp config file {1} '
            'using psutil'.format(name, search)
        )


class SSHDMixin(ModuleCase, ProcessManager, SaltReturnAssertsMixin):
    '''
    Functions to stand up an SSHD server to serve up git repos for tests.
    '''
    sshd_proc = None

    @classmethod
    def prep_server(cls):
        cls.sshd_config_dir = tempfile.mkdtemp(dir=TMP)
        cls.sshd_config = os.path.join(cls.sshd_config_dir, 'sshd_config')
        cls.sshd_port = get_unused_localhost_port()
        cls.url = 'ssh://{username}@127.0.0.1:{port}/~/repo.git'.format(
            username=cls.username,
            port=cls.sshd_port)
        home = '/root/.ssh'
        cls.ext_opts = {
            'url': cls.url,
            'privkey_nopass': os.path.join(home, cls.id_rsa_nopass),
            'pubkey_nopass': os.path.join(home, cls.id_rsa_nopass + '.pub'),
            'privkey_withpass': os.path.join(home, cls.id_rsa_withpass),
            'pubkey_withpass': os.path.join(home, cls.id_rsa_withpass + '.pub'),
            'passphrase': cls.passphrase}

    def spawn_server(self):
        ret = self.run_function(
            'state.apply',
            mods='git_pillar.ssh',
            pillar={'git_pillar': {'git_ssh': self.git_ssh,
                                   'id_rsa_nopass': self.id_rsa_nopass,
                                   'id_rsa_withpass': self.id_rsa_withpass,
                                   'sshd_bin': self.sshd_bin,
                                   'sshd_port': self.sshd_port,
                                   'sshd_config_dir': self.sshd_config_dir,
                                   'master_user': self.master_opts['user'],
                                   'user': self.username}}
        )

        try:
            self.sshd_proc = self.wait_proc(name='sshd',
                                            search=self.sshd_config)
        finally:
            # Do the assert after we check for the PID so that we can track
            # it regardless of whether or not something else in the SLS
            # failed (but the SSH server still started).
            self.assertSaltTrueReturn(ret)


class WebserverMixin(ModuleCase, ProcessManager, SaltReturnAssertsMixin):
    '''
    Functions to stand up an nginx + uWSGI + git-http-backend webserver to
    serve up git repos for tests.
    '''
    nginx_proc = uwsgi_proc = None

    @classmethod
    def prep_server(cls):
        '''
        Set up all the webserver paths. Designed to be run once in a
        setUpClass function.
        '''
        cls.root_dir = tempfile.mkdtemp(dir=TMP)
        cls.config_dir = os.path.join(cls.root_dir, 'config')
        cls.nginx_conf = os.path.join(cls.config_dir, 'nginx.conf')
        cls.uwsgi_conf = os.path.join(cls.config_dir, 'uwsgi.yml')
        cls.git_dir = os.path.join(cls.root_dir, 'git')
        cls.repo_dir = os.path.join(cls.git_dir, 'repos')
        cls.venv_dir = os.path.join(cls.root_dir, 'venv')
        cls.uwsgi_bin = os.path.join(cls.venv_dir, 'bin', 'uwsgi')
        cls.nginx_port = cls.uwsgi_port = get_unused_localhost_port()
        while cls.uwsgi_port == cls.nginx_port:
            # Ensure we don't hit a corner case in which two sucessive calls to
            # get_unused_localhost_port() return identical port numbers.
            cls.uwsgi_port = get_unused_localhost_port()
        cls.url = 'http://127.0.0.1:{port}/repo.git'.format(port=cls.nginx_port)
        cls.ext_opts = {'url': cls.url}
        # Add auth params if present (if so this will trigger the spawned
        # server to turn on HTTP basic auth).
        for credential_param in ('user', 'password'):
            if hasattr(cls, credential_param):
                cls.ext_opts[credential_param] = getattr(cls, credential_param)

    @requires_system_grains
    def spawn_server(self, grains):
        auth_enabled = hasattr(self, 'username') and hasattr(self, 'password')
        pillar = {'git_pillar': {'config_dir': self.config_dir,
                                 'git_dir': self.git_dir,
                                 'venv_dir': self.venv_dir,
                                 'root_dir': self.root_dir,
                                 'nginx_port': self.nginx_port,
                                 'uwsgi_port': self.uwsgi_port,
                                 'auth_enabled': auth_enabled}}

        # Different libexec dir for git backend on Debian-based systems
        git_core = '/usr/libexec/git-core' \
            if grains['os_family'] in ('RedHat') \
            else '/usr/lib/git-core'

        pillar['git_pillar']['git-http-backend'] = os.path.join(
            git_core,
            'git-http-backend')

        ret = self.run_function(
            'state.apply',
            mods='git_pillar.http',
            pillar=pillar)

        if not os.path.exists(pillar['git_pillar']['git-http-backend']):
            self.fail(
                '{0} not found. Either git is not installed, or the test '
                'class needs to be updated.'.format(
                    pillar['git_pillar']['git-http-backend']
                )
            )

        try:
            self.nginx_proc = self.wait_proc(name='nginx',
                                             search=self.nginx_conf)
            self.uwsgi_proc = self.wait_proc(name='uwsgi',
                                             search=self.uwsgi_conf)
        finally:
            # Do the assert after we check for the PID so that we can track
            # it regardless of whether or not something else in the SLS
            # failed (but the webserver still started).
            self.assertSaltTrueReturn(ret)


class GitTestBase(ModuleCase):
    '''
    Base class for all gitfs/git_pillar tests. Must be subclassed and paired
    with either SSHDMixin or WebserverMixin to provide the server.
    '''
    case = port = bare_repo = admin_repo = None
    maxDiff = None
    git_opts = '-c user.name="Foo Bar" -c user.email=foo@bar.com'
    ext_opts = {}

    # We need to temporarily skip pygit2 tests on EL7 until the EPEL packager
    # updates pygit2 to bring it up-to-date with libgit2.
    @requires_system_grains
    def is_el7(self, grains):
        return grains['os_family'] == 'RedHat' and grains['osmajorrelease'] == 7

    # Cent OS 6 has too old a version of git to handle the make_repo code, as
    # it lacks the -c option for git itself.
    @requires_system_grains
    def is_pre_el7(self, grains):
        return grains['os_family'] == 'RedHat' and grains['osmajorrelease'] < 7

    @classmethod
    def setUpClass(cls):
        cls.prep_server()

    def setUp(self):
        # Make the test class available to the tearDownClass so we can clean up
        # after ourselves. This (and the gated block below) prevent us from
        # needing to spend the extra time creating an ssh server and user and
        # then tear them down separately for each test.
        self.update_class(self)
        if self.is_pre_el7():  # pylint: disable=E1120
            self.skipTest(
                'RHEL < 7 has too old a version of git to run these tests')

    @classmethod
    def update_class(cls, case):
        '''
        Make the test class available to the tearDownClass. Note that this
        cannot be defined in a parent class and inherited, as this will cause
        the parent class to be modified.
        '''
        if getattr(cls, 'case') is None:
            setattr(cls, 'case', case)

    def make_repo(self, root_dir, user='root'):
        raise NotImplementedError()


class GitFSTestBase(GitTestBase, LoaderModuleMockMixin):
    '''
    Base class for all gitfs tests
    '''
    @requires_system_grains
    def setup_loader_modules(self, grains):  # pylint: disable=W0221
        return {
            gitfs: {
                '__opts__': copy.copy(_OPTS),
                '__grains__': grains,
            }
        }

    def make_repo(self, root_dir, user='root'):
        raise NotImplementedError()


class GitPillarTestBase(GitTestBase, LoaderModuleMockMixin):
    '''
    Base class for all git_pillar tests
    '''
    @requires_system_grains
    def setup_loader_modules(self, grains):  # pylint: disable=W0221
        return {
            git_pillar: {
                '__opts__': copy.copy(_OPTS),
                '__grains__': grains,
            }
        }

    def get_pillar(self, ext_pillar_conf):
        '''
        Run git_pillar with the specified configuration
        '''
        cachedir = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, cachedir, ignore_errors=True)
        ext_pillar_opts = salt.utils.yaml.safe_load(
            ext_pillar_conf.format(
                cachedir=cachedir,
                extmods=os.path.join(cachedir, 'extmods'),
                **self.ext_opts
            )
        )
        with patch.dict(git_pillar.__opts__, ext_pillar_opts):
            return git_pillar.ext_pillar(
                'minion',
                {},
                *ext_pillar_opts['ext_pillar'][0]['git']
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

        with salt.utils.files.fopen(
                os.path.join(self.admin_repo, 'top.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            base:
              '*':
                - foo
            '''))
        with salt.utils.files.fopen(
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
        with salt.utils.files.fopen(
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
        with salt.utils.files.fopen(
                os.path.join(self.admin_repo, 'top.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            dev:
              '*':
                - foo
            '''))
        with salt.utils.files.fopen(
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
        with salt.utils.files.fopen(
                os.path.join(self.admin_repo, 'top.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            base:
              '*':
                - bar
            '''))
        _push('top_only', 'add top_only branch')


class GitPillarSSHTestBase(GitPillarTestBase, SSHDMixin):
    '''
    Base class for GitPython and Pygit2 SSH tests
    '''
    id_rsa_nopass = id_rsa_withpass = None
    git_ssh = '/tmp/git_ssh'

    @classmethod
    def tearDownClass(cls):
        if cls.case.sshd_proc is not None:
            cls.case.sshd_proc.send_signal(signal.SIGTERM)
        cls.case.run_state('user.absent', name=cls.username, purge=True)
        for dirname in (cls.sshd_config_dir, cls.case.admin_repo,
                        cls.case.bare_repo):
            if dirname is not None:
                shutil.rmtree(dirname, ignore_errors=True)
        ssh_dir = os.path.expanduser('~/.ssh')
        for filename in (cls.id_rsa_nopass,
                         cls.id_rsa_nopass + '.pub',
                         cls.id_rsa_withpass,
                         cls.id_rsa_withpass + '.pub',
                         cls.git_ssh):
            try:
                os.remove(os.path.join(ssh_dir, filename))
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise

    def setUp(self):
        '''
        Create the SSH server and user, and create the git repo
        '''
        super(GitPillarSSHTestBase, self).setUp()
        self.sshd_proc = self.find_proc(name='sshd',
                                        search=self.sshd_config)
        self.sshd_bin = salt.utils.path.which('sshd')

        if self.sshd_proc is None:
            self.spawn_server()

            known_hosts_ret = self.run_function(
                'ssh.set_known_host',
                user=self.master_opts['user'],
                hostname='127.0.0.1',
                port=self.sshd_port,
                enc='ssh-rsa',
                fingerprint='fd:6f:7f:5d:06:6b:f2:06:0d:26:93:9e:5a:b5:19:46',
                hash_known_hosts=False,
                fingerprint_hash_type='md5',
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

    def get_pillar(self, ext_pillar_conf):
        '''
        Wrap the parent class' get_pillar() func in logic that temporarily
        changes the GIT_SSH to use our custom script, ensuring that the
        passphraselsess key is used to auth without needing to modify the root
        user's ssh config file.
        '''
        orig_git_ssh = os.environ.pop('GIT_SSH', NOTSET)
        os.environ['GIT_SSH'] = self.git_ssh
        try:
            return super(GitPillarSSHTestBase, self).get_pillar(ext_pillar_conf)
        finally:
            os.environ.pop('GIT_SSH', None)
            if orig_git_ssh is not NOTSET:
                os.environ['GIT_SSH'] = orig_git_ssh


class GitPillarHTTPTestBase(GitPillarTestBase, WebserverMixin):
    '''
    Base class for GitPython and Pygit2 HTTP tests
    '''
    @classmethod
    def tearDownClass(cls):
        for proc in (cls.case.nginx_proc, cls.case.uwsgi_proc):
            if proc is not None:
                try:
                    proc.send_signal(signal.SIGQUIT)
                except psutil.NoSuchProcess:
                    pass
        shutil.rmtree(cls.root_dir, ignore_errors=True)

    def setUp(self):
        '''
        Create and start the webserver, and create the git repo
        '''
        super(GitPillarHTTPTestBase, self).setUp()
        self.nginx_proc = self.find_proc(name='nginx',
                                         search=self.nginx_conf)
        self.uwsgi_proc = self.find_proc(name='uwsgi',
                                         search=self.uwsgi_conf)

        if self.nginx_proc is None and self.uwsgi_proc is None:
            self.spawn_server()  # pylint: disable=E1120

        self.make_repo(self.repo_dir)
