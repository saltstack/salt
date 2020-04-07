# -*- coding: utf-8 -*-
"""
A decorator which returns a function with the same signature of the function
which is being wrapped.
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import inspect
from functools import wraps

# Import Salt libs
import salt.utils.args

# Import 3rd-party libs
from salt.ext import six


def identical_signature_wrapper(original_function, wrapped_function):
    """
    Return a function with identical signature as ``original_function``'s which
    will call the ``wrapped_function``.
    """
    context = {"__wrapped__": wrapped_function}
    function_def = compile(
        "def {0}({1}):\n"
        "    return __wrapped__({2})".format(
            # Keep the original function name
            original_function.__name__,
            # The function signature including defaults, i.e., 'timeout=1'
            inspect.formatargspec(
                *salt.utils.args.get_function_argspec(original_function)
            )[1:-1],
            # The function signature without the defaults
            inspect.formatargspec(
                formatvalue=lambda val: "",
                *salt.utils.args.get_function_argspec(original_function)
            )[1:-1],
        ),
        "<string>",
        "exec",
    )
    six.exec_(function_def, context)
    return wraps(original_function)(context[original_function.__name__])
