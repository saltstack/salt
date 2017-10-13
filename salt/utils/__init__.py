# -*- coding: utf-8 -*-
'''
Some of the utils used by salt

NOTE: The dev team is working on splitting up this file for the Oxygen release.
Please do not add any new functions to this file. New functions should be
organized in other files under salt/utils/. Please consult the dev team if you
are unsure where a new function should go.
'''

# Import python libs
from __future__ import absolute_import, division, print_function
import contextlib
import copy
import collections
import datetime
import errno
import fnmatch
import hashlib
import json
import logging
import os
import random
import re
import shlex
import shutil
import sys
import pstats
import time
import types
import string
import subprocess

# Import 3rd-party libs
from salt.ext import six
# pylint: disable=import-error
# pylint: disable=redefined-builtin
from salt.ext.six.moves import range
# pylint: enable=import-error,redefined-builtin

if six.PY3:
    import importlib.util  # pylint: disable=no-name-in-module,import-error
else:
    import imp

try:
    import cProfile
    HAS_CPROFILE = True
except ImportError:
    HAS_CPROFILE = False

try:
    import timelib
    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False

try:
    import parsedatetime
    HAS_PARSEDATETIME = True
except ImportError:
    HAS_PARSEDATETIME = False

try:
    import win32api
    HAS_WIN32API = True
except ImportError:
    HAS_WIN32API = False

# Import salt libs
from salt.defaults import DEFAULT_TARGET_DELIM
import salt.defaults.exitcodes
import salt.log
import salt.utils.dictupdate
import salt.utils.versions
import salt.version
from salt.utils.decorators.jinja import jinja_filter
from salt.exceptions import (
    CommandExecutionError, SaltClientError,
    CommandNotFoundError, SaltSystemExit,
    SaltInvocationError, SaltException
)


log = logging.getLogger(__name__)


def get_context(template, line, num_lines=5, marker=None):
    '''
    Returns debugging context around a line in a given string

    Returns:: string
    '''
    import salt.utils.stringutils
    template_lines = template.splitlines()
    num_template_lines = len(template_lines)

    # in test, a single line template would return a crazy line number like,
    # 357.  do this sanity check and if the given line is obviously wrong, just
    # return the entire template
    if line > num_template_lines:
        return template

    context_start = max(0, line - num_lines - 1)  # subt 1 for 0-based indexing
    context_end = min(num_template_lines, line + num_lines)
    error_line_in_context = line - context_start - 1  # subtr 1 for 0-based idx

    buf = []
    if context_start > 0:
        buf.append('[...]')
        error_line_in_context += 1

    buf.extend(template_lines[context_start:context_end])

    if context_end < num_template_lines:
        buf.append('[...]')

    if marker:
        buf[error_line_in_context] += marker

    return u'---\n{0}\n---'.format(u'\n'.join(buf))


def get_master_key(key_user, opts, skip_perm_errors=False):
    # Late import to avoid circular import.
    import salt.utils.files
    import salt.utils.verify
    import salt.utils.platform

    if key_user == 'root':
        if opts.get('user', 'root') != 'root':
            key_user = opts.get('user', 'root')
    if key_user.startswith('sudo_'):
        key_user = opts.get('user', 'root')
    if salt.utils.platform.is_windows():
        # The username may contain '\' if it is in Windows
        # 'DOMAIN\username' format. Fix this for the keyfile path.
        key_user = key_user.replace('\\', '_')
    keyfile = os.path.join(opts['cachedir'],
                           '.{0}_key'.format(key_user))
    # Make sure all key parent directories are accessible
    salt.utils.verify.check_path_traversal(opts['cachedir'],
                                           key_user,
                                           skip_perm_errors)

    try:
        with salt.utils.files.fopen(keyfile, 'r') as key:
            return key.read()
    except (OSError, IOError):
        # Fall back to eauth
        return ''


def profile_func(filename=None):
    '''
    Decorator for adding profiling to a nested function in Salt
    '''
    def proffunc(fun):
        def profiled_func(*args, **kwargs):
            logging.info('Profiling function {0}'.format(fun.__name__))
            try:
                profiler = cProfile.Profile()
                retval = profiler.runcall(fun, *args, **kwargs)
                profiler.dump_stats((filename or '{0}_func.profile'
                                     .format(fun.__name__)))
            except IOError:
                logging.exception(
                    'Could not open profile file {0}'.format(filename)
                )

            return retval
        return profiled_func
    return proffunc


def activate_profile(test=True):
    pr = None
    if test:
        if HAS_CPROFILE:
            pr = cProfile.Profile()
            pr.enable()
        else:
            log.error('cProfile is not available on your platform')
    return pr


def output_profile(pr, stats_path='/tmp/stats', stop=False, id_=None):
    # Late import to avoid circular import.
    import salt.utils.files
    import salt.utils.hashutils
    import salt.utils.path
    import salt.utils.stringutils

    if pr is not None and HAS_CPROFILE:
        try:
            pr.disable()
            if not os.path.isdir(stats_path):
                os.makedirs(stats_path)
            date = datetime.datetime.now().isoformat()
            if id_ is None:
                id_ = salt.utils.hashutils.random_hash(size=32)
            ficp = os.path.join(stats_path, '{0}.{1}.pstats'.format(id_, date))
            fico = os.path.join(stats_path, '{0}.{1}.dot'.format(id_, date))
            ficn = os.path.join(stats_path, '{0}.{1}.stats'.format(id_, date))
            if not os.path.exists(ficp):
                pr.dump_stats(ficp)
                with salt.utils.files.fopen(ficn, 'w') as fic:
                    pstats.Stats(pr, stream=fic).sort_stats('cumulative')
            log.info('PROFILING: {0} generated'.format(ficp))
            log.info('PROFILING (cumulative): {0} generated'.format(ficn))
            pyprof = salt.utils.path.which('pyprof2calltree')
            cmd = [pyprof, '-i', ficp, '-o', fico]
            if pyprof:
                failed = False
                try:
                    pro = subprocess.Popen(
                        cmd, shell=False,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except OSError:
                    failed = True
                if pro.returncode:
                    failed = True
                if failed:
                    log.error('PROFILING (dot problem')
                else:
                    log.info('PROFILING (dot): {0} generated'.format(fico))
                log.trace('pyprof2calltree output:')
                log.trace(salt.utils.stringutils.to_str(pro.stdout.read()).strip() +
                          salt.utils.stringutils.to_str(pro.stderr.read()).strip())
            else:
                log.info('You can run {0} for additional stats.'.format(cmd))
        finally:
            if not stop:
                pr.enable()
    return pr


def required_module_list(docstring=None):
    '''
    Return a list of python modules required by a salt module that aren't
    in stdlib and don't exist on the current pythonpath.
    '''
    # Late import to avoid circular import.
    import salt.utils.doc

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
    modules = required_module_list(docstring)
    if not modules:
        return ''
    filename = os.path.basename(name).split('.')[0]
    msg = '\'{0}\' requires these python modules: {1}'
    return msg.format(filename, ', '.join(modules))


def get_accumulator_dir(cachedir):
    '''
    Return the directory that accumulator data is stored in, creating it if it
    doesn't exist.
    '''
    fn_ = os.path.join(cachedir, 'accumulator')
    if not os.path.isdir(fn_):
        # accumulator_dir is not present, create it
        os.makedirs(fn_)
    return fn_


def check_or_die(command):
    '''
    Simple convenience function for modules to use for gracefully blowing up
    if a required tool is not available in the system path.

    Lazily import `salt.modules.cmdmod` to avoid any sort of circular
    dependencies.
    '''
    import salt.utils.path
    if command is None:
        raise CommandNotFoundError('\'None\' is not a valid command.')

    if not salt.utils.path.which(command):
        raise CommandNotFoundError('\'{0}\' is not in the path'.format(command))


def backup_minion(path, bkroot):
    '''
    Backup a file on the minion
    '''
    import salt.utils.platform
    dname, bname = os.path.split(path)
    if salt.utils.platform.is_windows():
        src_dir = dname.replace(':', '_')
    else:
        src_dir = dname[1:]
    if not salt.utils.platform.is_windows():
        fstat = os.stat(path)
    msecs = str(int(time.time() * 1000000))[-6:]
    if salt.utils.platform.is_windows():
        # ':' is an illegal filesystem path character on Windows
        stamp = time.strftime('%a_%b_%d_%H-%M-%S_%Y')
    else:
        stamp = time.strftime('%a_%b_%d_%H:%M:%S_%Y')
    stamp = '{0}{1}_{2}'.format(stamp[:-4], msecs, stamp[-4:])
    bkpath = os.path.join(bkroot,
                          src_dir,
                          '{0}_{1}'.format(bname, stamp))
    if not os.path.isdir(os.path.dirname(bkpath)):
        os.makedirs(os.path.dirname(bkpath))
    shutil.copyfile(path, bkpath)
    if not salt.utils.platform.is_windows():
        os.chown(bkpath, fstat.st_uid, fstat.st_gid)
        os.chmod(bkpath, fstat.st_mode)


def build_whitespace_split_regex(text):
    '''
    Create a regular expression at runtime which should match ignoring the
    addition or deletion of white space or line breaks, unless between commas

    Example:

    .. code-block:: python

        >>> import re
        >>> import salt.utils
        >>> regex = salt.utils.build_whitespace_split_regex(
        ...     """if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then"""
        ... )

        >>> regex
        '(?:[\\s]+)?if(?:[\\s]+)?\\[(?:[\\s]+)?\\-z(?:[\\s]+)?\\"\\$debian'
        '\\_chroot\\"(?:[\\s]+)?\\](?:[\\s]+)?\\&\\&(?:[\\s]+)?\\[(?:[\\s]+)?'
        '\\-r(?:[\\s]+)?\\/etc\\/debian\\_chroot(?:[\\s]+)?\\]\\;(?:[\\s]+)?'
        'then(?:[\\s]+)?'
        >>> re.search(
        ...     regex,
        ...     """if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then"""
        ... )

        <_sre.SRE_Match object at 0xb70639c0>
        >>>

    '''
    def __build_parts(text):
        lexer = shlex.shlex(text)
        lexer.whitespace_split = True
        lexer.commenters = ''
        if '\'' in text:
            lexer.quotes = '"'
        elif '"' in text:
            lexer.quotes = '\''
        return list(lexer)

    regex = r''
    for line in text.splitlines():
        parts = [re.escape(s) for s in __build_parts(line)]
        regex += r'(?:[\s]+)?{0}(?:[\s]+)?'.format(r'(?:[\s]+)?'.join(parts))
    return r'(?m)^{0}$'.format(regex)


def format_call(fun,
                data,
                initial_ret=None,
                expected_extra_kws=(),
                is_class_method=None):
    '''
    Build the required arguments and keyword arguments required for the passed
    function.

    :param fun: The function to get the argspec from
    :param data: A dictionary containing the required data to build the
                 arguments and keyword arguments.
    :param initial_ret: The initial return data pre-populated as dictionary or
                        None
    :param expected_extra_kws: Any expected extra keyword argument names which
                               should not trigger a :ref:`SaltInvocationError`
    :param is_class_method: Pass True if you are sure that the function being passed
                            is a class method. The reason for this is that on Python 3
                            ``inspect.ismethod`` only returns ``True`` for bound methods,
                            while on Python 2, it returns ``True`` for bound and unbound
                            methods. So, on Python 3, in case of a class method, you'd
                            need the class to which the function belongs to be instantiated
                            and this is not always wanted.
    :returns: A dictionary with the function required arguments and keyword
              arguments.
    '''
    # Late import to avoid circular import
    import salt.utils.versions
    import salt.utils.args
    ret = initial_ret is not None and initial_ret or {}

    ret['args'] = []
    ret['kwargs'] = {}

    aspec = salt.utils.args.get_function_argspec(fun, is_class_method=is_class_method)

    arg_data = salt.utils.args.arg_lookup(fun, aspec)
    args = arg_data['args']
    kwargs = arg_data['kwargs']

    # Since we WILL be changing the data dictionary, let's change a copy of it
    data = data.copy()

    missing_args = []

    for key in kwargs:
        try:
            kwargs[key] = data.pop(key)
        except KeyError:
            # Let's leave the default value in place
            pass

    while args:
        arg = args.pop(0)
        try:
            ret['args'].append(data.pop(arg))
        except KeyError:
            missing_args.append(arg)

    if missing_args:
        used_args_count = len(ret['args']) + len(args)
        args_count = used_args_count + len(missing_args)
        raise SaltInvocationError(
            '{0} takes at least {1} argument{2} ({3} given)'.format(
                fun.__name__,
                args_count,
                args_count > 1 and 's' or '',
                used_args_count
            )
        )

    ret['kwargs'].update(kwargs)

    if aspec.keywords:
        # The function accepts **kwargs, any non expected extra keyword
        # arguments will made available.
        for key, value in six.iteritems(data):
            if key in expected_extra_kws:
                continue
            ret['kwargs'][key] = value

        # No need to check for extra keyword arguments since they are all
        # **kwargs now. Return
        return ret

    # Did not return yet? Lets gather any remaining and unexpected keyword
    # arguments
    extra = {}
    for key, value in six.iteritems(data):
        if key in expected_extra_kws:
            continue
        extra[key] = copy.deepcopy(value)

    # We'll be showing errors to the users until Salt Oxygen comes out, after
    # which, errors will be raised instead.
    salt.utils.versions.warn_until(
        'Oxygen',
        'It\'s time to start raising `SaltInvocationError` instead of '
        'returning warnings',
        # Let's not show the deprecation warning on the console, there's no
        # need.
        _dont_call_warnings=True
    )

    if extra:
        # Found unexpected keyword arguments, raise an error to the user
        if len(extra) == 1:
            msg = '\'{0[0]}\' is an invalid keyword argument for \'{1}\''.format(
                list(extra.keys()),
                ret.get(
                    # In case this is being called for a state module
                    'full',
                    # Not a state module, build the name
                    '{0}.{1}'.format(fun.__module__, fun.__name__)
                )
            )
        else:
            msg = '{0} and \'{1}\' are invalid keyword arguments for \'{2}\''.format(
                ', '.join(['\'{0}\''.format(e) for e in extra][:-1]),
                list(extra.keys())[-1],
                ret.get(
                    # In case this is being called for a state module
                    'full',
                    # Not a state module, build the name
                    '{0}.{1}'.format(fun.__module__, fun.__name__)
                )
            )

        # Return a warning to the user explaining what's going on
        ret.setdefault('warnings', []).append(
            '{0}. If you were trying to pass additional data to be used '
            'in a template context, please populate \'context\' with '
            '\'key: value\' pairs. Your approach will work until Salt '
            'Oxygen is out.{1}'.format(
                msg,
                '' if 'full' not in ret else ' Please update your state files.'
            )
        )

        # Lets pack the current extra kwargs as template context
        ret.setdefault('context', {}).update(extra)
    return ret


@jinja_filter('mysql_to_dict')
def mysql_to_dict(data, key):
    '''
    Convert MySQL-style output to a python dictionary
    '''
    import salt.utils.stringutils
    ret = {}
    headers = ['']
    for line in data:
        if not line:
            continue
        if line.startswith('+'):
            continue
        comps = line.split('|')
        for comp in range(len(comps)):
            comps[comp] = comps[comp].strip()
        if len(headers) > 1:
            index = len(headers) - 1
            row = {}
            for field in range(index):
                if field < 1:
                    continue
                else:
                    row[headers[field]] = salt.utils.stringutils.to_num(comps[field])
            ret[row[key]] = row
        else:
            headers = comps
    return ret


def expr_match(line, expr):
    '''
    Evaluate a line of text against an expression. First try a full-string
    match, next try globbing, and then try to match assuming expr is a regular
    expression. Originally designed to match minion IDs for
    whitelists/blacklists.
    '''
    if line == expr:
        return True
    if fnmatch.fnmatch(line, expr):
        return True
    try:
        if re.match(r'\A{0}\Z'.format(expr), line):
            return True
    except re.error:
        pass
    return False


@jinja_filter('check_whitelist_blacklist')
def check_whitelist_blacklist(value, whitelist=None, blacklist=None):
    '''
    Check a whitelist and/or blacklist to see if the value matches it.

    value
        The item to check the whitelist and/or blacklist against.

    whitelist
        The list of items that are white-listed. If ``value`` is found
        in the whitelist, then the function returns ``True``. Otherwise,
        it returns ``False``.

    blacklist
        The list of items that are black-listed. If ``value`` is found
        in the blacklist, then the function returns ``False``. Otherwise,
        it returns ``True``.

    If both a whitelist and a blacklist are provided, value membership
    in the blacklist will be examined first. If the value is not found
    in the blacklist, then the whitelist is checked. If the value isn't
    found in the whitelist, the function returns ``False``.
    '''
    if blacklist is not None:
        if not hasattr(blacklist, '__iter__'):
            blacklist = [blacklist]
        try:
            for expr in blacklist:
                if expr_match(value, expr):
                    return False
        except TypeError:
            log.error('Non-iterable blacklist {0}'.format(blacklist))

    if whitelist:
        if not hasattr(whitelist, '__iter__'):
            whitelist = [whitelist]
        try:
            for expr in whitelist:
                if expr_match(value, expr):
                    return True
        except TypeError:
            log.error('Non-iterable whitelist {0}'.format(whitelist))
    else:
        return True

    return False


def get_values_of_matching_keys(pattern_dict, user_name):
    '''
    Check a whitelist and/or blacklist to see if the value matches it.
    '''
    ret = []
    for expr in pattern_dict:
        if expr_match(user_name, expr):
            ret.extend(pattern_dict[expr])
    return ret


def sanitize_win_path_string(winpath):
    '''
    Remove illegal path characters for windows
    '''
    intab = '<>:|?*'
    outtab = '_' * len(intab)
    trantab = ''.maketrans(intab, outtab) if six.PY3 else string.maketrans(intab, outtab)  # pylint: disable=no-member
    if isinstance(winpath, six.string_types):
        winpath = winpath.translate(trantab)
    elif isinstance(winpath, six.text_type):
        winpath = winpath.translate(dict((ord(c), u'_') for c in intab))
    return winpath


def check_include_exclude(path_str, include_pat=None, exclude_pat=None):
    '''
    Check for glob or regexp patterns for include_pat and exclude_pat in the
    'path_str' string and return True/False conditions as follows.
      - Default: return 'True' if no include_pat or exclude_pat patterns are
        supplied
      - If only include_pat or exclude_pat is supplied: return 'True' if string
        passes the include_pat test or fails exclude_pat test respectively
      - If both include_pat and exclude_pat are supplied: return 'True' if
        include_pat matches AND exclude_pat does not match
    '''
    ret = True  # -- default true
    # Before pattern match, check if it is regexp (E@'') or glob(default)
    if include_pat:
        if re.match('E@', include_pat):
            retchk_include = True if re.search(
                include_pat[2:],
                path_str
            ) else False
        else:
            retchk_include = True if fnmatch.fnmatch(
                path_str,
                include_pat
            ) else False

    if exclude_pat:
        if re.match('E@', exclude_pat):
            retchk_exclude = False if re.search(
                exclude_pat[2:],
                path_str
            ) else True
        else:
            retchk_exclude = False if fnmatch.fnmatch(
                path_str,
                exclude_pat
            ) else True

    # Now apply include/exclude conditions
    if include_pat and not exclude_pat:
        ret = retchk_include
    elif exclude_pat and not include_pat:
        ret = retchk_exclude
    elif include_pat and exclude_pat:
        ret = retchk_include and retchk_exclude
    else:
        ret = True

    return ret


def option(value, default='', opts=None, pillar=None):
    '''
    Pass in a generic option and receive the value that will be assigned
    '''
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
        out = traverse_dict_and_list(source, val, default)
        if out is not default:
            return out
    return default


def print_cli(msg, retries=10, step=0.01):
    '''
    Wrapper around print() that suppresses tracebacks on broken pipes (i.e.
    when salt output is piped to less and less is stopped prematurely).
    '''
    while retries:
        try:
            try:
                print(msg)
            except UnicodeEncodeError:
                print(msg.encode('utf-8'))
        except IOError as exc:
            err = "{0}".format(exc)
            if exc.errno != errno.EPIPE:
                if (
                    ("temporarily unavailable" in err or
                     exc.errno in (errno.EAGAIN,)) and
                    retries
                ):
                    time.sleep(step)
                    retries -= 1
                    continue
                else:
                    raise
        break


def namespaced_function(function, global_dict, defaults=None, preserve_context=False):
    '''
    Redefine (clone) a function under a different globals() namespace scope

        preserve_context:
            Allow keeping the context taken from orignal namespace,
            and extend it with globals() taken from
            new targetted namespace.
    '''
    if defaults is None:
        defaults = function.__defaults__

    if preserve_context:
        _global_dict = function.__globals__.copy()
        _global_dict.update(global_dict)
        global_dict = _global_dict
    new_namespaced_function = types.FunctionType(
        function.__code__,
        global_dict,
        name=function.__name__,
        argdefs=defaults,
        closure=function.__closure__
    )
    new_namespaced_function.__dict__.update(function.__dict__)
    return new_namespaced_function


def alias_function(fun, name, doc=None):
    '''
    Copy a function
    '''
    alias_fun = types.FunctionType(fun.__code__,
                                   fun.__globals__,
                                   name,
                                   fun.__defaults__,
                                   fun.__closure__)
    alias_fun.__dict__.update(fun.__dict__)

    if doc and isinstance(doc, six.string_types):
        alias_fun.__doc__ = doc
    else:
        orig_name = fun.__name__
        alias_msg = ('\nThis function is an alias of '
                     '``{0}``.\n'.format(orig_name))
        alias_fun.__doc__ = alias_msg + fun.__doc__

    return alias_fun


def _win_console_event_handler(event):
    if event == 5:
        # Do nothing on CTRL_LOGOFF_EVENT
        return True
    return False


def enable_ctrl_logoff_handler():
    if HAS_WIN32API:
        win32api.SetConsoleCtrlHandler(_win_console_event_handler, 1)


def date_cast(date):
    '''
    Casts any object into a datetime.datetime object

    date
      any datetime, time string representation...
    '''
    if date is None:
        return datetime.datetime.now()
    elif isinstance(date, datetime.datetime):
        return date

    # fuzzy date
    try:
        if isinstance(date, six.string_types):
            try:
                if HAS_TIMELIB:
                    # py3: yes, timelib.strtodatetime wants bytes, not str :/
                    return timelib.strtodatetime(to_bytes(date))
            except ValueError:
                pass

            # not parsed yet, obviously a timestamp?
            if date.isdigit():
                date = int(date)
            else:
                date = float(date)

        return datetime.datetime.fromtimestamp(date)
    except Exception:
        if HAS_TIMELIB:
            raise ValueError('Unable to parse {0}'.format(date))

        raise RuntimeError(
                'Unable to parse {0}. Consider installing timelib'.format(date))


@jinja_filter('strftime')
def date_format(date=None, format="%Y-%m-%d"):
    '''
    Converts date into a time-based string

    date
      any datetime, time string representation...

    format
       :ref:`strftime<http://docs.python.org/2/library/datetime.html#datetime.datetime.strftime>` format

    >>> import datetime
    >>> src = datetime.datetime(2002, 12, 25, 12, 00, 00, 00)
    >>> date_format(src)
    '2002-12-25'
    >>> src = '2002/12/25'
    >>> date_format(src)
    '2002-12-25'
    >>> src = 1040814000
    >>> date_format(src)
    '2002-12-25'
    >>> src = '1040814000'
    >>> date_format(src)
    '2002-12-25'
    '''
    return date_cast(date).strftime(format)


def find_json(raw):
    '''
    Pass in a raw string and load the json when it starts. This allows for a
    string to start with garbage and end with json but be cleanly loaded
    '''
    ret = {}
    for ind in range(len(raw)):
        working = '\n'.join(raw.splitlines()[ind:])
        try:
            ret = json.loads(working, object_hook=decode_dict)
        except ValueError:
            continue
        if ret:
            return ret
    if not ret:
        # Not json, raise an error
        raise ValueError


def total_seconds(td):
    '''
    Takes a timedelta and returns the total number of seconds
    represented by the object. Wrapper for the total_seconds()
    method which does not exist in versions of Python < 2.7.
    '''
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


def import_json():
    '''
    Import a json module, starting with the quick ones and going down the list)
    '''
    for fast_json in ('ujson', 'yajl', 'json'):
        try:
            mod = __import__(fast_json)
            log.trace('loaded {0} json lib'.format(fast_json))
            return mod
        except ImportError:
            continue


def simple_types_filter(data):
    '''
    Convert the data list, dictionary into simple types, i.e., int, float, string,
    bool, etc.
    '''
    if data is None:
        return data

    simpletypes_keys = (six.string_types, six.text_type, six.integer_types, float, bool)
    simpletypes_values = tuple(list(simpletypes_keys) + [list, tuple])

    if isinstance(data, (list, tuple)):
        simplearray = []
        for value in data:
            if value is not None:
                if isinstance(value, (dict, list)):
                    value = simple_types_filter(value)
                elif not isinstance(value, simpletypes_values):
                    value = repr(value)
            simplearray.append(value)
        return simplearray

    if isinstance(data, dict):
        simpledict = {}
        for key, value in six.iteritems(data):
            if key is not None and not isinstance(key, simpletypes_keys):
                key = repr(key)
            if value is not None and isinstance(value, (dict, list, tuple)):
                value = simple_types_filter(value)
            elif value is not None and not isinstance(value, simpletypes_values):
                value = repr(value)
            simpledict[key] = value
        return simpledict

    return data


def fnmatch_multiple(candidates, pattern):
    '''
    Convenience function which runs fnmatch.fnmatch() on each element of passed
    iterable. The first matching candidate is returned, or None if there is no
    matching candidate.
    '''
    # Make sure that candidates is iterable to avoid a TypeError when we try to
    # iterate over its items.
    try:
        candidates_iter = iter(candidates)
    except TypeError:
        return None

    for candidate in candidates_iter:
        try:
            if fnmatch.fnmatch(candidate, pattern):
                return candidate
        except TypeError:
            pass
    return None


#
# MOVED FUNCTIONS
#
# These are deprecated and will be removed in Neon.
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


@jinja_filter('is_empty')
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


@contextlib.contextmanager
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


@contextlib.contextmanager
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
