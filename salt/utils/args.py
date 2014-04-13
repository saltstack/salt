# -*- coding: utf-8 -*-
'''
Functions used for CLI argument handling
'''

# Import python libs
import re

# Import salt libs
from salt._compat import string_types, integer_types

#KWARG_REGEX = re.compile(r'^([^\d\W][\w.-]*)=(?!=)(.*)$', re.UNICODE)  # python 3
KWARG_REGEX = re.compile(r'^([^\d\W][\w.-]*)=(?!=)(.*)$')


def condition_input(args, kwargs):
    '''
    Return a single arg structure for the publisher to safely use
    '''
    if isinstance(kwargs, dict) and kwargs:
        kw_ = {'__kwarg__': True}
        for key, val in kwargs.iteritems():
            kw_[key] = val
        return list(args) + [kw_]
    return args


def parse_input(args, condition=True):
    '''
    Parse out the args and kwargs from a list of input values. Optionally,
    return the args and kwargs without passing them to condition_input().

    Don't pull args with key=val apart if it has a newline in it.
    '''
    _args = []
    _kwargs = {}
    for arg in args:
        if isinstance(arg, string_types) and not r'\n' in arg:
            arg_name, arg_value = parse_kwarg(arg)
            if arg_name:
                _kwargs[arg_name] = yamlify_arg(arg_value)
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
    if not isinstance(arg, string_types):
        return arg

    if arg.strip() == '':
        # Because YAML loads empty strings as None, we return the original string
        # >>> import yaml
        # >>> yaml.load('') is None
        # True
        # >>> yaml.load('      ') is None
        # True
        return arg

    try:
        # Explicit late import to avoid circular import. DO NOT MOVE THIS.
        import salt.utils.yamlloader as yamlloader
        original_arg = arg
        if '#' in arg:
            # Don't yamlify this argument or the '#' and everything after
            # it will be interpreted as a comment.
            return arg
        if arg == 'None':
            arg = None
        else:
            arg = yamlloader.load(arg, Loader=yamlloader.SaltYamlSafeLoader)

        if isinstance(arg, dict):
            # dicts must be wrapped in curly braces
            if (isinstance(original_arg, string_types) and
                    not original_arg.startswith('{')):
                return original_arg
            else:
                return arg

        elif arg is None \
                or isinstance(arg, (list, float, integer_types, string_types)):
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
