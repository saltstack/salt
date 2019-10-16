# -*- coding: utf-8 -*-
'''
Functions for manipulating, inspecting, or otherwise working with data types
and data structures.
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import copy
import fnmatch
import logging
import re

try:
    from collections.abc import Mapping, MutableMapping, Sequence
except ImportError:
    from collections import Mapping, MutableMapping, Sequence

# Import Salt libs
import salt.utils.dictupdate
import salt.utils.stringutils
import salt.utils.yaml
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import SaltException
from salt.utils.decorators.jinja import jinja_filter
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin

log = logging.getLogger(__name__)


class CaseInsensitiveDict(MutableMapping):
    '''
    Inspired by requests' case-insensitive dict implementation, but works with
    non-string keys as well.
    '''
    def __init__(self, init=None, **kwargs):
        '''
        Force internal dict to be ordered to ensure a consistent iteration
        order, irrespective of case.
        '''
        self._data = OrderedDict()
        self.update(init or {}, **kwargs)

    def __len__(self):
        return len(self._data)

    def __setitem__(self, key, value):
        # Store the case-sensitive key so it is available for dict iteration
        self._data[to_lowercase(key)] = (key, value)

    def __delitem__(self, key):
        del self._data[to_lowercase(key)]

    def __getitem__(self, key):
        return self._data[to_lowercase(key)][1]

    def __iter__(self):
        return (item[0] for item in six.itervalues(self._data))

    def __eq__(self, rval):
        if not isinstance(rval, Mapping):
            # Comparing to non-mapping type (e.g. int) is always False
            return False
        return dict(self.items_lower()) == dict(CaseInsensitiveDict(rval).items_lower())

    def __repr__(self):
        return repr(dict(six.iteritems(self)))

    def items_lower(self):
        '''
        Returns a generator iterating over keys and values, with the keys all
        being lowercase.
        '''
        return ((key, val[1]) for key, val in six.iteritems(self._data))

    def copy(self):
        '''
        Returns a copy of the object
        '''
        return CaseInsensitiveDict(six.iteritems(self._data))


def __change_case(data, attr, preserve_dict_class=False):
    try:
        return getattr(data, attr)()
    except AttributeError:
        pass

    data_type = data.__class__

    if isinstance(data, Mapping):
        return (data_type if preserve_dict_class else dict)(
            (__change_case(key, attr, preserve_dict_class),
             __change_case(val, attr, preserve_dict_class))
            for key, val in six.iteritems(data)
        )
    elif isinstance(data, Sequence):
        return data_type(
            __change_case(item, attr, preserve_dict_class) for item in data)
    else:
        return data


def to_lowercase(data, preserve_dict_class=False):
    return __change_case(data, 'lower', preserve_dict_class)


def to_uppercase(data, preserve_dict_class=False):
    return __change_case(data, 'upper', preserve_dict_class)


@jinja_filter('compare_dicts')
def compare_dicts(old=None, new=None):
    '''
    Compare before and after results from various salt functions, returning a
    dict describing the changes that were made.
    '''
    ret = {}
    for key in set((new or {})).union((old or {})):
        if key not in old:
            # New key
            ret[key] = {'old': '',
                        'new': new[key]}
        elif key not in new:
            # Key removed
            ret[key] = {'new': '',
                        'old': old[key]}
        elif new[key] != old[key]:
            # Key modified
            ret[key] = {'old': old[key],
                        'new': new[key]}
    return ret


@jinja_filter('compare_lists')
def compare_lists(old=None, new=None):
    '''
    Compare before and after results from various salt functions, returning a
    dict describing the changes that were made
    '''
    ret = {}
    for item in new:
        if item not in old:
            ret.setdefault('new', []).append(item)
    for item in old:
        if item not in new:
            ret.setdefault('old', []).append(item)
    return ret


def decode(data, encoding=None, errors='strict', keep=False,
           normalize=False, preserve_dict_class=False, preserve_tuples=False,
           to_str=False):
    '''
    Generic function which will decode whichever type is passed, if necessary.
    Optionally use to_str=True to ensure strings are str types and not unicode
    on Python 2.

    If `strict` is True, and `keep` is False, and we fail to decode, a
    UnicodeDecodeError will be raised. Passing `keep` as True allows for the
    original value to silently be returned in cases where decoding fails. This
    can be useful for cases where the data passed to this function is likely to
    contain binary blobs, such as in the case of cp.recv.

    If `normalize` is True, then unicodedata.normalize() will be used to
    normalize unicode strings down to a single code point per glyph. It is
    recommended not to normalize unless you know what you're doing. For
    instance, if `data` contains a dictionary, it is possible that normalizing
    will lead to data loss because the following two strings will normalize to
    the same value:

    - u'\\u044f\\u0438\\u0306\\u0446\\u0430.txt'
    - u'\\u044f\\u0439\\u0446\\u0430.txt'

    One good use case for normalization is in the test suite. For example, on
    some platforms such as Mac OS, os.listdir() will produce the first of the
    two strings above, in which "й" is represented as two code points (i.e. one
    for the base character, and one for the breve mark). Normalizing allows for
    a more reliable test case.
    '''
    _decode_func = salt.utils.stringutils.to_unicode \
        if not to_str \
        else salt.utils.stringutils.to_str
    if isinstance(data, Mapping):
        return decode_dict(data, encoding, errors, keep, normalize,
                           preserve_dict_class, preserve_tuples, to_str)
    elif isinstance(data, list):
        return decode_list(data, encoding, errors, keep, normalize,
                           preserve_dict_class, preserve_tuples, to_str)
    elif isinstance(data, tuple):
        return decode_tuple(data, encoding, errors, keep, normalize,
                            preserve_dict_class, to_str) \
            if preserve_tuples \
            else decode_list(data, encoding, errors, keep, normalize,
                             preserve_dict_class, preserve_tuples, to_str)
    else:
        try:
            data = _decode_func(data, encoding, errors, normalize)
        except TypeError:
            # to_unicode raises a TypeError when input is not a
            # string/bytestring/bytearray. This is expected and simply means we
            # are going to leave the value as-is.
            pass
        except UnicodeDecodeError:
            if not keep:
                raise
        return data


def decode_dict(data, encoding=None, errors='strict', keep=False,
                normalize=False, preserve_dict_class=False,
                preserve_tuples=False, to_str=False):
    '''
    Decode all string values to Unicode. Optionally use to_str=True to ensure
    strings are str types and not unicode on Python 2.
    '''
    _decode_func = salt.utils.stringutils.to_unicode \
        if not to_str \
        else salt.utils.stringutils.to_str
    # Make sure we preserve OrderedDicts
    rv = data.__class__() if preserve_dict_class else {}
    for key, value in six.iteritems(data):
        if isinstance(key, tuple):
            key = decode_tuple(key, encoding, errors, keep, normalize,
                               preserve_dict_class, to_str) \
                if preserve_tuples \
                else decode_list(key, encoding, errors, keep, normalize,
                                 preserve_dict_class, preserve_tuples, to_str)
        else:
            try:
                key = _decode_func(key, encoding, errors, normalize)
            except TypeError:
                # to_unicode raises a TypeError when input is not a
                # string/bytestring/bytearray. This is expected and simply
                # means we are going to leave the value as-is.
                pass
            except UnicodeDecodeError:
                if not keep:
                    raise

        if isinstance(value, list):
            value = decode_list(value, encoding, errors, keep, normalize,
                                preserve_dict_class, preserve_tuples, to_str)
        elif isinstance(value, tuple):
            value = decode_tuple(value, encoding, errors, keep, normalize,
                                 preserve_dict_class, to_str) \
                if preserve_tuples \
                else decode_list(value, encoding, errors, keep, normalize,
                                 preserve_dict_class, preserve_tuples, to_str)
        elif isinstance(value, Mapping):
            value = decode_dict(value, encoding, errors, keep, normalize,
                                preserve_dict_class, preserve_tuples, to_str)
        else:
            try:
                value = _decode_func(value, encoding, errors, normalize)
            except TypeError:
                # to_unicode raises a TypeError when input is not a
                # string/bytestring/bytearray. This is expected and simply
                # means we are going to leave the value as-is.
                pass
            except UnicodeDecodeError:
                if not keep:
                    raise

        rv[key] = value
    return rv


def decode_list(data, encoding=None, errors='strict', keep=False,
                normalize=False, preserve_dict_class=False,
                preserve_tuples=False, to_str=False):
    '''
    Decode all string values to Unicode. Optionally use to_str=True to ensure
    strings are str types and not unicode on Python 2.
    '''
    _decode_func = salt.utils.stringutils.to_unicode \
        if not to_str \
        else salt.utils.stringutils.to_str
    rv = []
    for item in data:
        if isinstance(item, list):
            item = decode_list(item, encoding, errors, keep, normalize,
                               preserve_dict_class, preserve_tuples, to_str)
        elif isinstance(item, tuple):
            item = decode_tuple(item, encoding, errors, keep, normalize,
                                preserve_dict_class, to_str) \
                if preserve_tuples \
                else decode_list(item, encoding, errors, keep, normalize,
                                 preserve_dict_class, preserve_tuples, to_str)
        elif isinstance(item, Mapping):
            item = decode_dict(item, encoding, errors, keep, normalize,
                               preserve_dict_class, preserve_tuples, to_str)
        else:
            try:
                item = _decode_func(item, encoding, errors, normalize)
            except TypeError:
                # to_unicode raises a TypeError when input is not a
                # string/bytestring/bytearray. This is expected and simply
                # means we are going to leave the value as-is.
                pass
            except UnicodeDecodeError:
                if not keep:
                    raise

        rv.append(item)
    return rv


def decode_tuple(data, encoding=None, errors='strict', keep=False,
                 normalize=False, preserve_dict_class=False, to_str=False):
    '''
    Decode all string values to Unicode. Optionally use to_str=True to ensure
    strings are str types and not unicode on Python 2.
    '''
    return tuple(
        decode_list(data, encoding, errors, keep, normalize,
                    preserve_dict_class, True, to_str)
    )


def encode(data, encoding=None, errors='strict', keep=False,
           preserve_dict_class=False, preserve_tuples=False):
    '''
    Generic function which will encode whichever type is passed, if necessary

    If `strict` is True, and `keep` is False, and we fail to encode, a
    UnicodeEncodeError will be raised. Passing `keep` as True allows for the
    original value to silently be returned in cases where encoding fails. This
    can be useful for cases where the data passed to this function is likely to
    contain binary blobs.
    '''
    if isinstance(data, Mapping):
        return encode_dict(data, encoding, errors, keep,
                           preserve_dict_class, preserve_tuples)
    elif isinstance(data, list):
        return encode_list(data, encoding, errors, keep,
                           preserve_dict_class, preserve_tuples)
    elif isinstance(data, tuple):
        return encode_tuple(data, encoding, errors, keep, preserve_dict_class) \
            if preserve_tuples \
            else encode_list(data, encoding, errors, keep,
                             preserve_dict_class, preserve_tuples)
    else:
        try:
            return salt.utils.stringutils.to_bytes(data, encoding, errors)
        except TypeError:
            # to_bytes raises a TypeError when input is not a
            # string/bytestring/bytearray. This is expected and simply
            # means we are going to leave the value as-is.
            pass
        except UnicodeEncodeError:
            if not keep:
                raise
        return data


@jinja_filter('json_decode_dict')  # Remove this for Neon
@jinja_filter('json_encode_dict')  # Remove this for Neon
def encode_dict(data, encoding=None, errors='strict', keep=False,
                preserve_dict_class=False, preserve_tuples=False):
    '''
    Encode all string values to bytes
    '''
    rv = data.__class__() if preserve_dict_class else {}
    for key, value in six.iteritems(data):
        if isinstance(key, tuple):
            key = encode_tuple(key, encoding, errors, keep, preserve_dict_class) \
                if preserve_tuples \
                else encode_list(key, encoding, errors, keep,
                                 preserve_dict_class, preserve_tuples)
        else:
            try:
                key = salt.utils.stringutils.to_bytes(key, encoding, errors)
            except TypeError:
                # to_bytes raises a TypeError when input is not a
                # string/bytestring/bytearray. This is expected and simply
                # means we are going to leave the value as-is.
                pass
            except UnicodeEncodeError:
                if not keep:
                    raise

        if isinstance(value, list):
            value = encode_list(value, encoding, errors, keep,
                                preserve_dict_class, preserve_tuples)
        elif isinstance(value, tuple):
            value = encode_tuple(value, encoding, errors, keep, preserve_dict_class) \
                if preserve_tuples \
                else encode_list(value, encoding, errors, keep,
                                 preserve_dict_class, preserve_tuples)
        elif isinstance(value, Mapping):
            value = encode_dict(value, encoding, errors, keep,
                                preserve_dict_class, preserve_tuples)
        else:
            try:
                value = salt.utils.stringutils.to_bytes(value, encoding, errors)
            except TypeError:
                # to_bytes raises a TypeError when input is not a
                # string/bytestring/bytearray. This is expected and simply
                # means we are going to leave the value as-is.
                pass
            except UnicodeEncodeError:
                if not keep:
                    raise

        rv[key] = value
    return rv


@jinja_filter('json_decode_list')  # Remove this for Neon
@jinja_filter('json_encode_list')  # Remove this for Neon
def encode_list(data, encoding=None, errors='strict', keep=False,
                preserve_dict_class=False, preserve_tuples=False):
    '''
    Encode all string values to bytes
    '''
    rv = []
    for item in data:
        if isinstance(item, list):
            item = encode_list(item, encoding, errors, keep,
                               preserve_dict_class, preserve_tuples)
        elif isinstance(item, tuple):
            item = encode_tuple(item, encoding, errors, keep, preserve_dict_class) \
                if preserve_tuples \
                else encode_list(item, encoding, errors, keep,
                                 preserve_dict_class, preserve_tuples)
        elif isinstance(item, Mapping):
            item = encode_dict(item, encoding, errors, keep,
                               preserve_dict_class, preserve_tuples)
        else:
            try:
                item = salt.utils.stringutils.to_bytes(item, encoding, errors)
            except TypeError:
                # to_bytes raises a TypeError when input is not a
                # string/bytestring/bytearray. This is expected and simply
                # means we are going to leave the value as-is.
                pass
            except UnicodeEncodeError:
                if not keep:
                    raise

        rv.append(item)
    return rv


def encode_tuple(data, encoding=None, errors='strict', keep=False,
                 preserve_dict_class=False):
    '''
    Encode all string values to Unicode
    '''
    return tuple(
        encode_list(data, encoding, errors, keep, preserve_dict_class, True))


@jinja_filter('exactly_n_true')
def exactly_n(l, n=1):
    '''
    Tests that exactly N items in an iterable are "truthy" (neither None,
    False, nor 0).
    '''
    i = iter(l)
    return all(any(i) for j in range(n)) and not any(i)


@jinja_filter('exactly_one_true')
def exactly_one(l):
    '''
    Check if only one item is not None, False, or 0 in an iterable.
    '''
    return exactly_n(l)


def filter_by(lookup_dict,
              lookup,
              traverse,
              merge=None,
              default='default',
              base=None):
    '''
    Common code to filter data structures like grains and pillar
    '''
    ret = None
    # Default value would be an empty list if lookup not found
    val = traverse_dict_and_list(traverse, lookup, [])

    # Iterate over the list of values to match against patterns in the
    # lookup_dict keys
    for each in val if isinstance(val, list) else [val]:
        for key in lookup_dict:
            test_key = key if isinstance(key, six.string_types) \
                else six.text_type(key)
            test_each = each if isinstance(each, six.string_types) \
                else six.text_type(each)
            if fnmatch.fnmatchcase(test_each, test_key):
                ret = lookup_dict[key]
                break
        if ret is not None:
            break

    if ret is None:
        ret = lookup_dict.get(default, None)

    if base and base in lookup_dict:
        base_values = lookup_dict[base]
        if ret is None:
            ret = base_values

        elif isinstance(base_values, Mapping):
            if not isinstance(ret, Mapping):
                raise SaltException(
                    'filter_by default and look-up values must both be '
                    'dictionaries.')
            ret = salt.utils.dictupdate.update(copy.deepcopy(base_values), ret)

    if merge:
        if not isinstance(merge, Mapping):
            raise SaltException(
                'filter_by merge argument must be a dictionary.')

        if ret is None:
            ret = merge
        else:
            salt.utils.dictupdate.update(ret, copy.deepcopy(merge))

    return ret


def traverse_dict(data, key, default=None, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Traverse a dict using a colon-delimited (or otherwise delimited, using the
    'delimiter' param) target string. The target 'foo:bar:baz' will return
    data['foo']['bar']['baz'] if this value exists, and will otherwise return
    the dict in the default argument.
    '''
    ptr = data
    try:
        for each in key.split(delimiter):
            ptr = ptr[each]
    except (KeyError, IndexError, TypeError):
        # Encountered a non-indexable value in the middle of traversing
        return default
    return ptr


@jinja_filter('traverse')
def traverse_dict_and_list(data, key, default=None, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Traverse a dict or list using a colon-delimited (or otherwise delimited,
    using the 'delimiter' param) target string. The target 'foo:bar:0' will
    return data['foo']['bar'][0] if this value exists, and will otherwise
    return the dict in the default argument.
    Function will automatically determine the target type.
    The target 'foo:bar:0' will return data['foo']['bar'][0] if data like
    {'foo':{'bar':['baz']}} , if data like {'foo':{'bar':{'0':'baz'}}}
    then return data['foo']['bar']['0']
    '''
    ptr = data
    for each in key.split(delimiter):
        if isinstance(ptr, list):
            try:
                idx = int(each)
            except ValueError:
                embed_match = False
                # Index was not numeric, lets look at any embedded dicts
                for embedded in (x for x in ptr if isinstance(x, dict)):
                    try:
                        ptr = embedded[each]
                        embed_match = True
                        break
                    except KeyError:
                        pass
                if not embed_match:
                    # No embedded dicts matched, return the default
                    return default
            else:
                try:
                    ptr = ptr[idx]
                except IndexError:
                    return default
        else:
            try:
                ptr = ptr[each]
            except (KeyError, TypeError):
                return default
    return ptr


def subdict_match(data,
                  expr,
                  delimiter=DEFAULT_TARGET_DELIM,
                  regex_match=False,
                  exact_match=False):
    '''
    Check for a match in a dictionary using a delimiter character to denote
    levels of subdicts, and also allowing the delimiter character to be
    matched. Thus, 'foo:bar:baz' will match data['foo'] == 'bar:baz' and
    data['foo']['bar'] == 'baz'. The latter would take priority over the
    former, as more deeply-nested matches are tried first.
    '''
    def _match(target, pattern, regex_match=False, exact_match=False):
        # The reason for using six.text_type first and _then_ using
        # to_unicode as a fallback is because we want to eventually have
        # unicode types for comparison below. If either value is numeric then
        # six.text_type will turn it into a unicode string. However, if the
        # value is a PY2 str type with non-ascii chars, then the result will be
        # a UnicodeDecodeError. In those cases, we simply use to_unicode to
        # decode it to unicode. The reason we can't simply use to_unicode to
        # begin with is that (by design) to_unicode will raise a TypeError if a
        # non-string/bytestring/bytearray value is passed.
        try:
            target = six.text_type(target).lower()
        except UnicodeDecodeError:
            target = salt.utils.stringutils.to_unicode(target).lower()
        try:
            pattern = six.text_type(pattern).lower()
        except UnicodeDecodeError:
            pattern = salt.utils.stringutils.to_unicode(pattern).lower()

        if regex_match:
            try:
                return re.match(pattern, target)
            except Exception:
                log.error('Invalid regex \'%s\' in match', pattern)
                return False
        else:
            return target == pattern if exact_match \
                else fnmatch.fnmatch(target, pattern)

    def _dict_match(target, pattern, regex_match=False, exact_match=False):
        wildcard = pattern.startswith('*:')
        if wildcard:
            pattern = pattern[2:]

        if pattern == '*':
            # We are just checking that the key exists
            return True
        elif pattern in target:
            # We might want to search for a key
            return True
        elif subdict_match(target,
                           pattern,
                           regex_match=regex_match,
                           exact_match=exact_match):
            return True
        if wildcard:
            for key in target:
                if isinstance(target[key], dict):
                    if _dict_match(target[key],
                                   pattern,
                                   regex_match=regex_match,
                                   exact_match=exact_match):
                        return True
                elif isinstance(target[key], list):
                    for item in target[key]:
                        if _match(item,
                                  pattern,
                                  regex_match=regex_match,
                                  exact_match=exact_match):
                            return True
                elif _match(target[key],
                            pattern,
                            regex_match=regex_match,
                            exact_match=exact_match):
                    return True
        return False

    splits = expr.split(delimiter)
    num_splits = len(splits)
    if num_splits == 1:
        # Delimiter not present, this can't possibly be a match
        return False

    splits = expr.split(delimiter)
    num_splits = len(splits)
    if num_splits == 1:
        # Delimiter not present, this can't possibly be a match
        return False

    # If we have 4 splits, then we have three delimiters. Thus, the indexes we
    # want to use are 3, 2, and 1, in that order.
    for idx in range(num_splits - 1, 0, -1):
        key = delimiter.join(splits[:idx])
        if key == '*':
            # We are matching on everything under the top level, so we need to
            # treat the match as the entire data being passed in
            matchstr = expr
            match = data
        else:
            matchstr = delimiter.join(splits[idx:])
            match = traverse_dict_and_list(data, key, {}, delimiter=delimiter)
        log.debug("Attempting to match '%s' in '%s' using delimiter '%s'",
                  matchstr, key, delimiter)
        if match == {}:
            continue
        if isinstance(match, dict):
            if _dict_match(match,
                           matchstr,
                           regex_match=regex_match,
                           exact_match=exact_match):
                return True
            continue
        if isinstance(match, (list, tuple)):
            # We are matching a single component to a single list member
            for member in match:
                if isinstance(member, dict):
                    if _dict_match(member,
                                   matchstr,
                                   regex_match=regex_match,
                                   exact_match=exact_match):
                        return True
                if _match(member,
                          matchstr,
                          regex_match=regex_match,
                          exact_match=exact_match):
                    return True
            continue
        if _match(match,
                  matchstr,
                  regex_match=regex_match,
                  exact_match=exact_match):
            return True
    return False


@jinja_filter('substring_in_list')
def substr_in_list(string_to_search_for, list_to_search):
    '''
    Return a boolean value that indicates whether or not a given
    string is present in any of the strings which comprise a list
    '''
    return any(string_to_search_for in s for s in list_to_search)


def is_dictlist(data):
    '''
    Returns True if data is a list of one-element dicts (as found in many SLS
    schemas), otherwise returns False
    '''
    if isinstance(data, list):
        for element in data:
            if isinstance(element, dict):
                if len(element) != 1:
                    return False
            else:
                return False
        return True
    return False


def repack_dictlist(data,
                    strict=False,
                    recurse=False,
                    key_cb=None,
                    val_cb=None):
    '''
    Takes a list of one-element dicts (as found in many SLS schemas) and
    repacks into a single dictionary.
    '''
    if isinstance(data, six.string_types):
        try:
            data = salt.utils.yaml.safe_load(data)
        except salt.utils.yaml.parser.ParserError as err:
            log.error(err)
            return {}

    if key_cb is None:
        key_cb = lambda x: x
    if val_cb is None:
        val_cb = lambda x, y: y

    valid_non_dict = (six.string_types, six.integer_types, float)
    if isinstance(data, list):
        for element in data:
            if isinstance(element, valid_non_dict):
                continue
            elif isinstance(element, dict):
                if len(element) != 1:
                    log.error(
                        'Invalid input for repack_dictlist: key/value pairs '
                        'must contain only one element (data passed: %s).',
                        element
                    )
                    return {}
            else:
                log.error(
                    'Invalid input for repack_dictlist: element %s is '
                    'not a string/dict/numeric value', element
                )
                return {}
    else:
        log.error(
            'Invalid input for repack_dictlist, data passed is not a list '
            '(%s)', data
        )
        return {}

    ret = {}
    for element in data:
        if isinstance(element, valid_non_dict):
            ret[key_cb(element)] = None
        else:
            key = next(iter(element))
            val = element[key]
            if is_dictlist(val):
                if recurse:
                    ret[key_cb(key)] = repack_dictlist(val, recurse=recurse)
                elif strict:
                    log.error(
                        'Invalid input for repack_dictlist: nested dictlist '
                        'found, but recurse is set to False'
                    )
                    return {}
                else:
                    ret[key_cb(key)] = val_cb(key, val)
            else:
                ret[key_cb(key)] = val_cb(key, val)
    return ret


@jinja_filter('is_list')
def is_list(value):
    '''
    Check if a variable is a list.
    '''
    return isinstance(value, list)


@jinja_filter('is_iter')
def is_iter(y, ignore=six.string_types):
    '''
    Test if an object is iterable, but not a string type.

    Test if an object is an iterator or is iterable itself. By default this
    does not return True for string objects.

    The `ignore` argument defaults to a list of string types that are not
    considered iterable. This can be used to also exclude things like
    dictionaries or named tuples.

    Based on https://bitbucket.org/petershinners/yter
    '''

    if ignore and isinstance(y, ignore):
        return False
    try:
        iter(y)
        return True
    except TypeError:
        return False


@jinja_filter('sorted_ignorecase')
def sorted_ignorecase(to_sort):
    '''
    Sort a list of strings ignoring case.

    >>> L = ['foo', 'Foo', 'bar', 'Bar']
    >>> sorted(L)
    ['Bar', 'Foo', 'bar', 'foo']
    >>> sorted(L, key=lambda x: x.lower())
    ['bar', 'Bar', 'foo', 'Foo']
    >>>
    '''
    return sorted(to_sort, key=lambda x: x.lower())


def is_true(value=None):
    '''
    Returns a boolean value representing the "truth" of the value passed. The
    rules for what is a "True" value are:

        1. Integer/float values greater than 0
        2. The string values "True" and "true"
        3. Any object for which bool(obj) returns True
    '''
    # First, try int/float conversion
    try:
        value = int(value)
    except (ValueError, TypeError):
        pass
    try:
        value = float(value)
    except (ValueError, TypeError):
        pass

    # Now check for truthiness
    if isinstance(value, (six.integer_types, float)):
        return value > 0
    elif isinstance(value, six.string_types):
        return six.text_type(value).lower() == 'true'
    else:
        return bool(value)


@jinja_filter('mysql_to_dict')
def mysql_to_dict(data, key):
    '''
    Convert MySQL-style output to a python dictionary
    '''
    ret = {}
    headers = ['']
    for line in data:
        if not line:
            continue
        if line.startswith('+'):
            continue
        comps = line.split('|')
        for comp in range(len(comps)):
            comps[comp] = comps[comp].strip()
        if len(headers) > 1:
            index = len(headers) - 1
            row = {}
            for field in range(index):
                if field < 1:
                    continue
                else:
                    row[headers[field]] = salt.utils.stringutils.to_num(comps[field])
            ret[row[key]] = row
        else:
            headers = comps
    return ret


def simple_types_filter(data):
    '''
    Convert the data list, dictionary into simple types, i.e., int, float, string,
    bool, etc.
    '''
    if data is None:
        return data

    simpletypes_keys = (six.string_types, six.text_type, six.integer_types, float, bool)
    simpletypes_values = tuple(list(simpletypes_keys) + [list, tuple])

    if isinstance(data, (list, tuple)):
        simplearray = []
        for value in data:
            if value is not None:
                if isinstance(value, (dict, list)):
                    value = simple_types_filter(value)
                elif not isinstance(value, simpletypes_values):
                    value = repr(value)
            simplearray.append(value)
        return simplearray

    if isinstance(data, dict):
        simpledict = {}
        for key, value in six.iteritems(data):
            if key is not None and not isinstance(key, simpletypes_keys):
                key = repr(key)
            if value is not None and isinstance(value, (dict, list, tuple)):
                value = simple_types_filter(value)
            elif value is not None and not isinstance(value, simpletypes_values):
                value = repr(value)
            simpledict[key] = value
        return simpledict

    return data


def stringify(data):
    '''
    Given an iterable, returns its items as a list, with any non-string items
    converted to unicode strings.
    '''
    ret = []
    for item in data:
        if six.PY2 and isinstance(item, str):
            item = salt.utils.stringutils.to_unicode(item)
        elif not isinstance(item, six.string_types):
            item = six.text_type(item)
        ret.append(item)
    return ret
