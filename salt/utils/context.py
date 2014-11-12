# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.utils.context
    ~~~~~~~~~~~~~~~~~~

    Context managers used throughout Salt's source code.
'''
from __future__ import absolute_import

# Import python libs
from contextlib import contextmanager


@contextmanager
def func_globals_inject(func, **overrides):
    '''
    Override specific variables within a function's global context.
    '''
    # recognize methods
    if hasattr(func, "im_func"):
        func = func.__func__

    # Get a reference to the function globals dictionary
    func_globals = func.__globals__
    # Save the current function globals dictionary state values for the
    # overridden objects
    injected_func_globals = []
    overridden_func_globals = {}
    for override in overrides:
        if override in func_globals:
            overridden_func_globals[override] = func_globals[override]
        else:
            injected_func_globals.append(override)

    # Override the function globals with what's passed in the above overrides
    func_globals.update(overrides)

    # The context is now ready to be used
    yield

    # We're now done with the context

    # Restore the overwritten function globals
    func_globals.update(overridden_func_globals)

    # Remove any entry injected in the function globals
    for injected in injected_func_globals:
        del func_globals[injected]
