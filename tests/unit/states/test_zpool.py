# -*- coding: utf-8 -*-
'''
Tests for salt.states.zpool

:codeauthor:    Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs, salt.modules.zpool
:platform:      illumos,freebsd,linux
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import test data from salt.utils.zfs test
from tests.unit.utils.test_zfs import utils_patch

# Import Salt Execution module to test
import salt.utils.zfs
import salt.states.zpool as zpool

# Import Salt Utils
import salt.loader
from salt.utils.odict import OrderedDict


def test_mode():
    return patch.dict(zpool.__opts__, {'test': True})


def patch_fn(fn_name, patch_with):
    return patch.dict(zpool.__salt__, {'zpool.{}'.format(fn_name): patch_with})


def patch_exists(exists):
    return patch_fn('exists', MagicMock(return_value=exists))


def patch_get(properties):
    return patch_fn('get', MagicMock(return_value=properties))


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZpoolTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.zpool
    '''
    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(opts, whitelist=['zfs'])
        zpool_obj = {
            zpool: {
                '__opts__': opts,
                '__grains__': {'kernel': 'SunOS'},
                '__utils__': utils,
            }
        }

        return zpool_obj

    def test_absent_without_pool(self):
        '''
        Test zpool absent without a pool
        '''
        ret = {'name': 'myzpool',
               'result': True,
               'comment': 'zpool is absent',
               'changes': {}}

        with patch_exists(False), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.absent('myzpool'), ret)

    def test_absent_destroy_pool(self):
        '''
        Test zpool absent destroying pool
        '''
        ret = {
            'name': 'myzpool',
            'result': True,
            'comment': 'zpool was destroyed',
            'changes': {'destroyed': 'myzpool'},
        }

        mock_destroy = MagicMock(return_value=OrderedDict([
            ('destroyed', True),
        ]))
        with patch_exists(True), \
             patch_fn('destroy', mock_destroy), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.absent('myzpool'), ret)

    def test_absent_exporty_pool(self):
        '''
        Test zpool absent exporting pool
        '''
        ret = {
            'name': 'myzpool',
            'result': True,
            'comment': 'zpool was exported',
            'changes': {'exported': 'myzpool'},
        }

        mock_destroy = MagicMock(return_value=OrderedDict([
            ('exported', True),
        ]))
        with patch_exists(True), \
             patch_fn('export', mock_destroy), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.absent('myzpool', export=True), ret)

    def test_absent_busy(self):
        '''
        Test zpool absent on a busy pool
        '''
        ret = {
            'name': 'myzpool',
            'result': False,
            'comment': "\n".join([
                "Failed to export zpool:",
                "cannot unmount '/myzpool': Device busy",
                "cannot export 'myzpool': pool is busy",
            ]),
            'changes': {},
        }

        mock_destroy = MagicMock(return_value=OrderedDict([
            ('exported', False),
            ('error', "\n".join([
                "cannot unmount '/myzpool': Device busy",
                "cannot export 'myzpool': pool is busy",
            ])),
        ]))
        with patch_exists(True), \
             patch_fn('export', mock_destroy), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.absent('myzpool', export=True), ret)

    def test_present_import_success(self):
        '''
        Test zpool present with import allowed and unimported pool
        '''
        ret = {'name': 'myzpool',
               'result': True,
               'comment': 'zpool was imported',
               'changes': {'imported': 'myzpool'}}

        config = {
            'import': True,
        }

        mock_import = MagicMock(return_value=OrderedDict([
            ('imported', True),
        ]))
        with patch_exists(False), \
             patch_fn('import', mock_import), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.present('myzpool', config=config), ret)

    def test_present_import_fail(self):
        '''
        Test zpool present with import allowed and no unimported pool or layout
        '''
        ret = {'name': 'myzpool',
               'result': False,
               'comment': 'zpool could not be imported and no (valid) layout was specified to create it',
               'changes': {}}

        config = {
            'import': True,
        }

        mock_import = MagicMock(return_value=OrderedDict([
            ('imported', False),
        ]))
        with patch_exists(False), \
             patch_fn('import', mock_import), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.present('myzpool', config=config), ret)

    def test_present_create_success(self):
        '''
        Test zpool present with non existing pool
        '''
        ret = {'name': 'myzpool',
               'result': True,
               'comment': 'zpool was created',
               'changes': {'created': 'myzpool',
               'properties': {
                   'autoexpand': True,
                   'quota': 5368709120,
               }}}

        config = {
            'import': False,
        }
        layout = [
            OrderedDict([('mirror', ['disk0', 'disk1'])]),
            OrderedDict([('mirror', ['disk2', 'disk3'])]),
        ]
        properties = {
            'autoexpand': True,
        }
        filesystem_properties = {
            'quota': '5G',
        }

        mock_create = MagicMock(return_value=OrderedDict([
            ('created', True),
            ('vdevs', OrderedDict([
                ('mirror-0', ['/dev/dsk/disk0', '/dev/dsk/disk1']),
                ('mirror-1', ['/dev/dsk/disk2', '/dev/dsk/disk3']),
            ])),
        ]))
        with patch_exists(False), \
             patch_fn('create', mock_create), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(
                zpool.present(
                    'myzpool',
                    config=config,
                    layout=layout,
                    properties=properties,
                    filesystem_properties=filesystem_properties,
                ),
                ret,
            )

    def test_present_create_fail(self):
        '''
        Test zpool present with non existing pool (without a layout)
        '''
        ret = {'name': 'myzpool',
               'result': False,
               'comment': 'zpool could not be imported and no (valid) layout was specified to create it',
               'changes': {}}

        config = {
            'import': False,
        }

        with patch_exists(False), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.present('myzpool', config=config), ret)

    def test_present_create_passthrough_fail(self):
        '''
        Test zpool present with non existing pool (without a layout)
        '''
        ret = {'name': 'myzpool',
               'result': False,
               'comment': "\n".join([
                   'Failed to create zpool:',
                    "invalid vdev specification",
                    "use 'force=True' to override the following errors:",
                    "/data/salt/vdisk0 is part of exported pool 'zsalt'",
                    "/data/salt/vdisk1 is part of exported pool 'zsalt'",
                ]),
               'changes': {}}

        config = {
            'force': False,
            'import': False,
        }
        layout = [
            OrderedDict([('mirror', ['disk0', 'disk1'])]),
            OrderedDict([('mirror', ['disk2', 'disk3'])]),
        ]
        properties = {
            'autoexpand': True,
        }
        filesystem_properties = {
            'quota': '5G',
        }

        mock_create = MagicMock(return_value=OrderedDict([
            ('created', False),
            ('error', "\n".join([
                "invalid vdev specification",
                "use 'force=True' to override the following errors:",
                "/data/salt/vdisk0 is part of exported pool 'zsalt'",
                "/data/salt/vdisk1 is part of exported pool 'zsalt'",
            ])),
        ]))
        with patch_exists(False), \
             patch_fn('create', mock_create), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(
                zpool.present(
                    'myzpool',
                    config=config,
                    layout=layout,
                    properties=properties,
                    filesystem_properties=filesystem_properties,
                ),
                ret,
            )

    def test_present_update_success(self):
        '''
        Test zpool present with an existing pool that needs an update
        '''
        ret = {'name': 'myzpool',
               'result': True,
               'comment': 'Properties updated',
               'changes': {'autoexpand': {'new': False, 'old': True}}}

        config = {
            'import': False,
        }
        layout = [
            OrderedDict([('mirror', ['disk0', 'disk1'])]),
            OrderedDict([('mirror', ['disk2', 'disk3'])]),
        ]
        properties = {
            'autoexpand': False,
        }

        mock_properties = OrderedDict([
            ('comment', 'salt managed pool'),
            ('freeing', 0),
            ('listsnapshots', False),
            ('leaked', 0),
            ('feature@obsolete_counts', 'enabled'),
            ('feature@sha512', 'enabled'),
            ('delegation', True),
            ('dedupditto', '0'),
            ('dedupratio', '1.00x'),
            ('autoexpand', True),
            ('feature@bookmarks', 'enabled'),
            ('allocated', 115712),
            ('guid', 1591906802560842214),
            ('feature@large_blocks', 'enabled'),
            ('size', 2113929216),
            ('feature@enabled_txg', 'active'),
            ('feature@hole_birth', 'active'),
            ('capacity', 0),
            ('feature@multi_vdev_crash_dump', 'enabled'),
            ('feature@extensible_dataset', 'enabled'),
            ('cachefile', '-'),
            ('bootfs', '-'),
            ('autoreplace', True),
            ('readonly', False),
            ('version', '-'),
            ('health', 'ONLINE'),
            ('expandsize', '-'),
            ('feature@embedded_data', 'active'),
            ('feature@lz4_compress', 'active'),
            ('feature@async_destroy', 'enabled'),
            ('feature@skein', 'enabled'),
            ('feature@empty_bpobj', 'enabled'),
            ('feature@spacemap_histogram', 'active'),
            ('bootsize', '-'),
            ('free', 2113813504),
            ('feature@device_removal', 'enabled'),
            ('failmode', 'wait'),
            ('feature@filesystem_limits', 'enabled'),
            ('feature@edonr', 'enabled'),
            ('altroot', '-'),
            ('fragmentation', '0%'),
        ])
        mock_set = MagicMock(return_value=OrderedDict([
            ('set', True),
        ]))
        with patch_exists(True), \
             patch_get(mock_properties), \
             patch_fn('set', mock_set), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(
                zpool.present(
                    'myzpool',
                    config=config,
                    layout=layout,
                    properties=properties,
                ),
                ret,
            )

    def test_present_update_nochange_success(self):
        '''
        Test zpool present with non existing pool
        '''
        ret = {'name': 'myzpool',
               'result': True,
               'comment': 'zpool is up-to-date',
               'changes': {}}

        config = {
            'import': False,
        }
        layout = [
            OrderedDict([('mirror', ['disk0', 'disk1'])]),
            OrderedDict([('mirror', ['disk2', 'disk3'])]),
        ]
        properties = {
            'autoexpand': True,
        }

        mock_properties = OrderedDict([
            ('comment', 'salt managed pool'),
            ('freeing', 0),
            ('listsnapshots', False),
            ('leaked', 0),
            ('feature@obsolete_counts', 'enabled'),
            ('feature@sha512', 'enabled'),
            ('delegation', True),
            ('dedupditto', '0'),
            ('dedupratio', '1.00x'),
            ('autoexpand', True),
            ('feature@bookmarks', 'enabled'),
            ('allocated', 115712),
            ('guid', 1591906802560842214),
            ('feature@large_blocks', 'enabled'),
            ('size', 2113929216),
            ('feature@enabled_txg', 'active'),
            ('feature@hole_birth', 'active'),
            ('capacity', 0),
            ('feature@multi_vdev_crash_dump', 'enabled'),
            ('feature@extensible_dataset', 'enabled'),
            ('cachefile', '-'),
            ('bootfs', '-'),
            ('autoreplace', True),
            ('readonly', False),
            ('version', '-'),
            ('health', 'ONLINE'),
            ('expandsize', '-'),
            ('feature@embedded_data', 'active'),
            ('feature@lz4_compress', 'active'),
            ('feature@async_destroy', 'enabled'),
            ('feature@skein', 'enabled'),
            ('feature@empty_bpobj', 'enabled'),
            ('feature@spacemap_histogram', 'active'),
            ('bootsize', '-'),
            ('free', 2113813504),
            ('feature@device_removal', 'enabled'),
            ('failmode', 'wait'),
            ('feature@filesystem_limits', 'enabled'),
            ('feature@edonr', 'enabled'),
            ('altroot', '-'),
            ('fragmentation', '0%'),
        ])
        with patch_exists(True), \
             patch_get(mock_properties), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(
                zpool.present(
                    'myzpool',
                    config=config,
                    layout=layout,
                    properties=properties,
                ),
                ret,
            )

    def test_testmode_create_needed(self):
        '''
        Check that a pending creation in test mode returns the correct information
        '''
        ret = {
            'name': 'test-zpool',
            'result': None,
            'comment': 'zpool will be created',
            'changes': {},
        }

        with patch_exists(False), \
             test_mode(), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.present('test-zpool', config={}, layout=[], properties={}), ret)

    def test_testmode_no_changes(self):
        '''
        Check that an up-to-date zpool returns no changes in test mode
        '''
        ret = {
            'name': 'test-zpool',
            'result': True,
            'comment': 'zpool is up-to-date',
            'changes': {},
        }

        with patch_exists(True), \
             patch_get({}), \
             test_mode(), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.present('test-zpool', config={}, layout=[], properties={}), ret)

    def test_testmode_properties_change(self):
        '''
        Check that pending property changes in test mode returns the correct
        state changes
        '''
        ret = {
            'name': 'test-zpool',
            'result': None,
            'comment': 'Properties will be updated',
            'changes': {},
        }

        want_props = {
            'foo': 'bar',
        }
        cur_props = {
            'foo': 'baz',
        }
        with test_mode(), patch_get(cur_props), \
             patch_exists(True), \
             patch.dict(zpool.__utils__, utils_patch):
            self.assertEqual(zpool.present('test-zpool', config={}, layout=[], properties=want_props), ret)
