# -*- coding: utf-8 -*-
"""
Compare lists of dictionaries by a specified key.

The following can be retrieved:
    (1) List of added, removed, intersect elements
    (2) List of diffs having the following format:
        <key_val>: {<elem_key: {'old': <old_value>, 'new': <new_value>}}
        A recursive diff is done between the the values (dicts) with the same
        key
    (3) List with the new values for each key
    (4) List with the old values for each key
    (5) List of changed items in the format
        ('<key_val>.<elem_key>', {'old': <old_value>, 'new': <new_value>})
    (5) String representations of the list diff

Note: All dictionaries keys are expected to be strings
"""
from __future__ import absolute_import, unicode_literals

from salt.ext import six
from salt.utils.dictdiffer import recursive_diff


def list_diff(list_a, list_b, key):
    return ListDictDiffer(list_a, list_b, key)


class ListDictDiffer(object):
    """
    Calculates the differences between two lists of dictionaries.

    It matches the items based on a given key and uses the recursive_diff to
    diff the two values.
    """

    def __init__(self, current_list, next_list, key):
        self._intersect = []
        self._removed = []
        self._added = []
        self._new = next_list
        self._current = current_list
        self._key = key
        for current_item in current_list:
            if key not in current_item:
                raise ValueError(
                    "The supplied key '{0}' does not "
                    "exist in item, the available keys are: {1}"
                    "".format(key, current_item.keys())
                )
            for next_item in next_list:
                if key not in next_item:
                    raise ValueError(
                        "The supplied key '{0}' does not "
                        "exist in item, the available keys are: "
                        "{1}".format(key, next_item.keys())
                    )
                if next_item[key] == current_item[key]:
                    item = {key: next_item[key], "old": current_item, "new": next_item}
                    self._intersect.append(item)
                    break
            else:
                self._removed.append(current_item)

        for next_item in next_list:
            for current_item in current_list:
                if next_item[key] == current_item[key]:
                    break
            else:
                self._added.append(next_item)

    def _get_recursive_difference(self, type):
        """Returns the recursive diff between dict values"""
        if type == "intersect":
            return [
                recursive_diff(item["old"], item["new"]) for item in self._intersect
            ]
        elif type == "added":
            return [recursive_diff({}, item) for item in self._added]
        elif type == "removed":
            return [
                recursive_diff(item, {}, ignore_missing_keys=False)
                for item in self._removed
            ]
        elif type == "all":
            recursive_list = []
            recursive_list.extend(
                [recursive_diff(item["old"], item["new"]) for item in self._intersect]
            )
            recursive_list.extend([recursive_diff({}, item) for item in self._added])
            recursive_list.extend(
                [
                    recursive_diff(item, {}, ignore_missing_keys=False)
                    for item in self._removed
                ]
            )
            return recursive_list
        else:
            raise ValueError(
                "The given type for recursive list matching " "is not supported."
            )

    @property
    def removed(self):
        """Returns the objects which are removed from the list"""
        return self._removed

    @property
    def added(self):
        """Returns the objects which are added to the list"""
        return self._added

    @property
    def intersect(self):
        """Returns the intersect objects"""
        return self._intersect

    def remove_diff(self, diff_key=None, diff_list="intersect"):
        """Deletes an attribute from all of the intersect objects"""
        if diff_list == "intersect":
            for item in self._intersect:
                item["old"].pop(diff_key, None)
                item["new"].pop(diff_key, None)
        if diff_list == "removed":
            for item in self._removed:
                item.pop(diff_key, None)

    @property
    def diffs(self):
        """
        Returns a list of dictionaries with key value pairs.
        The values are the differences between the items identified by the key.
        """
        differences = []
        for item in self._get_recursive_difference(type="all"):
            if item.diffs:
                if item.past_dict:
                    differences.append({item.past_dict[self._key]: item.diffs})
                elif item.current_dict:
                    differences.append({item.current_dict[self._key]: item.diffs})
        return differences

    @property
    def changes_str(self):
        """Returns a string describing the changes"""
        changes = ""
        for item in self._get_recursive_difference(type="intersect"):
            if item.diffs:
                changes = "".join(
                    [
                        changes,
                        # Tabulate comment deeper, show the key attribute and the value
                        # Next line should be tabulated even deeper,
                        #  every change should be tabulated 1 deeper
                        "\tidentified by {0} {1}:\n\t{2}\n".format(
                            self._key,
                            item.past_dict[self._key],
                            item.changes_str.replace("\n", "\n\t"),
                        ),
                    ]
                )
        for item in self._get_recursive_difference(type="removed"):
            if item.past_dict:
                changes = "".join(
                    [
                        changes,
                        # Tabulate comment deeper, show the key attribute and the value
                        "\tidentified by {0} {1}:"
                        "\n\twill be removed\n".format(
                            self._key, item.past_dict[self._key]
                        ),
                    ]
                )
        for item in self._get_recursive_difference(type="added"):
            if item.current_dict:
                changes = "".join(
                    [
                        changes,
                        # Tabulate comment deeper, show the key attribute and the value
                        "\tidentified by {0} {1}:"
                        "\n\twill be added\n".format(
                            self._key, item.current_dict[self._key]
                        ),
                    ]
                )
        return changes

    @property
    def changes_str2(self, tab_string="  "):
        """
        Returns a string in a more compact format describing the changes.

        The output better alligns with the one in recursive_diff.
        """
        changes = []
        for item in self._get_recursive_difference(type="intersect"):
            if item.diffs:
                changes.append(
                    "{tab}{0}={1} (updated):\n{tab}{tab}{2}"
                    "".format(
                        self._key,
                        item.past_dict[self._key],
                        item.changes_str.replace("\n", "\n{0}{0}".format(tab_string)),
                        tab=tab_string,
                    )
                )
        for item in self._get_recursive_difference(type="removed"):
            if item.past_dict:
                changes.append(
                    "{tab}{0}={1} (removed)".format(
                        self._key, item.past_dict[self._key], tab=tab_string
                    )
                )
        for item in self._get_recursive_difference(type="added"):
            if item.current_dict:
                changes.append(
                    "{tab}{0}={1} (added): {2}".format(
                        self._key,
                        item.current_dict[self._key],
                        dict(item.current_dict),
                        tab=tab_string,
                    )
                )
        return "\n".join(changes)

    @property
    def new_values(self):
        """Returns the new values from the diff"""

        def get_new_values_and_key(item):
            values = item.new_values
            if item.past_dict:
                values.update({self._key: item.past_dict[self._key]})
            else:
                # This is a new item as it has no past_dict
                values.update({self._key: item.current_dict[self._key]})
            return values

        return [
            get_new_values_and_key(el)
            for el in self._get_recursive_difference("all")
            if el.diffs and el.current_dict
        ]

    @property
    def old_values(self):
        """Returns the old values from the diff"""

        def get_old_values_and_key(item):
            values = item.old_values
            values.update({self._key: item.past_dict[self._key]})
            return values

        return [
            get_old_values_and_key(el)
            for el in self._get_recursive_difference("all")
            if el.diffs and el.past_dict
        ]

    def changed(self, selection="all"):
        """
        Returns the list of changed values.
        The key is added to each item.

        selection
            Specifies the desired changes.
            Supported values are
                ``all`` - all changed items are included in the output
                ``intersect`` - changed items present in both lists are included
        """
        changed = []
        if selection == "all":
            for recursive_item in self._get_recursive_difference(type="all"):
                # We want the unset values as well
                recursive_item.ignore_unset_values = False
                key_val = (
                    six.text_type(recursive_item.past_dict[self._key])
                    if self._key in recursive_item.past_dict
                    else six.text_type(recursive_item.current_dict[self._key])
                )

                for change in recursive_item.changed():
                    if change != self._key:
                        changed.append(".".join([self._key, key_val, change]))
            return changed
        elif selection == "intersect":
            # We want the unset values as well
            for recursive_item in self._get_recursive_difference(type="intersect"):
                recursive_item.ignore_unset_values = False
                key_val = (
                    six.text_type(recursive_item.past_dict[self._key])
                    if self._key in recursive_item.past_dict
                    else six.text_type(recursive_item.current_dict[self._key])
                )

                for change in recursive_item.changed():
                    if change != self._key:
                        changed.append(".".join([self._key, key_val, change]))
            return changed

    @property
    def current_list(self):
        return self._current

    @property
    def new_list(self):
        return self._new
