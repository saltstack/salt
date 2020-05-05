# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import getpass
import os
import tempfile
import time

import salt.master
import salt.transport.client
import salt.utils.platform
import salt.utils.files
import salt.utils.user

from tests.support.case import TestCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.runtests import RUNTIME_VARS


def keyuser():
    user = salt.utils.user.get_specific_user()
    if user.startswith('sudo_'):
        user = user[5:].replace('\\', '_')
    return user


class ClearFuncsAuthTestCase(TestCase):

    def test_auth_info_not_allowed(self):
        assert hasattr(salt.master.ClearFuncs, '_prep_auth_info')
        master = '127.0.0.1'
        ret_port = 64506
        user = getpass.getuser()
        keyfile = '.{}_key'.format(user)

        keypath = os.path.join(RUNTIME_VARS.TMP, 'rootdir', 'cache', keyfile)

        with salt.utils.files.fopen(keypath) as keyfd:
            key = keyfd.read()

        minion_config = {
            'transport': 'zeromq',
            'pki_dir': '/tmp',
            'id': 'root',
            'master_ip': master,
            'master_port': ret_port,
            'auth_timeout': 5,
            'auth_tries': 1,
            'master_uri': 'tcp://{0}:{1}'.format(master, ret_port)
        }

        clear_channel = salt.transport.client.ReqChannel.factory(
            minion_config, crypt='clear')

        msg = {'cmd': '_prep_auth_info'}
        rets = clear_channel.send(msg, timeout=15)
        ret_key = None
        for ret in rets:
            try:
                ret_key = ret[user]
                break
            except (TypeError, KeyError):
                pass
        assert ret_key != key, 'Able to retrieve user key'


class ClearFuncsPubTestCase(TestCase):

    def setUp(self):
        self.master = '127.0.0.1'
        self.ret_port = 64506
        self.tmpfile = os.path.join(tempfile.mkdtemp(), 'evil_file')
        self.master_opts = AdaptedConfigurationTestCaseMixin.get_config('master')

    def tearDown(self):
        try:
            os.remove(self.tmpfile + 'x')
        except OSError:
            pass
        delattr(self, 'master')
        delattr(self, 'ret_port')
        delattr(self, 'tmpfile')

    def test_pub_not_allowed(self):
        assert hasattr(salt.master.ClearFuncs, '_send_pub')
        assert not os.path.exists(self.tmpfile)
        minion_config = {
            'transport': 'zeromq',
            'pki_dir': '/tmp',
            'id': 'root',
            'master_ip': self.master,
            'master_port': self.ret_port,
            'auth_timeout': 5,
            'auth_tries': 1,
            'master_uri': 'tcp://{0}:{1}'.format(self.master, self.ret_port),
        }
        clear_channel = salt.transport.client.ReqChannel.factory(
            minion_config, crypt='clear')
        jid = '202003100000000001'
        msg = {
            'cmd': '_send_pub',
            'fun': 'file.write',
            'jid': jid,
            'arg': [self.tmpfile, 'evil contents'],
            'kwargs': {'show_jid': False, 'show_timeout': False},
            'ret': '',
            'tgt': 'minion',
            'tgt_type': 'glob',
            'user': 'root'
        }
        eventbus = salt.utils.event.get_event(
            'master',
            sock_dir=self.master_opts['sock_dir'],
            transport=self.master_opts['transport'],
            opts=self.master_opts)
        ret = clear_channel.send(msg, timeout=15)
        if salt.utils.platform.is_windows():
            time.sleep(30)
            timeout = 30
        else:
            timeout = 5
        ret_evt = None
        start = time.time()
        while time.time() - start <= timeout:
            raw = eventbus.get_event(timeout, auto_reconnect=True)
            if raw and 'jid' in raw and raw['jid'] == jid:
                ret_evt = raw
                break
        assert not os.path.exists(self.tmpfile), 'Evil file created'


class ClearFuncsConfigTest(TestCase):

    def setUp(self):
        master_opts = AdaptedConfigurationTestCaseMixin.get_config('master')
        self.conf_dir = os.path.dirname(master_opts['conf_file'])
        master = '127.0.0.1'
        ret_port = 64506
        user = keyuser()
        keyfile = '.{}_key'.format(user)
        keypath = os.path.join(RUNTIME_VARS.TMP, 'rootdir', 'cache', keyfile)

        with salt.utils.files.fopen(keypath) as keyfd:
            self.key = keyfd.read()

        self.minion_config = {
            'transport': 'zeromq',
            'pki_dir': '/tmp',
            'id': 'root',
            'master_ip': master,
            'master_port': ret_port,
            'auth_timeout': 5,
            'auth_tries': 1,
            'master_uri': 'tcp://{0}:{1}'.format(master, ret_port)
        }

    def tearDown(self):
        try:
            os.remove(os.path.join(self.conf_dir, 'evil.conf'))
        except OSError:
            pass
        delattr(self, 'conf_dir')
        delattr(self, 'key')
        delattr(self, 'minion_config')

    def test_clearfuncs_config(self):
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt='clear')

        msg = {
           'key': self.key,
           'cmd': 'wheel',
           'fun': 'config.update_config',
           'file_name': '../evil',
           'yaml_contents': 'win',
        }
        ret = clear_channel.send(msg, timeout=5)
        assert not os.path.exists(os.path.join(self.conf_dir, 'evil.conf')), \
            'Wrote file via directory traversal'
        assert ret['data']['return'] == 'Invalid path'


class ClearFuncsFileRoots(TestCase):

    def setUp(self):
        self.master_opts = AdaptedConfigurationTestCaseMixin.get_config('master')
        self.target_dir = os.path.dirname(
            self.master_opts['file_roots']['base'][0]
        )
        master = '127.0.0.1'
        ret_port = 64506
        user = keyuser()
        self.keyfile = '.{}_key'.format(user)
        keypath = os.path.join(RUNTIME_VARS.TMP, 'rootdir', 'cache', self.keyfile)

        with salt.utils.files.fopen(keypath) as keyfd:
            self.key = keyfd.read()

        self.minion_config = {
            'transport': 'zeromq',
            'pki_dir': '/tmp',
            'id': 'root',
            'master_ip': master,
            'master_port': ret_port,
            'auth_timeout': 5,
            'auth_tries': 1,
            'master_uri': 'tcp://{0}:{1}'.format(master, ret_port)
        }

    def tearDown(self):
        try:
            os.remove(os.path.join(self.target_dir, 'pwn.txt'))
        except OSError:
            pass
        delattr(self, 'master_opts')
        delattr(self, 'target_dir')
        delattr(self, 'keyfile')
        delattr(self, 'key')
        delattr(self, 'minion_config')

    def test_fileroots_write(self):
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt='clear')

        msg = {
            'key': self.key,
            'cmd': 'wheel',
            'fun': 'file_roots.write',
            'data': 'win',
            'path': os.path.join('..', 'pwn.txt'),
            'saltenv': 'base',
        }
        ret = clear_channel.send(msg, timeout=5)
        assert not os.path.exists(os.path.join(self.target_dir, 'pwn.txt')), \
            'Wrote file via directory traversal'

    def test_fileroots_read(self):
        rootdir = self.master_opts['root_dir']
        fileroot = self.master_opts['file_roots']['base'][0]
        # If this asserion fails the test may need to be re-written
        assert os.path.dirname(os.path.dirname(rootdir)) == os.path.dirname(fileroot)
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt='clear')
        readpath = os.path.join(
            '..',
            'salt-tests-tmpdir',
            'rootdir',
            'cache',
            self.keyfile,
        )
        msg = {
            'key': self.key,
            'cmd': 'wheel',
            'fun': 'file_roots.read',
            'path': os.path.join(
                '..',
                'salt-tests-tmpdir',
                'rootdir',
                'cache',
                self.keyfile,
            ),
            'saltenv': 'base',
        }

        ret = clear_channel.send(msg, timeout=5)
        try:
            # When vulnerable this assertion will fail.
            assert list(ret['data']['return'][0].items())[0][1] != self.key, \
                'Read file via directory traversal'
        except IndexError:
            pass
        # If the vulnerability is fixed, no data will be returned.
        assert ret['data']['return'] == []


class ClearFuncsTokenTest(TestCase):

    def setUp(self):
        self.master_opts = AdaptedConfigurationTestCaseMixin.get_config('master')
        master = '127.0.0.1'
        ret_port = 64506
        self.minion_config = {
            'transport': 'zeromq',
            'pki_dir': '/tmp',
            'id': 'root',
            'master_ip': master,
            'master_port': ret_port,
            'auth_timeout': 5,
            'auth_tries': 1,
            'master_uri': 'tcp://{0}:{1}'.format(master, ret_port)
        }

    def tearDown(self):
        delattr(self, 'master_opts')
        delattr(self, 'minion_config')

    def test_token(self):
        tokensdir = os.path.join(
            self.master_opts['root_dir'],
            self.master_opts['cachedir'],
            'tokens'
        )
        assert os.path.exists(tokensdir), tokensdir
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt='clear')
        msg = {
            'arg': [],
            'cmd': 'get_token',
            'token': os.path.join('..', 'minions', 'minion', 'data.p'),
        }
        ret = clear_channel.send(msg, timeout=5)
        assert 'pillar' not in ret, 'Read minion data via directory traversal'
