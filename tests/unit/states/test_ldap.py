# -*- coding: utf-8 -*-
'''Test cases for the ``ldap`` state module

This code is gross.  I started out trying to remove some of the
duplicate code in the test cases, and before I knew it the test code
was an ugly second implementation.

I'm leaving it for now, but this should really be gutted and replaced
with something sensible.
'''

from __future__ import absolute_import

import copy
import salt.ext.six as six
import salt.states.ldap

from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch,
)

# emulates the LDAP database.  each key is the DN of an entry and it
# maps to a dict which maps attribute names to sets of values.
db = {}


def _init_db(newdb=None):
    if newdb is None:
        newdb = {}
    global db
    db = newdb


def _complex_db():
    return {
        'dnfoo': {
            'attrfoo1': set((
                'valfoo1.1',
                'valfoo1.2',
            )),
            'attrfoo2': set((
                'valfoo2.1',
            )),
        },
        'dnbar': {
            'attrbar1': set((
                'valbar1.1',
                'valbar1.2',
            )),
            'attrbar2': set((
                'valbar2.1',
            )),
        },
    }


class _dummy_ctx(object):
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def _dummy_connect(connect_spec):
    return _dummy_ctx()


def _dummy_search(connect_spec, base, scope):
    if base not in db:
        return {}
    return {base: dict(((attr, sorted(db[base][attr]))
                        for attr in db[base]
                        if len(db[base][attr])))}


def _dummy_add(connect_spec, dn, attributes):
    assert dn not in db
    assert len(attributes)
    db[dn] = {}
    for attr, vals in six.iteritems(attributes):
        assert len(vals)
        db[dn][attr] = set(vals)
    return True


def _dummy_delete(connect_spec, dn):
    assert dn in db
    del db[dn]
    return True


def _dummy_change(connect_spec, dn, before, after):
    assert before != after
    assert len(before)
    assert len(after)
    assert dn in db
    e = db[dn]
    assert e == before
    all_attrs = set()
    all_attrs.update(before)
    all_attrs.update(after)
    directives = []
    for attr in all_attrs:
        if attr not in before:
            assert attr in after
            assert len(after[attr])
            directives.append(('add', attr, after[attr]))
        elif attr not in after:
            assert attr in before
            assert len(before[attr])
            directives.append(('delete', attr, ()))
        else:
            assert len(before[attr])
            assert len(after[attr])
            to_del = before[attr] - after[attr]
            if len(to_del):
                directives.append(('delete', attr, to_del))
            to_add = after[attr] - before[attr]
            if len(to_add):
                directives.append(('add', attr, to_add))
    return _dummy_modify(connect_spec, dn, directives)


def _dummy_modify(connect_spec, dn, directives):
    assert dn in db
    e = db[dn]
    for op, attr, vals in directives:
        if op == 'add':
            assert len(vals)
            existing_vals = e.setdefault(attr, set())
            for val in vals:
                assert val not in existing_vals
                existing_vals.add(val)
        elif op == 'delete':
            assert attr in e
            existing_vals = e[attr]
            assert len(existing_vals)
            if not len(vals):
                del e[attr]
                continue
            for val in vals:
                assert val in existing_vals
                existing_vals.remove(val)
            if not len(existing_vals):
                del e[attr]
        elif op == 'replace':
            e.pop(attr, None)
            e[attr] = set(vals)
        else:
            raise ValueError()
    return True


def _dump_db(d=None):
    if d is None:
        d = db
    return dict(((dn, dict(((attr, sorted(d[dn][attr]))
                            for attr in d[dn])))
                 for dn in d))


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LDAPTestCase(TestCase):

    def setUp(self):
        __opts = getattr(salt.states.ldap, '__opts__', {})
        salt.states.ldap.__opts__ = __opts
        __salt = getattr(salt.states.ldap, '__salt__', {})
        salt.states.ldap.__salt__ = __salt
        self.patchers = [
            patch.dict('salt.states.ldap.__opts__', {'test': False}),
        ]
        for f in ('connect', 'search', 'add', 'delete', 'change', 'modify'):
            self.patchers.append(
                patch.dict('salt.states.ldap.__salt__',
                           {'ldap3.' + f: globals()['_dummy_' + f]}))
        for p in self.patchers:
            p.start()
        self.maxDiff = None

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()

    def _test_helper(self, init_db, expected_ret, replace,
                     delete_others=False):
        _init_db(copy.deepcopy(init_db))
        old = _dump_db()
        new = _dump_db()
        expected_db = copy.deepcopy(init_db)
        for dn, attrs in six.iteritems(replace):
            for attr, vals in six.iteritems(attrs):
                if len(vals):
                    new.setdefault(dn, {})[attr] = sorted(set(vals))
                    expected_db.setdefault(dn, {})[attr] = set(vals)
                elif dn in expected_db:
                    new[dn].pop(attr, None)
                    expected_db[dn].pop(attr, None)
            if not len(expected_db.get(dn, {})):
                new.pop(dn, None)
                expected_db.pop(dn, None)
        if delete_others:
            dn_to_delete = set()
            for dn, attrs in six.iteritems(expected_db):
                if dn in replace:
                    to_delete = set()
                    for attr, vals in six.iteritems(attrs):
                        if attr not in replace[dn]:
                            to_delete.add(attr)
                    for attr in to_delete:
                        del attrs[attr]
                        del new[dn][attr]
                    if not len(attrs):
                        dn_to_delete.add(dn)
            for dn in dn_to_delete:
                del new[dn]
                del expected_db[dn]
        name = 'ldapi:///'
        expected_ret['name'] = name
        expected_ret.setdefault('result', True)
        expected_ret.setdefault('comment', 'Successfully updated LDAP entries')
        expected_ret.setdefault('changes', dict(
            ((dn, {'old': dict((attr, vals)
                               for attr, vals in six.iteritems(old[dn])
                               if vals != new.get(dn, {}).get(attr, ()))
                          if dn in old else None,
                   'new': dict((attr, vals)
                               for attr, vals in six.iteritems(new[dn])
                               if vals != old.get(dn, {}).get(attr, ()))
                          if dn in new else None})
             for dn in replace
             if old.get(dn, {}) != new.get(dn, {}))))
        entries = [{dn: [{'replace': attrs},
                         {'delete_others': delete_others}]}
                   for dn, attrs in six.iteritems(replace)]
        actual = salt.states.ldap.managed(name, entries)
        self.assertDictEqual(expected_ret, actual)
        self.assertDictEqual(expected_db, db)

    def _test_helper_success(self, init_db, replace, delete_others=False):
        self._test_helper(init_db, {}, replace, delete_others)

    def _test_helper_nochange(self, init_db, replace, delete_others=False):
        expected = {
            'changes': {},
            'comment': 'LDAP entries already set',
        }
        self._test_helper(init_db, expected, replace, delete_others)

    def test_managed_empty(self):
        _init_db()
        name = 'ldapi:///'
        expected = {
            'name': name,
            'changes': {},
            'result': True,
            'comment': 'LDAP entries already set',
        }
        actual = salt.states.ldap.managed(name, {})
        self.assertDictEqual(expected, actual)

    def test_managed_add_entry(self):
        self._test_helper_success(
            {},
            {'dummydn': {'foo': ['bar', 'baz']}})

    def test_managed_add_attr(self):
        self._test_helper_success(
            _complex_db(),
            {'dnfoo': {'attrfoo3': ['valfoo3.1']}})

    def test_managed_simplereplace(self):
        self._test_helper_success(
            _complex_db(),
            {'dnfoo': {'attrfoo1': ['valfoo1.3']}})

    def test_managed_deleteattr(self):
        self._test_helper_success(
            _complex_db(),
            {'dnfoo': {'attrfoo1': []}})

    def test_managed_deletenonexistattr(self):
        self._test_helper_nochange(
            _complex_db(),
            {'dnfoo': {'dummyattr': []}})

    def test_managed_deleteentry(self):
        self._test_helper_success(
            _complex_db(),
            {'dnfoo': {}},
            True)

    def test_managed_deletenonexistentry(self):
        self._test_helper_nochange(
            _complex_db(),
            {'dummydn': {}},
            True)

    def test_managed_deletenonexistattrinnonexistentry(self):
        self._test_helper_nochange(
            _complex_db(),
            {'dummydn': {'dummyattr': []}})

    def test_managed_add_attr_delete_others(self):
        self._test_helper_success(
            _complex_db(),
            {'dnfoo': {'dummyattr': ['dummyval']}},
            True)

    def test_managed_no_net_change(self):
        self._test_helper_nochange(
            _complex_db(),
            {'dnfoo': {'attrfoo1': ['valfoo1.2', 'valfoo1.1']}})

    def test_managed_repeated_values(self):
        self._test_helper_success(
            {},
            {'dummydn': {'dummyattr': ['dummyval', 'dummyval']}})
