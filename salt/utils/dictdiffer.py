# -*- coding: utf-8 -*-
'''
 Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values

  Originally posted at http://stackoverflow.com/questions/1165352/fast-comparison-between-two-python-dictionary/1165552#1165552
  Available at repository: https://github.com/hughdbrown/dictdiffer
'''
from __future__ import absolute_import
from copy import deepcopy
from collections import Mapping


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
        return set(o for o in self.intersect if self.past_dict[o] != self.current_dict[o])

    def unchanged(self):
        return set(o for o in self.intersect if self.past_dict[o] == self.current_dict[o])


def deep_diff(old, new, ignore=None):
    ignore = ignore or []
    res = {}
    old = deepcopy(old)
    new = deepcopy(new)
    stack = [(old, new, False)]

    while len(stack) > 0:
        tmps = []
        tmp_old, tmp_new, reentrant = stack.pop()
        for key in set(list(tmp_old) + list(tmp_new)):
            if key in tmp_old and key in tmp_new \
                    and tmp_old[key] == tmp_new[key]:
                del tmp_old[key]
                del tmp_new[key]
                continue
            if not reentrant:
                if key in tmp_old and key in ignore:
                    del tmp_old[key]
                if key in tmp_new and key in ignore:
                    del tmp_new[key]
                if isinstance(tmp_old.get(key), Mapping) \
                        and isinstance(tmp_new.get(key), Mapping):
                    tmps.append((tmp_old[key], tmp_new[key], False))
        if tmps:
            stack.extend([(tmp_old, tmp_new, True)] + tmps)
    if old:
        res['old'] = old
    if new:
        res['new'] = new
    return res
