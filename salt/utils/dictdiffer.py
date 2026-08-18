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

import copy
from collections.abc import Mapping


def diff(current_dict, past_dict):
    return DictDiffer(current_dict, past_dict)


class DictDiffer:
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
        return {o for o in self.intersect if self.past_dict[o] != self.current_dict[o]}

    def unchanged(self):
        return {o for o in self.intersect if self.past_dict[o] == self.current_dict[o]}


def deep_diff(old, new, ignore=None):
    ignore = ignore or []
    res = {}
    old = copy.deepcopy(old)
    new = copy.deepcopy(new)
    stack = [(old, new, False)]

    while stack:
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
        (2) the diffs in the format above (diff property)
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
        super().__init__(current_dict, past_dict)
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
        for p in dict1:
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
            for p in dict2:
                if p not in dict1:
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
        for p in diff_dict:
            if type in diff_dict[p]:
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
        for p in sorted(diff_dict):
            if set(diff_dict[p]) == {"new", "old"}:
                changes = {
                    "old_value": diff_dict[p]["old"],
                    "new_value": diff_dict[p]["new"],
                }
                for ref in ("old_value", "new_value"):
                    val = changes[ref]
                    # Some string formatting
                    if val == cls.NONE_VALUE:
                        changes[ref] = "nothing"
                    elif isinstance(val, str):
                        changes[ref] = f"'{val}'"
                    elif isinstance(val, list):
                        changes[ref] = f"'{', '.join(val)}'"
                changes_strings.append(
                    f"{p} from {changes['old_value']} to {changes['new_value']}"
                )
            else:
                sub_changes = cls._get_changes(diff_dict[p])
                if sub_changes:
                    changes_strings.append(f"{p}:")
                    changes_strings.extend([f"  {c}" for c in sub_changes])
        return changes_strings

    def _it_addrm(
        self,
        key_a,
        key_b,
        include_nested=False,
        diffs=None,
        prefix="",
        is_nested=False,
        separator=".",
    ):
        keys = []
        if diffs is None:
            diffs = self.diffs

        for key in diffs:
            if is_nested:
                keys.append(f"{prefix}{key}")

            if not isinstance(diffs[key], dict):
                continue

            if is_nested and include_nested:
                keys.extend(
                    self._it_addrm(
                        key_a,
                        key_b,
                        diffs=diffs[key],
                        prefix=f"{prefix}{key}{separator}",
                        is_nested=is_nested,
                        include_nested=include_nested,
                        separator=separator,
                    )
                )
            elif "old" not in diffs[key]:
                keys.extend(
                    self._it_addrm(
                        key_a,
                        key_b,
                        diffs=diffs[key],
                        prefix=f"{prefix}{key}{separator}",
                        is_nested=is_nested,
                        include_nested=include_nested,
                        separator=separator,
                    )
                )
            elif diffs[key][key_a] == self.NONE_VALUE:
                keys.append(f"{prefix}{key}")

                if isinstance(diffs[key][key_b], dict) and include_nested:
                    keys.extend(
                        self._it_addrm(
                            key_a,
                            key_b,
                            diffs=diffs[key][key_b],
                            is_nested=True,
                            prefix=f"{prefix}{key}{separator}",
                            include_nested=include_nested,
                            separator=separator,
                        )
                    )
            # type change from/to dict
            elif (
                not is_nested
                and not isinstance(diffs[key][key_a], dict)
                and isinstance(diffs[key][key_b], dict)
            ):
                keys.extend(
                    self._it_addrm(
                        key_a,
                        key_b,
                        diffs=diffs[key][key_b],
                        is_nested=True,
                        prefix=f"{prefix}{key}{separator}",
                        include_nested=include_nested,
                        separator=separator,
                    )
                )

        return keys

    def added(
        self, include_nested=False, separator="."
    ):  # pylint: disable=arguments-differ
        """
        Returns all keys that have been added.

        include_nested
            If an added key contains a dictionary, include its
            keys in dot notation as well. Defaults to false.

            .. versionadded:: 3006.0

        separator
            Separator used to indicate nested keys. Defaults to ``.``.

            .. versionadded:: 3006.0
        """
        return sorted(self._it_addrm("old", "new", include_nested, separator=separator))

    def removed(
        self, include_nested=False, separator="."
    ):  # pylint: disable=arguments-differ
        """
        Returns all keys that have been removed.

        include_nested
            If an added key contains a dictionary, include its
            keys in dot notation as well. Defaults to false.

            .. versionadded:: 3006.0

        separator
            Separator used to indicate nested keys. Defaults to ``.``.

            .. versionadded:: 3006.0
        """
        return sorted(self._it_addrm("new", "old", include_nested, separator=separator))

    def changed(self, separator="."):  # pylint: disable=arguments-differ
        """
        Returns all keys that have been changed.

        separator
            Separator used to indicate nested keys. Defaults to ``.``.

            .. versionadded:: 3006.0
        """

        def _changed(diffs, prefix, separator):
            keys = []
            for key in diffs:
                if not isinstance(diffs[key], dict):
                    continue

                if isinstance(diffs[key], dict) and "old" not in diffs[key]:
                    keys.extend(
                        _changed(
                            diffs[key],
                            prefix=f"{prefix}{key}{separator}",
                            separator=separator,
                        )
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
                                    prefix=f"{prefix}{key}{separator}",
                                    separator=separator,
                                )
                            )
                        else:
                            keys.append(f"{prefix}{key}")
                    elif isinstance(diffs[key], dict):
                        keys.extend(
                            _changed(
                                diffs[key],
                                prefix=f"{prefix}{key}{separator}",
                                separator=separator,
                            )
                        )
                else:
                    if "old" in diffs[key] and "new" in diffs[key]:
                        if isinstance(diffs[key]["new"], dict):
                            keys.extend(
                                _changed(
                                    diffs[key]["new"],
                                    prefix=f"{prefix}{key}{separator}",
                                    separator=separator,
                                )
                            )
                        else:
                            keys.append(f"{prefix}{key}")
                    elif isinstance(diffs[key], dict):
                        keys.extend(
                            _changed(
                                diffs[key],
                                prefix=f"{prefix}{key}{separator}",
                                separator=separator,
                            )
                        )

            return keys

        return sorted(_changed(self._diffs, prefix="", separator=separator))

    def unchanged(self, separator="."):  # pylint: disable=arguments-differ
        """
        Returns all keys that have been unchanged.

        separator
            Separator used to indicate nested keys. Defaults to ``.``.

            .. versionadded:: 3006.0
        """

        def _unchanged(current_dict, diffs, prefix, separator):
            keys = []
            for key in current_dict:
                if key not in diffs:
                    keys.append(f"{prefix}{key}")
                elif isinstance(current_dict[key], dict):
                    if "new" in diffs[key]:
                        # There is a diff
                        continue
                    keys.extend(
                        _unchanged(
                            current_dict[key],
                            diffs[key],
                            prefix=f"{prefix}{key}{separator}",
                            separator=separator,
                        )
                    )

            return keys

        return sorted(
            _unchanged(self.current_dict, self._diffs, prefix="", separator=separator)
        )

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
