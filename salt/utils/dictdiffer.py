# -*- coding: utf-8 -*-
"""
 Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values

  Originally posted at http://stackoverflow.com/questions/1165352/fast-comparison-between-two-python-dictionary/1165552#1165552
  Available at repository: https://github.com/hughdbrown/dictdiffer

  Added the ability to recursively compare dictionaries
"""
from __future__ import absolute_import, print_function, unicode_literals

import copy

from salt.ext import six

try:
    from collections.abc import Mapping
except ImportError:
    # pylint: disable=no-name-in-module
    from collections import Mapping

    # pylint: enable=no-name-in-module


def diff(current_dict, past_dict):
    return DictDiffer(current_dict, past_dict)


class DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current, self.set_past = set(list(current_dict)), set(list(past_dict))
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(
            o for o in self.intersect if self.past_dict[o] != self.current_dict[o]
        )

    def unchanged(self):
        return set(
            o for o in self.intersect if self.past_dict[o] == self.current_dict[o]
        )


def deep_diff(old, new, ignore=None):
    ignore = ignore or []
    res = {}
    old = copy.deepcopy(old)
    new = copy.deepcopy(new)
    stack = [(old, new, False)]

    while len(stack) > 0:
        tmps = []
        tmp_old, tmp_new, reentrant = stack.pop()
        for key in set(list(tmp_old) + list(tmp_new)):
            if key in tmp_old and key in tmp_new and tmp_old[key] == tmp_new[key]:
                del tmp_old[key]
                del tmp_new[key]
                continue
            if not reentrant:
                if key in tmp_old and key in ignore:
                    del tmp_old[key]
                if key in tmp_new and key in ignore:
                    del tmp_new[key]
                if isinstance(tmp_old.get(key), Mapping) and isinstance(
                    tmp_new.get(key), Mapping
                ):
                    tmps.append((tmp_old[key], tmp_new[key], False))
        if tmps:
            stack.extend([(tmp_old, tmp_new, True)] + tmps)
    if old:
        res["old"] = old
    if new:
        res["new"] = new
    return res


def recursive_diff(past_dict, current_dict, ignore_missing_keys=True):
    """
    Returns a RecursiveDictDiffer object that computes the recursive diffs
    between two dictionaries

    past_dict
            Past dictionary

    current_dict
        Current dictionary

    ignore_missing_keys
        Flag specifying whether to ignore keys that no longer exist in the
        current_dict, but exist in the past_dict. If true, the diff will
        not contain the missing keys.
        Default is True.
    """
    return RecursiveDictDiffer(past_dict, current_dict, ignore_missing_keys)


class RecursiveDictDiffer(DictDiffer):
    """
    Calculates a recursive diff between the current_dict and the past_dict
    creating a diff in the format

    {'new': new_value, 'old': old_value}

    It recursively searches differences in common keys whose values are
    dictionaries creating a diff dict in the format

    {'common_key' : {'new': new_value, 'old': old_value}

    The class overrides all DictDiffer methods, returning lists of keys and
    subkeys using the . notation (i.e 'common_key1.common_key2.changed_key')

    The class provides access to:
        (1) the added, removed, changes keys and subkeys (using the . notation)
               ``added``, ``removed``, ``changed`` methods
        (2) the diffs in the format aboce (diff property)
                ``diffs`` property
        (3) a dict with the new changed values only (new_values property)
                ``new_values`` property
        (4) a dict with the old changed values only (old_values property)
                ``old_values`` property
        (5) a string representation of the changes in the format:
                ``changes_str`` property

    Note:
        The <_null_> value is a reserved value

.. code-block:: text

            common_key1:
              common_key2:
                changed_key1 from '<old_str>' to '<new_str>'
                changed_key2 from '[<old_elem1>, ..]' to '[<new_elem1>, ..]'
            common_key3:
              changed_key3 from <old_int> to <new_int>

    """

    NONE_VALUE = "<_null_>"

    def __init__(self, past_dict, current_dict, ignore_missing_keys):
        """
        past_dict
            Past dictionary.

        current_dict
            Current dictionary.

        ignore_missing_keys
            Flag specifying whether to ignore keys that no longer exist in the
            current_dict, but exist in the past_dict. If true, the diff will
            not contain the missing keys.
        """
        super(RecursiveDictDiffer, self).__init__(current_dict, past_dict)
        self._diffs = self._get_diffs(
            self.current_dict, self.past_dict, ignore_missing_keys
        )
        # Ignores unet values when assessing the changes
        self.ignore_unset_values = True

    @classmethod
    def _get_diffs(cls, dict1, dict2, ignore_missing_keys):
        """
        Returns a dict with the differences between dict1 and dict2

        Notes:
            Keys that only exist in dict2 are not included in the diff if
            ignore_missing_keys is True, otherwise they are
            Simple compares are done on lists
        """
        ret_dict = {}
        for p in dict1.keys():
            if p not in dict2:
                ret_dict.update({p: {"new": dict1[p], "old": cls.NONE_VALUE}})
            elif dict1[p] != dict2[p]:
                if isinstance(dict1[p], dict) and isinstance(dict2[p], dict):
                    sub_diff_dict = cls._get_diffs(
                        dict1[p], dict2[p], ignore_missing_keys
                    )
                    if sub_diff_dict:
                        ret_dict.update({p: sub_diff_dict})
                else:
                    ret_dict.update({p: {"new": dict1[p], "old": dict2[p]}})
        if not ignore_missing_keys:
            for p in dict2.keys():
                if p not in dict1.keys():
                    ret_dict.update({p: {"new": cls.NONE_VALUE, "old": dict2[p]}})
        return ret_dict

    @classmethod
    def _get_values(cls, diff_dict, type="new"):
        """
        Returns a dictionaries with the 'new' values in a diff dict.

        type
            Which values to return, 'new' or 'old'
        """
        ret_dict = {}
        for p in diff_dict.keys():
            if type in diff_dict[p].keys():
                ret_dict.update({p: diff_dict[p][type]})
            else:
                ret_dict.update({p: cls._get_values(diff_dict[p], type=type)})
        return ret_dict

    @classmethod
    def _get_changes(cls, diff_dict):
        """
        Returns a list of string message with the differences in a diff dict.

        Each inner difference is tabulated two space deeper
        """
        changes_strings = []
        for p in sorted(diff_dict.keys()):
            if sorted(diff_dict[p].keys()) == ["new", "old"]:
                # Some string formatting
                old_value = diff_dict[p]["old"]
                if diff_dict[p]["old"] == cls.NONE_VALUE:
                    old_value = "nothing"
                elif isinstance(diff_dict[p]["old"], six.string_types):
                    old_value = "'{0}'".format(diff_dict[p]["old"])
                elif isinstance(diff_dict[p]["old"], list):
                    old_value = "'{0}'".format(", ".join(diff_dict[p]["old"]))
                new_value = diff_dict[p]["new"]
                if diff_dict[p]["new"] == cls.NONE_VALUE:
                    new_value = "nothing"
                elif isinstance(diff_dict[p]["new"], six.string_types):
                    new_value = "'{0}'".format(diff_dict[p]["new"])
                elif isinstance(diff_dict[p]["new"], list):
                    new_value = "'{0}'".format(", ".join(diff_dict[p]["new"]))
                changes_strings.append(
                    "{0} from {1} to {2}".format(p, old_value, new_value)
                )
            else:
                sub_changes = cls._get_changes(diff_dict[p])
                if sub_changes:
                    changes_strings.append("{0}:".format(p))
                    changes_strings.extend(["  {0}".format(c) for c in sub_changes])
        return changes_strings

    def added(self):
        """
        Returns all keys that have been added.

        If the keys are in child dictionaries they will be represented with
        . notation
        """

        def _added(diffs, prefix):
            keys = []
            for key in diffs.keys():
                if isinstance(diffs[key], dict) and "old" not in diffs[key]:
                    keys.extend(
                        _added(diffs[key], prefix="{0}{1}.".format(prefix, key))
                    )
                elif diffs[key]["old"] == self.NONE_VALUE:
                    if isinstance(diffs[key]["new"], dict):
                        keys.extend(
                            _added(
                                diffs[key]["new"], prefix="{0}{1}.".format(prefix, key)
                            )
                        )
                    else:
                        keys.append("{0}{1}".format(prefix, key))
            return keys

        return sorted(_added(self._diffs, prefix=""))

    def removed(self):
        """
        Returns all keys that have been removed.

        If the keys are in child dictionaries they will be represented with
        . notation
        """

        def _removed(diffs, prefix):
            keys = []
            for key in diffs.keys():
                if isinstance(diffs[key], dict) and "old" not in diffs[key]:
                    keys.extend(
                        _removed(diffs[key], prefix="{0}{1}.".format(prefix, key))
                    )
                elif diffs[key]["new"] == self.NONE_VALUE:
                    keys.append("{0}{1}".format(prefix, key))
                elif isinstance(diffs[key]["new"], dict):
                    keys.extend(
                        _removed(
                            diffs[key]["new"], prefix="{0}{1}.".format(prefix, key)
                        )
                    )
            return keys

        return sorted(_removed(self._diffs, prefix=""))

    def changed(self):
        """
        Returns all keys that have been changed.

        If the keys are in child dictionaries they will be represented with
        . notation
        """

        def _changed(diffs, prefix):
            keys = []
            for key in diffs.keys():
                if not isinstance(diffs[key], dict):
                    continue

                if isinstance(diffs[key], dict) and "old" not in diffs[key]:
                    keys.extend(
                        _changed(diffs[key], prefix="{0}{1}.".format(prefix, key))
                    )
                    continue
                if self.ignore_unset_values:
                    if (
                        "old" in diffs[key]
                        and "new" in diffs[key]
                        and diffs[key]["old"] != self.NONE_VALUE
                        and diffs[key]["new"] != self.NONE_VALUE
                    ):
                        if isinstance(diffs[key]["new"], dict):
                            keys.extend(
                                _changed(
                                    diffs[key]["new"],
                                    prefix="{0}{1}.".format(prefix, key),
                                )
                            )
                        else:
                            keys.append("{0}{1}".format(prefix, key))
                    elif isinstance(diffs[key], dict):
                        keys.extend(
                            _changed(diffs[key], prefix="{0}{1}.".format(prefix, key))
                        )
                else:
                    if "old" in diffs[key] and "new" in diffs[key]:
                        if isinstance(diffs[key]["new"], dict):
                            keys.extend(
                                _changed(
                                    diffs[key]["new"],
                                    prefix="{0}{1}.".format(prefix, key),
                                )
                            )
                        else:
                            keys.append("{0}{1}".format(prefix, key))
                    elif isinstance(diffs[key], dict):
                        keys.extend(
                            _changed(diffs[key], prefix="{0}{1}.".format(prefix, key))
                        )

            return keys

        return sorted(_changed(self._diffs, prefix=""))

    def unchanged(self):
        """
        Returns all keys that have been unchanged.

        If the keys are in child dictionaries they will be represented with
        . notation
        """

        def _unchanged(current_dict, diffs, prefix):
            keys = []
            for key in current_dict.keys():
                if key not in diffs:
                    keys.append("{0}{1}".format(prefix, key))
                elif isinstance(current_dict[key], dict):
                    if "new" in diffs[key]:
                        # There is a diff
                        continue
                    else:
                        keys.extend(
                            _unchanged(
                                current_dict[key],
                                diffs[key],
                                prefix="{0}{1}.".format(prefix, key),
                            )
                        )

            return keys

        return sorted(_unchanged(self.current_dict, self._diffs, prefix=""))

    @property
    def diffs(self):
        """Returns a dict with the recursive diffs current_dict - past_dict"""
        return self._diffs

    @property
    def new_values(self):
        """Returns a dictionary with the new values"""
        return self._get_values(self._diffs, type="new")

    @property
    def old_values(self):
        """Returns a dictionary with the old values"""
        return self._get_values(self._diffs, type="old")

    @property
    def changes_str(self):
        """Returns a string describing the changes"""
        return "\n".join(self._get_changes(self._diffs))
