# -*- coding: utf-8 -*-
'''
Some of the utils used by salt

PLEASE DO NOT ADD ANY NEW FUNCTIONS TO THIS FILE.

New functions should be organized in other files under salt/utils/. Please
consult the dev team if you are unsure where a new function should go.
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.defaults import DEFAULT_TARGET_DELIM

# Import 3rd-party libs
from salt.ext import six


#
# DEPRECATED FUNCTIONS
#
# These are not referenced anywhere in the codebase and are slated for removal.
#
def option(value, default='', opts=None, pillar=None):
    '''
    Pass in a generic option and receive the value that will be assigned
    '''
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.option\' detected. This function has been '
        'deprecated and will be removed in Salt Neon.'
    )

    if opts is None:
        opts = {}
    if pillar is None:
        pillar = {}
    sources = (
        (opts, value),
        (pillar, 'master:{0}'.format(value)),
        (pillar, value),
    )
    for source, val in sources:
        out = salt.utils.data.traverse_dict_and_list(source, val, default)
        if out is not default:
            return out
    return default


def required_module_list(docstring=None):
    '''
    Return a list of python modules required by a salt module that aren't
    in stdlib and don't exist on the current pythonpath.
    '''
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.doc
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.required_module_list\' detected. This function '
        'has been deprecated and will be removed in Salt Neon.'
    )

    if six.PY3:
        import importlib.util  # pylint: disable=no-name-in-module,import-error
    else:
        import imp

    if not docstring:
        return []
    ret = []
    modules = salt.utils.doc.parse_docstring(docstring).get('deps', [])
    for mod in modules:
        try:
            if six.PY3:
                if importlib.util.find_spec(mod) is None:  # pylint: disable=no-member
                    ret.append(mod)
            else:
                imp.find_module(mod)
        except ImportError:
            ret.append(mod)
    return ret


def required_modules_error(name, docstring):
    '''
    Pretty print error messages in critical salt modules which are
    missing deps not always in stdlib such as win32api on windows.
    '''
    # Late import to avoid circular import.
    import salt.utils.versions
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.required_modules_error\' detected. This function '
        'has been deprecated and will be removed in Salt Neon.'
    )
    modules = required_module_list(docstring)
    if not modules:
        return ''
    import os
    filename = os.path.basename(name).split('.')[0]
    msg = '\'{0}\' requires these python modules: {1}'
    return msg.format(filename, ', '.join(modules))


#
# MOVED FUNCTIONS
#
# These functions have been moved to new locations. The functions below are
# convenience functions which will allow the old function locations to continue
# to work. The convenience functions will be removed in the Neon release.
#
def get_accumulator_dir(cachedir):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.state
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_accumulator_dir\' detected. This function '
        'has been moved to \'salt.state.get_accumulator_dir\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.state.get_accumulator_dir(cachedir)


def fnmatch_multiple(candidates, pattern):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.itertools
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.fnmatch_multiple\' detected. This function has been '
        'moved to \'salt.utils.itertools.fnmatch_multiple\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.itertools.fnmatch_multiple(candidates, pattern)


def appendproctitle(name):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.process
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.appendproctitle\' detected. This function has been '
        'moved to \'salt.utils.process.appendproctitle\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.process.appendproctitle(name)


def daemonize(redirect_out=True):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.process
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.daemonize\' detected. This function has been '
        'moved to \'salt.utils.process.daemonize\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.process.daemonize(redirect_out)


def daemonize_if(opts):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.process
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.daemonize_if\' detected. This function has been '
        'moved to \'salt.utils.process.daemonize_if\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.process.daemonize_if(opts)


def reinit_crypto():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.crypt
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.reinit_crypto\' detected. This function has been '
        'moved to \'salt.utils.crypt.reinit_crypto\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.crypt.reinit_crypto()


def pem_finger(path=None, key=None, sum_type='sha256'):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.crypt
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.pem_finger\' detected. This function has been '
        'moved to \'salt.utils.crypt.pem_finger\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.crypt.pem_finger(path, key, sum_type)


def to_bytes(s, encoding=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.to_bytes\' detected. This function has been '
        'moved to \'salt.utils.stringutils.to_bytes\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.to_bytes(s, encoding)


def to_str(s, encoding=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.to_str\' detected. This function has been moved '
        'to \'salt.utils.stringutils.to_str\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.to_str(s, encoding)


def to_unicode(s, encoding=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.to_unicode\' detected. This function has been '
        'moved to \'salt.utils.stringutils.to_unicode\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.to_unicode(s, encoding)


def str_to_num(text):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.str_to_num\' detected. This function has been '
        'moved to \'salt.utils.stringutils.to_num\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.to_num(text)


def is_quoted(value):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_quoted\' detected. This function has been '
        'moved to \'salt.utils.stringutils.is_quoted\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.is_quoted(value)


def dequote(value):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.dequote\' detected. This function has been moved '
        'to \'salt.utils.stringutils.dequote\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.dequote(value)


def is_hex(value):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_hex\' detected. This function has been moved '
        'to \'salt.utils.stringutils.is_hex\' as of Salt Oxygen. This warning '
        'will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.is_hex(value)


def is_bin_str(data):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_bin_str\' detected. This function has been '
        'moved to \'salt.utils.stringutils.is_binary\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.is_binary(data)


def rand_string(size=32):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.rand_string\' detected. This function has been '
        'moved to \'salt.utils.stringutils.random\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.random(size)


def contains_whitespace(text):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.contains_whitespace\' detected. This function '
        'has been moved to \'salt.utils.stringutils.contains_whitespace\' as '
        'of Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.contains_whitespace(text)


def build_whitespace_split_regex(text):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.build_whitespace_split_regex\' detected. This '
        'function has been moved to '
        '\'salt.utils.stringutils.build_whitespace_split_regex\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.build_whitespace_split_regex(text)


def expr_match(line, expr):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.expr_match\' detected. This function '
        'has been moved to \'salt.utils.stringutils.expr_match\' as '
        'of Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.expr_match(line, expr)


def check_whitelist_blacklist(value, whitelist=None, blacklist=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.check_whitelist_blacklist\' detected. This '
        'function has been moved to '
        '\'salt.utils.stringutils.check_whitelist_blacklist\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.check_whitelist_blacklist(
        value, whitelist, blacklist)


def check_include_exclude(path_str, include_pat=None, exclude_pat=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.check_include_exclude\' detected. This '
        'function has been moved to '
        '\'salt.utils.stringutils.check_include_exclude\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.check_include_exclude(
        path_str, include_pat, exclude_pat)


def print_cli(msg, retries=10, step=0.01):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.stringutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.print_cli\' detected. This function '
        'has been moved to \'salt.utils.stringutils.print_cli\' as '
        'of Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.stringutils.print_cli(msg, retries, step)


def clean_kwargs(**kwargs):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.args
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.clean_kwargs\' detected. This function has been '
        'moved to \'salt.utils.args.clean_kwargs\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.args.clean_kwargs(**kwargs)


def invalid_kwargs(invalid_kwargs, raise_exc=True):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.args
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.invalid_kwargs\' detected. This function has '
        'been moved to \'salt.utils.args.invalid_kwargs\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.args.invalid_kwargs(invalid_kwargs, raise_exc)


def shlex_split(s, **kwargs):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.args
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.shlex_split\' detected. This function has been '
        'moved to \'salt.utils.args.shlex_split\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.args.shlex_split(s, **kwargs)


def arg_lookup(fun, aspec=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.args
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.arg_lookup\' detected. This function has been '
        'moved to \'salt.utils.args.arg_lookup\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.args.arg_lookup(fun, aspec=aspec)


def argspec_report(functions, module=''):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.args
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.argspec_report\' detected. This function has been '
        'moved to \'salt.utils.args.argspec_report\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.args.argspec_report(functions, module=module)


def split_input(val):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.args
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.split_input\' detected. This function has been '
        'moved to \'salt.utils.args.split_input\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.args.split_input(val)


def test_mode(**kwargs):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.args
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.test_mode\' detected. This function has been '
        'moved to \'salt.utils.args.test_mode\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.args.test_mode(**kwargs)


def format_call(fun, data, initial_ret=None, expected_extra_kws=(),
                is_class_method=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.args
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.format_call\' detected. This function has been '
        'moved to \'salt.utils.args.format_call\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.args.format_call(
        fun, data, initial_ret, expected_extra_kws, is_class_method)


def which(exe=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.path
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.which\' detected. This function has been moved to '
        '\'salt.utils.path.which\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.path.which(exe)


def which_bin(exes):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.path
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.which_bin\' detected. This function has been '
        'moved to \'salt.utils.path.which_bin\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.path.which_bin(exes)


def path_join(*parts, **kwargs):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.path
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.path_join\' detected. This function has been '
        'moved to \'salt.utils.path.join\' as of Salt Oxygen. This warning '
        'will be removed in Salt Neon.'
    )
    return salt.utils.path.join(*parts, **kwargs)


def check_or_die(command):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.path
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.check_or_die\' detected. This function has been '
        'moved to \'salt.utils.path.check_or_die\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.path.check_or_die(command)


def sanitize_win_path_string(winpath):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.path
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.sanitize_win_path_string\' detected. This '
        'function has been moved to \'salt.utils.path.sanitize_win_path\' as '
        'of Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.path.sanitize_win_path(winpath)


def rand_str(size=9999999999, hash_type=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.hashutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.rand_str\' detected. This function has been '
        'moved to \'salt.utils.hashutils.random_hash\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.hashutils.random_hash(size, hash_type)


def get_hash(path, form='sha256', chunk_size=65536):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.hashutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_hash\' detected. This function has been '
        'moved to \'salt.utils.hashutils.get_hash\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.hashutils.get_hash(path, form, chunk_size)


def is_windows():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_windows\' detected. This function has been '
        'moved to \'salt.utils.platform.is_windows\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_windows()


def is_proxy():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_proxy\' detected. This function has been '
        'moved to \'salt.utils.platform.is_proxy\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_proxy()


def is_linux():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_linux\' detected. This function has been '
        'moved to \'salt.utils.platform.is_linux\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_linux()


def is_darwin():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_darwin\' detected. This function has been '
        'moved to \'salt.utils.platform.is_darwin\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_darwin()


def is_sunos():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_sunos\' detected. This function has been '
        'moved to \'salt.utils.platform.is_sunos\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_sunos()


def is_smartos():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_smartos\' detected. This function has been '
        'moved to \'salt.utils.platform.is_smartos\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_smartos()


def is_smartos_globalzone():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_smartos_globalzone\' detected. This function '
        'has been moved to \'salt.utils.platform.is_smartos_globalzone\' as '
        'of Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_smartos_globalzone()


def is_smartos_zone():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_smartos_zone\' detected. This function has '
        'been moved to \'salt.utils.platform.is_smartos_zone\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_smartos_zone()


def is_freebsd():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_freebsd\' detected. This function has been '
        'moved to \'salt.utils.platform.is_freebsd\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_freebsd()


def is_netbsd():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_netbsd\' detected. This function has been '
        'moved to \'salt.utils.platform.is_netbsd\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_netbsd()


def is_openbsd():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_openbsd\' detected. This function has been '
        'moved to \'salt.utils.platform.is_openbsd\' as of Salt Oxygen. This '
        'warning will be removed in Salt Neon.'
    )
    return salt.utils.platform.is_openbsd()


def is_aix():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.platform
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_aix\' detected. This function has been moved to '
        '\'salt.utils.platform.is_aix\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.platform.is_aix()


def safe_rm(tgt):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.safe_rm\' detected. This function has been moved to '
        '\'salt.utils.files.safe_rm\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.files.safe_rm(tgt)


def is_empty(filename):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_empty\' detected. This function has been moved to '
        '\'salt.utils.files.is_empty\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.files.is_empty(filename)


def fopen(*args, **kwargs):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.fopen\' detected. This function has been moved to '
        '\'salt.utils.files.fopen\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.files.fopen(*args, **kwargs)  # pylint: disable=W8470


def flopen(*args, **kwargs):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.flopen\' detected. This function has been moved to '
        '\'salt.utils.files.flopen\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.files.flopen(*args, **kwargs)


def fpopen(*args, **kwargs):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.fpopen\' detected. This function has been moved to '
        '\'salt.utils.files.fpopen\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.files.fpopen(*args, **kwargs)


def rm_rf(path):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.rm_rf\' detected. This function has been moved to '
        '\'salt.utils.files.rm_rf\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.files.rm_rf(path)


def mkstemp(*args, **kwargs):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.mkstemp\' detected. This function has been moved to '
        '\'salt.utils.files.mkstemp\' as of Salt Oxygen. This warning will be '
        'removed in Salt Neon.'
    )
    return salt.utils.files.mkstemp(*args, **kwargs)


def istextfile(fp_, blocksize=512):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.istextfile\' detected. This function has been moved '
        'to \'salt.utils.files.is_text_file\' as of Salt Oxygen. This warning will '
        'be removed in Salt Neon.'
    )
    return salt.utils.files.is_text_file(fp_, blocksize=blocksize)


def is_bin_file(path):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_bin_file\' detected. This function has been moved '
        'to \'salt.utils.files.is_binary\' as of Salt Oxygen. This warning will '
        'be removed in Salt Neon.'
    )
    return salt.utils.files.is_binary(path)


def list_files(directory):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.list_files\' detected. This function has been moved '
        'to \'salt.utils.files.list_files\' as of Salt Oxygen. This warning will '
        'be removed in Salt Neon.'
    )
    return salt.utils.files.list_files(directory)


def safe_walk(top, topdown=True, onerror=None, followlinks=True, _seen=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.safe_walk\' detected. This function has been moved '
        'to \'salt.utils.files.safe_walk\' as of Salt Oxygen. This warning will '
        'be removed in Salt Neon.'
    )
    return salt.utils.files.safe_walk(top, topdown, onerror, followlinks, _seen)


def st_mode_to_octal(mode):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.st_mode_to_octal\' detected. This function has '
        'been moved to \'salt.utils.files.st_mode_to_octal\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.files.st_mode_to_octal(mode)


def normalize_mode(mode):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.normalize_mode\' detected. This function has '
        'been moved to \'salt.utils.files.normalize_mode\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.files.normalize_mode(mode)


def human_size_to_bytes(human_size):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.human_size_to_bytes\' detected. This function has '
        'been moved to \'salt.utils.files.human_size_to_bytes\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.files.human_size_to_bytes(human_size)


def backup_minion(path, bkroot):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.files

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.backup_minion\' detected. This function has '
        'been moved to \'salt.utils.files.backup_minion\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.files.backup_minion(path, bkroot)


def str_version_to_evr(verstring):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.pkg.rpm
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.str_version_to_evr\' detected. This function has '
        'been moved to \'salt.utils.pkg.rpm.version_to_evr\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.pkg.rpm.version_to_evr(verstring)


def parse_docstring(docstring):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.doc
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.parse_docstring\' detected. This function has '
        'been moved to \'salt.utils.doc.parse_docstring\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.doc.parse_docstring(docstring)


def compare_versions(ver1='', oper='==', ver2='', cmp_func=None, ignore_epoch=False):
    # Late import to avoid circular import.
    import salt.utils.versions
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.compare_versions\' detected. This function has '
        'been moved to \'salt.utils.versions.compare\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.versions.compare(ver1=ver1,
                                       oper=oper,
                                       ver2=ver2,
                                       cmp_func=cmp_func,
                                       ignore_epoch=ignore_epoch)


def version_cmp(pkg1, pkg2, ignore_epoch=False):
    # Late import to avoid circular import.
    import salt.utils.versions
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.version_cmp\' detected. This function has '
        'been moved to \'salt.utils.versions.version_cmp\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.versions.version_cmp(pkg1,
                                           pkg2,
                                           ignore_epoch=ignore_epoch)


def warn_until(version,
               message,
               category=DeprecationWarning,
               stacklevel=None,
               _version_info_=None,
               _dont_call_warnings=False):
    # Late import to avoid circular import.
    import salt.utils.versions
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.warn_until\' detected. This function has '
        'been moved to \'salt.utils.versions.warn_until\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.versions.warn_until(version,
                                          message,
                                          category=category,
                                          stacklevel=stacklevel,
                                          _version_info_=_version_info_,
                                          _dont_call_warnings=_dont_call_warnings)


def kwargs_warn_until(kwargs,
                      version,
                      category=DeprecationWarning,
                      stacklevel=None,
                      _version_info_=None,
                      _dont_call_warnings=False):
    # Late import to avoid circular import.
    import salt.utils.versions
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.kwargs_warn_until\' detected. This function has '
        'been moved to \'salt.utils.versions.kwargs_warn_until\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.versions.kwargs_warn_until(
        kwargs,
        version,
        category=category,
        stacklevel=stacklevel,
        _version_info_=_version_info_,
        _dont_call_warnings=_dont_call_warnings)


def get_color_theme(theme):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.color

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_color_theme\' detected. This function has '
        'been moved to \'salt.utils.color.get_color_theme\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.color.get_color_theme(theme)


def get_colors(use=True, theme=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.color

    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_colors\' detected. This function has '
        'been moved to \'salt.utils.color.get_colors\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.color.get_colors(use=use, theme=theme)


def gen_state_tag(low):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.state
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.gen_state_tag\' detected. This function has been '
        'moved to \'salt.utils.state.gen_tag\' as of Salt Oxygen. This warning '
        'will be removed in Salt Neon.'
    )
    return salt.utils.state.gen_tag(low)


def search_onfail_requisites(sid, highstate):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.state
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.search_onfail_requisites\' detected. This function '
        'has been moved to \'salt.utils.state.search_onfail_requisites\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.state.search_onfail_requisites(sid, highstate)


def check_onfail_requisites(state_id, state_result, running, highstate):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.state
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.check_onfail_requisites\' detected. This function '
        'has been moved to \'salt.utils.state.check_onfail_requisites\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.state.check_onfail_requisites(
        state_id, state_result, running, highstate
    )


def check_state_result(running, recurse=False, highstate=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.state
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.check_state_result\' detected. This function '
        'has been moved to \'salt.utils.state.check_result\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.state.check_result(
        running, recurse=recurse, highstate=highstate
    )


def get_user():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_user\' detected. This function '
        'has been moved to \'salt.utils.user.get_user\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.get_user()


def get_uid(user=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_uid\' detected. This function '
        'has been moved to \'salt.utils.user.get_uid\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.get_uid(user)


def get_specific_user():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_specific_user\' detected. This function '
        'has been moved to \'salt.utils.user.get_specific_user\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.get_specific_user()


def chugid(runas):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.chugid\' detected. This function '
        'has been moved to \'salt.utils.user.chugid\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.chugid(runas)


def chugid_and_umask(runas, umask):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.chugid_and_umask\' detected. This function '
        'has been moved to \'salt.utils.user.chugid_and_umask\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.chugid_and_umask(runas, umask)


def get_default_group(user):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_default_group\' detected. This function '
        'has been moved to \'salt.utils.user.get_default_group\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.get_default_group(user)


def get_group_list(user, include_default=True):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_group_list\' detected. This function '
        'has been moved to \'salt.utils.user.get_group_list\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.get_group_list(user, include_default)


def get_group_dict(user=None, include_default=True):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_group_dict\' detected. This function '
        'has been moved to \'salt.utils.user.get_group_dict\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.get_group_dict(user, include_default)


def get_gid_list(user, include_default=True):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_gid_list\' detected. This function '
        'has been moved to \'salt.utils.user.get_gid_list\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.get_gid_list(user, include_default)


def get_gid(group=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.user
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_gid\' detected. This function '
        'has been moved to \'salt.utils.user.get_gid\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.user.get_gid(group)


def enable_ctrl_logoff_handler():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.win_functions
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.enable_ctrl_logoff_handler\' detected. This '
        'function has been moved to '
        '\'salt.utils.win_functions.enable_ctrl_logoff_handler\' as of Salt '
        'Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.win_functions.enable_ctrl_logoff_handler()


def traverse_dict(data, key, default=None, delimiter=DEFAULT_TARGET_DELIM):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.traverse_dict\' detected. This function '
        'has been moved to \'salt.utils.data.traverse_dict\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.traverse_dict(data, key, default, delimiter)


def traverse_dict_and_list(data, key, default=None, delimiter=DEFAULT_TARGET_DELIM):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.traverse_dict_and_list\' detected. This function '
        'has been moved to \'salt.utils.data.traverse_dict_and_list\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.traverse_dict_and_list(data, key, default, delimiter)


def filter_by(lookup_dict,
              lookup,
              traverse,
              merge=None,
              default='default',
              base=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.filter_by\' detected. This function '
        'has been moved to \'salt.utils.data.filter_by\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.filter_by(
        lookup_dict, lookup, traverse, merge, default, base)


def subdict_match(data,
                  expr,
                  delimiter=DEFAULT_TARGET_DELIM,
                  regex_match=False,
                  exact_match=False):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.subdict_match\' detected. This function '
        'has been moved to \'salt.utils.data.subdict_match\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.subdict_match(
        data, expr, delimiter, regex_match, exact_match)


def substr_in_list(string_to_search_for, list_to_search):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.substr_in_list\' detected. This function '
        'has been moved to \'salt.utils.data.substr_in_list\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.substr_in_list(string_to_search_for, list_to_search)


def is_dictlist(data):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_dictlist\' detected. This function '
        'has been moved to \'salt.utils.data.is_dictlist\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.is_dictlist(data)


def repack_dictlist(data,
                    strict=False,
                    recurse=False,
                    key_cb=None,
                    val_cb=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_dictlist\' detected. This function '
        'has been moved to \'salt.utils.data.is_dictlist\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.repack_dictlist(data, strict, recurse, key_cb, val_cb)


def compare_dicts(old=None, new=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.compare_dicts\' detected. This function '
        'has been moved to \'salt.utils.data.compare_dicts\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.compare_dicts(old, new)


def compare_lists(old=None, new=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.compare_lists\' detected. This function '
        'has been moved to \'salt.utils.data.compare_lists\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.compare_lists(old, new)


def decode_dict(data):

    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.decode_dict\' detected. This function '
        'has been moved to \'salt.utils.data.decode_dict\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.decode_dict(data)


def decode_list(data):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.decode_list\' detected. This function '
        'has been moved to \'salt.utils.data.decode_list\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.decode_list(data)


def exactly_n(l, n=1):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.exactly_n\' detected. This function '
        'has been moved to \'salt.utils.data.exactly_n\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.exactly_n(l, n)


def exactly_one(l):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.exactly_one\' detected. This function '
        'has been moved to \'salt.utils.data.exactly_one\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.exactly_one(l)


def is_list(value):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_list\' detected. This function '
        'has been moved to \'salt.utils.data.is_list\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.is_list(value)


def is_iter(y, ignore=six.string_types):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_iter\' detected. This function '
        'has been moved to \'salt.utils.data.is_iter\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.is_iter(y, ignore)


def isorted(to_sort):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.isorted\' detected. This function '
        'has been moved to \'salt.utils.data.sorted_ignorecase\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.sorted_ignorecase(to_sort)


def is_true(value=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.is_true\' detected. This function '
        'has been moved to \'salt.utils.data.is_true\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.is_true(value)


def mysql_to_dict(data, key):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.mysql_to_dict\' detected. This function '
        'has been moved to \'salt.utils.data.mysql_to_dict\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.mysql_to_dict(data, key)


def simple_types_filter(data):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.data
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.simple_types_filter\' detected. This function '
        'has been moved to \'salt.utils.data.simple_types_filter\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.data.simple_types_filter(data)


def ip_bracket(addr):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.zeromq
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.ip_bracket\' detected. This function '
        'has been moved to \'salt.utils.zeromq.ip_bracket\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.zeromq.ip_bracket(addr)


def gen_mac(prefix='AC:DE:48'):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.network
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.gen_mac\' detected. This function '
        'has been moved to \'salt.utils.network.gen_mac\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.network.gen_mac(prefix)


def mac_str_to_bytes(mac_str):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.network
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.mac_str_to_bytes\' detected. This function '
        'has been moved to \'salt.utils.network.mac_str_to_bytes\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.network.mac_str_to_bytes(mac_str)


def refresh_dns():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.network
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.refresh_dns\' detected. This function '
        'has been moved to \'salt.utils.network.refresh_dns\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.network.refresh_dns()


def dns_check(addr, port, safe=False, ipv6=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.network
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.dns_check\' detected. This function '
        'has been moved to \'salt.utils.network.dns_check\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.network.dns_check(addr, port, safe, ipv6)


def get_context(template, line, num_lines=5, marker=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.templates
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_context\' detected. This function '
        'has been moved to \'salt.utils.templates.get_context\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.templates.get_context(template, line, num_lines, marker)


def get_master_key(key_user, opts, skip_perm_errors=False):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.master
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_master_key\' detected. This function '
        'has been moved to \'salt.utils.master.get_master_key\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.master.get_master_key(key_user, opts, skip_perm_errors)


def get_values_of_matching_keys(pattern_dict, user_name):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.master
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.get_values_of_matching_keys\' detected. '
        'This function has been moved to '
        '\'salt.utils.master.get_values_of_matching_keys\' as of Salt Oxygen. '
        'This warning will be removed in Salt Neon.'
    )
    return salt.utils.master.get_values_of_matching_keys(pattern_dict, user_name)


def date_cast(date):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.dateutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.date_cast\' detected. This function '
        'has been moved to \'salt.utils.dateutils.date_cast\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.dateutils.date_cast(date)


def date_format(date=None, format="%Y-%m-%d"):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.dateutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.date_format\' detected. This function '
        'has been moved to \'salt.utils.dateutils.strftime\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.dateutils.strftime(date, format)


def total_seconds(td):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.dateutils
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.total_seconds\' detected. This function '
        'has been moved to \'salt.utils.dateutils.total_seconds\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.dateutils.total_seconds(td)


def find_json(raw):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.json
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.find_json\' detected. This function '
        'has been moved to \'salt.utils.json.find_json\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.json.find_json(raw)


def import_json():
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.json
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.import_json\' detected. This function '
        'has been moved to \'salt.utils.json.import_json\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.json.import_json()


def namespaced_function(function, global_dict, defaults=None,
                        preserve_context=False):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.functools
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.namespaced_function\' detected. This function '
        'has been moved to \'salt.utils.functools.namespaced_function\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.functools.namespaced_function(
        function, global_dict, defaults, preserve_context)


def alias_function(fun, name, doc=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.functools
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.alias_function\' detected. This function '
        'has been moved to \'salt.utils.functools.alias_function\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.functools.alias_function(fun, name, doc)


def profile_func(filename=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.profile
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.profile_func\' detected. This function '
        'has been moved to \'salt.utils.profile.profile_func\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.profile.profile_func(filename)


def activate_profile(test=True):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.profile
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.activate_profile\' detected. This function '
        'has been moved to \'salt.utils.profile.activate_profile\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.profile.activate_profile(test)


def output_profile(pr, stats_path='/tmp/stats', stop=False, id_=None):
    # Late import to avoid circular import.
    import salt.utils.versions
    import salt.utils.profile
    salt.utils.versions.warn_until(
        'Neon',
        'Use of \'salt.utils.output_profile\' detected. This function '
        'has been moved to \'salt.utils.profile.output_profile\' as of '
        'Salt Oxygen. This warning will be removed in Salt Neon.'
    )
    return salt.utils.profile.output_profile(pr, stats_path, stop, id_)
