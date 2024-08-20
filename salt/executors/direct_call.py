"""
Direct call executor module
"""


def execute(opts, data, func, args, kwargs):
    """
    Directly calls the given function with arguments
    """
    return func(*args, **kwargs)
