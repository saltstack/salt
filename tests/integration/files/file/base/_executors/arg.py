# -*- coding: utf-8 -*-


def __virtual__():
    return True


def execute(*args, **kwargs):
    # we use the dunder to assert the loader is provided minionmods
    return __salt__['test.arg']('test.arg fired')
