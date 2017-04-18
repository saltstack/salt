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
import salt.utils.args
from salt.exceptions import CommandNotFoundError, CommandExecutionError
from salt.version import SaltStackVersion, __saltstack_version__
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
    dependency_dict = defaultdict(lambda: defaultdict(dict))

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
            _, kind, mod_name = frame.f_globals['__name__'].rsplit('.', 2)
            fun_name = function.__name__
            for dep in self.dependencies:
                self.dependency_dict[kind][dep][(mod_name, fun_name)] = \
                        (frame, self.fallback_function)
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
        for dependency, dependent_dict in six.iteritems(cls.dependency_dict[kind]):
            for (mod_name, func_name), (frame, fallback_function) in six.iteritems(dependent_dict):
                # check if dependency is loaded
                if dependency is True:
                    log.trace(
                        'Dependency for {0}.{1} exists, not unloading'.format(
                            mod_name,
                            func_name
                        )
                    )
                    continue
                # check if you have the dependency
                if dependency in frame.f_globals \
                        or dependency in frame.f_locals:
                    log.trace(
                        'Dependency ({0}) already loaded inside {1}, '
                        'skipping'.format(
                            dependency,
                            mod_name
                        )
                    )
                    continue
                log.trace(
                    'Unloading {0}.{1} because dependency ({2}) is not '
                    'imported'.format(
                        mod_name,
                        func_name,
                        dependency
                    )
                )
                # if not, unload the function
                if frame:
                    try:
                        func_name = frame.f_globals['__func_alias__'][func_name]
                    except (AttributeError, KeyError):
                        pass

                    mod_key = '{0}.{1}'.format(mod_name, func_name)

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


depends = Depends


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
                *salt.utils.args.get_function_argspec(original_function)
            )[1:-1],
            # The function signature without the defaults
            inspect.formatargspec(
                formatvalue=lambda val: '',
                *salt.utils.args.get_function_argspec(original_function)
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


class _DeprecationDecorator(object):
    '''
    Base mix-in class for the deprecation decorator.
    Takes care of a common functionality, used in its derivatives.
    '''

    def __init__(self, globals, version):
        '''
        Constructor.

        :param globals: Module globals. Important for finding out replacement functions
        :param version: Expiration version
        :return:
        '''

        self._globals = globals
        self._exp_version_name = version
        self._exp_version = SaltStackVersion.from_name(self._exp_version_name)
        self._curr_version = __saltstack_version__.info
        self._options = self._globals['__opts__']
        self._raise_later = None
        self._function = None
        self._orig_f_name = None

    def _get_args(self, kwargs):
        '''
        Extract function-specific keywords from all of the kwargs.

        :param kwargs:
        :return:
        '''
        _args = list()
        _kwargs = dict()

        for arg_item in kwargs.get('__pub_arg', list()):
            if type(arg_item) == dict:
                _kwargs.update(arg_item.copy())
            else:
                _args.append(arg_item)
        return _args, _kwargs

    def _call_function(self, kwargs):
        '''
        Call target function that has been decorated.

        :return:
        '''
        if self._raise_later:
            raise self._raise_later  # pylint: disable=E0702

        if self._function:
            args, kwargs = self._get_args(kwargs)
            try:
                return self._function(*args, **kwargs)
            except TypeError as error:
                error = str(error).replace(self._function.__name__, self._orig_f_name)  # Hide hidden functions
                log.error('Function "{f_name}" was not properly called: {error}'.format(f_name=self._orig_f_name,
                                                                                        error=error))
                return self._function.__doc__
            except Exception as error:
                log.error('Unhandled exception occurred in '
                          'function "{f_name}: {error}'.format(f_name=self._function.__name__,
                                                               error=error))
                raise error
        else:
            raise CommandExecutionError("Function is deprecated, but the successor function was not found.")

    def __call__(self, function):
        '''
        Callable method of the decorator object when
        the decorated function is gets called.

        :param function:
        :return:
        '''
        self._function = function
        self._orig_f_name = self._function.__name__


class _IsDeprecated(_DeprecationDecorator):
    '''
    This decorator should be used only with the deprecated functions
    to mark them as deprecated and alter its behavior a corresponding way.
    The usage is only suitable if deprecation process is renaming
    the function from one to another. In case function name or even function
    signature stays the same, please use 'with_deprecated' decorator instead.

    It has the following functionality:

    1. Put a warning level message to the log, informing that
       the deprecated function has been in use.

    2. Raise an exception, if deprecated function is being called,
       but the lifetime of it already expired.

    3. Point to the successor of the deprecated function in the
       log messages as well during the blocking it, once expired.

    Usage of this decorator as follows. In this example no successor
    is mentioned, hence the function "foo()" will be logged with the
    warning each time is called and blocked completely, once EOF of
    it is reached:

        from salt.util.decorators import is_deprecated

        @is_deprecated(globals(), "Beryllium")
        def foo():
            pass

    In the following example a successor function is mentioned, hence
    every time the function "bar()" is called, message will suggest
    to use function "baz()" instead. Once EOF is reached of the function
    "bar()", an exception will ask to use function "baz()", in order
    to continue:

        from salt.util.decorators import is_deprecated

        @is_deprecated(globals(), "Beryllium", with_successor="baz")
        def bar():
            pass

        def baz():
            pass
    '''

    def __init__(self, globals, version, with_successor=None):
        '''
        Constructor of the decorator 'is_deprecated'.

        :param globals: Module globals
        :param version: Version to be deprecated
        :param with_successor: Successor function (optional)
        :return:
        '''
        _DeprecationDecorator.__init__(self, globals, version)
        self._successor = with_successor

    def __call__(self, function):
        '''
        Callable method of the decorator object when
        the decorated function is gets called.

        :param function:
        :return:
        '''
        _DeprecationDecorator.__call__(self, function)

        def _decorate(*args, **kwargs):
            '''
            Decorator function.

            :param args:
            :param kwargs:
            :return:
            '''
            if self._curr_version < self._exp_version:
                msg = ['The function "{f_name}" is deprecated and will '
                       'expire in version "{version_name}".'.format(f_name=self._function.__name__,
                                                                    version_name=self._exp_version_name)]
                if self._successor:
                    msg.append('Use successor "{successor}" instead.'.format(successor=self._successor))
                log.warning(' '.join(msg))
            else:
                msg = ['The lifetime of the function "{f_name}" expired.'.format(f_name=self._function.__name__)]
                if self._successor:
                    msg.append('Please use its successor "{successor}" instead.'.format(successor=self._successor))
                log.warning(' '.join(msg))
                raise CommandExecutionError(' '.join(msg))
            return self._call_function(kwargs)
        return _decorate


is_deprecated = _IsDeprecated


class _WithDeprecated(_DeprecationDecorator):
    '''
    This decorator should be used with the successor functions
    to mark them as a new and alter its behavior in a corresponding way.
    It is used alone if a function content or function signature
    needs to be replaced, leaving the name of the function same.
    In case function needs to be renamed or just dropped, it has
    to be used in pair with 'is_deprecated' decorator.

    It has the following functionality:

    1. Put a warning level message to the log, in case a component
       is using its deprecated version.

    2. Switch between old and new function in case an older version
       is configured for the desired use.

    3. Raise an exception, if deprecated version reached EOL and
       point out for the new version.

    Usage of this decorator as follows. If 'with_name' is not specified,
    then the name of the deprecated function is assumed with the "_" prefix.
    In this case, in order to deprecate a function, it is required:

    - Add a prefix "_" to an existing function. E.g.: "foo()" to "_foo()".

    - Implement a new function with exactly the same name, just without
      the prefix "_".

    Example:

        from salt.util.decorators import with_deprecated

        @with_deprecated(globals(), "Beryllium")
        def foo():
            "This is a new function"

        def _foo():
            "This is a deprecated function"


    In case there is a need to deprecate a function and rename it,
    the decorator should be used with the 'with_name' parameter. This
    parameter is pointing to the existing deprecated function. In this
    case deprecation process as follows:

    - Leave a deprecated function without changes, as is.

    - Implement a new function and decorate it with this decorator.

    - Set a parameter 'with_name' to the deprecated function.

    - If a new function has a different name than a deprecated,
      decorate a deprecated function with the  'is_deprecated' decorator
      in order to let the function have a deprecated behavior.

    Example:

        from salt.util.decorators import with_deprecated

        @with_deprecated(globals(), "Beryllium", with_name="an_old_function")
        def a_new_function():
            "This is a new function"

        @is_deprecated(globals(), "Beryllium", with_successor="a_new_function")
        def an_old_function():
            "This is a deprecated function"

    '''
    MODULE_NAME = '__virtualname__'
    CFG_KEY = 'use_deprecated'

    def __init__(self, globals, version, with_name=None):
        '''
        Constructor of the decorator 'with_deprecated'

        :param globals:
        :param version:
        :param with_name:
        :return:
        '''
        _DeprecationDecorator.__init__(self, globals, version)
        self._with_name = with_name

    def _set_function(self, function):
        '''
        Based on the configuration, set to execute an old or a new function.
        :return:
        '''
        full_name = "{m_name}.{f_name}".format(m_name=self._globals.get(self.MODULE_NAME, ''),
                                               f_name=function.__name__)
        if full_name.startswith("."):
            self._raise_later = CommandExecutionError('Module not found for function "{f_name}"'.format(
                f_name=function.__name__))

        if full_name in self._options.get(self.CFG_KEY, list()):
            self._function = self._globals.get(self._with_name or "_{0}".format(function.__name__))

    def _is_used_deprecated(self):
        '''
        Returns True, if a component configuration explicitly is
        asking to use an old version of the deprecated function.

        :return:
        '''
        return "{m_name}.{f_name}".format(m_name=self._globals.get(self.MODULE_NAME, ''),
                                          f_name=self._orig_f_name) in self._options.get(self.CFG_KEY, list())

    def __call__(self, function):
        '''
        Callable method of the decorator object when
        the decorated function is gets called.

        :param function:
        :return:
        '''
        _DeprecationDecorator.__call__(self, function)

        def _decorate(*args, **kwargs):
            '''
            Decorator function.

            :param args:
            :param kwargs:
            :return:
            '''
            self._set_function(function)
            if self._is_used_deprecated():
                if self._curr_version < self._exp_version:
                    msg = list()
                    if self._with_name:
                        msg.append('The function "{f_name}" is deprecated and will '
                                   'expire in version "{version_name}".'.format(
                                       f_name=self._with_name.startswith("_") and self._orig_f_name or self._with_name,
                                       version_name=self._exp_version_name))
                    else:
                        msg.append('The function is using its deprecated version and will '
                                   'expire in version "{version_name}".'.format(version_name=self._exp_version_name))
                    msg.append('Use its successor "{successor}" instead.'.format(successor=self._orig_f_name))
                    log.warning(' '.join(msg))
                else:
                    msg_patt = 'The lifetime of the function "{f_name}" expired.'
                    if '_' + self._orig_f_name == self._function.__name__:
                        msg = [msg_patt.format(f_name=self._orig_f_name),
                               'Please turn off its deprecated version in the configuration']
                    else:
                        msg = ['Although function "{f_name}" is called, an alias "{f_alias}" '
                               'is configured as its deprecated version.'.format(
                                   f_name=self._orig_f_name, f_alias=self._with_name or self._orig_f_name),
                               msg_patt.format(f_name=self._with_name or self._orig_f_name),
                               'Please use its successor "{successor}" instead.'.format(successor=self._orig_f_name)]
                    log.error(' '.join(msg))
                    raise CommandExecutionError(' '.join(msg))
            return self._call_function(kwargs)

        _decorate.__doc__ = self._function.__doc__
        return _decorate


with_deprecated = _WithDeprecated
