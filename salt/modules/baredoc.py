# -*- coding: utf-8 -*-
'''
Baredoc walks the installed module and state directories and generates
dictionaries and lists of the function names and their arguments.

.. versionadded:: Neon

'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import logging
import os
import re

# Import salt libs
import salt.loader
import salt.runner
import salt.state
import salt.utils.data
import salt.utils.files
import salt.utils.args
import salt.utils.schema

# Import 3rd-party libs
from salt.ext import six
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)


def _parse_function_definition(fn_def, modulename, ret):
    args = []
    match = re.match(r'def\s+(.*?)\((.*)\):$', fn_def)
    if match is None:
        return
    fn_name = match.group(1)
    if fn_name.startswith('_'):
        return
    if fn_name.endswith('_'):
        fn_name = fn_name[0:-1]
    fn_name = fn_name.strip('"')
    fn_name = fn_name.strip("'")
    try:
        raw_args = match.group(2)
        raw_args = re.sub(r'(.*)\(.*\)(.*)', r'\1\2', raw_args)
        raw_args = re.sub(r'(.*)\'.*\'(.*)', r'\1\2', raw_args)
        individual_args = raw_args.split(',')
        for a in individual_args:
            if '*' in a:
                continue
            args.append(a.split('=')[0].strip())
    except AttributeError:
        pass
    key = '{}.{}'.format(modulename, fn_name)
    if key in ret:
        ret[key].extend(args)
    else:
        ret[key] = args
    ret[key] = list(set(ret[key]))


def _mods_with_args(dirs):
    ret = {}
    for d in dirs:
        for m in os.listdir(d):
            if m.endswith('.py'):
                with salt.utils.files.fopen(os.path.join(d, m), 'r') as f:
                    in_def = False
                    fn_def = u''
                    modulename = m.split('.')[0]
                    virtualname = None

                    for l in f:
                        l = salt.utils.data.decode(l, encoding='utf-8').rstrip()
                        l = re.sub(r'(.*)#(.*)', r'\1', l)
                        if '__virtualname__ =' in l and not virtualname:
                            virtualname = l.split()[2].strip("'").strip('"')
                            continue
                        if l.startswith(u'def '):
                            in_def = True
                            fn_def = l
                        if ':' in l:
                            if in_def:
                                if not l.startswith(u'def '):
                                    fn_def = fn_def + l
                                _parse_function_definition(fn_def, virtualname or modulename, ret)
                                fn_def = u''
                                in_def = False
                                continue
                        if in_def and not l.startswith(u'def '):
                            fn_def = fn_def + l
    return ret


def modules_and_args(modules=True, states=False, names_only=False):
    '''
    Walk the Salt install tree and return a dictionary or a list
    of the functions therein as well as their arguments.

    :param modules: Walk the modules directory if True
    :param states: Walk the states directory if True
    :param names_only: Return only a list of the callable functions instead of a dictionary with arguments
    :return: An OrderedDict with callable function names as keys and lists of arguments as
             values (if ``names_only`` == False) or simply an ordered list of callable
             function nanes (if ``names_only`` == True).

    CLI Example:
    (example truncated for brevity)

    .. code-block:: bash

        salt myminion baredoc.modules_and_args

        myminion:
            ----------
        [...]
            at.atrm:
            at.jobcheck:
            at.mod_watch:
                - name
            at.present:
                - unique_tag
                - name
                - timespec
                - job
                - tag
                - user
            at.watch:
                - unique_tag
                - name
                - timespec
                - job
                - tag
                - user
        [...]
    '''
    dirs = []
    module_dir = os.path.dirname(os.path.realpath(__file__))
    state_dir = os.path.join(os.path.dirname(module_dir), 'states')

    if modules:
        dirs.append(module_dir)
    if states:
        dirs.append(state_dir)

    ret = _mods_with_args(dirs)
    if names_only:
        return sorted(ret.keys())
    else:
        return OrderedDict(sorted(ret.items()))


def modules_with_test():
    '''
    Return a list of callable functions that have a ``test=`` flag.

    CLI Example:

    (results trimmed for brevity)

    .. code-block:: bash

        salt myminion baredoc.modules_with_test

        myminion:
            ----------
            - boto_elb.set_instances
            - netconfig.managed
            - netconfig.replace_pattern
            - pkg.install
            - salt.state
            - state.high
            - state.highstate

    '''
    mods = modules_and_args()
    testmods = []
    for module_name, module_args in six.iteritems(mods):
        if 'test' in module_args:
            testmods.append(module_name)

    return sorted(testmods)
