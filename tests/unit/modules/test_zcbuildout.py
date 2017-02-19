# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import tempfile
import logging
import shutil

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six as six
from salt.ext.six.moves.urllib.error import URLError
from salt.ext.six.moves.urllib.request import urlopen
# pylint: enable=import-error,no-name-in-module,redefined-builtin

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import FILES, TMP
from tests.support.unit import TestCase, skipIf
from tests.support.helpers import requires_network, skip_if_binaries_missing

# Import Salt libs
import salt.utils
from salt.modules import zcbuildout as buildout
from salt.modules import cmdmod as cmd

ROOT = os.path.join(FILES, 'file', 'base', 'buildout')

KNOWN_VIRTUALENV_BINARY_NAMES = (
    'virtualenv',
    'virtualenv2',
    'virtualenv-2.6',
    'virtualenv-2.7'
)

BOOT_INIT = {
    1: [
        'var/ver/1/bootstrap/bootstrap.py',
    ],
    2: [
        'var/ver/2/bootstrap/bootstrap.py',
        'b/bootstrap.py',
    ]}

log = logging.getLogger(__name__)


def download_to(url, dest):
    with salt.utils.fopen(dest, 'w') as fic:
        fic.write(urlopen(url, timeout=10).read())


@skipIf(True, 'These tests are not running reliably')
class Base(TestCase, LoaderModuleMockMixin):

    loader_module = buildout

    def loader_module_globals(self):
        return {
            '__salt__': {
                'cmd.run_all': cmd.run_all,
                'cmd.run': cmd.run,
                'cmd.retcode': cmd.retcode,
            }
        }

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(TMP):
            os.makedirs(TMP)
        cls.rdir = tempfile.mkdtemp(dir=TMP)
        cls.tdir = os.path.join(cls.rdir, 'test')
        for idx, url in six.iteritems(buildout._URL_VERSIONS):
            log.debug('Downloading bootstrap from {0}'.format(url))
            dest = os.path.join(
                cls.rdir, '{0}_bootstrap.py'.format(idx)
            )
            try:
                download_to(url, dest)
            except URLError:
                log.debug('Failed to download {0}'.format(url))
        # creating a new setuptools install
        cls.ppy_st = os.path.join(cls.rdir, 'psetuptools')
        cls.py_st = os.path.join(cls.ppy_st, 'bin', 'python')
        ret1 = buildout._Popen((
            '{0} --no-site-packages {1};'
            '{1}/bin/pip install -U setuptools; '
            '{1}/bin/easy_install -U distribute;').format(
                salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES),
                cls.ppy_st
            )
        )
        assert ret1['retcode'] == 0

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(cls.rdir):
            shutil.rmtree(cls.rdir)

    def setUp(self):
        super(Base, self).setUp()
        self._remove_dir()
        shutil.copytree(ROOT, self.tdir)

        for idx in BOOT_INIT:
            path = os.path.join(
                self.rdir, '{0}_bootstrap.py'.format(idx)
            )
            for fname in BOOT_INIT[idx]:
                shutil.copy2(path, os.path.join(self.tdir, fname))

    def tearDown(self):
        super(Base, self).tearDown()
        self._remove_dir()

    def _remove_dir(self):
        if os.path.isdir(self.tdir):
            shutil.rmtree(self.tdir)


@skipIf(True, 'These tests are not running reliably')
@skipIf(salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES) is None,
        'The \'virtualenv\' packaged needs to be installed')
@skip_if_binaries_missing(['tar'])
class BuildoutTestCase(Base):

    @requires_network()
    def test_onlyif_unless(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.buildout(b_dir, onlyif='/bin/false')
        self.assertTrue(ret['comment'] == 'onlyif execution failed')
        self.assertTrue(ret['status'] is True)
        ret = buildout.buildout(b_dir, unless='/bin/true')
        self.assertTrue(ret['comment'] == 'unless execution succeeded')
        self.assertTrue(ret['status'] is True)

    @requires_network()
    def test_salt_callback(self):
        @buildout._salt_callback
        def callback1(a, b=1):
            for i in buildout.LOG.levels:
                getattr(buildout.LOG, i)('{0}bar'.format(i[0]))
            return 'foo'

        def callback2(a, b=1):
            raise Exception('foo')

        # pylint: disable=invalid-sequence-index
        ret1 = callback1(1, b=3)
        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        #self.assertEqual(ret1['status'], True)
        #self.assertEqual(ret1['logs_by_level']['warn'], ['wbar'])
        #self.assertEqual(ret1['comment'], '')
        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        #self.assertTrue(
        #     u''
        #     u'OUTPUT:\n'
        #     u'foo\n'
        #     u''
        #    in ret1['outlog']
        #)

        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        #self.assertTrue(u'Log summary:\n' in ret1['outlog'])
        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        # self.assertTrue(
        #     u'INFO: ibar\n'
        #     u'WARN: wbar\n'
        #     u'DEBUG: dbar\n'
        #     u'ERROR: ebar\n'
        #    in ret1['outlog']
        #)
        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        #self.assertTrue('by level' in ret1['outlog_by_level'])
        #self.assertEqual(ret1['out'], 'foo')
        ret2 = buildout._salt_callback(callback2)(2, b=6)
        self.assertEqual(ret2['status'], False)
        self.assertTrue(
            ret2['logs_by_level']['error'][0].startswith('Traceback'))
        self.assertTrue(
            'We did not get any '
            'expectable answer '
            'from buildout' in ret2['comment'])
        self.assertEqual(ret2['out'], None)
        for l in buildout.LOG.levels:
            self.assertTrue(0 == len(buildout.LOG.by_level[l]))
        # pylint: enable=invalid-sequence-index

    @requires_network()
    def test_get_bootstrap_url(self):
        for path in [os.path.join(self.tdir, 'var/ver/1/dumppicked'),
                     os.path.join(self.tdir, 'var/ver/1/bootstrap'),
                     os.path.join(self.tdir, 'var/ver/1/versions')]:
            self.assertEqual(buildout._URL_VERSIONS[1],
                             buildout._get_bootstrap_url(path),
                             "b1 url for {0}".format(path))
        for path in [
            os.path.join(self.tdir, '/non/existing'),
            os.path.join(self.tdir, 'var/ver/2/versions'),
            os.path.join(self.tdir, 'var/ver/2/bootstrap'),
            os.path.join(self.tdir, 'var/ver/2/default'),
        ]:
            self.assertEqual(buildout._URL_VERSIONS[2],
                             buildout._get_bootstrap_url(path),
                             "b2 url for {0}".format(path))

    @requires_network()
    def test_get_buildout_ver(self):
        for path in [os.path.join(self.tdir, 'var/ver/1/dumppicked'),
                     os.path.join(self.tdir, 'var/ver/1/bootstrap'),
                     os.path.join(self.tdir, 'var/ver/1/versions')]:
            self.assertEqual(1,
                             buildout._get_buildout_ver(path),
                             "1 for {0}".format(path))
        for path in [os.path.join(self.tdir, '/non/existing'),
                     os.path.join(self.tdir, 'var/ver/2/versions'),
                     os.path.join(self.tdir, 'var/ver/2/bootstrap'),
                     os.path.join(self.tdir, 'var/ver/2/default')]:
            self.assertEqual(2,
                             buildout._get_buildout_ver(path),
                             "2 for {0}".format(path))

    @requires_network()
    def test_get_bootstrap_content(self):
        self.assertEqual(
            '',
            buildout._get_bootstrap_content(
                os.path.join(self.tdir, '/non/existing'))
        )
        self.assertEqual(
            '',
            buildout._get_bootstrap_content(
                os.path.join(self.tdir, 'var/tb/1')))
        self.assertEqual(
            'foo\n',
            buildout._get_bootstrap_content(
                os.path.join(self.tdir, 'var/tb/2')))

    @requires_network()
    def test_logger_clean(self):
        buildout.LOG.clear()
        # nothing in there
        self.assertTrue(
            True not in
            [len(buildout.LOG.by_level[a]) > 0
             for a in buildout.LOG.by_level])
        buildout.LOG.info('foo')
        self.assertTrue(
            True in
            [len(buildout.LOG.by_level[a]) > 0
             for a in buildout.LOG.by_level])
        buildout.LOG.clear()
        self.assertTrue(
            True not in
            [len(buildout.LOG.by_level[a]) > 0
             for a in buildout.LOG.by_level])

    @requires_network()
    def test_logger_loggers(self):
        buildout.LOG.clear()
        # nothing in there
        for i in buildout.LOG.levels:
            getattr(buildout.LOG, i)('foo')
            getattr(buildout.LOG, i)('bar')
            getattr(buildout.LOG, i)('moo')
            self.assertTrue(len(buildout.LOG.by_level[i]) == 3)
            self.assertEqual(buildout.LOG.by_level[i][0], 'foo')
            self.assertEqual(buildout.LOG.by_level[i][-1], 'moo')

    @requires_network()
    def test__find_cfgs(self):
        result = sorted(
            [a.replace(ROOT, '') for a in buildout._find_cfgs(ROOT)])
        assertlist = sorted(
            ['/buildout.cfg',
             '/c/buildout.cfg',
             '/etc/buildout.cfg',
             '/e/buildout.cfg',
             '/b/buildout.cfg',
             '/b/bdistribute/buildout.cfg',
             '/b/b2/buildout.cfg',
             '/foo/buildout.cfg'])
        self.assertEqual(result, assertlist)

    @requires_network()
    def skip_test_upgrade_bootstrap(self):
        b_dir = os.path.join(self.tdir, 'b')
        bpy = os.path.join(b_dir, 'bootstrap.py')
        buildout.upgrade_bootstrap(b_dir)
        time1 = os.stat(bpy).st_mtime
        with salt.utils.fopen(bpy) as fic:
            data = fic.read()
        self.assertTrue('setdefaulttimeout(2)' in data)
        flag = os.path.join(b_dir, '.buildout', '2.updated_bootstrap')
        self.assertTrue(os.path.exists(flag))
        buildout.upgrade_bootstrap(b_dir, buildout_ver=1)
        time2 = os.stat(bpy).st_mtime
        with salt.utils.fopen(bpy) as fic:
            data = fic.read()
        self.assertTrue('setdefaulttimeout(2)' in data)
        flag = os.path.join(b_dir, '.buildout', '1.updated_bootstrap')
        self.assertTrue(os.path.exists(flag))
        buildout.upgrade_bootstrap(b_dir, buildout_ver=1)
        time3 = os.stat(bpy).st_mtime
        self.assertNotEqual(time2, time1)
        self.assertEqual(time2, time3)


@skipIf(salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES) is None,
        'The \'virtualenv\' packaged needs to be installed')
@skipIf(True, 'These tests are not running reliably')
class BuildoutOnlineTestCase(Base):

    @classmethod
    def setUpClass(cls):
        super(BuildoutOnlineTestCase, cls).setUpClass()
        cls.ppy_dis = os.path.join(cls.rdir, 'pdistibute')
        cls.ppy_blank = os.path.join(cls.rdir, 'pblank')
        cls.py_dis = os.path.join(cls.ppy_dis, 'bin', 'python')
        cls.py_blank = os.path.join(cls.ppy_blank, 'bin', 'python')
        # creating a distribute based install
        try:
            ret20 = buildout._Popen((
                '{0} --no-site-packages --no-setuptools --no-pip {1}'.format(
                    salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES),
                    cls.ppy_dis
                )
            ))
        except buildout._BuildoutError:
            ret20 = buildout._Popen((
                '{0} --no-site-packages {1}'.format(
                    salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES),
                    cls.ppy_dis
                ))
            )
        assert ret20['retcode'] == 0

        download_to('https://pypi.python.org/packages/source'
                    '/d/distribute/distribute-0.6.43.tar.gz',
                    os.path.join(cls.ppy_dis, 'distribute-0.6.43.tar.gz'))

        ret2 = buildout._Popen((
            'cd {0} &&'
            ' tar xzvf distribute-0.6.43.tar.gz && cd distribute-0.6.43 &&'
            ' {0}/bin/python setup.py install'
        ).format(cls.ppy_dis))
        assert ret2['retcode'] == 0

        # creating a blank based install
        try:
            ret3 = buildout._Popen((
                '{0} --no-site-packages --no-setuptools --no-pip {1}'.format(
                    salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES),
                    cls.ppy_blank
                )
            ))
        except buildout._BuildoutError:
            ret3 = buildout._Popen((
                '{0} --no-site-packages {1}'.format(
                    salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES),
                    cls.ppy_blank
                )
            ))

        assert ret3['retcode'] == 0

    @requires_network()
    def test_buildout_bootstrap(self):
        b_dir = os.path.join(self.tdir, 'b')
        bd_dir = os.path.join(self.tdir, 'b', 'bdistribute')
        b2_dir = os.path.join(self.tdir, 'b', 'b2')
        self.assertTrue(buildout._has_old_distribute(self.py_dis))
        # this is too hard to check as on debian & other where old
        # packages are present (virtualenv), we can't have
        # a clean site-packages
        # self.assertFalse(buildout._has_old_distribute(self.py_blank))
        self.assertFalse(buildout._has_old_distribute(self.py_st))
        self.assertFalse(buildout._has_setuptools7(self.py_dis))
        self.assertTrue(buildout._has_setuptools7(self.py_st))
        self.assertFalse(buildout._has_setuptools7(self.py_blank))

        ret = buildout.bootstrap(
            bd_dir, buildout_ver=1, python=self.py_dis)
        comment = ret['outlog']
        self.assertTrue('--distribute' in comment)
        self.assertTrue('Generated script' in comment)

        ret = buildout.bootstrap(b_dir, buildout_ver=1, python=self.py_blank)
        comment = ret['outlog']
        # as we may have old packages, this test the two
        # behaviors (failure with old setuptools/distribute)
        self.assertTrue(
            ('Got ' in comment
             and 'Generated script' in comment)
            or ('setuptools>=0.7' in comment)
        )

        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_blank)
        comment = ret['outlog']
        self.assertTrue(
            ('setuptools' in comment
             and 'Generated script' in comment)
            or ('setuptools>=0.7' in comment)
        )

        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_st)
        comment = ret['outlog']
        self.assertTrue(
            ('setuptools' in comment
             and 'Generated script' in comment)
            or ('setuptools>=0.7' in comment)
        )

        ret = buildout.bootstrap(b2_dir, buildout_ver=2, python=self.py_st)
        comment = ret['outlog']
        self.assertTrue(
            ('setuptools' in comment
             and 'Creating directory' in comment)
            or ('setuptools>=0.7' in comment)
        )

    @requires_network()
    def test_run_buildout(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_st)
        self.assertTrue(ret['status'])
        ret = buildout.run_buildout(b_dir,
                                    parts=['a', 'b'])
        out = ret['out']
        self.assertTrue('Installing a' in out)
        self.assertTrue('Installing b' in out)

    @requires_network()
    def test_buildout(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.buildout(b_dir, buildout_ver=2, python=self.py_st)
        self.assertTrue(ret['status'])
        out = ret['out']
        comment = ret['comment']
        self.assertTrue(ret['status'])
        self.assertTrue('Creating directory' in out)
        self.assertTrue('Installing a.' in out)
        self.assertTrue('psetuptools/bin/python bootstrap.py' in comment)
        self.assertTrue('buildout -c buildout.cfg' in comment)
        ret = buildout.buildout(b_dir,
                                parts=['a', 'b', 'c'],
                                buildout_ver=2,
                                python=self.py_st)
        outlog = ret['outlog']
        out = ret['out']
        comment = ret['comment']
        self.assertTrue('Installing single part: a' in outlog)
        self.assertTrue('buildout -c buildout.cfg -N install a' in comment)
        self.assertTrue('Installing b.' in out)
        self.assertTrue('Installing c.' in out)
        ret = buildout.buildout(b_dir,
                                parts=['a', 'b', 'c'],
                                buildout_ver=2,
                                newest=True,
                                python=self.py_st)
        outlog = ret['outlog']
        out = ret['out']
        comment = ret['comment']
        self.assertTrue('buildout -c buildout.cfg -n install a' in comment)


@skipIf(True, 'These tests are not running reliably')
class BuildoutAPITestCase(TestCase):

    def test_merge(self):
        buildout.LOG.clear()
        buildout.LOG.info('àé')
        buildout.LOG.info(u'àé')
        buildout.LOG.error('àé')
        buildout.LOG.error(u'àé')
        ret1 = buildout._set_status({}, out='éà')
        uret1 = buildout._set_status({}, out=u'éà')
        buildout.LOG.clear()
        buildout.LOG.info('ççàé')
        buildout.LOG.info(u'ççàé')
        buildout.LOG.error('ççàé')
        buildout.LOG.error(u'ççàé')
        ret2 = buildout._set_status({}, out='çéà')
        uret2 = buildout._set_status({}, out=u'çéà')
        uretm = buildout._merge_statuses([ret1, uret1, ret2, uret2])
        for ret in ret1, uret1, ret2, uret2:
            out = ret['out']
            if not isinstance(ret['out'], six.text_type):
                out = ret['out'].decode('utf-8')

        for out in ['àé', 'ççàé']:
            self.assertTrue(out in uretm['logs_by_level']['info'])
            self.assertTrue(out in uretm['outlog_by_level'])

    def test_setup(self):
        buildout.LOG.clear()
        buildout.LOG.info('àé')
        buildout.LOG.info(u'àé')
        buildout.LOG.error('àé')
        buildout.LOG.error(u'àé')
        ret = buildout._set_status({}, out='éà')
        uret = buildout._set_status({}, out=u'éà')
        self.assertTrue(ret['outlog'] == uret['outlog'])
        self.assertTrue('àé' in uret['outlog_by_level'])
