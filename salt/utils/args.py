# -*- coding: utf-8 -*-
'''
Functions used for CLI argument handling
'''

# Import python libs
import re
import yaml

# Import salt libs
from salt._compat import string_types, integer_types

#KWARG_REGEX = re.compile(r'^([^\d\W][\w-]*)=(?!=)(.*)$', re.UNICODE)  # python 3
KWARG_REGEX = re.compile(r'^([^\d\W][\w-]*)=(?!=)(.*)$')


def parse_cli(args):
    '''
    Parse out the args and kwargs from a list of CLI args
    '''
    _args = []
    _kwargs = {}
    for arg in args:
        if isinstance(arg, string_types):
            arg_name, arg_value = parse_kwarg(arg)
            if arg_name:
                _kwargs[arg_name] = yamlify_arg(arg_value)
            else:
                _args.append(yamlify_arg(arg))
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
    yaml.safe_load the arg unless it has a newline in it.
    '''
    if not isinstance(arg, string_types):
        return arg
    try:
        original_arg = str(arg)
        if isinstance(arg, string_types):
            if '#' in arg:
                # Don't yamlify this argument or the '#' and everything after
                # it will be interpreted as a comment.
                return arg
            if '\n' not in arg:
                arg = yaml.safe_load(arg)
        print('arg = {0}'.format(arg))
        if isinstance(arg, dict):
            # dicts must be wrapped in curly braces
            if (isinstance(original_arg, string_types) and
                    not original_arg.startswith('{')):
                return original_arg
            else:
                return arg
        elif isinstance(arg, (list, float, integer_types, string_types)):
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
