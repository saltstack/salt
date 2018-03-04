# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
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
from tests.support.helpers import get_unused_localhost_port, skip_if_not_root
from tests.support.unit import skipIf
import tests.support.paths as paths

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

log = logging.getLogger(__name__)


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

    def test_get_file(self):
        '''
        cp.get_file
        '''
        tgt = os.path.join(paths.TMP, 'scene33')
        self.run_function(
                'cp.get_file',
                [
                    'salt://grail/scene33',
                    tgt,
                ])
        with salt.utils.files.fopen(tgt, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_file_to_dir(self):
        '''
        cp.get_file
        '''
        tgt = os.path.join(paths.TMP, '')
        self.run_function(
                'cp.get_file',
                [
                    'salt://grail/scene33',
                    tgt,
                ])
        with salt.utils.files.fopen(tgt + 'scene33', 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_file_templated_paths(self):
        '''
        cp.get_file
        '''
        tgt = os.path.join(paths.TMP, 'cheese')
        self.run_function(
            'cp.get_file',
            [
                'salt://{{grains.test_grain}}',
                tgt.replace('cheese', '{{grains.test_grain}}')
            ],
            template='jinja'
        )
        with salt.utils.files.fopen(tgt, 'r') as cheese:
            data = salt.utils.stringutils.to_unicode(cheese.read())
        self.assertIn('Gromit', data)
        self.assertNotIn('bacon', data)

    def test_get_file_gzipped(self):
        '''
        cp.get_file
        '''
        tgt = os.path.join(paths.TMP, 'file.big')
        src = os.path.join(paths.FILES, 'file', 'base', 'file.big')
        with salt.utils.files.fopen(src, 'rb') as fp_:
            hash_str = hashlib.md5(fp_.read()).hexdigest()

        self.run_function(
            'cp.get_file',
            [
                'salt://file.big',
                tgt,
            ],
            gzip=5
        )
        with salt.utils.files.fopen(tgt, 'rb') as scene:
            data = scene.read()
        self.assertEqual(hash_str, hashlib.md5(data).hexdigest())
        data = salt.utils.stringutils.to_unicode(data)
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_file_makedirs(self):
        '''
        cp.get_file
        '''
        tgt = os.path.join(paths.TMP, 'make', 'dirs', 'scene33')
        self.run_function(
            'cp.get_file',
            [
                'salt://grail/scene33',
                tgt,
            ],
            makedirs=True
        )
        self.addCleanup(shutil.rmtree, os.path.join(paths.TMP, 'make'), ignore_errors=True)
        with salt.utils.files.fopen(tgt, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_template(self):
        '''
        cp.get_template
        '''
        tgt = os.path.join(paths.TMP, 'scene33')
        self.run_function(
                'cp.get_template',
                ['salt://grail/scene33', tgt],
                spam='bacon')
        with salt.utils.files.fopen(tgt, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('bacon', data)
        self.assertNotIn('spam', data)

    def test_get_dir(self):
        '''
        cp.get_dir
        '''
        tgt = os.path.join(paths.TMP, 'many')
        self.run_function(
                'cp.get_dir',
                [
                    'salt://grail',
                    tgt
                ])
        self.assertIn('grail', os.listdir(tgt))
        self.assertIn('36', os.listdir(os.path.join(tgt, 'grail')))
        self.assertIn('empty', os.listdir(os.path.join(tgt, 'grail')))
        self.assertIn('scene', os.listdir(os.path.join(tgt, 'grail', '36')))

    def test_get_dir_templated_paths(self):
        '''
        cp.get_dir
        '''
        tgt = os.path.join(paths.TMP, 'many')
        self.run_function(
            'cp.get_dir',
            [
                'salt://{{grains.script}}',
                tgt.replace('many', '{{grains.alot}}')
            ]
        )
        self.assertIn('grail', os.listdir(tgt))
        self.assertIn('36', os.listdir(os.path.join(tgt, 'grail')))
        self.assertIn('empty', os.listdir(os.path.join(tgt, 'grail')))
        self.assertIn('scene', os.listdir(os.path.join(tgt, 'grail', '36')))

    # cp.get_url tests

    def test_get_url(self):
        '''
        cp.get_url with salt:// source given
        '''
        tgt = os.path.join(paths.TMP, 'scene33')
        self.run_function(
            'cp.get_url',
            [
                'salt://grail/scene33',
                tgt,
            ])
        with salt.utils.files.fopen(tgt, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_url_makedirs(self):
        '''
        cp.get_url
        '''
        tgt = os.path.join(paths.TMP, 'make', 'dirs', 'scene33')
        self.run_function(
                'cp.get_url',
                [
                    'salt://grail/scene33',
                    tgt,
                ],
                makedirs=True
            )
        self.addCleanup(shutil.rmtree, os.path.join(paths.TMP, 'make'), ignore_errors=True)
        with salt.utils.files.fopen(tgt, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_url_dest_empty(self):
        '''
        cp.get_url with salt:// source given and destination omitted.
        '''
        ret = self.run_function(
            'cp.get_url',
            [
                'salt://grail/scene33',
            ])
        with salt.utils.files.fopen(ret, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_url_no_dest(self):
        '''
        cp.get_url with salt:// source given and destination set as None
        '''
        tgt = None
        ret = self.run_function(
            'cp.get_url',
            [
                'salt://grail/scene33',
                tgt,
            ])
        self.assertIn('KNIGHT:  They\'re nervous, sire.', ret)

    def test_get_url_nonexistent_source(self):
        '''
        cp.get_url with nonexistent salt:// source given
        '''
        tgt = None
        ret = self.run_function(
            'cp.get_url',
            [
                'salt://grail/nonexistent_scene',
                tgt,
            ])
        self.assertEqual(ret, False)

    def test_get_url_to_dir(self):
        '''
        cp.get_url with salt:// source
        '''
        tgt = os.path.join(paths.TMP, '')
        self.run_function(
                'cp.get_url',
                [
                    'salt://grail/scene33',
                    tgt,
                ])
        with salt.utils.files.fopen(tgt + 'scene33', 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_url_https(self):
        '''
        cp.get_url with https:// source given
        '''
        tgt = os.path.join(paths.TMP, 'test_get_url_https')
        self.run_function(
            'cp.get_url',
            [
                'https://repo.saltstack.com/index.html',
                tgt,
            ])
        with salt.utils.files.fopen(tgt, 'r') as instructions:
            data = salt.utils.stringutils.to_unicode(instructions.read())
        self.assertIn('Bootstrap', data)
        self.assertIn('Debian', data)
        self.assertIn('Windows', data)
        self.assertNotIn('AYBABTU', data)

    def test_get_url_https_dest_empty(self):
        '''
        cp.get_url with https:// source given and destination omitted.
        '''
        ret = self.run_function(
            'cp.get_url',
            [
                'https://repo.saltstack.com/index.html',
            ])
        with salt.utils.files.fopen(ret, 'r') as instructions:
            data = salt.utils.stringutils.to_unicode(instructions.read())
        self.assertIn('Bootstrap', data)
        self.assertIn('Debian', data)
        self.assertIn('Windows', data)
        self.assertNotIn('AYBABTU', data)

    def test_get_url_https_no_dest(self):
        '''
        cp.get_url with https:// source given and destination set as None
        '''
        tgt = None
        ret = self.run_function(
            'cp.get_url',
            [
                'https://repo.saltstack.com/index.html',
                tgt,
            ])
        self.assertIn('Bootstrap', ret)
        self.assertIn('Debian', ret)
        self.assertIn('Windows', ret)
        self.assertNotIn('AYBABTU', ret)

    def test_get_url_file(self):
        '''
        cp.get_url with file:// source given
        '''
        tgt = ''
        src = os.path.join('file://', paths.FILES, 'file', 'base', 'file.big')
        ret = self.run_function(
            'cp.get_url',
            [
                src,
                tgt,
            ])
        with salt.utils.files.fopen(ret, 'r') as scene:
            data = salt.utils.stringutils.to_unicode(scene.read())
        self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
        self.assertNotIn('bacon', data)

    def test_get_url_file_no_dest(self):
        '''
        cp.get_url with file:// source given and destination set as None
        '''
        tgt = None
        src = os.path.join('file://', paths.FILES, 'file', 'base', 'file.big')
        ret = self.run_function(
            'cp.get_url',
            [
                src,
                tgt,
            ])
        self.assertIn('KNIGHT:  They\'re nervous, sire.', ret)
        self.assertNotIn('bacon', ret)

    # cp.get_file_str tests

    def test_get_file_str_salt(self):
        '''
        cp.get_file_str with salt:// source given
        '''
        src = 'salt://grail/scene33'
        ret = self.run_function(
            'cp.get_file_str',
            [
                src,
            ])
        self.assertIn('KNIGHT:  They\'re nervous, sire.', ret)

    def test_get_file_str_nonexistent_source(self):
        '''
        cp.get_file_str with nonexistent salt:// source given
        '''
        src = 'salt://grail/nonexistent_scene'
        ret = self.run_function(
            'cp.get_file_str',
            [
                src,
            ])
        self.assertEqual(ret, False)

    def test_get_file_str_https(self):
        '''
        cp.get_file_str with https:// source given
        '''
        src = 'https://repo.saltstack.com/index.html'
        ret = self.run_function(
            'cp.get_file_str',
            [
                src,
            ])
        self.assertIn('Bootstrap', ret)
        self.assertIn('Debian', ret)
        self.assertIn('Windows', ret)
        self.assertNotIn('AYBABTU', ret)

    def test_get_file_str_local(self):
        '''
        cp.get_file_str with file:// source given
        '''
        src = os.path.join('file://', paths.FILES, 'file', 'base', 'file.big')
        ret = self.run_function(
            'cp.get_file_str',
            [
                src,
            ])
        self.assertIn('KNIGHT:  They\'re nervous, sire.', ret)
        self.assertNotIn('bacon', ret)

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

    def test_cache_master(self):
        '''
        cp.cache_master
        '''
        ret = self.run_function(
                'cp.cache_master',
                )
        for path in ret:
            self.assertTrue(os.path.exists(path))

    def test_cache_local_file(self):
        '''
        cp.cache_local_file
        '''
        src = os.path.join(paths.TMP, 'random')
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
        temp_dir = tempfile.mkdtemp(dir=paths.TMP)
        self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
        nginx_root_dir = os.path.join(temp_dir, 'root')
        nginx_conf_dir = os.path.join(temp_dir, 'conf')
        nginx_conf = os.path.join(nginx_conf_dir, 'nginx.conf')
        nginx_pidfile = os.path.join(nginx_conf_dir, 'nginx.pid')
        file_contents = 'Hello world!'

        for dirname in (nginx_root_dir, nginx_conf_dir):
            os.mkdir(dirname)

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

    def test_list_states(self):
        '''
        cp.list_states
        '''
        ret = self.run_function(
                'cp.list_states',
                )
        self.assertIn('core', ret)
        self.assertIn('top', ret)

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

    def test_get_file_from_env_predefined(self):
        '''
        cp.get_file
        '''
        tgt = os.path.join(paths.TMP, 'cheese')
        try:
            self.run_function('cp.get_file', ['salt://cheese', tgt])
            with salt.utils.files.fopen(tgt, 'r') as cheese:
                data = salt.utils.stringutils.to_unicode(cheese.read())
            self.assertIn('Gromit', data)
            self.assertNotIn('Comte', data)
        finally:
            os.unlink(tgt)

    def test_get_file_from_env_in_url(self):
        tgt = os.path.join(paths.TMP, 'cheese')
        try:
            self.run_function('cp.get_file', ['salt://cheese?saltenv=prod', tgt])
            with salt.utils.files.fopen(tgt, 'r') as cheese:
                data = salt.utils.stringutils.to_unicode(cheese.read())
            self.assertIn('Gromit', data)
            self.assertIn('Comte', data)
        finally:
            os.unlink(tgt)

    def test_push(self):
        log_to_xfer = os.path.join(paths.TMP, uuid.uuid4().hex)
        open(log_to_xfer, 'w').close()  # pylint: disable=resource-leakage
        try:
            self.run_function('cp.push', [log_to_xfer])
            tgt_cache_file = os.path.join(
                    paths.TMP,
                    'master-minion-root',
                    'cache',
                    'minions',
                    'minion',
                    'files',
                    paths.TMP,
                    log_to_xfer)
            self.assertTrue(os.path.isfile(tgt_cache_file), 'File was not cached on the master')
        finally:
            os.unlink(tgt_cache_file)
