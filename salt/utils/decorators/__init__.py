# -*- coding: utf-8 -*-
'''
Helpful decorators for module writing
'''

# Import python libs
from __future__ import absolute_import
import inspect
import logging
import time
from functools import wraps
from collections import defaultdict

# Import salt libs
import salt.utils
from salt.exceptions import CommandNotFoundError
from salt.log import LOG_LEVELS

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


class Depends(object):
    '''
    This decorator will check the module when it is loaded and check that the
    dependencies passed in are in the globals of the module. If not, it will
    cause the function to be unloaded (or replaced)
    '''
    # kind -> Dependency -> list of things that depend on it
    dependency_dict = defaultdict(lambda: defaultdict(set))

    def __init__(self, *dependencies, **kwargs):
        '''
        The decorator is instantiated with a list of dependencies (string of
        global name)

        An example use of this would be:

            @depends('modulename')
            def test():
                return 'foo'

            OR

            @depends('modulename', fallback_function=function)
            def test():
                return 'foo'
        '''

        log.trace(
            'Depends decorator instantiated with dep list of {0}'.format(
                dependencies
            )
        )
        self.dependencies = dependencies
        self.fallback_function = kwargs.get('fallback_function')

    def __call__(self, function):
        '''
        The decorator is "__call__"d with the function, we take that function
        and determine which module and function name it is to store in the
        class wide depandancy_dict
        '''
        try:
            # This inspect call may fail under certain conditions in the loader. Possibly related to
            # a Python bug here:
            # http://bugs.python.org/issue17735
            frame = inspect.stack()[1][0]
            # due to missing *.py files under esky we cannot use inspect.getmodule
            # module name is something like salt.loaded.int.modules.test
            kind = frame.f_globals['__name__'].rsplit('.', 2)[1]
            for dep in self.dependencies:
                self.dependency_dict[kind][dep].add(
                    (frame, function, self.fallback_function)
                )
        except Exception as exc:
            log.error('Exception encountered when attempting to inspect frame in '
                      'dependency decorator: {0}'.format(exc))
        return function

    @classmethod
    def enforce_dependencies(cls, functions, kind):
        '''
        This is a class global method to enforce the dependencies that you
        currently know about.
        It will modify the "functions" dict and remove/replace modules that
        are missing dependencies.
        '''
        for dependency, dependent_set in six.iteritems(cls.dependency_dict[kind]):
            # check if dependency is loaded
            for frame, func, fallback_function in dependent_set:
                # check if you have the dependency
                if dependency is True:
                    log.trace(
                        'Dependency for {0}.{1} exists, not unloading'.format(
                            frame.f_globals['__name__'].split('.')[-1],
                            func.__name__,
                        )
                    )
                    continue

                if dependency in frame.f_globals \
                        or dependency in frame.f_locals:
                    log.trace(
                        'Dependency ({0}) already loaded inside {1}, '
                        'skipping'.format(
                            dependency,
                            frame.f_globals['__name__'].split('.')[-1]
                        )
                    )
                    continue
                log.trace(
                    'Unloading {0}.{1} because dependency ({2}) is not '
                    'imported'.format(
                        frame.f_globals['__name__'],
                        func,
                        dependency
                    )
                )
                # if not, unload dependent_set
                if frame:
                    try:
                        func_name = frame.f_globals['__func_alias__'][func.__name__]
                    except (AttributeError, KeyError):
                        func_name = func.__name__

                    mod_key = '{0}.{1}'.format(frame.f_globals['__name__'].split('.')[-1],
                                               func_name)

                    # if we don't have this module loaded, skip it!
                    if mod_key not in functions:
                        continue

                    try:
                        if fallback_function is not None:
                            functions[mod_key] = fallback_function
                        else:
                            del functions[mod_key]
                    except AttributeError:
                        # we already did???
                        log.trace('{0} already removed, skipping'.format(mod_key))
                        continue


class depends(Depends):  # pylint: disable=C0103
    '''
    Wrapper of Depends for capitalization
    '''


def timing(function):
    '''
    Decorator wrapper to log execution time, for profiling purposes
    '''
    @wraps(function)
    def wrapped(*args, **kwargs):
        start_time = time.time()
        ret = function(*args, **salt.utils.clean_kwargs(**kwargs))
        end_time = time.time()
        if function.__module__.startswith('salt.loaded.int.'):
            mod_name = function.__module__[16:]
        else:
            mod_name = function.__module__
        log.profile(
            'Function {0}.{1} took {2:.20f} seconds to execute'.format(
                mod_name,
                function.__name__,
                end_time - start_time
            )
        )
        return ret
    return wrapped


def which(exe):
    '''
    Decorator wrapper for salt.utils.which
    '''
    def wrapper(function):
        def wrapped(*args, **kwargs):
            if salt.utils.which(exe) is None:
                raise CommandNotFoundError(
                    'The \'{0}\' binary was not found in $PATH.'.format(exe)
                )
            return function(*args, **kwargs)
        return identical_signature_wrapper(function, wrapped)
    return wrapper


def which_bin(exes):
    '''
    Decorator wrapper for salt.utils.which_bin
    '''
    def wrapper(function):
        def wrapped(*args, **kwargs):
            if salt.utils.which_bin(exes) is None:
                raise CommandNotFoundError(
                    'None of provided binaries({0}) was not found '
                    'in $PATH.'.format(
                        ['\'{0}\''.format(exe) for exe in exes]
                    )
                )
            return function(*args, **kwargs)
        return identical_signature_wrapper(function, wrapped)
    return wrapper


def identical_signature_wrapper(original_function, wrapped_function):
    '''
    Return a function with identical signature as ``original_function``'s which
    will call the ``wrapped_function``.
    '''
    context = {'__wrapped__': wrapped_function}
    function_def = compile(
        'def {0}({1}):\n'
        '    return __wrapped__({2})'.format(
            # Keep the original function name
            original_function.__name__,
            # The function signature including defaults, i.e., 'timeout=1'
            inspect.formatargspec(
                *inspect.getargspec(original_function)
            )[1:-1],
            # The function signature without the defaults
            inspect.formatargspec(
                formatvalue=lambda val: '',
                *inspect.getargspec(original_function)
            )[1:-1]
        ),
        '<string>',
        'exec'
    )
    six.exec_(function_def, context)
    return wraps(original_function)(context[original_function.__name__])


def memoize(func):
    '''
    Memoize aka cache the return output of a function
    given a specific set of arguments
    '''
    cache = {}

    @wraps(func)
    def _memoize(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    return _memoize
