from functools import wraps


def flaky_catcher(fun, exception, msg=None, exception_msg=None):
    @wraps(fun)
    def flaky_catcher_helper(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except exception as e:
            pass

    return flaky_catcher_helper
