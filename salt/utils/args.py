# -*- coding: utf-8 -*-
'''
Functions used for CLI argument handling
'''
from __future__ import absolute_import

# Import python libs
import re
import inspect

# Import salt libs
import salt.utils.jid

# Import 3rd-party libs
import salt.ext.six as six


if six.PY3:
    KWARG_REGEX = re.compile(r'^([^\d\W][\w.-]*)=(?!=)(.*)$', re.UNICODE)
else:
    KWARG_REGEX = re.compile(r'^([^\d\W][\w.-]*)=(?!=)(.*)$')


def condition_input(args, kwargs):
    '''
    Return a single arg structure for the publisher to safely use
    '''
    ret = []
    for arg in args:
        if (six.PY3 and isinstance(arg, six.integer_types) and salt.utils.jid.is_jid(str(arg))) or \
        (six.PY2 and isinstance(arg, long)):  # pylint: disable=incompatible-py3-code
            ret.append(str(arg))
        else:
            ret.append(arg)
    if isinstance(kwargs, dict) and kwargs:
        kw_ = {'__kwarg__': True}
        for key, val in six.iteritems(kwargs):
            kw_[key] = val
        return ret + [kw_]
    return ret


def parse_input(args, condition=True, no_parse=None):
    '''
    Parse out the args and kwargs from a list of input values. Optionally,
    return the args and kwargs without passing them to condition_input().

    Don't pull args with key=val apart if it has a newline in it.
    '''
    if no_parse is None:
        no_parse = ()
    _args = []
    _kwargs = {}
    for arg in args:
        if isinstance(arg, six.string_types):
            arg_name, arg_value = parse_kwarg(arg)
            if arg_name:
                _kwargs[arg_name] = yamlify_arg(arg_value) \
                    if arg_name not in no_parse \
                    else arg_value
            else:
                _args.append(yamlify_arg(arg))
        elif isinstance(arg, dict):
            # Yes, we're popping this key off and adding it back if
            # condition_input is called below, but this is the only way to
            # gracefully handle both CLI and API input.
            if arg.pop('__kwarg__', False) is True:
                _kwargs.update(arg)
            else:
                _args.append(arg)
        else:
            _args.append(arg)
    if condition:
        return condition_input(_args, _kwargs)
    return _args, _kwargs


def parse_kwarg(string_):
    '''
    Parses the string and looks for the following kwarg format:

    "{argument name}={argument value}"

    For example: "my_message=Hello world"

    Returns the kwarg name and value, or (None, None) if the regex was not
    matched.
    '''
    try:
        return KWARG_REGEX.match(string_).groups()
    except AttributeError:
        return None, None


def yamlify_arg(arg):
    '''
    yaml.safe_load the arg
    '''
    if not isinstance(arg, six.string_types):
        return arg

    if arg.strip() == '':
        # Because YAML loads empty strings as None, we return the original string
        # >>> import yaml
        # >>> yaml.load('') is None
        # True
        # >>> yaml.load('      ') is None
        # True
        return arg

    elif '_' in arg and all([x in '0123456789_' for x in arg.strip()]):
        return arg

    try:
        # Explicit late import to avoid circular import. DO NOT MOVE THIS.
        import salt.utils.yamlloader as yamlloader
        original_arg = arg
        if '#' in arg:
            # Only yamlify if it parses into a non-string type, to prevent
            # loss of content due to # as comment character
            parsed_arg = yamlloader.load(arg, Loader=yamlloader.SaltYamlSafeLoader)
            if isinstance(parsed_arg, six.string_types) or parsed_arg is None:
                return arg
            return parsed_arg
        if arg == 'None':
            arg = None
        else:
            arg = yamlloader.load(arg, Loader=yamlloader.SaltYamlSafeLoader)

        if isinstance(arg, dict):
            # dicts must be wrapped in curly braces
            if (isinstance(original_arg, six.string_types) and
                    not original_arg.startswith('{')):
                return original_arg
            else:
                return arg

        elif arg is None \
                or isinstance(arg, (list, float, six.integer_types, six.string_types)):
            # yaml.safe_load will load '|' as '', don't let it do that.
            if arg == '' and original_arg in ('|',):
                return original_arg
            # yaml.safe_load will treat '#' as a comment, so a value of '#'
            # will become None. Keep this value from being stomped as well.
            elif arg is None and original_arg.strip().startswith('#'):
                return original_arg
            else:
                return arg
        else:
            # we don't support this type
            return original_arg
    except Exception:
        # In case anything goes wrong...
        return original_arg


if six.PY3:
    from collections import namedtuple  # pylint: disable=wrong-import-position,wrong-import-order

    _ArgSpec = namedtuple('ArgSpec', 'args varargs keywords defaults')

    def _getargspec(func):
        '''
        Python 3 wrapper for inspect.getargsspec

        inspect.getargsspec is deprecated and will be removed in Python 3.6.
        '''
        args, varargs, varkw, defaults, kwonlyargs, _, ann = \
            inspect.getfullargspec(func)  # pylint: disable=no-member
        if kwonlyargs or ann:
            raise ValueError('Function has keyword-only arguments or annotations'
                             ', use getfullargspec() API which can support them')
        return _ArgSpec(args, varargs, varkw, defaults)


def get_function_argspec(func, is_class_method=None):
    '''
    A small wrapper around getargspec that also supports callable classes
    :param is_class_method: Pass True if you are sure that the function being passed
                            is a class method. The reason for this is that on Python 3
                            ``inspect.ismethod`` only returns ``True`` for bound methods,
                            while on Python 2, it returns ``True`` for bound and unbound
                            methods. So, on Python 3, in case of a class method, you'd
                            need the class to which the function belongs to be instantiated
                            and this is not always wanted.
    '''
    if not callable(func):
        raise TypeError('{0} is not a callable'.format(func))

    if six.PY2:
        if is_class_method is True:
            aspec = inspect.getargspec(func)
            del aspec.args[0]  # self
        elif inspect.isfunction(func):
            aspec = inspect.getargspec(func)
        elif inspect.ismethod(func):
            aspec = inspect.getargspec(func)
            del aspec.args[0]  # self
        elif isinstance(func, object):
            aspec = inspect.getargspec(func.__call__)
            del aspec.args[0]  # self
        else:
            raise TypeError(
                'Cannot inspect argument list for \'{0}\''.format(func)
            )
    else:
        if is_class_method is True:
            aspec = _getargspec(func)
            del aspec.args[0]  # self
        elif inspect.isfunction(func):
            aspec = _getargspec(func)  # pylint: disable=redefined-variable-type
        elif inspect.ismethod(func):
            aspec = _getargspec(func)
            del aspec.args[0]  # self
        elif isinstance(func, object):
            aspec = _getargspec(func.__call__)
            del aspec.args[0]  # self
        else:
            raise TypeError(
                'Cannot inspect argument list for \'{0}\''.format(func)
            )
    return aspec
