# -*- coding: utf-8 -*-


def __virtual__():
    return True


def execute(*args, **kwargs):
    # we use the dunder to assert the loader is provided minionmods
<<<<<<< HEAD
    return __salt__['test.arg']('test.arg fired')
=======
    return __salt__["test.arg"]("test.arg fired")
>>>>>>> 8d70836c614efff36c045d0a87f7a94614409610
