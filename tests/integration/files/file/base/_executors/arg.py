def __virtual__():
    return True


def execute(*args, **kwargs):
    # we use the dunder to assert the loader is provided minionmods
    return __salt__['test.arg'](['a', 'b', 'c', 1], foo='bar')
