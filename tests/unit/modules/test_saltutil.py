# -*- coding: utf-8 -*-

from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import MagicMock, sentinel as s

import salt.modules.saltutil as saltutil


class ScheduleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {saltutil: {}}

    def test_exec_kwargs(self):
        _cmd_expected_kwargs = {'tgt': s.tgt, 'fun': s.fun, 'arg': s.arg,
                                'tgt_type': s.tgt_type, 'ret': s.ret, 'kwarg': s.kwarg}
        client = MagicMock()

        saltutil._exec(client, timeout=s.timeout, **_cmd_expected_kwargs)
        client.cmd_iter.assert_called_with(timeout=s.timeout, **_cmd_expected_kwargs)

        saltutil._exec(client, s.tgt, s.fun, s.arg, s.timeout, s.tgt_type, s.ret, s.kwarg, **{'batch': s.batch})
        client.cmd_batch.assert_called_with(batch=s.batch, **_cmd_expected_kwargs)

        saltutil._exec(client, s.tgt, s.fun, s.arg, s.timeout, s.tgt_type, s.ret, s.kwarg, **{'subset': s.subset})
        client.cmd_subset.assert_called_with(subset=s.subset, cli=True, **_cmd_expected_kwargs)

    def test_exec_kwargs_batch_and_subset(self):
        # cmd_batch doesn't know what to do with 'subset', don't pass it along.
        _cmd_expected_kwargs = {'tgt': s.tgt, 'fun': s.fun, 'arg': s.arg,
                                'tgt_type': s.tgt_type, 'ret': s.ret, 'kwarg': s.kwarg}
        client = MagicMock()

        saltutil._exec(client, s.tgt, s.fun, s.arg, s.timeout, s.tgt_type, s.ret, s.kwarg,
                       **{'batch': s.batch, 'subset': s.subset})
        client.cmd_batch.assert_called_with(batch=s.batch, **_cmd_expected_kwargs)
