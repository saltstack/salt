# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import uuid
import hashlib
import logging
import psutil
import shutil
import signal
import tempfile
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import (
    get_unused_localhost_port,
    skip_if_not_root,
    with_tempfile)
from tests.support.unit import skipIf
from tests.support.runtests import RUNTIME_VARS

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

log = logging.getLogger(__name__)


SSL3_SUPPORT = sys.version_info >= (2, 7, 9)


class CPModuleTest(ModuleCase):
    '''
    Validate the cp module
    '''
    def run_function(self, *args, **kwargs):
        '''
        Ensure that results are decoded

        TODO: maybe move this behavior to ModuleCase itself?
        '''
        return salt.utils.data.decode(
            super(CPModuleTest, self).run_function(*args, **kwargs)
        )
    # caching tests

    def test_cache_file(self):
        '''
        cp.cache_file
        '''
        ret = self.run_function(
                'cp.cache_file',
                [
                    'salt://grail/scene33',
                ])
        with salt.utils.files.fopen(ret, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_cache_files(self):
        '''
        cp.cache_files
        '''
        ret = self.run_function(
                'cp.cache_files',
                [
                    ['salt://grail/scene33', 'salt://grail/36/scene'],
                ])
        for path in ret:
            with salt.utils.files.fopen(path, 'r') as scene:
                data = salt.utils.stringutils.to_unicode(scene.read())
            self.assertIn('ARTHUR:', data)
            self.assertNotIn('bacon', data)

    @with_tempfile()
    def test_cache_master(self, tgt):
        '''
        cp.cache_master
        '''
        ret = self.run_function(
                'cp.cache_master',
                [tgt],
                )
        for path in ret:
            self.assertTrue(os.path.exists(path))

    def test_cache_local_file(self):
        '''
        cp.cache_local_file
        '''
        src = os.path.join(RUNTIME_VARS.TMP, 'random')
        with salt.utils.files.fopen(src, 'w+') as fn_:
            fn_.write(salt.utils.stringutils.to_str('foo'))
        ret = self.run_function(
                'cp.cache_local_file',
                [src])
        with salt.utils.files.fopen(ret, 'r') as cp_:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(cp_.read()),
                'foo'
            )

    @skipIf(not salt.utils.path.which('nginx'), 'nginx not installed')
    @skip_if_not_root
    def test_cache_remote_file(self):
        '''
        cp.cache_file
        '''
        nginx_port = get_unused_localhost_port()
        url_prefix = 'http://localhost:{0}/'.format(nginx_port)
        temp_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
        nginx_root_dir = os.path.join(temp_dir, 'root')
        nginx_conf_dir = os.path.join(temp_dir, 'conf')
        nginx_conf = os.path.join(nginx_conf_dir, 'nginx.conf')
        nginx_pidfile = os.path.join(nginx_conf_dir, 'nginx.pid')
        file_contents = 'Hello world!'

        for dirname in (nginx_root_dir, nginx_conf_dir):
            os.makedirs(dirname)

        # Write the temp file
        with salt.utils.files.fopen(os.path.join(nginx_root_dir, 'actual_file'), 'w') as fp_:
            fp_.write(salt.utils.stringutils.to_str(file_contents))

        # Write the nginx config
        with salt.utils.files.fopen(nginx_conf, 'w') as fp_:
            fp_.write(textwrap.dedent(salt.utils.stringutils.to_str(
                '''\
                user root;
                worker_processes 1;
                error_log {nginx_conf_dir}/server_error.log;
                pid {nginx_pidfile};

                events {{
                    worker_connections 1024;
                }}

                http {{
                    include       /etc/nginx/mime.types;
                    default_type  application/octet-stream;

                    access_log {nginx_conf_dir}/access.log;
                    error_log {nginx_conf_dir}/error.log;

                    server {{
                        listen {nginx_port} default_server;
                        server_name cachefile.local;
                        root {nginx_root_dir};

                        location ~ ^/301$ {{
                            return 301 /actual_file;
                        }}

                        location ~ ^/302$ {{
                            return 302 /actual_file;
                        }}
                    }}
                }}'''.format(**locals())
            )))

        self.run_function(
            'cmd.run',
            [['nginx', '-c', nginx_conf]],
            python_shell=False
        )
        with salt.utils.files.fopen(nginx_pidfile) as fp_:
            nginx_pid = int(fp_.read().strip())
            nginx_proc = psutil.Process(pid=nginx_pid)
            self.addCleanup(nginx_proc.send_signal, signal.SIGQUIT)

        for code in ('', '301', '302'):
            url = url_prefix + (code or 'actual_file')
            log.debug('attempting to cache %s', url)
            ret = self.run_function('cp.cache_file', [url])
            self.assertTrue(ret)
            with salt.utils.files.fopen(ret) as fp_:
                cached_contents = salt.utils.stringutils.to_unicode(fp_.read())
                self.assertEqual(cached_contents, file_contents)

    def test_list_minion(self):
        '''
        cp.list_minion
        '''
        self.run_function(
                'cp.cache_file',
                [
                    'salt://grail/scene33',
                ])
        ret = self.run_function('cp.list_minion')
        found = False
        search = 'grail/scene33'
        if salt.utils.platform.is_windows():
            search = r'grail\scene33'
        for path in ret:
            if search in path:
                found = True
                break
        self.assertTrue(found)

    def test_is_cached(self):
        '''
        cp.is_cached
        '''
        self.run_function(
                'cp.cache_file',
                [
                    'salt://grail/scene33',
                ])
        ret1 = self.run_function(
                'cp.is_cached',
                [
                    'salt://grail/scene33',
                ])
        self.assertTrue(ret1)
        ret2 = self.run_function(
                'cp.is_cached',
                [
                    'salt://fasldkgj/poicxzbn',
                ])
        self.assertFalse(ret2)

    def test_hash_file(self):
        '''
        cp.hash_file
        '''
        sha256_hash = self.run_function(
                'cp.hash_file',
                [
                    'salt://grail/scene33',
                ])
        path = self.run_function(
                'cp.cache_file',
                [
                    'salt://grail/scene33',
                ])
        with salt.utils.files.fopen(path, 'rb') as fn_:
            data = fn_.read()
            self.assertEqual(
                sha256_hash['hsum'], hashlib.sha256(data).hexdigest())

    @with_tempfile()
    def test_get_file_from_env_predefined(self, tgt):
        '''
        cp.get_file
        '''
        tgt = os.path.join(RUNTIME_VARS.TMP, 'cheese')
        try:
            self.run_function('cp.get_file', ['salt://cheese', tgt])
            with salt.utils.files.fopen(tgt, 'r') as cheese:
                data = salt.utils.stringutils.to_unicode(cheese.read())
            self.assertIn('Gromit', data)
            self.assertNotIn('Comte', data)
        finally:
            os.unlink(tgt)

    @with_tempfile()
    def test_get_file_from_env_in_url(self, tgt):
        tgt = os.path.join(RUNTIME_VARS.TMP, 'cheese')
        try:
            self.run_function('cp.get_file', ['salt://cheese?saltenv=prod', tgt])
            with salt.utils.files.fopen(tgt, 'r') as cheese:
                data = salt.utils.stringutils.to_unicode(cheese.read())
            self.assertIn('Gromit', data)
            self.assertIn('Comte', data)
        finally:
            os.unlink(tgt)

    def test_push(self):
        log_to_xfer = os.path.join(RUNTIME_VARS.TMP, uuid.uuid4().hex)
        open(log_to_xfer, 'w').close()  # pylint: disable=resource-leakage
        try:
            self.run_function('cp.push', [log_to_xfer])
            tgt_cache_file = os.path.join(
                    RUNTIME_VARS.TMP,
                    'master-minion-root',
                    'cache',
                    'minions',
                    'minion',
                    'files',
                    RUNTIME_VARS.TMP,
                    log_to_xfer)
            self.assertTrue(os.path.isfile(tgt_cache_file), 'File was not cached on the master')
        finally:
            os.unlink(tgt_cache_file)

    def test_envs(self):
        self.assertEqual(sorted(self.run_function('cp.envs')), sorted(['base', 'prod']))
