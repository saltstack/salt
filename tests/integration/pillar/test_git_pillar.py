# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
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

from salt.utils.gitfs import GITPYTHON_MINVER, PYGIT2_MINVER

# Import Salt Testing libs
import tests.integration as integration
from tests.support.case import ModuleCase
from tests.support.mixins import LoaderModuleMockMixin, SaltReturnAssertsMixin
from tests.support.helpers import destructiveTest, requires_system_grains
from tests.support.unit import skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.utils
from salt.pillar import git_pillar
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin
from salt.utils.versions import LooseVersion

try:
    import git
    HAS_GITPYTHON = \
        LooseVersion(git.__version__) >= LooseVersion(GITPYTHON_MINVER)
except ImportError:
    HAS_GITPYTHON = False

try:
    import pygit2
    HAS_PYGIT2 = \
        LooseVersion(pygit2.__version__) >= LooseVersion(PYGIT2_MINVER)
except ImportError:
    HAS_PYGIT2 = False

NOTSET = object()
SSHD_PORT = 54309
USER = 'gitpillaruser'
UID = 5920

log = logging.getLogger(__name__)


def _rand_key_name(length):
    return 'id_rsa_{0}'.format(
        ''.join(random.choice(string.ascii_letters) for _ in range(length))
    )


class SSHTestBase(ModuleCase, LoaderModuleMockMixin, SaltReturnAssertsMixin):
    '''
    Base class for GitPython and Pygit2 SSH tests
    '''
    maxDiff = None
    # Define a few variables and set to None so they're not culled in the
    # cleanup when the test function completes, and remain available to the
    # tearDownClass. The setUp will handle assigning values to these.
    case = sshd_proc = bare_repo = admin_repo = None
    # Creates random key names to (hopefully) ensure we're not overwriting an
    # existing key in /root/.ssh. Even though these are destructive tests, we
    # don't want to mess with something as important as ssh.
    id_rsa_nopass = _rand_key_name(8)
    id_rsa_withpass = _rand_key_name(8)
    git_opts = '-c user.name="Foo Bar" -c user.email=foo@bar.com'
    sshd_port = SSHD_PORT
    sshd_wait = 10
    user = USER
    uid = UID
    passphrase = 'saltrules'
    url = 'ssh://{user}@127.0.0.1:{port}/~/repo.git'.format(
        user=USER,
        port=SSHD_PORT)

    def setup_loader_modules(self):
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
                '__grains__': {},
            }
        }

    @classmethod
    def update_class(cls, case):
        '''
        Make the test class available to the tearDownClass
        '''
        if getattr(cls, 'case') is None:
            setattr(cls, 'case', case)

    @classmethod
    def setUpClass(cls):
        cls.orig_uid = os.geteuid()
        cls.orig_gid = os.getegid()
        cls.environ = dict([(x, y) for x, y in six.iteritems(os.environ)
                            if x in ('USER', 'HOME')])
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
        cls.case.run_state('user.absent', name=cls.user, purge=True)
        for dirname in (cls.sshd_config_dir, cls.case.admin_repo,
                        cls.case.bare_repo):
            if dirname is not None:
                shutil.rmtree(dirname, ignore_errors=True)
        ssh_dir = os.path.expanduser('~/.ssh')
        for key_name in (cls.id_rsa_nopass, cls.id_rsa_withpass):
            try:
                os.remove(os.path.join(ssh_dir, key_name))
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise

    @requires_system_grains
    def setUp(self, grains):
        '''
        Create the SSH server and user
        '''
        self.grains = grains
        # Make the test class available to the tearDownClass so we can clean up
        # after ourselves. This (and the gated block below) prevent us from
        # needing to spend the extra time creating an ssh server and user and
        # then tear them down separately for each test.
        self.update_class(self)

        sshd_config_file = os.path.join(self.sshd_config_dir, 'sshd_config')
        self.sshd_proc = self.find_sshd(sshd_config_file)
        self.sshd_bin = salt.utils.which('sshd')
        self.git_ssh = '/tmp/git_ssh'

        if self.sshd_proc is None:
            user_files = os.listdir(
                os.path.join(
                    integration.FILES, 'file/base/git_pillar/ssh/user/files'
                )
            )
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
                                       'user': self.user,
                                       'uid': self.uid,
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
                port=self.sshd_port,
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

        self.make_repo()

    def make_repo(self):
        self.bare_repo = os.path.expanduser('~{0}/repo.git'.format(self.user))
        if self.bare_repo.startswith('~'):
            self.bare_repo = None
            self.fail(
                'Unable to resolve homedir for user \'{0}\''.format(self.user))

        # Don't need to repeat the startswith check for this one, if we were
        # unable to resolve the homedir here, we'd have aborted already.
        self.admin_repo = os.path.expanduser('~{0}/admin_repo'.format(self.user))

        for dirname in (self.bare_repo, self.admin_repo):
            shutil.rmtree(dirname, ignore_errors=True)

        # Create bare repo
        self.run_function(
            'git.init',
            [self.bare_repo],
            user=self.user,
            bare=True)

        # Clone bare repo
        self.run_function(
            'git.clone',
            [self.admin_repo],
            url=self.bare_repo,
            user=self.user)

        def _push(branch, message):
            self.run_function(
                'git.add',
                [self.admin_repo, '.'],
                user=self.user)
            self.run_function(
                'git.commit',
                [self.admin_repo, message],
                user=self.user,
                git_opts=self.git_opts,
            )
            self.run_function(
                'git.push',
                [self.admin_repo],
                remote='origin',
                ref=branch,
                user=self.user,
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
            user=self.user,
            opts='-b dev')
        # The bar.sls shouldn't be in any branch but master
        self.run_function(
            'git.rm',
            [self.admin_repo, 'bar.sls'],
            user=self.user)
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
            user=self.user,
            opts='-b top_only')
        # The top.sls should be the only file in this branch
        self.run_function(
            'git.rm',
            [self.admin_repo, 'foo.sls'],
            user=self.user)
        with salt.utils.fopen(
                os.path.join(self.admin_repo, 'top.sls'), 'w') as fp_:
            fp_.write(textwrap.dedent('''\
            base:
              '*':
                - bar
            '''))
        _push('top_only', 'add top_only branch')

    def find_sshd(self, sshd_config_file):
        for proc in psutil.process_iter():
            if 'sshd' in proc.name():
                if sshd_config_file in proc.cmdline():
                    return proc
        return None

    def get_pillar(self, ext_pillar_conf):
        '''
        Run git_pillar with the specified configuration
        '''
        cachedir = tempfile.mkdtemp(dir=integration.TMP)
        self.addCleanup(shutil.rmtree, cachedir, ignore_errors=True)
        ext_pillar_opts = yaml.safe_load(
            ext_pillar_conf.format(
                cachedir=cachedir,
                extmods=os.path.join(cachedir, 'extmods'),
                **self.ext_opts
            )
        )
        with patch.dict(git_pillar.__opts__, ext_pillar_opts):
            with patch.dict(git_pillar.__grains__, self.grains):
                return git_pillar.ext_pillar(
                    'minion',
                    ext_pillar_opts['ext_pillar'][0]['git'],
                    {}
                )


@destructiveTest
@skipIf(not salt.utils.which('sshd'), 'sshd not present')
@skipIf(not HAS_GITPYTHON, 'GitPython >= {0} required'.format(GITPYTHON_MINVER))
@skipIf(salt.utils.is_windows(), 'minion is windows')
@skipIf(os.getuid() != 0, 'must be root to run this test')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestGitPythonSSH(SSHTestBase):
    '''
    Test git_pillar with GitPython using SSH authentication

    NOTE: Any tests added to this test class should have equivalent tests (if
    possible) in the TestPygit2SSH class. Also, bear in mind that the pygit2
    versions of these tests need to be more complex in that they need to test
    both with passphraseless and passphrase-protecteed keys, both with global
    and per-remote configuration. So for every time we run a GitPython test, we
    need to run that same test four different ways for pygit2. This is because
    GitPython's ability to use git-over-SSH is limited to passphraseless keys.
    So, unlike pygit2, we don't need to test global or per-repo credential
    config params since GitPython doesn't use them.
    '''
    sshd_config_dir = tempfile.mkdtemp(dir=integration.TMP)

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
            return super(TestGitPythonSSH, self).get_pillar(ext_pillar_conf)
        finally:
            os.environ.pop('GIT_SSH', None)
            if orig_git_ssh is not NOTSET:
                os.environ['GIT_SSH'] = orig_git_ssh

    def test_git_pillar_single_source(self):
        '''
        Test using a single ext_pillar repo
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True}}}
        )

    def test_git_pillar_multiple_sources_master_dev_no_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists disabled.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'dev',
             'mylist': ['dev'],
             'mydict': {'master': True,
                        'dev': True,
                        'nested_list': ['dev'],
                        'nested_dict': {'master': True, 'dev': True}}}
        )

    def test_git_pillar_multiple_sources_dev_master_no_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists disabled.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'dev': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True, 'dev': True}}}
        )

    def test_git_pillar_multiple_sources_master_dev_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists enabled.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'dev',
             'mylist': ['master', 'dev'],
             'mydict': {'master': True,
                        'dev': True,
                        'nested_list': ['master', 'dev'],
                        'nested_dict': {'master': True, 'dev': True}}}
        )

    def test_git_pillar_multiple_sources_dev_master_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists enabled.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['dev', 'master'],
             'mydict': {'master': True,
                        'dev': True,
                        'nested_list': ['dev', 'master'],
                        'nested_dict': {'master': True, 'dev': True}}}
        )

    def test_git_pillar_multiple_sources_with_pillarenv(self):
        '''
        Test using pillarenv to restrict results to those from a single branch
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True}}}
        )

    def test_git_pillar_includes_enabled(self):
        '''
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, so we should see the key from that
        SLS file (included_pillar) in the compiled pillar data.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True}},
             'included_pillar': True}
        )

    def test_git_pillar_includes_disabled(self):
        '''
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, but since includes are disabled it
        will not find the SLS file and the "included_pillar" key should not be
        present in the compiled pillar data. We should instead see an error
        message in the compiled data.
        '''
        ret = self.get_pillar('''\
            git_pillar_provider: gitpython
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(
            ret,
            {'branch': 'master',
             'mylist': ['master'],
             'mydict': {'master': True,
                        'nested_list': ['master'],
                        'nested_dict': {'master': True}},
             '_errors': ["Specified SLS 'bar' in environment 'base' is not "
                         "available on the salt master"]}
        )


@destructiveTest
@skipIf(not salt.utils.which('sshd'), 'sshd not present')
@skipIf(not HAS_PYGIT2, 'pygit2 >= {0} required'.format(PYGIT2_MINVER))
@skipIf(salt.utils.is_windows(), 'minion is windows')
@skipIf(os.getuid() != 0, 'must be root to run this test')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestPygit2SSH(SSHTestBase):
    '''
    Test git_pillar with pygit2 using SSH authentication

    NOTE: Any tests added to this test class should have equivalent tests (if
    possible) in the TestGitPythonSSH class.
    '''
    sshd_config_dir = tempfile.mkdtemp(dir=integration.TMP)

    def test_git_pillar_single_source(self):
        '''
        Test using a single ext_pillar repo
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True}}
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_master_dev_no_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists disabled.
        '''
        expected = {
            'branch': 'dev',
            'mylist': ['dev'],
            'mydict': {'master': True,
                       'dev': True,
                       'nested_list': ['dev'],
                       'nested_dict': {'master': True, 'dev': True}}
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_dev_master_no_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists disabled.
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'dev': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True, 'dev': True}}
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_master_dev_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists enabled.
        '''
        expected = {
            'branch': 'dev',
            'mylist': ['master', 'dev'],
            'mydict': {'master': True,
                       'dev': True,
                       'nested_list': ['master', 'dev'],
                       'nested_dict': {'master': True, 'dev': True}}
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_dev_master_merge_lists(self):
        '''
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists enabled.
        '''
        expected = {
            'branch': 'master',
            'mylist': ['dev', 'master'],
            'mydict': {'master': True,
                       'dev': True,
                       'nested_list': ['dev', 'master'],
                       'nested_dict': {'master': True, 'dev': True}}
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_multiple_sources_with_pillarenv(self):
        '''
        Test using pillarenv to restrict results to those from a single branch
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True}}
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            ''')
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_includes_enabled(self):
        '''
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, so we should see the
        "included_pillar" key from that SLS file in the compiled pillar data.
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True}},
            'included_pillar': True
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_only {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_only {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            ''')
        self.assertEqual(ret, expected)

    def test_git_pillar_includes_disabled(self):
        '''
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, but since includes are disabled it
        will not find the SLS file and the "included_pillar" key should not be
        present in the compiled pillar data. We should instead see an error
        message in the compiled data.
        '''
        expected = {
            'branch': 'master',
            'mylist': ['master'],
            'mydict': {'master': True,
                       'nested_list': ['master'],
                       'nested_dict': {'master': True}},
            '_errors': ["Specified SLS 'bar' in environment 'base' is not "
                        "available on the salt master"]
        }

        # passphraseless key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_includes: False
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphraseless key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_only {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, global credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_includes: False
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            ''')
        self.assertEqual(ret, expected)

        # passphrase-protected key, per-repo credential options
        ret = self.get_pillar('''\
            git_pillar_provider: pygit2
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_only {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            ''')
        self.assertEqual(ret, expected)
