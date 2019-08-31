# -*- coding: utf-8 -*-
'''
tests.support.comparables
~~~~~~~~~~~~~~~~~~~~~~~~~

Comparable data structures for pytest assertions
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import re
import pprint
import logging

# Import Salt libs
import salt.ext.six as six
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)


class ComparableSubDict(dict):
    __comparable_keys__ = ()

    def __init__(self, *args, **kwargs):
        super(ComparableSubDict, self).__init__(*args, **kwargs)
        self._original = self.copy()
        self._comparable_subset = OrderedDict()

    def get_comparable_dict(self):
        if not self._comparable_subset:
            for key in self.__comparable_keys__:
                if key not in self:
                    continue
                self._comparable_subset[key] = self[key]
        return self._comparable_subset

    def construct_comparable_instance(self, data):
        return self.__class__(data)

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, dict.__repr__(self))

    def __eq__(self, other):
        return self.compare_with(other, explain=False) is True

    def __ne__(self, other):
        return self.compare_with(other, explain=False) is False

    def explain_comparisson_with(self, other):
        return self.compare_with(other, explain=True)

    def compare_with(self, other, explain=False):
        if not isinstance(other, self.__class__):
            other = self.construct_comparable_instance(other)

        if explain:
            explanation = ['Comparing instances of {}:'.format(self.__class__.__name__)]

        comparable_self = self.get_comparable_dict()
        comparable_other = other.get_comparable_dict()

        if comparable_self == comparable_other:
            # They match directly, return fast
            return True

        if comparable_self and not comparable_other or not comparable_self and comparable_other:
            # Make sure comparissons are not run if one of the dictionaries is empty but not both
            if explain:
                explanation.append(
                    '  - Cannot compare instances of {} against an empty comparable counterpart'.format(
                        self.__class__.__name__
                    )
                )
                return explanation
            return False

        if not set(comparable_self).intersection(set(comparable_other)):
            # There's not a single key to compare, we can't blindly match
            if explain:
                explanation.append(
                    '  - Nothing to compare because the intersection of the comparable keys is empty.'
                )
                return explanation
            return False

        for key in comparable_self:
            if key not in comparable_other:
                continue
            comparable_self_value = comparable_self[key]
            comparable_other_value = comparable_other[key]
            if explain:
                if isinstance(comparable_self_value, ComparableSubDict):
                    explanation.extend(comparable_self_value.explain_comparisson_with(comparable_other_value))
                    continue
            # pylint: disable=repr-flag-used-in-string
            compare_func = getattr(self, 'compare_{}'.format(key), None)
            if compare_func is not None:
                comparisson_matched = compare_func(comparable_self_value, comparable_other_value) is True
            else:
                comparisson_matched = comparable_self_value == comparable_other_value

            if not comparisson_matched:
                if explain:
                    explanation.extend(pprint.pformat(comparable_other_value).splitlines())
                    explanation.append('  - The values for the \'{}\' key do not match:'.format(key))
                    explanation.append('     {!r} != {!r}'.format(comparable_self_value, comparable_other_value))
                else:
                    return False
            # pylint: enable=repr-flag-used-in-string
        if explain:
            return explanation
        return True


class ComparableChangesMixin(object):

    def compare_changes(self, this_value, other_value):
        if this_value == other_value:
            # They match directly, return fast
            return True

        if not set(this_value).intersection(set(other_value)):
            # There's not a single key to compare, we can't run a "sub" comparison
            return False

        for key in this_value:
            if key not in other_value:
                continue

            t_value = this_value[key]
            o_value = other_value[key]

            if isinstance(t_value, bool):
                if t_value is not o_value:
                    return False
            elif isinstance(t_value, str):
                if t_value == o_value:
                    # Values match directly
                    continue
                if re.match(o_value, t_value, re.DOTALL) is None:
                    # Didn't match using regex
                    return False
            else:
                if t_value != o_value:
                    return False
        return True


class ComparableCommentMixin(object):

    def compare_comment(self, this_value, other_value):
        '''
        We support regex matching on comparissons
        '''
        if not isinstance(this_value, six.string_types):
            this_value = '\n'.join(this_value)
        if not isinstance(other_value, six.string_types):
            other_value = '\n'.join(other_value)
        if this_value == other_value:
            return True
        return re.match(other_value, this_value, re.DOTALL) is not None


class ComparableResultMixin(object):
    def compare_result(self, this_value, other_value):
        return this_value is other_value


class ComparableStateEntry(ComparableSubDict,
                           ComparableChangesMixin,
                           ComparableCommentMixin,
                           ComparableResultMixin):
    '''
    We create a state entry which subclasses from a dictionary
    because we want to allow pytest to run specific assertions
    against the contents.
    '''
    __comparable_keys__ = ('__id__', '__sls__', 'changes', 'comment', 'name', 'result', 'status')

    def compare_name(self, this_value, other_value):
        '''
        We support regex matching on comparissons
        '''
        if this_value == other_value:
            return True
        return re.match(other_value, this_value) is not None

    def compare___id__(self, this_value, other_value):
        return self.compare_name(this_value, other_value)

    def compare___sls__(self, this_value, other_value):
        return self.compare_name(this_value, other_value)

    def compare_status(self, this_value, other_value):
        return this_value == other_value


class StateReturn(ComparableSubDict):
    '''
    We create a state return which subclasses from a dictionary
    because we want to allow pytest to run specific assertions
    against the contents.
    '''

    __comparable_keys__ = ('state_entries',)

    def __init__(self, *args, **kwargs):
        super(StateReturn, self).__init__(*args, **kwargs)
        self.setdefault('state_entries', [])
        for idx, passed_in_state_entry in enumerate(self['state_entries']):
            self['state_entries'][idx] = ComparableStateEntry(passed_in_state_entry)
        state_entries = {}
        for key in list(self):
            if not isinstance(self[key], dict):
                continue
            if '_|-' in key or key in ('*', '.*') or '__sls__' in self[key]:
                state_entries[key] = self.pop(key)
        for key, value in sorted(state_entries.items(), key=lambda kv: kv[1]['__run_num__']):
            value['__state_entry_name__'] = key
            self['state_entries'].append(ComparableStateEntry(value))

        # If by now state entries are empty, remove it because it's comparisson function,
        # compare_state_entries is quite permissive and would allow things like:
        #   {} == a != {}
        if not self['state_entries']:
            self.pop('state_entries')

    def construct_comparable_instance(self, data):
        for key, value in data.items():
            if ('_|-' in key or key in ('*', '.*') or '__sls__' in value) and '__run_num__' not in value:
                value['__run_num__'] = 0
        return super(StateReturn, self).construct_comparable_instance(data)

    def compare_state_entries(self, this_value, other_value):
        if this_value and not other_value or not this_value and other_value:
            return True
        return this_value == other_value

    @property
    def result(self):
        return all([state['result'] for state in self.get('state_entries') or ()])

    def items(self):
        _items = {}
        for state_entry in self.get('state_entries', ()):
            state_entry_copy = state_entry.copy()
            _items[state_entry_copy.pop('__state_entry_name__')] = state_entry_copy
        return _items.items()

    def keys(self):
        _keys = []
        for state_entry in self.get('state_entries', ()):
            _keys.append(state_entry['__state_entry_name__'])
        return _keys

    def values(self):
        _values = []
        for _, value in self.items():
            _values.append(value)
        return _values


class StateReturnError(list):

    def construct_comparable_instance(self, data):
        if not isinstance(data, list):
            data = [data]
        return self.__class__(data)

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, list.__repr__(self))

    def __eq__(self, other):
        return self.compare_with(other, explain=False) is True

    def __ne__(self, other):
        return self.compare_with(other, explain=False) is False

    def __contains__(self, other):
        return self.compare_with(other, explain=False) is True

    def explain_comparisson_with(self, other):
        return self.compare_with(other, explain=True)

    def compare_with(self, other, explain=False):
        if not isinstance(other, self.__class__):
            other = self.construct_comparable_instance(other)

        if explain:
            explanation = ['Comparing instances of {}:'.format(self.__class__.__name__)]

        #if self == other:
        #    # They match directly, return fast
        #    return True

        if self and not other or not self and other:
            # Make sure comparissons are not run if one of the lists is empty but not both
            if explain:
                explanation.append(
                    '  - Cannot compare instances of {} against an empty comparable counterpart'.format(
                        self.__class__.__name__
                    )
                )
                return explanation
            return False

        # pylint: disable=repr-flag-used-in-string
        comparisson_matched = self.compare_errors(other)
        if not comparisson_matched:
            if explain:
                explanation.append('  - The state errors do not match:')
                explanation.append('     {!r} != {!r}'.format(self, other))
            else:
                return False
            # pylint: enable=repr-flag-used-in-string
        if explain:
            return explanation
        return True

    def compare_errors(self, other_value):
        '''
        We support regex matching on comparissons
        '''
        this_value = '\n'.join(self)
        other_value = '\n'.join(other_value)
        if this_value == other_value:
            return True
        return re.match(other_value, this_value, re.DOTALL) is not None
