# -*- coding: utf-8 -*-
'''
The module used to execute states in salt. A state is unlike a module
execution in that instead of just executing a command it ensure that a
certain state is present on the system.

The data sent to the state calls is as follows:
    { 'state': '<state module name>',
      'fun': '<state function name>',
      'name': '<the name argument passed to all states>'
      'argn': '<arbitrary argument, can have many of these>'
      }
'''

# Import python libs
from __future__ import absolute_import
import os
import sys
import copy
import site
import fnmatch
import logging
import datetime
import traceback
import re
import time
import random

# Import salt libs
import salt.loader
import salt.minion
import salt.pillar
import salt.fileclient
import salt.utils.args
import salt.utils.crypt
import salt.utils.dictupdate
import salt.utils.event
import salt.utils.files
import salt.utils.immutabletypes as immutabletypes
import salt.utils.platform
import salt.utils.process
import salt.utils.url
import salt.syspaths as syspaths
from salt.template import compile_template, compile_template_str
from salt.exceptions import (
    SaltException,
    SaltRenderError,
    SaltReqTimeoutError
)
from salt.utils.odict import OrderedDict, DefaultOrderedDict
from salt.utils.locales import sdecode
# Explicit late import to avoid circular import. DO NOT MOVE THIS.
import salt.utils.yamlloader as yamlloader

# Import third party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import map, range, reload_module
# pylint: enable=import-error,no-name-in-module,redefined-builtin
import msgpack

log = logging.getLogger(__name__)


# These are keywords passed to state module functions which are to be used
# by salt in this state module and not on the actual state module function
STATE_REQUISITE_KEYWORDS = frozenset([
    u'onchanges',
    u'onfail',
    u'onfail_stop',
    u'prereq',
    u'prerequired',
    u'watch',
    u'require',
    u'listen',
    ])
STATE_REQUISITE_IN_KEYWORDS = frozenset([
    u'onchanges_in',
    u'onfail_in',
    u'prereq_in',
    u'watch_in',
    u'require_in',
    u'listen_in',
    ])
STATE_RUNTIME_KEYWORDS = frozenset([
    u'fun',
    u'state',
    u'check_cmd',
    u'failhard',
    u'onlyif',
    u'unless',
    u'retry',
    u'order',
    u'parallel',
    u'prereq',
    u'prereq_in',
    u'prerequired',
    u'reload_modules',
    u'reload_grains',
    u'reload_pillar',
    u'runas',
    u'runas_password',
    u'fire_event',
    u'saltenv',
    u'use',
    u'use_in',
    u'__env__',
    u'__sls__',
    u'__id__',
    u'__orchestration_jid__',
    u'__pub_user',
    u'__pub_arg',
    u'__pub_jid',
    u'__pub_fun',
    u'__pub_tgt',
    u'__pub_ret',
    u'__pub_pid',
    u'__pub_tgt_type',
    u'__prereq__',
    ])

STATE_INTERNAL_KEYWORDS = STATE_REQUISITE_KEYWORDS.union(STATE_REQUISITE_IN_KEYWORDS).union(STATE_RUNTIME_KEYWORDS)


def _odict_hashable(self):
    return id(self)


OrderedDict.__hash__ = _odict_hashable


def split_low_tag(tag):
    '''
    Take a low tag and split it back into the low dict that it came from
    '''
    state, id_, name, fun = tag.split(u'_|-')

    return {u'state': state,
            u'__id__': id_,
            u'name': name,
            u'fun': fun}


def _gen_tag(low):
    '''
    Generate the running dict tag string from the low data structure
    '''
    return u'{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(low)


def _clean_tag(tag):
    '''
    Make tag name safe for filenames
    '''
    return salt.utils.files.safe_filename_leaf(tag)


def _l_tag(name, id_):
    low = {u'name': u'listen_{0}'.format(name),
           u'__id__': u'listen_{0}'.format(id_),
           u'state': u'Listen_Error',
           u'fun': u'Listen_Error'}
    return _gen_tag(low)


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


def trim_req(req):
    '''
    Trim any function off of a requisite
    '''
    reqfirst = next(iter(req))
    if u'.' in reqfirst:
        return {reqfirst.split(u'.')[0]: req[reqfirst]}
    return req


def state_args(id_, state, high):
    '''
    Return a set of the arguments passed to the named state
    '''
    args = set()
    if id_ not in high:
        return args
    if state not in high[id_]:
        return args
    for item in high[id_][state]:
        if not isinstance(item, dict):
            continue
        if len(item) != 1:
            continue
        args.add(next(iter(item)))
    return args


def find_name(name, state, high):
    '''
    Scan high data for the id referencing the given name and return a list of (IDs, state) tuples that match

    Note: if `state` is sls, then we are looking for all IDs that match the given SLS
    '''
    ext_id = []
    if name in high:
        ext_id.append((name, state))
    # if we are requiring an entire SLS, then we need to add ourselves to everything in that SLS
    elif state == u'sls':
        for nid, item in six.iteritems(high):
            if item[u'__sls__'] == name:
                ext_id.append((nid, next(iter(item))))
    # otherwise we are requiring a single state, lets find it
    else:
        # We need to scan for the name
        for nid in high:
            if state in high[nid]:
                if isinstance(high[nid][state], list):
                    for arg in high[nid][state]:
                        if not isinstance(arg, dict):
                            continue
                        if len(arg) != 1:
                            continue
                        if arg[next(iter(arg))] == name:
                            ext_id.append((nid, state))
    return ext_id


def find_sls_ids(sls, high):
    '''
    Scan for all ids in the given sls and return them in a dict; {name: state}
    '''
    ret = []
    for nid, item in six.iteritems(high):
        if item[u'__sls__'] == sls:
            for st_ in item:
                if st_.startswith(u'__'):
                    continue
                ret.append((nid, st_))
    return ret


def format_log(ret):
    '''
    Format the state into a log message
    '''
    msg = u''
    if isinstance(ret, dict):
        # Looks like the ret may be a valid state return
        if u'changes' in ret:
            # Yep, looks like a valid state return
            chg = ret[u'changes']
            if not chg:
                if ret[u'comment']:
                    msg = ret[u'comment']
                else:
                    msg = u'No changes made for {0[name]}'.format(ret)
            elif isinstance(chg, dict):
                if u'diff' in chg:
                    if isinstance(chg[u'diff'], six.string_types):
                        msg = u'File changed:\n{0}'.format(chg[u'diff'])
                if all([isinstance(x, dict) for x in six.itervalues(chg)]):
                    if all([(u'old' in x and u'new' in x)
                            for x in six.itervalues(chg)]):
                        msg = u'Made the following changes:\n'
                        for pkg in chg:
                            old = chg[pkg][u'old']
                            if not old and old not in (False, None):
                                old = u'absent'
                            new = chg[pkg][u'new']
                            if not new and new not in (False, None):
                                new = u'absent'
                            # This must be able to handle unicode as some package names contain
                            # non-ascii characters like "Français" or "Español". See Issue #33605.
                            msg += u'\'{0}\' changed from \'{1}\' to \'{2}\'\n'.format(pkg, old, new)
            if not msg:
                msg = str(ret[u'changes'])
            if ret[u'result'] is True or ret[u'result'] is None:
                log.info(msg)
            else:
                log.error(msg)
    else:
        # catch unhandled data
        log.info(str(ret))


def master_compile(master_opts, minion_opts, grains, id_, saltenv):
    '''
    Compile the master side low state data, and build the hidden state file
    '''
    st_ = MasterHighState(master_opts, minion_opts, grains, id_, saltenv)
    return st_.compile_highstate()


def ishashable(obj):
    try:
        hash(obj)
    except TypeError:
        return False
    return True


def mock_ret(cdata):
    '''
    Returns a mocked return dict with information about the run, without
    executing the state function
    '''
    # As this is expanded it should be sent into the execution module
    # layer or it should be turned into a standalone loader system
    if cdata[u'args']:
        name = cdata[u'args'][0]
    else:
        name = cdata[u'kwargs'][u'name']
    return {u'name': name,
            u'comment': u'Not called, mocked',
            u'changes': {},
            u'result': True}


class StateError(Exception):
    '''
    Custom exception class.
    '''
    pass


class Compiler(object):
    '''
    Class used to compile and manage the High Data structure
    '''
    def __init__(self, opts, renderers):
        self.opts = opts
        self.rend = renderers

    def render_template(self, template, **kwargs):
        '''
        Enforce the states in a template
        '''
        high = compile_template(template,
                                self.rend,
                                self.opts[u'renderer'],
                                self.opts[u'renderer_blacklist'],
                                self.opts[u'renderer_whitelist'],
                                **kwargs)
        if not high:
            return high
        return self.pad_funcs(high)

    def pad_funcs(self, high):
        '''
        Turns dot delimited function refs into function strings
        '''
        for name in high:
            if not isinstance(high[name], dict):
                if isinstance(high[name], six.string_types):
                    # Is this is a short state? It needs to be padded!
                    if u'.' in high[name]:
                        comps = high[name].split(u'.')
                        if len(comps) >= 2:
                            # Merge the comps
                            comps[1] = u'.'.join(comps[1:len(comps)])
                        high[name] = {
                            # '__sls__': template,
                            # '__env__': None,
                            comps[0]: [comps[1]]
                        }
                        continue
                    continue
            skeys = set()
            for key in sorted(high[name]):
                if key.startswith(u'_'):
                    continue
                if not isinstance(high[name][key], list):
                    continue
                if u'.' in key:
                    comps = key.split(u'.')
                    if len(comps) >= 2:
                        # Merge the comps
                        comps[1] = u'.'.join(comps[1:len(comps)])
                    # Salt doesn't support state files such as:
                    #
                    # /etc/redis/redis.conf:
                    #   file.managed:
                    #     - user: redis
                    #     - group: redis
                    #     - mode: 644
                    #   file.comment:
                    #     - regex: ^requirepass
                    if comps[0] in skeys:
                        continue
                    high[name][comps[0]] = high[name].pop(key)
                    high[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)
        return high

    def verify_high(self, high):
        '''
        Verify that the high data is viable and follows the data structure
        '''
        errors = []
        if not isinstance(high, dict):
            errors.append(u'High data is not a dictionary and is invalid')
        reqs = OrderedDict()
        for name, body in six.iteritems(high):
            if name.startswith(u'__'):
                continue
            if not isinstance(name, six.string_types):
                errors.append(
                    u'ID \'{0}\' in SLS \'{1}\' is not formed as a string, but '
                    u'is a {2}'.format(
                        name,
                        body[u'__sls__'],
                        type(name).__name__
                    )
                )
            if not isinstance(body, dict):
                err = (u'The type {0} in {1} is not formatted as a dictionary'
                       .format(name, body))
                errors.append(err)
                continue
            for state in body:
                if state.startswith(u'__'):
                    continue
                if not isinstance(body[state], list):
                    errors.append(
                        u'State \'{0}\' in SLS \'{1}\' is not formed as a list'
                        .format(name, body[u'__sls__'])
                    )
                else:
                    fun = 0
                    if u'.' in state:
                        fun += 1
                    for arg in body[state]:
                        if isinstance(arg, six.string_types):
                            fun += 1
                            if u' ' in arg.strip():
                                errors.append((u'The function "{0}" in state '
                                u'"{1}" in SLS "{2}" has '
                                u'whitespace, a function with whitespace is '
                                u'not supported, perhaps this is an argument '
                                u'that is missing a ":"').format(
                                    arg,
                                    name,
                                    body[u'__sls__']))
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            #
                            # Add the requires to the reqs dict and check them
                            # all for recursive requisites.
                            argfirst = next(iter(arg))
                            if argfirst in (u'require', u'watch', u'prereq', u'onchanges'):
                                if not isinstance(arg[argfirst], list):
                                    errors.append((u'The {0}'
                                    u' statement in state \'{1}\' in SLS \'{2}\' '
                                    u'needs to be formed as a list').format(
                                        argfirst,
                                        name,
                                        body[u'__sls__']
                                        ))
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    reqs[name] = {u'state': state}
                                    for req in arg[argfirst]:
                                        if isinstance(req, six.string_types):
                                            req = {u'id': req}
                                        if not isinstance(req, dict):
                                            err = (u'Requisite declaration {0}'
                                            u' in SLS {1} is not formed as a'
                                            u' single key dictionary').format(
                                                req,
                                                body[u'__sls__'])
                                            errors.append(err)
                                            continue
                                        req_key = next(iter(req))
                                        req_val = req[req_key]
                                        if u'.' in req_key:
                                            errors.append((
                                                u'Invalid requisite type \'{0}\' '
                                                u'in state \'{1}\', in SLS '
                                                u'\'{2}\'. Requisite types must '
                                                u'not contain dots, did you '
                                                u'mean \'{3}\'?'.format(
                                                    req_key,
                                                    name,
                                                    body[u'__sls__'],
                                                    req_key[:req_key.find(u'.')]
                                                )
                                            ))
                                        if not ishashable(req_val):
                                            errors.append((
                                                u'Illegal requisite "{0}", '
                                                u'is SLS {1}\n'
                                                ).format(
                                                    str(req_val),
                                                    body[u'__sls__']))
                                            continue

                                        # Check for global recursive requisites
                                        reqs[name][req_val] = req_key
                                        # I am going beyond 80 chars on
                                        # purpose, this is just too much
                                        # of a pain to deal with otherwise
                                        if req_val in reqs:
                                            if name in reqs[req_val]:
                                                if reqs[req_val][name] == state:
                                                    if reqs[req_val][u'state'] == reqs[name][req_val]:
                                                        err = (u'A recursive '
                                                        u'requisite was found, SLS '
                                                        u'"{0}" ID "{1}" ID "{2}"'
                                                        ).format(
                                                                body[u'__sls__'],
                                                                name,
                                                                req_val
                                                                )
                                                        errors.append(err)
                                # Make sure that there is only one key in the
                                # dict
                                if len(list(arg)) != 1:
                                    errors.append((u'Multiple dictionaries '
                                    u'defined in argument of state \'{0}\' in SLS'
                                    u' \'{1}\'').format(
                                        name,
                                        body[u'__sls__']))
                    if not fun:
                        if state == u'require' or state == u'watch':
                            continue
                        errors.append((u'No function declared in state \'{0}\' in'
                            u' SLS \'{1}\'').format(state, body[u'__sls__']))
                    elif fun > 1:
                        errors.append(
                            u'Too many functions declared in state \'{0}\' in '
                            u'SLS \'{1}\''.format(state, body[u'__sls__'])
                        )
        return errors

    def order_chunks(self, chunks):
        '''
        Sort the chunk list verifying that the chunks follow the order
        specified in the order options.
        '''
        cap = 1
        for chunk in chunks:
            if u'order' in chunk:
                if not isinstance(chunk[u'order'], int):
                    continue

                chunk_order = chunk[u'order']
                if chunk_order > cap - 1 and chunk_order > 0:
                    cap = chunk_order + 100
        for chunk in chunks:
            if u'order' not in chunk:
                chunk[u'order'] = cap
                continue

            if not isinstance(chunk[u'order'], (int, float)):
                if chunk[u'order'] == u'last':
                    chunk[u'order'] = cap + 1000000
                elif chunk[u'order'] == u'first':
                    chunk[u'order'] = 0
                else:
                    chunk[u'order'] = cap
            if u'name_order' in chunk:
                chunk[u'order'] = chunk[u'order'] + chunk.pop(u'name_order') / 10000.0
            if chunk[u'order'] < 0:
                chunk[u'order'] = cap + 1000000 + chunk[u'order']
            chunk[u'name'] = sdecode(chunk[u'name'])
        chunks.sort(key=lambda chunk: (chunk[u'order'], u'{0[state]}{0[name]}{0[fun]}'.format(chunk)))
        return chunks

    def compile_high_data(self, high):
        '''
        "Compile" the high data as it is retrieved from the CLI or YAML into
        the individual state executor structures
        '''
        chunks = []
        for name, body in six.iteritems(high):
            if name.startswith(u'__'):
                continue
            for state, run in six.iteritems(body):
                funcs = set()
                names = []
                if state.startswith(u'__'):
                    continue
                chunk = {u'state': state,
                         u'name': name}
                if u'__sls__' in body:
                    chunk[u'__sls__'] = body[u'__sls__']
                if u'__env__' in body:
                    chunk[u'__env__'] = body[u'__env__']
                chunk[u'__id__'] = name
                for arg in run:
                    if isinstance(arg, six.string_types):
                        funcs.add(arg)
                        continue
                    if isinstance(arg, dict):
                        for key, val in six.iteritems(arg):
                            if key == u'names':
                                for _name in val:
                                    if _name not in names:
                                        names.append(_name)
                                continue
                            else:
                                chunk.update(arg)
                if names:
                    name_order = 1
                    for entry in names:
                        live = copy.deepcopy(chunk)
                        if isinstance(entry, dict):
                            low_name = next(six.iterkeys(entry))
                            live[u'name'] = low_name
                            list(map(live.update, entry[low_name]))
                        else:
                            live[u'name'] = entry
                        live[u'name_order'] = name_order
                        name_order = name_order + 1
                        for fun in funcs:
                            live[u'fun'] = fun
                            chunks.append(live)
                else:
                    live = copy.deepcopy(chunk)
                    for fun in funcs:
                        live[u'fun'] = fun
                        chunks.append(live)
        chunks = self.order_chunks(chunks)
        return chunks

    def apply_exclude(self, high):
        '''
        Read in the __exclude__ list and remove all excluded objects from the
        high data
        '''
        if u'__exclude__' not in high:
            return high
        ex_sls = set()
        ex_id = set()
        exclude = high.pop(u'__exclude__')
        for exc in exclude:
            if isinstance(exc, six.string_types):
                # The exclude statement is a string, assume it is an sls
                ex_sls.add(exc)
            if isinstance(exc, dict):
                # Explicitly declared exclude
                if len(exc) != 1:
                    continue
                key = next(six.iterkeys(exc))
                if key == u'sls':
                    ex_sls.add(exc[u'sls'])
                elif key == u'id':
                    ex_id.add(exc[u'id'])
        # Now the excludes have been simplified, use them
        if ex_sls:
            # There are sls excludes, find the associtaed ids
            for name, body in six.iteritems(high):
                if name.startswith(u'__'):
                    continue
                if body.get(u'__sls__', u'') in ex_sls:
                    ex_id.add(name)
        for id_ in ex_id:
            if id_ in high:
                high.pop(id_)
        return high


class State(object):
    '''
    Class used to execute salt states
    '''
    def __init__(
            self,
            opts,
            pillar_override=None,
            jid=None,
            pillar_enc=None,
            proxy=None,
            context=None,
            mocked=False,
            loader=u'states',
            initial_pillar=None):
        self.states_loader = loader
        if u'grains' not in opts:
            opts[u'grains'] = salt.loader.grains(opts)
        self.opts = opts
        self.proxy = proxy
        self._pillar_override = pillar_override
        if pillar_enc is not None:
            try:
                pillar_enc = pillar_enc.lower()
            except AttributeError:
                pillar_enc = str(pillar_enc).lower()
        self._pillar_enc = pillar_enc
        if initial_pillar is not None:
            self.opts[u'pillar'] = initial_pillar
            if self._pillar_override:
                self.opts[u'pillar'] = salt.utils.dictupdate.merge(
                    self.opts[u'pillar'],
                    self._pillar_override,
                    self.opts.get(u'pillar_source_merging_strategy', u'smart'),
                    self.opts.get(u'renderer', u'yaml'),
                    self.opts.get(u'pillar_merge_lists', False))
        else:
            self.opts[u'pillar'] = self._gather_pillar()
        self.state_con = context or {}
        self.load_modules()
        self.active = set()
        self.mod_init = set()
        self.pre = {}
        self.__run_num = 0
        self.jid = jid
        self.instance_id = str(id(self))
        self.inject_globals = {}
        self.mocked = mocked

    def _gather_pillar(self):
        '''
        Whenever a state run starts, gather the pillar data fresh
        '''
        if self._pillar_override:
            if self._pillar_enc:
                try:
                    self._pillar_override = salt.utils.crypt.decrypt(
                        self._pillar_override,
                        self._pillar_enc,
                        translate_newlines=True,
                        renderers=getattr(self, u'rend', None),
                        opts=self.opts,
                        valid_rend=self.opts[u'decrypt_pillar_renderers'])
                except Exception as exc:
                    log.error(u'Failed to decrypt pillar override: %s', exc)

            if isinstance(self._pillar_override, six.string_types):
                # This can happen if an entire pillar dictionary was passed as
                # a single encrypted string. The override will have been
                # decrypted above, and should now be a stringified dictionary.
                # Use the YAML loader to convert that to a Python dictionary.
                try:
                    self._pillar_override = yamlloader.load(
                        self._pillar_override,
                        Loader=yamlloader.SaltYamlSafeLoader)
                except Exception as exc:
                    log.error(u'Failed to load CLI pillar override')
                    log.exception(exc)

            if not isinstance(self._pillar_override, dict):
                log.error(u'Pillar override was not passed as a dictionary')
                self._pillar_override = None

        pillar = salt.pillar.get_pillar(
                self.opts,
                self.opts[u'grains'],
                self.opts[u'id'],
                self.opts[u'environment'],
                pillar_override=self._pillar_override,
                pillarenv=self.opts.get(u'pillarenv'))
        return pillar.compile_pillar()

    def _mod_init(self, low):
        '''
        Check the module initialization function, if this is the first run
        of a state package that has a mod_init function, then execute the
        mod_init function in the state module.
        '''
        # ensure that the module is loaded
        try:
            self.states[u'{0}.{1}'.format(low[u'state'], low[u'fun'])]  # pylint: disable=W0106
        except KeyError:
            return
        minit = u'{0}.mod_init'.format(low[u'state'])
        if low[u'state'] not in self.mod_init:
            if minit in self.states._dict:
                mret = self.states[minit](low)
                if not mret:
                    return
                self.mod_init.add(low[u'state'])

    def _mod_aggregate(self, low, running, chunks):
        '''
        Execute the aggregation systems to runtime modify the low chunk
        '''
        agg_opt = self.functions[u'config.option'](u'state_aggregate')
        if u'aggregate' in low:
            agg_opt = low[u'aggregate']
        if agg_opt is True:
            agg_opt = [low[u'state']]
        elif not isinstance(agg_opt, list):
            return low
        if low[u'state'] in agg_opt and not low.get(u'__agg__'):
            agg_fun = u'{0}.mod_aggregate'.format(low[u'state'])
            if agg_fun in self.states:
                try:
                    low = self.states[agg_fun](low, chunks, running)
                    low[u'__agg__'] = True
                except TypeError:
                    log.error(u'Failed to execute aggregate for state %s', low[u'state'])
        return low

    def _run_check(self, low_data):
        '''
        Check that unless doesn't return 0, and that onlyif returns a 0.
        '''
        ret = {u'result': False}
        cmd_opts = {}

        if u'shell' in self.opts[u'grains']:
            cmd_opts[u'shell'] = self.opts[u'grains'].get(u'shell')
        if u'onlyif' in low_data:
            if not isinstance(low_data[u'onlyif'], list):
                low_data_onlyif = [low_data[u'onlyif']]
            else:
                low_data_onlyif = low_data[u'onlyif']
            for entry in low_data_onlyif:
                if not isinstance(entry, six.string_types):
                    ret.update({u'comment': u'onlyif execution failed, bad type passed', u'result': False})
                    return ret
                cmd = self.functions[u'cmd.retcode'](
                    entry, ignore_retcode=True, python_shell=True, **cmd_opts)
                log.debug(u'Last command return code: %s', cmd)
                if cmd != 0 and ret[u'result'] is False:
                    ret.update({u'comment': u'onlyif execution failed',
                                u'skip_watch': True,
                                u'result': True})
                    return ret
                elif cmd == 0:
                    ret.update({u'comment': u'onlyif execution succeeded', u'result': False})
            return ret

        if u'unless' in low_data:
            if not isinstance(low_data[u'unless'], list):
                low_data_unless = [low_data[u'unless']]
            else:
                low_data_unless = low_data[u'unless']
            for entry in low_data_unless:
                if not isinstance(entry, six.string_types):
                    ret.update({u'comment': u'unless execution failed, bad type passed', u'result': False})
                    return ret
                cmd = self.functions[u'cmd.retcode'](
                    entry, ignore_retcode=True, python_shell=True, **cmd_opts)
                log.debug(u'Last command return code: %s', cmd)
                if cmd == 0 and ret[u'result'] is False:
                    ret.update({u'comment': u'unless execution succeeded',
                                u'skip_watch': True,
                                u'result': True})
                elif cmd != 0:
                    ret.update({u'comment': u'unless execution failed', u'result': False})
                    return ret

        # No reason to stop, return ret
        return ret

    def _run_check_cmd(self, low_data):
        '''
        Alter the way a successful state run is determined
        '''
        ret = {u'result': False}
        cmd_opts = {}
        if u'shell' in self.opts[u'grains']:
            cmd_opts[u'shell'] = self.opts[u'grains'].get(u'shell')
        for entry in low_data[u'check_cmd']:
            cmd = self.functions[u'cmd.retcode'](
                entry, ignore_retcode=True, python_shell=True, **cmd_opts)
            log.debug(u'Last command return code: %s', cmd)
            if cmd == 0 and ret[u'result'] is False:
                ret.update({u'comment': u'check_cmd determined the state succeeded', u'result': True})
            elif cmd != 0:
                ret.update({u'comment': u'check_cmd determined the state failed', u'result': False})
                return ret
        return ret

    def reset_run_num(self):
        '''
        Rest the run_num value to 0
        '''
        self.__run_num = 0

    def _load_states(self):
        '''
        Read the state loader value and loadup the correct states subsystem
        '''
        if self.states_loader == u'thorium':
            self.states = salt.loader.thorium(self.opts, self.functions, {})  # TODO: Add runners, proxy?
        else:
            self.states = salt.loader.states(self.opts, self.functions, self.utils,
                                             self.serializers, proxy=self.proxy)

    def load_modules(self, data=None, proxy=None):
        '''
        Load the modules into the state
        '''
        log.info(u'Loading fresh modules for state activity')
        self.utils = salt.loader.utils(self.opts)
        self.functions = salt.loader.minion_mods(self.opts, self.state_con,
                                                 utils=self.utils,
                                                 proxy=self.proxy)
        if isinstance(data, dict):
            if data.get(u'provider', False):
                if isinstance(data[u'provider'], six.string_types):
                    providers = [{data[u'state']: data[u'provider']}]
                elif isinstance(data[u'provider'], list):
                    providers = data[u'provider']
                else:
                    providers = {}
                for provider in providers:
                    for mod in provider:
                        funcs = salt.loader.raw_mod(self.opts,
                                provider[mod],
                                self.functions)
                        if funcs:
                            for func in funcs:
                                f_key = u'{0}{1}'.format(
                                        mod,
                                        func[func.rindex(u'.'):]
                                        )
                                self.functions[f_key] = funcs[func]
        self.serializers = salt.loader.serializers(self.opts)
        self._load_states()
        self.rend = salt.loader.render(self.opts, self.functions,
                                       states=self.states, proxy=self.proxy)

    def module_refresh(self):
        '''
        Refresh all the modules
        '''
        log.debug(u'Refreshing modules...')
        if self.opts[u'grains'].get(u'os') != u'MacOS':
            # In case a package has been installed into the current python
            # process 'site-packages', the 'site' module needs to be reloaded in
            # order for the newly installed package to be importable.
            try:
                reload_module(site)
            except RuntimeError:
                log.error(u'Error encountered during module reload. Modules were not reloaded.')
            except TypeError:
                log.error(u'Error encountered during module reload. Modules were not reloaded.')
        self.load_modules()
        if not self.opts.get(u'local', False) and self.opts.get(u'multiprocessing', True):
            self.functions[u'saltutil.refresh_modules']()

    def check_refresh(self, data, ret):
        '''
        Check to see if the modules for this state instance need to be updated,
        only update if the state is a file or a package and if it changed
        something. If the file function is managed check to see if the file is a
        possible module type, e.g. a python, pyx, or .so. Always refresh if the
        function is recurse, since that can lay down anything.
        '''
        _reload_modules = False
        if data.get(u'reload_grains', False):
            log.debug(u'Refreshing grains...')
            self.opts[u'grains'] = salt.loader.grains(self.opts)
            _reload_modules = True

        if data.get(u'reload_pillar', False):
            log.debug(u'Refreshing pillar...')
            self.opts[u'pillar'] = self._gather_pillar()
            _reload_modules = True

        if not ret[u'changes']:
            if data.get(u'force_reload_modules', False):
                self.module_refresh()
            return

        if data.get(u'reload_modules', False) or _reload_modules:
            # User explicitly requests a reload
            self.module_refresh()
            return

        if data[u'state'] == u'file':
            if data[u'fun'] == u'managed':
                if data[u'name'].endswith(
                    (u'.py', u'.pyx', u'.pyo', u'.pyc', u'.so')):
                    self.module_refresh()
            elif data[u'fun'] == u'recurse':
                self.module_refresh()
            elif data[u'fun'] == u'symlink':
                if u'bin' in data[u'name']:
                    self.module_refresh()
        elif data[u'state'] in (u'pkg', u'ports'):
            self.module_refresh()

    @staticmethod
    def verify_ret(ret):
        '''
        Perform basic verification of the raw state return data
        '''
        if not isinstance(ret, dict):
            raise SaltException(
                u'Malformed state return, return must be a dict'
            )
        bad = []
        for val in [u'name', u'result', u'changes', u'comment']:
            if val not in ret:
                bad.append(val)
        if bad:
            m = u'The following keys were not present in the state return: {0}'
            raise SaltException(m.format(u','.join(bad)))

    @staticmethod
    def munge_ret_for_export(ret):
        '''
        Process raw state return data to make it suitable for export,
        to ensure consistency of the data format seen by external systems
        '''
        # We support lists of strings for ret['comment'] internal
        # to the state system for improved ergonomics.
        # However, to maintain backwards compatability with external tools,
        # the list representation is not allowed to leave the state system,
        # and should be converted like this at external boundaries.
        if isinstance(ret[u'comment'], list):
            ret[u'comment'] = u'\n'.join(ret[u'comment'])

    @staticmethod
    def verify_ret_for_export(ret):
        '''
        Verify the state return data for export outside the state system
        '''
        State.verify_ret(ret)

        for key in [u'name', u'comment']:
            if not isinstance(ret[key], six.string_types):
                msg = (
                    u'The value for the {0} key in the state return '
                    u'must be a string, found {1}'
                )
                raise SaltException(msg.format(key, repr(ret[key])))

        if ret[u'result'] not in [True, False, None]:
            msg = (
                u'The value for the result key in the state return '
                u'must be True, False, or None, found {0}'
            )
            raise SaltException(msg.format(repr(ret[u'result'])))

        if not isinstance(ret[u'changes'], dict):
            msg = (
                u'The value for the changes key in the state return '
                u'must be a dict, found {0}'
            )
            raise SaltException(msg.format(repr(ret[u'changes'])))

    def verify_data(self, data):
        '''
        Verify the data, return an error statement if something is wrong
        '''
        errors = []
        if u'state' not in data:
            errors.append(u'Missing "state" data')
        if u'fun' not in data:
            errors.append(u'Missing "fun" data')
        if u'name' not in data:
            errors.append(u'Missing "name" data')
        if data[u'name'] and not isinstance(data[u'name'], six.string_types):
            errors.append(
                u'ID \'{0}\' {1}is not formed as a string, but is a {2}'.format(
                    data[u'name'],
                    u'in SLS \'{0}\' '.format(data[u'__sls__'])
                        if u'__sls__' in data else u'',
                    type(data[u'name']).__name__
                )
            )
        if errors:
            return errors
        full = data[u'state'] + u'.' + data[u'fun']
        if full not in self.states:
            if u'__sls__' in data:
                errors.append(
                    u'State \'{0}\' was not found in SLS \'{1}\''.format(
                        full,
                        data[u'__sls__']
                        )
                    )
                reason = self.states.missing_fun_string(full)
                if reason:
                    errors.append(u'Reason: {0}'.format(reason))
            else:
                errors.append(
                        u'Specified state \'{0}\' was not found'.format(
                            full
                            )
                        )
        else:
            # First verify that the parameters are met
            aspec = salt.utils.args.get_function_argspec(self.states[full])
            arglen = 0
            deflen = 0
            if isinstance(aspec.args, list):
                arglen = len(aspec.args)
            if isinstance(aspec.defaults, tuple):
                deflen = len(aspec.defaults)
            for ind in range(arglen - deflen):
                if aspec.args[ind] not in data:
                    errors.append(
                        u'Missing parameter {0} for state {1}'.format(
                            aspec.args[ind],
                            full
                        )
                    )
        # If this chunk has a recursive require, then it will cause a
        # recursive loop when executing, check for it
        reqdec = u''
        if u'require' in data:
            reqdec = u'require'
        if u'watch' in data:
            # Check to see if the service has a mod_watch function, if it does
            # not, then just require
            # to just require extend the require statement with the contents
            # of watch so that the mod_watch function is not called and the
            # requisite capability is still used
            if u'{0}.mod_watch'.format(data[u'state']) not in self.states:
                if u'require' in data:
                    data[u'require'].extend(data.pop(u'watch'))
                else:
                    data[u'require'] = data.pop(u'watch')
                reqdec = u'require'
            else:
                reqdec = u'watch'
        if reqdec:
            for req in data[reqdec]:
                reqfirst = next(iter(req))
                if data[u'state'] == reqfirst:
                    if (fnmatch.fnmatch(data[u'name'], req[reqfirst])
                            or fnmatch.fnmatch(data[u'__id__'], req[reqfirst])):
                        err = (u'Recursive require detected in SLS {0} for'
                               u' require {1} in ID {2}').format(
                                   data[u'__sls__'],
                                   req,
                                   data[u'__id__'])
                        errors.append(err)
        return errors

    def verify_high(self, high):
        '''
        Verify that the high data is viable and follows the data structure
        '''
        errors = []
        if not isinstance(high, dict):
            errors.append(u'High data is not a dictionary and is invalid')
        reqs = OrderedDict()
        for name, body in six.iteritems(high):
            try:
                if name.startswith(u'__'):
                    continue
            except AttributeError:
                pass
            if not isinstance(name, six.string_types):
                errors.append(
                    u'ID \'{0}\' in SLS \'{1}\' is not formed as a string, but '
                    u'is a {2}. It may need to be quoted.'.format(
                        name, body[u'__sls__'], type(name).__name__)
                )
            if not isinstance(body, dict):
                err = (u'The type {0} in {1} is not formatted as a dictionary'
                       .format(name, body))
                errors.append(err)
                continue
            for state in body:
                if state.startswith(u'__'):
                    continue
                if body[state] is None:
                    errors.append(
                        u'ID \'{0}\' in SLS \'{1}\' contains a short declaration '
                        u'({2}) with a trailing colon. When not passing any '
                        u'arguments to a state, the colon must be omitted.'
                        .format(name, body[u'__sls__'], state)
                    )
                    continue
                if not isinstance(body[state], list):
                    errors.append(
                        u'State \'{0}\' in SLS \'{1}\' is not formed as a list'
                        .format(name, body[u'__sls__'])
                    )
                else:
                    fun = 0
                    if u'.' in state:
                        fun += 1
                    for arg in body[state]:
                        if isinstance(arg, six.string_types):
                            fun += 1
                            if u' ' in arg.strip():
                                errors.append((u'The function "{0}" in state '
                                u'"{1}" in SLS "{2}" has '
                                u'whitespace, a function with whitespace is '
                                u'not supported, perhaps this is an argument '
                                u'that is missing a ":"').format(
                                    arg,
                                    name,
                                    body[u'__sls__']))
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            #
                            # Add the requires to the reqs dict and check them
                            # all for recursive requisites.
                            argfirst = next(iter(arg))
                            if argfirst == u'names':
                                if not isinstance(arg[argfirst], list):
                                    errors.append(
                                        u'The \'names\' argument in state '
                                        u'\'{0}\' in SLS \'{1}\' needs to be '
                                        u'formed as a list'
                                        .format(name, body[u'__sls__'])
                                    )
                            if argfirst in (u'require', u'watch', u'prereq', u'onchanges'):
                                if not isinstance(arg[argfirst], list):
                                    errors.append(
                                        u'The {0} statement in state \'{1}\' in '
                                        u'SLS \'{2}\' needs to be formed as a '
                                        u'list'.format(argfirst,
                                                      name,
                                                      body[u'__sls__'])
                                    )
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    reqs[name] = OrderedDict(state=state)
                                    for req in arg[argfirst]:
                                        if isinstance(req, six.string_types):
                                            req = {u'id': req}
                                        if not isinstance(req, dict):
                                            err = (u'Requisite declaration {0}'
                                            u' in SLS {1} is not formed as a'
                                            u' single key dictionary').format(
                                                req,
                                                body[u'__sls__'])
                                            errors.append(err)
                                            continue
                                        req_key = next(iter(req))
                                        req_val = req[req_key]
                                        if u'.' in req_key:
                                            errors.append(
                                                u'Invalid requisite type \'{0}\' '
                                                u'in state \'{1}\', in SLS '
                                                u'\'{2}\'. Requisite types must '
                                                u'not contain dots, did you '
                                                u'mean \'{3}\'?'.format(
                                                    req_key,
                                                    name,
                                                    body[u'__sls__'],
                                                    req_key[:req_key.find(u'.')]
                                                )
                                            )
                                        if not ishashable(req_val):
                                            errors.append((
                                                u'Illegal requisite "{0}", '
                                                u'please check your syntax.\n'
                                                ).format(req_val))
                                            continue

                                        # Check for global recursive requisites
                                        reqs[name][req_val] = req_key
                                        # I am going beyond 80 chars on
                                        # purpose, this is just too much
                                        # of a pain to deal with otherwise
                                        if req_val in reqs:
                                            if name in reqs[req_val]:
                                                if reqs[req_val][name] == state:
                                                    if reqs[req_val][u'state'] == reqs[name][req_val]:
                                                        err = (u'A recursive '
                                                        u'requisite was found, SLS '
                                                        u'"{0}" ID "{1}" ID "{2}"'
                                                        ).format(
                                                                body[u'__sls__'],
                                                                name,
                                                                req_val
                                                                )
                                                        errors.append(err)
                                # Make sure that there is only one key in the
                                # dict
                                if len(list(arg)) != 1:
                                    errors.append(
                                        u'Multiple dictionaries defined in '
                                        u'argument of state \'{0}\' in SLS \'{1}\''
                                        .format(name, body[u'__sls__'])
                                    )
                    if not fun:
                        if state == u'require' or state == u'watch':
                            continue
                        errors.append(
                            u'No function declared in state \'{0}\' in SLS \'{1}\''
                            .format(state, body[u'__sls__'])
                        )
                    elif fun > 1:
                        errors.append(
                            u'Too many functions declared in state \'{0}\' in '
                            u'SLS \'{1}\''.format(state, body[u'__sls__'])
                        )
        return errors

    def verify_chunks(self, chunks):
        '''
        Verify the chunks in a list of low data structures
        '''
        err = []
        for chunk in chunks:
            err += self.verify_data(chunk)
        return err

    def order_chunks(self, chunks):
        '''
        Sort the chunk list verifying that the chunks follow the order
        specified in the order options.
        '''
        cap = 1
        for chunk in chunks:
            if u'order' in chunk:
                if not isinstance(chunk[u'order'], int):
                    continue

                chunk_order = chunk[u'order']
                if chunk_order > cap - 1 and chunk_order > 0:
                    cap = chunk_order + 100
        for chunk in chunks:
            if u'order' not in chunk:
                chunk[u'order'] = cap
                continue

            if not isinstance(chunk[u'order'], (int, float)):
                if chunk[u'order'] == u'last':
                    chunk[u'order'] = cap + 1000000
                elif chunk[u'order'] == u'first':
                    chunk[u'order'] = 0
                else:
                    chunk[u'order'] = cap
            if u'name_order' in chunk:
                chunk[u'order'] = chunk[u'order'] + chunk.pop(u'name_order') / 10000.0
            if chunk[u'order'] < 0:
                chunk[u'order'] = cap + 1000000 + chunk[u'order']
        chunks.sort(key=lambda chunk: (chunk[u'order'], u'{0[state]}{0[name]}{0[fun]}'.format(chunk)))
        return chunks

    def compile_high_data(self, high, orchestration_jid=None):
        '''
        "Compile" the high data as it is retrieved from the CLI or YAML into
        the individual state executor structures
        '''
        chunks = []
        for name, body in six.iteritems(high):
            if name.startswith(u'__'):
                continue
            for state, run in six.iteritems(body):
                funcs = set()
                names = []
                if state.startswith(u'__'):
                    continue
                chunk = {u'state': state,
                         u'name': name}
                if orchestration_jid is not None:
                    chunk[u'__orchestration_jid__'] = orchestration_jid
                if u'__sls__' in body:
                    chunk[u'__sls__'] = body[u'__sls__']
                if u'__env__' in body:
                    chunk[u'__env__'] = body[u'__env__']
                chunk[u'__id__'] = name
                for arg in run:
                    if isinstance(arg, six.string_types):
                        funcs.add(arg)
                        continue
                    if isinstance(arg, dict):
                        for key, val in six.iteritems(arg):
                            if key == u'names':
                                for _name in val:
                                    if _name not in names:
                                        names.append(_name)
                            elif key == u'state':
                                # Don't pass down a state override
                                continue
                            elif (key == u'name' and
                                  not isinstance(val, six.string_types)):
                                # Invalid name, fall back to ID
                                chunk[key] = name
                            else:
                                chunk[key] = val
                if names:
                    name_order = 1
                    for entry in names:
                        live = copy.deepcopy(chunk)
                        if isinstance(entry, dict):
                            low_name = next(six.iterkeys(entry))
                            live[u'name'] = low_name
                            list(map(live.update, entry[low_name]))
                        else:
                            live[u'name'] = entry
                        live[u'name_order'] = name_order
                        name_order += 1
                        for fun in funcs:
                            live[u'fun'] = fun
                            chunks.append(live)
                else:
                    live = copy.deepcopy(chunk)
                    for fun in funcs:
                        live[u'fun'] = fun
                        chunks.append(live)
        chunks = self.order_chunks(chunks)
        return chunks

    def reconcile_extend(self, high):
        '''
        Pull the extend data and add it to the respective high data
        '''
        errors = []
        if u'__extend__' not in high:
            return high, errors
        ext = high.pop(u'__extend__')
        for ext_chunk in ext:
            for name, body in six.iteritems(ext_chunk):
                if name not in high:
                    state_type = next(
                        x for x in body if not x.startswith(u'__')
                    )
                    # Check for a matching 'name' override in high data
                    ids = find_name(name, state_type, high)
                    if len(ids) != 1:
                        errors.append(
                            u'Cannot extend ID \'{0}\' in \'{1}:{2}\'. It is not '
                            u'part of the high state.\n'
                            u'This is likely due to a missing include statement '
                            u'or an incorrectly typed ID.\nEnsure that a '
                            u'state with an ID of \'{0}\' is available\nin '
                            u'environment \'{1}\' and to SLS \'{2}\''.format(
                                name,
                                body.get(u'__env__', u'base'),
                                body.get(u'__sls__', u'base'))
                            )
                        continue
                    else:
                        name = ids[0][0]

                for state, run in six.iteritems(body):
                    if state.startswith(u'__'):
                        continue
                    if state not in high[name]:
                        high[name][state] = run
                        continue
                    # high[name][state] is extended by run, both are lists
                    for arg in run:
                        update = False
                        for hind in range(len(high[name][state])):
                            if isinstance(arg, six.string_types) and isinstance(high[name][state][hind], six.string_types):
                                # replacing the function, replace the index
                                high[name][state].pop(hind)
                                high[name][state].insert(hind, arg)
                                update = True
                                continue
                            if isinstance(arg, dict) and isinstance(high[name][state][hind], dict):
                                # It is an option, make sure the options match
                                argfirst = next(iter(arg))
                                if argfirst == next(iter(high[name][state][hind])):
                                    # If argfirst is a requisite then we must merge
                                    # our requisite with that of the target state
                                    if argfirst in STATE_REQUISITE_KEYWORDS:
                                        high[name][state][hind][argfirst].extend(arg[argfirst])
                                    # otherwise, its not a requisite and we are just extending (replacing)
                                    else:
                                        high[name][state][hind] = arg
                                    update = True
                                if (argfirst == u'name' and
                                    next(iter(high[name][state][hind])) == u'names'):
                                    # If names are overwritten by name use the name
                                    high[name][state][hind] = arg
                        if not update:
                            high[name][state].append(arg)
        return high, errors

    def apply_exclude(self, high):
        '''
        Read in the __exclude__ list and remove all excluded objects from the
        high data
        '''
        if u'__exclude__' not in high:
            return high
        ex_sls = set()
        ex_id = set()
        exclude = high.pop(u'__exclude__')
        for exc in exclude:
            if isinstance(exc, six.string_types):
                # The exclude statement is a string, assume it is an sls
                ex_sls.add(exc)
            if isinstance(exc, dict):
                # Explicitly declared exclude
                if len(exc) != 1:
                    continue
                key = next(six.iterkeys(exc))
                if key == u'sls':
                    ex_sls.add(exc[u'sls'])
                elif key == u'id':
                    ex_id.add(exc[u'id'])
        # Now the excludes have been simplified, use them
        if ex_sls:
            # There are sls excludes, find the associated ids
            for name, body in six.iteritems(high):
                if name.startswith(u'__'):
                    continue
                sls = body.get(u'__sls__', u'')
                if not sls:
                    continue
                for ex_ in ex_sls:
                    if fnmatch.fnmatch(sls, ex_):
                        ex_id.add(name)
        for id_ in ex_id:
            if id_ in high:
                high.pop(id_)
        return high

    def requisite_in(self, high):
        '''
        Extend the data reference with requisite_in arguments
        '''
        req_in = set([
            u'require_in',
            u'watch_in',
            u'onfail_in',
            u'onchanges_in',
            u'use',
            u'use_in',
            u'prereq',
            u'prereq_in',
            ])
        req_in_all = req_in.union(
                set([
                    u'require',
                    u'watch',
                    u'onfail',
                    u'onfail_stop',
                    u'onchanges',
                    ]))
        extend = {}
        errors = []
        for id_, body in six.iteritems(high):
            if not isinstance(body, dict):
                continue
            for state, run in six.iteritems(body):
                if state.startswith(u'__'):
                    continue
                for arg in run:
                    if isinstance(arg, dict):
                        # It is not a function, verify that the arg is a
                        # requisite in statement
                        if len(arg) < 1:
                            # Empty arg dict
                            # How did we get this far?
                            continue
                        # Split out the components
                        key = next(iter(arg))
                        if key not in req_in:
                            continue
                        rkey = key.split(u'_')[0]
                        items = arg[key]
                        if isinstance(items, dict):
                            # Formatted as a single req_in
                            for _state, name in six.iteritems(items):

                                # Not a use requisite_in
                                found = False
                                if name not in extend:
                                    extend[name] = OrderedDict()
                                if u'.' in _state:
                                    errors.append(
                                        u'Invalid requisite in {0}: {1} for '
                                        u'{2}, in SLS \'{3}\'. Requisites must '
                                        u'not contain dots, did you mean \'{4}\'?'
                                        .format(
                                            rkey,
                                            _state,
                                            name,
                                            body[u'__sls__'],
                                            _state[:_state.find(u'.')]
                                        )
                                    )
                                    _state = _state.split(u'.')[0]
                                if _state not in extend[name]:
                                    extend[name][_state] = []
                                extend[name][u'__env__'] = body[u'__env__']
                                extend[name][u'__sls__'] = body[u'__sls__']
                                for ind in range(len(extend[name][_state])):
                                    if next(iter(
                                        extend[name][_state][ind])) == rkey:
                                        # Extending again
                                        extend[name][_state][ind][rkey].append(
                                                {state: id_}
                                                )
                                        found = True
                                if found:
                                    continue
                                # The rkey is not present yet, create it
                                extend[name][_state].append(
                                        {rkey: [{state: id_}]}
                                        )

                        if isinstance(items, list):
                            # Formed as a list of requisite additions
                            hinges = []
                            for ind in items:
                                if not isinstance(ind, dict):
                                    # Malformed req_in
                                    continue
                                if len(ind) < 1:
                                    continue
                                pstate = next(iter(ind))
                                pname = ind[pstate]
                                if pstate == u'sls':
                                    # Expand hinges here
                                    hinges = find_sls_ids(pname, high)
                                else:
                                    hinges.append((pname, pstate))
                                if u'.' in pstate:
                                    errors.append(
                                        u'Invalid requisite in {0}: {1} for '
                                        u'{2}, in SLS \'{3}\'. Requisites must '
                                        u'not contain dots, did you mean \'{4}\'?'
                                        .format(
                                            rkey,
                                            pstate,
                                            pname,
                                            body[u'__sls__'],
                                            pstate[:pstate.find(u'.')]
                                        )
                                    )
                                    pstate = pstate.split(u".")[0]
                                for tup in hinges:
                                    name, _state = tup
                                    if key == u'prereq_in':
                                        # Add prerequired to origin
                                        if id_ not in extend:
                                            extend[id_] = OrderedDict()
                                        if state not in extend[id_]:
                                            extend[id_][state] = []
                                        extend[id_][state].append(
                                                {u'prerequired': [{_state: name}]}
                                                )
                                    if key == u'prereq':
                                        # Add prerequired to prereqs
                                        ext_ids = find_name(name, _state, high)
                                        for ext_id, _req_state in ext_ids:
                                            if ext_id not in extend:
                                                extend[ext_id] = OrderedDict()
                                            if _req_state not in extend[ext_id]:
                                                extend[ext_id][_req_state] = []
                                            extend[ext_id][_req_state].append(
                                                    {u'prerequired': [{state: id_}]}
                                                    )
                                        continue
                                    if key == u'use_in':
                                        # Add the running states args to the
                                        # use_in states
                                        ext_ids = find_name(name, _state, high)
                                        for ext_id, _req_state in ext_ids:
                                            if not ext_id:
                                                continue
                                            ext_args = state_args(ext_id, _state, high)
                                            if ext_id not in extend:
                                                extend[ext_id] = OrderedDict()
                                            if _req_state not in extend[ext_id]:
                                                extend[ext_id][_req_state] = []
                                            ignore_args = req_in_all.union(ext_args)
                                            for arg in high[id_][state]:
                                                if not isinstance(arg, dict):
                                                    continue
                                                if len(arg) != 1:
                                                    continue
                                                if next(iter(arg)) in ignore_args:
                                                    continue
                                                # Don't use name or names
                                                if next(six.iterkeys(arg)) == u'name':
                                                    continue
                                                if next(six.iterkeys(arg)) == u'names':
                                                    continue
                                                extend[ext_id][_req_state].append(arg)
                                        continue
                                    if key == u'use':
                                        # Add the use state's args to the
                                        # running state
                                        ext_ids = find_name(name, _state, high)
                                        for ext_id, _req_state in ext_ids:
                                            if not ext_id:
                                                continue
                                            loc_args = state_args(id_, state, high)
                                            if id_ not in extend:
                                                extend[id_] = OrderedDict()
                                            if state not in extend[id_]:
                                                extend[id_][state] = []
                                            ignore_args = req_in_all.union(loc_args)
                                            for arg in high[ext_id][_req_state]:
                                                if not isinstance(arg, dict):
                                                    continue
                                                if len(arg) != 1:
                                                    continue
                                                if next(iter(arg)) in ignore_args:
                                                    continue
                                                # Don't use name or names
                                                if next(six.iterkeys(arg)) == u'name':
                                                    continue
                                                if next(six.iterkeys(arg)) == u'names':
                                                    continue
                                                extend[id_][state].append(arg)
                                        continue
                                    found = False
                                    if name not in extend:
                                        extend[name] = OrderedDict()
                                    if _state not in extend[name]:
                                        extend[name][_state] = []
                                    extend[name][u'__env__'] = body[u'__env__']
                                    extend[name][u'__sls__'] = body[u'__sls__']
                                    for ind in range(len(extend[name][_state])):
                                        if next(iter(
                                            extend[name][_state][ind])) == rkey:
                                            # Extending again
                                            extend[name][_state][ind][rkey].append(
                                                    {state: id_}
                                                    )
                                            found = True
                                    if found:
                                        continue
                                    # The rkey is not present yet, create it
                                    extend[name][_state].append(
                                            {rkey: [{state: id_}]}
                                            )
        high[u'__extend__'] = []
        for key, val in six.iteritems(extend):
            high[u'__extend__'].append({key: val})
        req_in_high, req_in_errors = self.reconcile_extend(high)
        errors.extend(req_in_errors)
        return req_in_high, errors

    def _call_parallel_target(self, cdata, low):
        '''
        The target function to call that will create the parallel thread/process
        '''
        tag = _gen_tag(low)
        try:
            ret = self.states[cdata[u'full']](*cdata[u'args'],
                                             **cdata[u'kwargs'])
        except Exception:
            trb = traceback.format_exc()
            # There are a number of possibilities to not have the cdata
            # populated with what we might have expected, so just be smart
            # enough to not raise another KeyError as the name is easily
            # guessable and fallback in all cases to present the real
            # exception to the user
            if len(cdata[u'args']) > 0:
                name = cdata[u'args'][0]
            elif u'name' in cdata[u'kwargs']:
                name = cdata[u'kwargs'][u'name']
            else:
                name = low.get(u'name', low.get(u'__id__'))
            ret = {
                u'result': False,
                u'name': name,
                u'changes': {},
                u'comment': u'An exception occurred in this state: {0}'.format(
                    trb)
            }
        troot = os.path.join(self.opts[u'cachedir'], self.jid)
        tfile = os.path.join(troot, _clean_tag(tag))
        if not os.path.isdir(troot):
            try:
                os.makedirs(troot)
            except OSError:
                # Looks like the directory was created between the check
                # and the attempt, we are safe to pass
                pass
        with salt.utils.files.fopen(tfile, u'wb+') as fp_:
            fp_.write(msgpack.dumps(ret))

    def call_parallel(self, cdata, low):
        '''
        Call the state defined in the given cdata in parallel
        '''
        proc = salt.utils.process.MultiprocessingProcess(
                target=self._call_parallel_target,
                args=(cdata, low))
        proc.start()
        ret = {u'name': cdata[u'args'][0],
                u'result': None,
                u'changes': {},
                u'comment': u'Started in a seperate process',
                u'proc': proc}
        return ret

    def call(self, low, chunks=None, running=None, retries=1):
        '''
        Call a state directly with the low data structure, verify data
        before processing.
        '''
        utc_start_time = datetime.datetime.utcnow()
        local_start_time = utc_start_time - (datetime.datetime.utcnow() - datetime.datetime.now())
        log.info(u'Running state [%s] at time %s',
            low[u'name'].strip() if isinstance(low[u'name'], six.string_types)
                else low[u'name'],
            local_start_time.time().isoformat()
        )
        errors = self.verify_data(low)
        if errors:
            ret = {
                u'result': False,
                u'name': low[u'name'],
                u'changes': {},
                u'comment': u'',
                }
            for err in errors:
                ret[u'comment'] += u'{0}\n'.format(err)
            ret[u'__run_num__'] = self.__run_num
            self.__run_num += 1
            format_log(ret)
            self.check_refresh(low, ret)
            return ret
        else:
            ret = {u'result': False, u'name': low[u'name'], u'changes': {}}

        self.state_con[u'runas'] = low.get(u'runas', None)

        if low[u'state'] == u'cmd' and u'password' in low:
            self.state_con[u'runas_password'] = low[u'password']
        else:
            self.state_con[u'runas_password'] = low.get(u'runas_password', None)

        if not low.get(u'__prereq__'):
            log.info(
                u'Executing state %s.%s for [%s]',
                low[u'state'],
                low[u'fun'],
                low[u'name'].strip() if isinstance(low[u'name'], six.string_types)
                    else low[u'name']
            )

        if u'provider' in low:
            self.load_modules(low)

        state_func_name = u'{0[state]}.{0[fun]}'.format(low)
        cdata = salt.utils.args.format_call(
            self.states[state_func_name],
            low,
            initial_ret={u'full': state_func_name},
            expected_extra_kws=STATE_INTERNAL_KEYWORDS
        )
        inject_globals = {
            # Pass a copy of the running dictionary, the low state chunks and
            # the current state dictionaries.
            # We pass deep copies here because we don't want any misbehaving
            # state module to change these at runtime.
            u'__low__': immutabletypes.freeze(low),
            u'__running__': immutabletypes.freeze(running) if running else {},
            u'__instance_id__': self.instance_id,
            u'__lowstate__': immutabletypes.freeze(chunks) if chunks else {}
        }

        if self.inject_globals:
            inject_globals.update(self.inject_globals)

        if low.get(u'__prereq__'):
            test = sys.modules[self.states[cdata[u'full']].__module__].__opts__[u'test']
            sys.modules[self.states[cdata[u'full']].__module__].__opts__[u'test'] = True
        try:
            # Let's get a reference to the salt environment to use within this
            # state call.
            #
            # If the state function accepts an 'env' keyword argument, it
            # allows the state to be overridden(we look for that in cdata). If
            # that's not found in cdata, we look for what we're being passed in
            # the original data, namely, the special dunder __env__. If that's
            # not found we default to 'base'
            if (u'unless' in low and u'{0[state]}.mod_run_check'.format(low) not in self.states) or \
                    (u'onlyif' in low and u'{0[state]}.mod_run_check'.format(low) not in self.states):
                ret.update(self._run_check(low))

            if u'saltenv' in low:
                inject_globals[u'__env__'] = six.text_type(low[u'saltenv'])
            elif isinstance(cdata[u'kwargs'].get(u'env', None), six.string_types):
                # User is using a deprecated env setting which was parsed by
                # format_call.
                # We check for a string type since module functions which
                # allow setting the OS environ also make use of the "env"
                # keyword argument, which is not a string
                inject_globals[u'__env__'] = six.text_type(cdata[u'kwargs'][u'env'])
            elif u'__env__' in low:
                # The user is passing an alternative environment using __env__
                # which is also not the appropriate choice, still, handle it
                inject_globals[u'__env__'] = six.text_type(low[u'__env__'])
            else:
                # Let's use the default environment
                inject_globals[u'__env__'] = u'base'

            if u'__orchestration_jid__' in low:
                inject_globals[u'__orchestration_jid__'] = \
                    low[u'__orchestration_jid__']

            if u'result' not in ret or ret[u'result'] is False:
                self.states.inject_globals = inject_globals
                if self.mocked:
                    ret = mock_ret(cdata)
                else:
                    # Execute the state function
                    if not low.get(u'__prereq__') and low.get(u'parallel'):
                        # run the state call in parallel, but only if not in a prereq
                        ret = self.call_parallel(cdata, low)
                    else:
                        ret = self.states[cdata[u'full']](*cdata[u'args'],
                                                          **cdata[u'kwargs'])
                self.states.inject_globals = {}
            if u'check_cmd' in low and u'{0[state]}.mod_run_check_cmd'.format(low) not in self.states:
                ret.update(self._run_check_cmd(low))
            self.verify_ret(ret)
            self.munge_ret_for_export(ret)
        except Exception:
            trb = traceback.format_exc()
            # There are a number of possibilities to not have the cdata
            # populated with what we might have expected, so just be smart
            # enough to not raise another KeyError as the name is easily
            # guessable and fallback in all cases to present the real
            # exception to the user
            if len(cdata[u'args']) > 0:
                name = cdata[u'args'][0]
            elif u'name' in cdata[u'kwargs']:
                name = cdata[u'kwargs'][u'name']
            else:
                name = low.get(u'name', low.get(u'__id__'))
            ret = {
                u'result': False,
                u'name': name,
                u'changes': {},
                u'comment': u'An exception occurred in this state: {0}'.format(
                    trb)
            }
        finally:
            if low.get(u'__prereq__'):
                sys.modules[self.states[cdata[u'full']].__module__].__opts__[
                    u'test'] = test

            self.state_con.pop('runas')
            self.state_con.pop('runas_password')
            self.verify_ret_for_export(ret)

        # If format_call got any warnings, let's show them to the user
        if u'warnings' in cdata:
            ret.setdefault(u'warnings', []).extend(cdata[u'warnings'])

        if u'provider' in low:
            self.load_modules()

        if low.get(u'__prereq__'):
            low[u'__prereq__'] = False
            return ret

        ret[u'__sls__'] = low.get(u'__sls__')
        ret[u'__run_num__'] = self.__run_num
        self.__run_num += 1
        format_log(ret)
        self.check_refresh(low, ret)
        utc_finish_time = datetime.datetime.utcnow()
        timezone_delta = datetime.datetime.utcnow() - datetime.datetime.now()
        local_finish_time = utc_finish_time - timezone_delta
        local_start_time = utc_start_time - timezone_delta
        ret[u'start_time'] = local_start_time.time().isoformat()
        delta = (utc_finish_time - utc_start_time)
        # duration in milliseconds.microseconds
        duration = (delta.seconds * 1000000 + delta.microseconds)/1000.0
        ret[u'duration'] = duration
        ret[u'__id__'] = low[u'__id__']
        log.info(
            u'Completed state [%s] at time %s (duration_in_ms=%s)',
            low[u'name'].strip() if isinstance(low[u'name'], six.string_types)
                else low[u'name'],
            local_finish_time.time().isoformat(),
            duration
        )
        if u'retry' in low:
            low[u'retry'] = self.verify_retry_data(low[u'retry'])
            if not sys.modules[self.states[cdata[u'full']].__module__].__opts__[u'test']:
                if low[u'retry'][u'until'] != ret[u'result']:
                    if low[u'retry'][u'attempts'] > retries:
                        interval = low[u'retry'][u'interval']
                        if low[u'retry'][u'splay'] != 0:
                            interval = interval + random.randint(0, low[u'retry'][u'splay'])
                        log.info(
                            u'State result does not match retry until value, '
                            u'state will be re-run in %s seconds', interval
                        )
                        self.functions[u'test.sleep'](interval)
                        retry_ret = self.call(low, chunks, running, retries=retries+1)
                        orig_ret = ret
                        ret = retry_ret
                        ret[u'comment'] = u'\n'.join(
                                [(
                                     u'Attempt {0}: Returned a result of "{1}", '
                                     u'with the following comment: "{2}"'.format(
                                         retries,
                                         orig_ret[u'result'],
                                         orig_ret[u'comment'])
                                 ),
                                 u'' if not ret[u'comment'] else ret[u'comment']])
                        ret[u'duration'] = ret[u'duration'] + orig_ret[u'duration'] + (interval * 1000)
                        if retries == 1:
                            ret[u'start_time'] = orig_ret[u'start_time']
            else:
                ret[u'comment'] = u'  '.join(
                        [u'' if not ret[u'comment'] else ret[u'comment'],
                         (u'The state would be retried every {1} seconds '
                          u'(with a splay of up to {3} seconds) '
                          u'a maximum of {0} times or until a result of {2} '
                          u'is returned').format(low[u'retry'][u'attempts'],
                                                low[u'retry'][u'interval'],
                                                low[u'retry'][u'until'],
                                                low[u'retry'][u'splay'])])
        return ret

    def verify_retry_data(self, retry_data):
        '''
        verifies the specified retry data
        '''
        retry_defaults = {
                u'until': True,
                u'attempts': 2,
                u'splay': 0,
                u'interval': 30,
        }
        expected_data = {
            u'until': bool,
            u'attempts': int,
            u'interval': int,
            u'splay': int,
        }
        validated_retry_data = {}
        if isinstance(retry_data, dict):
            for expected_key, value_type in six.iteritems(expected_data):
                if expected_key in retry_data:
                    if isinstance(retry_data[expected_key], value_type):
                        validated_retry_data[expected_key] = retry_data[expected_key]
                    else:
                        log.warning(
                            u'An invalid value was passed for the retry %s, '
                            u'using default value \'%s\'',
                            expected_key, retry_defaults[expected_key]
                        )
                        validated_retry_data[expected_key] = retry_defaults[expected_key]
                else:
                    validated_retry_data[expected_key] = retry_defaults[expected_key]
        else:
            log.warning((u'State is set to retry, but a valid dict for retry '
                         u'configuration was not found.  Using retry defaults'))
            validated_retry_data = retry_defaults
        return validated_retry_data

    def call_chunks(self, chunks):
        '''
        Iterate over a list of chunks and call them, checking for requires.
        '''
        # Check for any disabled states
        disabled = {}
        if u'state_runs_disabled' in self.opts[u'grains']:
            for low in chunks[:]:
                state_ = u'{0}.{1}'.format(low[u'state'], low[u'fun'])
                for pat in self.opts[u'grains'][u'state_runs_disabled']:
                    if fnmatch.fnmatch(state_, pat):
                        comment = (
                                    u'The state function "{0}" is currently disabled by "{1}", '
                                    u'to re-enable, run state.enable {1}.'
                                  ).format(
                                    state_,
                                    pat,
                                  )
                        _tag = _gen_tag(low)
                        disabled[_tag] = {u'changes': {},
                                          u'result': False,
                                          u'comment': comment,
                                          u'__run_num__': self.__run_num,
                                          u'__sls__': low[u'__sls__']}
                        self.__run_num += 1
                        chunks.remove(low)
                        break
        running = {}
        for low in chunks:
            if u'__FAILHARD__' in running:
                running.pop(u'__FAILHARD__')
                return running
            tag = _gen_tag(low)
            if tag not in running:
                running = self.call_chunk(low, running, chunks)
                if self.check_failhard(low, running):
                    return running
            self.active = set()
        while True:
            if self.reconcile_procs(running):
                break
            time.sleep(0.01)
        ret = dict(list(disabled.items()) + list(running.items()))
        return ret

    def check_failhard(self, low, running):
        '''
        Check if the low data chunk should send a failhard signal
        '''
        tag = _gen_tag(low)
        if self.opts.get(u'test', False):
            return False
        if (low.get(u'failhard', False) or self.opts[u'failhard']) and tag in running:
            if running[tag][u'result'] is None:
                return False
            return not running[tag][u'result']
        return False

    def reconcile_procs(self, running):
        '''
        Check the running dict for processes and resolve them
        '''
        retset = set()
        for tag in running:
            proc = running[tag].get(u'proc')
            if proc:
                if not proc.is_alive():
                    ret_cache = os.path.join(self.opts[u'cachedir'], self.jid, _clean_tag(tag))
                    if not os.path.isfile(ret_cache):
                        ret = {u'result': False,
                               u'comment': u'Parallel process failed to return',
                               u'name': running[tag][u'name'],
                               u'changes': {}}
                    try:
                        with salt.utils.files.fopen(ret_cache, u'rb') as fp_:
                            ret = msgpack.loads(fp_.read())
                    except (OSError, IOError):
                        ret = {u'result': False,
                               u'comment': u'Parallel cache failure',
                               u'name': running[tag][u'name'],
                               u'changes': {}}
                    running[tag].update(ret)
                    running[tag].pop(u'proc')
                else:
                    retset.add(False)
        return False not in retset

    def check_requisite(self, low, running, chunks, pre=False):
        '''
        Look into the running data to check the status of all requisite
        states
        '''
        present = False
        # If mod_watch is not available make it a require
        if u'watch' in low:
            if u'{0}.mod_watch'.format(low[u'state']) not in self.states:
                if u'require' in low:
                    low[u'require'].extend(low.pop(u'watch'))
                else:
                    low[u'require'] = low.pop(u'watch')
            else:
                present = True
        if u'require' in low:
            present = True
        if u'prerequired' in low:
            present = True
        if u'prereq' in low:
            present = True
        if u'onfail' in low:
            present = True
        if u'onchanges' in low:
            present = True
        if not present:
            return u'met', ()
        self.reconcile_procs(running)
        reqs = {
                u'require': [],
                u'watch': [],
                u'prereq': [],
                u'onfail': [],
                u'onchanges': []}
        if pre:
            reqs[u'prerequired'] = []
        for r_state in reqs:
            if r_state in low and low[r_state] is not None:
                for req in low[r_state]:
                    if isinstance(req, six.string_types):
                        req = {u'id': req}
                    req = trim_req(req)
                    found = False
                    for chunk in chunks:
                        req_key = next(iter(req))
                        req_val = req[req_key]
                        if req_val is None:
                            continue
                        if req_key == u'sls':
                            # Allow requisite tracking of entire sls files
                            if fnmatch.fnmatch(chunk[u'__sls__'], req_val):
                                found = True
                                reqs[r_state].append(chunk)
                            continue
                        try:
                            if isinstance(req_val, six.string_types):
                                if (fnmatch.fnmatch(chunk[u'name'], req_val) or
                                    fnmatch.fnmatch(chunk[u'__id__'], req_val)):
                                    if req_key == u'id' or chunk[u'state'] == req_key:
                                        found = True
                                        reqs[r_state].append(chunk)
                            else:
                                raise KeyError
                        except KeyError as exc:
                            raise SaltRenderError(
                                u'Could not locate requisite of [{0}] present in state with name [{1}]'.format(
                                    req_key, chunk[u'name']))
                        except TypeError:
                            # On Python 2, the above req_val, being an OrderedDict, will raise a KeyError,
                            # however on Python 3 it will raise a TypeError
                            # This was found when running tests.unit.test_state.StateCompilerTestCase.test_render_error_on_invalid_requisite
                            raise SaltRenderError(
                                u'Could not locate requisite of [{0}] present in state with name [{1}]'.format(
                                    req_key, chunk[u'name']))
                    if not found:
                        return u'unmet', ()
        fun_stats = set()
        for r_state, chunks in six.iteritems(reqs):
            if r_state == u'prereq':
                run_dict = self.pre
            else:
                run_dict = running
            for chunk in chunks:
                tag = _gen_tag(chunk)
                if tag not in run_dict:
                    fun_stats.add(u'unmet')
                    continue
                if run_dict[tag].get(u'proc'):
                    # Run in parallel, first wait for a touch and then recheck
                    time.sleep(0.01)
                    return self.check_requisite(low, running, chunks, pre)
                if r_state == u'onfail':
                    if run_dict[tag][u'result'] is True:
                        fun_stats.add(u'onfail')  # At least one state is OK
                        continue
                else:
                    if run_dict[tag][u'result'] is False:
                        fun_stats.add(u'fail')
                        continue
                if r_state == u'onchanges':
                    if not run_dict[tag][u'changes']:
                        fun_stats.add(u'onchanges')
                    else:
                        fun_stats.add(u'onchangesmet')
                    continue
                if r_state == u'watch' and run_dict[tag][u'changes']:
                    fun_stats.add(u'change')
                    continue
                if r_state == u'prereq' and run_dict[tag][u'result'] is None:
                    fun_stats.add(u'premet')
                if r_state == u'prereq' and not run_dict[tag][u'result'] is None:
                    fun_stats.add(u'pre')
                else:
                    fun_stats.add(u'met')

        if u'unmet' in fun_stats:
            status = u'unmet'
        elif u'fail' in fun_stats:
            status = u'fail'
        elif u'pre' in fun_stats:
            if u'premet' in fun_stats:
                status = u'met'
            else:
                status = u'pre'
        elif u'onfail' in fun_stats and u'met' not in fun_stats:
            status = u'onfail'  # all onfail states are OK
        elif u'onchanges' in fun_stats and u'onchangesmet' not in fun_stats:
            status = u'onchanges'
        elif u'change' in fun_stats:
            status = u'change'
        else:
            status = u'met'

        return status, reqs

    def event(self, chunk_ret, length, fire_event=False):
        '''
        Fire an event on the master bus

        If `fire_event` is set to True an event will be sent with the
        chunk name in the tag and the chunk result in the event data.

        If `fire_event` is set to a string such as `mystate/is/finished`,
        an event will be sent with the string added to the tag and the chunk
        result in the event data.

        If the `state_events` is set to True in the config, then after the
        chunk is evaluated an event will be set up to the master with the
        results.
        '''
        if not self.opts.get(u'local') and (self.opts.get(u'state_events', True) or fire_event):
            if not self.opts.get(u'master_uri'):
                ev_func = lambda ret, tag, preload=None: salt.utils.event.get_master_event(
                    self.opts, self.opts[u'sock_dir'], listen=False).fire_event(ret, tag)
            else:
                ev_func = self.functions[u'event.fire_master']

            ret = {u'ret': chunk_ret}
            if fire_event is True:
                tag = salt.utils.event.tagify(
                        [self.jid, self.opts[u'id'], str(chunk_ret[u'name'])], u'state_result'
                        )
            elif isinstance(fire_event, six.string_types):
                tag = salt.utils.event.tagify(
                        [self.jid, self.opts[u'id'], str(fire_event)], u'state_result'
                        )
            else:
                tag = salt.utils.event.tagify(
                        [self.jid, u'prog', self.opts[u'id'], str(chunk_ret[u'__run_num__'])], u'job'
                        )
                ret[u'len'] = length
            preload = {u'jid': self.jid}
            ev_func(ret, tag, preload=preload)

    def call_chunk(self, low, running, chunks):
        '''
        Check if a chunk has any requires, execute the requires and then
        the chunk
        '''
        low = self._mod_aggregate(low, running, chunks)
        self._mod_init(low)
        tag = _gen_tag(low)
        if not low.get(u'prerequired'):
            self.active.add(tag)
        requisites = [u'require', u'watch', u'prereq', u'onfail', u'onchanges']
        if not low.get(u'__prereq__'):
            requisites.append(u'prerequired')
            status, reqs = self.check_requisite(low, running, chunks, pre=True)
        else:
            status, reqs = self.check_requisite(low, running, chunks)
        if status == u'unmet':
            lost = {}
            reqs = []
            for requisite in requisites:
                lost[requisite] = []
                if requisite not in low:
                    continue
                for req in low[requisite]:
                    if isinstance(req, six.string_types):
                        req = {u'id': req}
                    req = trim_req(req)
                    found = False
                    req_key = next(iter(req))
                    req_val = req[req_key]
                    for chunk in chunks:
                        if req_val is None:
                            continue
                        if req_key == u'sls':
                            # Allow requisite tracking of entire sls files
                            if fnmatch.fnmatch(chunk[u'__sls__'], req_val):
                                if requisite == u'prereq':
                                    chunk[u'__prereq__'] = True
                                reqs.append(chunk)
                                found = True
                            continue
                        if (fnmatch.fnmatch(chunk[u'name'], req_val) or
                            fnmatch.fnmatch(chunk[u'__id__'], req_val)):
                            if req_key == u'id' or chunk[u'state'] == req_key:
                                if requisite == u'prereq':
                                    chunk[u'__prereq__'] = True
                                elif requisite == u'prerequired':
                                    chunk[u'__prerequired__'] = True
                                reqs.append(chunk)
                                found = True
                    if not found:
                        lost[requisite].append(req)
            if lost[u'require'] or lost[u'watch'] or lost[u'prereq'] \
                        or lost[u'onfail'] or lost[u'onchanges'] \
                        or lost.get(u'prerequired'):
                comment = u'The following requisites were not found:\n'
                for requisite, lreqs in six.iteritems(lost):
                    if not lreqs:
                        continue
                    comment += \
                        u'{0}{1}:\n'.format(u' ' * 19, requisite)
                    for lreq in lreqs:
                        req_key = next(iter(lreq))
                        req_val = lreq[req_key]
                        comment += \
                            u'{0}{1}: {2}\n'.format(u' ' * 23, req_key, req_val)
                if low.get('__prereq__'):
                    run_dict = self.pre
                else:
                    run_dict = running
                run_dict[tag] = {u'changes': {},
                                 u'result': False,
                                 u'comment': comment,
                                 u'__run_num__': self.__run_num,
                                 u'__sls__': low[u'__sls__']}
                self.__run_num += 1
                self.event(run_dict[tag], len(chunks), fire_event=low.get(u'fire_event'))
                return running
            for chunk in reqs:
                # Check to see if the chunk has been run, only run it if
                # it has not been run already
                ctag = _gen_tag(chunk)
                if ctag not in running:
                    if ctag in self.active:
                        if chunk.get(u'__prerequired__'):
                            # Prereq recusive, run this chunk with prereq on
                            if tag not in self.pre:
                                low[u'__prereq__'] = True
                                self.pre[ctag] = self.call(low, chunks, running)
                                return running
                            else:
                                return running
                        elif ctag not in running:
                            log.error(u'Recursive requisite found')
                            running[tag] = {
                                    u'changes': {},
                                    u'result': False,
                                    u'comment': u'Recursive requisite found',
                                    u'__run_num__': self.__run_num,
                                    u'__sls__': low[u'__sls__']}
                        self.__run_num += 1
                        self.event(running[tag], len(chunks), fire_event=low.get(u'fire_event'))
                        return running
                    running = self.call_chunk(chunk, running, chunks)
                    if self.check_failhard(chunk, running):
                        running[u'__FAILHARD__'] = True
                        return running
            if low.get(u'__prereq__'):
                status, reqs = self.check_requisite(low, running, chunks)
                self.pre[tag] = self.call(low, chunks, running)
                if not self.pre[tag][u'changes'] and status == u'change':
                    self.pre[tag][u'changes'] = {u'watch': u'watch'}
                    self.pre[tag][u'result'] = None
            else:
                running = self.call_chunk(low, running, chunks)
            if self.check_failhard(chunk, running):
                running[u'__FAILHARD__'] = True
                return running
        elif status == u'met':
            if low.get(u'__prereq__'):
                self.pre[tag] = self.call(low, chunks, running)
            else:
                running[tag] = self.call(low, chunks, running)
        elif status == u'fail':
            # if the requisite that failed was due to a prereq on this low state
            # show the normal error
            if tag in self.pre:
                running[tag] = self.pre[tag]
                running[tag][u'__run_num__'] = self.__run_num
                running[tag][u'__sls__'] = low[u'__sls__']
            # otherwise the failure was due to a requisite down the chain
            else:
                # determine what the requisite failures where, and return
                # a nice error message
                failed_requisites = set()
                # look at all requisite types for a failure
                for req_lows in six.itervalues(reqs):
                    for req_low in req_lows:
                        req_tag = _gen_tag(req_low)
                        req_ret = self.pre.get(req_tag, running.get(req_tag))
                        # if there is no run output for the requisite it
                        # can't be the failure
                        if req_ret is None:
                            continue
                        # If the result was False (not None) it was a failure
                        if req_ret[u'result'] is False:
                            # use SLS.ID for the key-- so its easier to find
                            key = u'{sls}.{_id}'.format(sls=req_low[u'__sls__'],
                                                        _id=req_low[u'__id__'])
                            failed_requisites.add(key)

                _cmt = u'One or more requisite failed: {0}'.format(
                    u', '.join(str(i) for i in failed_requisites)
                )
                running[tag] = {
                    u'changes': {},
                    u'result': False,
                    u'comment': _cmt,
                    u'__run_num__': self.__run_num,
                    u'__sls__': low[u'__sls__']
                }
            self.__run_num += 1
        elif status == u'change' and not low.get(u'__prereq__'):
            ret = self.call(low, chunks, running)
            if not ret[u'changes'] and not ret.get(u'skip_watch', False):
                low = low.copy()
                low[u'sfun'] = low[u'fun']
                low[u'fun'] = u'mod_watch'
                low[u'__reqs__'] = reqs
                ret = self.call(low, chunks, running)
            running[tag] = ret
        elif status == u'pre':
            pre_ret = {u'changes': {},
                       u'result': True,
                       u'comment': u'No changes detected',
                       u'__run_num__': self.__run_num,
                       u'__sls__': low[u'__sls__']}
            running[tag] = pre_ret
            self.pre[tag] = pre_ret
            self.__run_num += 1
        elif status == u'onfail':
            running[tag] = {u'changes': {},
                            u'result': True,
                            u'comment': u'State was not run because onfail req did not change',
                            u'__run_num__': self.__run_num,
                            u'__sls__': low[u'__sls__']}
            self.__run_num += 1
        elif status == u'onchanges':
            running[tag] = {u'changes': {},
                            u'result': True,
                            u'comment': u'State was not run because none of the onchanges reqs changed',
                            u'__run_num__': self.__run_num,
                            u'__sls__': low[u'__sls__']}
            self.__run_num += 1
        else:
            if low.get(u'__prereq__'):
                self.pre[tag] = self.call(low, chunks, running)
            else:
                running[tag] = self.call(low, chunks, running)
        if tag in running:
            self.event(running[tag], len(chunks), fire_event=low.get(u'fire_event'))
        return running

    def call_listen(self, chunks, running):
        '''
        Find all of the listen routines and call the associated mod_watch runs
        '''
        listeners = []
        crefs = {}
        for chunk in chunks:
            crefs[(chunk[u'state'], chunk[u'name'])] = chunk
            crefs[(chunk[u'state'], chunk[u'__id__'])] = chunk
            if u'listen' in chunk:
                listeners.append({(chunk[u'state'], chunk[u'__id__']): chunk[u'listen']})
            if u'listen_in' in chunk:
                for l_in in chunk[u'listen_in']:
                    for key, val in six.iteritems(l_in):
                        listeners.append({(key, val): [{chunk[u'state']: chunk[u'__id__']}]})
        mod_watchers = []
        errors = {}
        for l_dict in listeners:
            for key, val in six.iteritems(l_dict):
                for listen_to in val:
                    if not isinstance(listen_to, dict):
                        continue
                    for lkey, lval in six.iteritems(listen_to):
                        if (lkey, lval) not in crefs:
                            rerror = {_l_tag(lkey, lval):
                                      {
                                          u'comment': u'Referenced state {0}: {1} does not exist'.format(lkey, lval),
                                          u'name': u'listen_{0}:{1}'.format(lkey, lval),
                                          u'result': False,
                                          u'changes': {}
                                      }}
                            errors.update(rerror)
                            continue
                        to_tag = _gen_tag(crefs[(lkey, lval)])
                        if to_tag not in running:
                            continue
                        if running[to_tag][u'changes']:
                            if key not in crefs:
                                rerror = {_l_tag(key[0], key[1]):
                                             {u'comment': u'Referenced state {0}: {1} does not exist'.format(key[0], key[1]),
                                              u'name': u'listen_{0}:{1}'.format(key[0], key[1]),
                                              u'result': False,
                                              u'changes': {}}}
                                errors.update(rerror)
                                continue
                            chunk = crefs[key]
                            low = chunk.copy()
                            low[u'sfun'] = chunk[u'fun']
                            low[u'fun'] = u'mod_watch'
                            low[u'__id__'] = u'listener_{0}'.format(low[u'__id__'])
                            for req in STATE_REQUISITE_KEYWORDS:
                                if req in low:
                                    low.pop(req)
                            mod_watchers.append(low)
        ret = self.call_chunks(mod_watchers)
        running.update(ret)
        for err in errors:
            errors[err][u'__run_num__'] = self.__run_num
            self.__run_num += 1
        running.update(errors)
        return running

    def call_high(self, high, orchestration_jid=None):
        '''
        Process a high data call and ensure the defined states.
        '''
        errors = []
        # If there is extension data reconcile it
        high, ext_errors = self.reconcile_extend(high)
        errors += ext_errors
        errors += self.verify_high(high)
        if errors:
            return errors
        high, req_in_errors = self.requisite_in(high)
        errors += req_in_errors
        high = self.apply_exclude(high)
        # Verify that the high data is structurally sound
        if errors:
            return errors
        # Compile and verify the raw chunks
        chunks = self.compile_high_data(high, orchestration_jid)

        # If there are extensions in the highstate, process them and update
        # the low data chunks
        if errors:
            return errors
        ret = self.call_chunks(chunks)
        ret = self.call_listen(chunks, ret)

        def _cleanup_accumulator_data():
            accum_data_path = os.path.join(
                get_accumulator_dir(self.opts[u'cachedir']),
                self.instance_id
            )
            try:
                os.remove(accum_data_path)
                log.debug(u'Deleted accumulator data file %s', accum_data_path)
            except OSError:
                log.debug(u'File %s does not exist, no need to cleanup', accum_data_path)
        _cleanup_accumulator_data()

        return ret

    def render_template(self, high, template):
        errors = []
        if not high:
            return high, errors

        if not isinstance(high, dict):
            errors.append(
                u'Template {0} does not render to a dictionary'.format(template)
            )
            return high, errors

        invalid_items = (u'include', u'exclude', u'extends')
        for item in invalid_items:
            if item in high:
                errors.append(
                    u'The \'{0}\' declaration found on \'{1}\' is invalid when '
                    u'rendering single templates'.format(item, template)
                )
                return high, errors

        for name in high:
            if not isinstance(high[name], dict):
                if isinstance(high[name], six.string_types):
                    # Is this is a short state, it needs to be padded
                    if u'.' in high[name]:
                        comps = high[name].split(u'.')
                        high[name] = {
                            # '__sls__': template,
                            # '__env__': None,
                            comps[0]: [comps[1]]
                        }
                        continue

                    errors.append(
                        u'ID {0} in template {1} is not a dictionary'.format(
                            name, template
                        )
                    )
                    continue
            skeys = set()
            for key in sorted(high[name]):
                if key.startswith(u'_'):
                    continue
                if high[name][key] is None:
                    errors.append(
                        u'ID \'{0}\' in template {1} contains a short '
                        u'declaration ({2}) with a trailing colon. When not '
                        u'passing any arguments to a state, the colon must be '
                        u'omitted.'.format(name, template, key)
                    )
                    continue
                if not isinstance(high[name][key], list):
                    continue
                if u'.' in key:
                    comps = key.split(u'.')
                    # Salt doesn't support state files such as:
                    #
                    # /etc/redis/redis.conf:
                    #   file.managed:
                    #     - user: redis
                    #     - group: redis
                    #     - mode: 644
                    #   file.comment:
                    #     - regex: ^requirepass
                    if comps[0] in skeys:
                        errors.append(
                            u'ID \'{0}\' in template \'{1}\' contains multiple '
                            u'state declarations of the same type'
                            .format(name, template)
                        )
                        continue
                    high[name][comps[0]] = high[name].pop(key)
                    high[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)

        return high, errors

    def call_template(self, template):
        '''
        Enforce the states in a template
        '''
        high = compile_template(template,
                                self.rend,
                                self.opts[u'renderer'],
                                self.opts[u'renderer_blacklist'],
                                self.opts[u'renderer_whitelist'])
        if not high:
            return high
        high, errors = self.render_template(high, template)
        if errors:
            return errors
        return self.call_high(high)

    def call_template_str(self, template):
        '''
        Enforce the states in a template, pass the template as a string
        '''
        high = compile_template_str(template,
                                    self.rend,
                                    self.opts[u'renderer'],
                                    self.opts[u'renderer_blacklist'],
                                    self.opts[u'renderer_whitelist'])
        if not high:
            return high
        high, errors = self.render_template(high, u'<template-str>')
        if errors:
            return errors
        return self.call_high(high)


class BaseHighState(object):
    '''
    The BaseHighState is an abstract base class that is the foundation of
    running a highstate, extend it and add a self.state object of type State.

    When extending this class, please note that ``self.client`` and
    ``self.matcher`` should be instantiated and handled.
    '''
    def __init__(self, opts):
        self.opts = self.__gen_opts(opts)
        self.iorder = 10000
        self.avail = self.__gather_avail()
        self.serial = salt.payload.Serial(self.opts)
        self.building_highstate = OrderedDict()

    def __gather_avail(self):
        '''
        Gather the lists of available sls data from the master
        '''
        avail = {}
        for saltenv in self._get_envs():
            avail[saltenv] = self.client.list_states(saltenv)
        return avail

    def __gen_opts(self, opts):
        '''
        The options used by the High State object are derived from options
        on the minion and the master, or just the minion if the high state
        call is entirely local.
        '''
        # If the state is intended to be applied locally, then the local opts
        # should have all of the needed data, otherwise overwrite the local
        # data items with data from the master
        if u'local_state' in opts:
            if opts[u'local_state']:
                return opts
        mopts = self.client.master_opts()
        if not isinstance(mopts, dict):
            # An error happened on the master
            opts[u'renderer'] = u'yaml_jinja'
            opts[u'failhard'] = False
            opts[u'state_top'] = salt.utils.url.create(u'top.sls')
            opts[u'nodegroups'] = {}
            opts[u'file_roots'] = {u'base': [syspaths.BASE_FILE_ROOTS_DIR]}
        else:
            opts[u'renderer'] = mopts[u'renderer']
            opts[u'failhard'] = mopts.get(u'failhard', False)
            if mopts[u'state_top'].startswith(u'salt://'):
                opts[u'state_top'] = mopts[u'state_top']
            elif mopts[u'state_top'].startswith(u'/'):
                opts[u'state_top'] = salt.utils.url.create(mopts[u'state_top'][1:])
            else:
                opts[u'state_top'] = salt.utils.url.create(mopts[u'state_top'])
            opts[u'state_top_saltenv'] = mopts.get(u'state_top_saltenv', None)
            opts[u'nodegroups'] = mopts.get(u'nodegroups', {})
            opts[u'state_auto_order'] = mopts.get(
                u'state_auto_order',
                opts[u'state_auto_order'])
            opts[u'file_roots'] = mopts[u'file_roots']
            opts[u'top_file_merging_strategy'] = mopts.get(u'top_file_merging_strategy',
                                                           opts.get(u'top_file_merging_strategy'))
            opts[u'env_order'] = mopts.get(u'env_order', opts.get(u'env_order', []))
            opts[u'default_top'] = mopts.get(u'default_top', opts.get(u'default_top'))
            opts[u'state_events'] = mopts.get(u'state_events')
            opts[u'state_aggregate'] = mopts.get(u'state_aggregate', opts.get(u'state_aggregate', False))
            opts[u'jinja_lstrip_blocks'] = mopts.get(u'jinja_lstrip_blocks', False)
            opts[u'jinja_trim_blocks'] = mopts.get(u'jinja_trim_blocks', False)
        return opts

    def _get_envs(self):
        '''
        Pull the file server environments out of the master options
        '''
        envs = [u'base']
        if u'file_roots' in self.opts:
            envs.extend([x for x in list(self.opts[u'file_roots'])
                         if x not in envs])
        env_order = self.opts.get(u'env_order', [])
        # Remove duplicates while preserving the order
        members = set()
        env_order = [env for env in env_order if not (env in members or members.add(env))]
        client_envs = self.client.envs()
        if env_order and client_envs:
            return [env for env in env_order if env in client_envs]

        elif env_order:
            return env_order
        else:
            envs.extend([env for env in client_envs if env not in envs])
            return envs

    def get_tops(self):
        '''
        Gather the top files
        '''
        tops = DefaultOrderedDict(list)
        include = DefaultOrderedDict(list)
        done = DefaultOrderedDict(list)
        found = 0  # did we find any contents in the top files?
        # Gather initial top files
        merging_strategy = self.opts[u'top_file_merging_strategy']
        if merging_strategy == u'same' and not self.opts[u'environment']:
            if not self.opts[u'default_top']:
                raise SaltRenderError(
                    u'top_file_merging_strategy set to \'same\', but no '
                    u'default_top configuration option was set'
                )

        if self.opts[u'environment']:
            contents = self.client.cache_file(
                self.opts[u'state_top'],
                self.opts[u'environment']
            )
            if contents:
                found = 1
                tops[self.opts[u'environment']] = [
                    compile_template(
                        contents,
                        self.state.rend,
                        self.state.opts[u'renderer'],
                        self.state.opts[u'renderer_blacklist'],
                        self.state.opts[u'renderer_whitelist'],
                        saltenv=self.opts[u'environment']
                    )
                ]
            else:
                tops[self.opts[u'environment']] = [{}]

        else:
            found = 0
            state_top_saltenv = self.opts.get(u'state_top_saltenv', False)
            if state_top_saltenv \
                    and not isinstance(state_top_saltenv, six.string_types):
                state_top_saltenv = str(state_top_saltenv)

            for saltenv in [state_top_saltenv] if state_top_saltenv \
                    else self._get_envs():
                contents = self.client.cache_file(
                    self.opts[u'state_top'],
                    saltenv
                )
                if contents:
                    found = found + 1
                    tops[saltenv].append(
                        compile_template(
                            contents,
                            self.state.rend,
                            self.state.opts[u'renderer'],
                            self.state.opts[u'renderer_blacklist'],
                            self.state.opts[u'renderer_whitelist'],
                            saltenv=saltenv
                        )
                    )
                else:
                    tops[saltenv].append({})
                    log.debug(u'No contents loaded for saltenv \'%s\'', saltenv)

            if found > 1 and merging_strategy == u'merge' and not self.opts.get(u'env_order', None):
                log.warning(
                    u'top_file_merging_strategy is set to \'%s\' and '
                    u'multiple top files were found. Merging order is not '
                    u'deterministic, it may be desirable to either set '
                    u'top_file_merging_strategy to \'same\' or use the '
                    u'\'env_order\' configuration parameter to specify the '
                    u'merging order.', merging_strategy
                )

        if found == 0:
            log.debug(
                u'No contents found in top file. If this is not expected, '
                u'verify that the \'file_roots\' specified in \'etc/master\' '
                u'are accessible. The \'file_roots\' configuration is: %s',
                repr(self.state.opts[u'file_roots'])
            )

        # Search initial top files for includes
        for saltenv, ctops in six.iteritems(tops):
            for ctop in ctops:
                if u'include' not in ctop:
                    continue
                for sls in ctop[u'include']:
                    include[saltenv].append(sls)
                ctop.pop(u'include')
        # Go through the includes and pull out the extra tops and add them
        while include:
            pops = []
            for saltenv, states in six.iteritems(include):
                pops.append(saltenv)
                if not states:
                    continue
                for sls_match in states:
                    for sls in fnmatch.filter(self.avail[saltenv], sls_match):
                        if sls in done[saltenv]:
                            continue
                        tops[saltenv].append(
                            compile_template(
                                self.client.get_state(
                                    sls,
                                    saltenv
                                ).get(u'dest', False),
                                self.state.rend,
                                self.state.opts[u'renderer'],
                                self.state.opts[u'renderer_blacklist'],
                                self.state.opts[u'renderer_whitelist'],
                                saltenv
                            )
                        )
                        done[saltenv].append(sls)
            for saltenv in pops:
                if saltenv in include:
                    include.pop(saltenv)
        return tops

    def merge_tops(self, tops):
        '''
        Cleanly merge the top files
        '''
        merging_strategy = self.opts[u'top_file_merging_strategy']
        try:
            merge_attr = u'_merge_tops_{0}'.format(merging_strategy)
            merge_func = getattr(self, merge_attr)
            if not hasattr(merge_func, u'__call__'):
                msg = u'\'{0}\' is not callable'.format(merge_attr)
                log.error(msg)
                raise TypeError(msg)
        except (AttributeError, TypeError):
            log.warning(
                u'Invalid top_file_merging_strategy \'%s\', falling back to '
                u'\'merge\'', merging_strategy
            )
            merge_func = self._merge_tops_merge
        return merge_func(tops)

    def _merge_tops_merge(self, tops):
        '''
        The default merging strategy. The base env is authoritative, so it is
        checked first, followed by the remaining environments. In top files
        from environments other than "base", only the section matching the
        environment from the top file will be considered, and it too will be
        ignored if that environment was defined in the "base" top file.
        '''
        top = DefaultOrderedDict(OrderedDict)

        # Check base env first as it is authoritative
        base_tops = tops.pop(u'base', DefaultOrderedDict(OrderedDict))
        for ctop in base_tops:
            for saltenv, targets in six.iteritems(ctop):
                if saltenv == u'include':
                    continue
                try:
                    for tgt in targets:
                        top[saltenv][tgt] = ctop[saltenv][tgt]
                except TypeError:
                    raise SaltRenderError(u'Unable to render top file. No targets found.')

        for cenv, ctops in six.iteritems(tops):
            for ctop in ctops:
                for saltenv, targets in six.iteritems(ctop):
                    if saltenv == u'include':
                        continue
                    elif saltenv != cenv:
                        log.debug(
                            u'Section for saltenv \'%s\' in the \'%s\' '
                            u'saltenv\'s top file will be ignored, as the '
                            u'top_file_merging_strategy is set to \'merge\' '
                            u'and the saltenvs do not match',
                            saltenv, cenv
                        )
                        continue
                    elif saltenv in top:
                        log.debug(
                            u'Section for saltenv \'%s\' in the \'%s\' '
                            u'saltenv\'s top file will be ignored, as this '
                            u'saltenv was already defined in the \'base\' top '
                            u'file', saltenv, cenv
                        )
                        continue
                    try:
                        for tgt in targets:
                            top[saltenv][tgt] = ctop[saltenv][tgt]
                    except TypeError:
                        raise SaltRenderError(u'Unable to render top file. No targets found.')
        return top

    def _merge_tops_same(self, tops):
        '''
        For each saltenv, only consider the top file from that saltenv. All
        sections matching a given saltenv, which appear in a different
        saltenv's top file, will be ignored.
        '''
        top = DefaultOrderedDict(OrderedDict)
        for cenv, ctops in six.iteritems(tops):
            if all([x == {} for x in ctops]):
                # No top file found in this env, check the default_top
                default_top = self.opts[u'default_top']
                fallback_tops = tops.get(default_top, [])
                if all([x == {} for x in fallback_tops]):
                    # Nothing in the fallback top file
                    log.error(
                        u'The \'%s\' saltenv has no top file, and the fallback '
                        u'saltenv specified by default_top (%s) also has no '
                        u'top file', cenv, default_top
                    )
                    continue

                for ctop in fallback_tops:
                    for saltenv, targets in six.iteritems(ctop):
                        if saltenv != cenv:
                            continue
                        log.debug(
                            u'The \'%s\' saltenv has no top file, using the '
                            u'default_top saltenv (%s)', cenv, default_top
                        )
                        for tgt in targets:
                            top[saltenv][tgt] = ctop[saltenv][tgt]
                        break
                    else:
                        log.error(
                            u'The \'%s\' saltenv has no top file, and no '
                            u'matches were found in the top file for the '
                            u'default_top saltenv (%s)', cenv, default_top
                        )

                continue

            else:
                for ctop in ctops:
                    for saltenv, targets in six.iteritems(ctop):
                        if saltenv == u'include':
                            continue
                        elif saltenv != cenv:
                            log.debug(
                                u'Section for saltenv \'%s\' in the \'%s\' '
                                u'saltenv\'s top file will be ignored, as the '
                                u'top_file_merging_strategy is set to \'same\' '
                                u'and the saltenvs do not match',
                                saltenv, cenv
                            )
                            continue

                        try:
                            for tgt in targets:
                                top[saltenv][tgt] = ctop[saltenv][tgt]
                        except TypeError:
                            raise SaltRenderError(u'Unable to render top file. No targets found.')
        return top

    def _merge_tops_merge_all(self, tops):
        '''
        Merge the top files into a single dictionary
        '''
        def _read_tgt(tgt):
            match_type = None
            states = []
            for item in tgt:
                if isinstance(item, dict):
                    match_type = item
                if isinstance(item, six.string_types):
                    states.append(item)
            return match_type, states

        top = DefaultOrderedDict(OrderedDict)
        for ctops in six.itervalues(tops):
            for ctop in ctops:
                for saltenv, targets in six.iteritems(ctop):
                    if saltenv == u'include':
                        continue
                    try:
                        for tgt in targets:
                            if tgt not in top[saltenv]:
                                top[saltenv][tgt] = ctop[saltenv][tgt]
                                continue
                            m_type1, m_states1 = _read_tgt(top[saltenv][tgt])
                            m_type2, m_states2 = _read_tgt(ctop[saltenv][tgt])
                            merged = []
                            match_type = m_type2 or m_type1
                            if match_type is not None:
                                merged.append(match_type)
                            merged.extend(m_states1)
                            merged.extend([x for x in m_states2 if x not in merged])
                            top[saltenv][tgt] = merged
                    except TypeError:
                        raise SaltRenderError(u'Unable to render top file. No targets found.')
        return top

    def verify_tops(self, tops):
        '''
        Verify the contents of the top file data
        '''
        errors = []
        if not isinstance(tops, dict):
            errors.append(u'Top data was not formed as a dict')
            # No further checks will work, bail out
            return errors
        for saltenv, matches in six.iteritems(tops):
            if saltenv == u'include':
                continue
            if not isinstance(saltenv, six.string_types):
                errors.append(
                    u'Environment {0} in top file is not formed as a '
                    u'string'.format(saltenv)
                )
            if saltenv == u'':
                errors.append(u'Empty saltenv statement in top file')
            if not isinstance(matches, dict):
                errors.append(
                    u'The top file matches for saltenv {0} are not '
                    u'formatted as a dict'.format(saltenv)
                )
            for slsmods in six.itervalues(matches):
                if not isinstance(slsmods, list):
                    errors.append(u'Malformed topfile (state declarations not '
                                  u'formed as a list)')
                    continue
                for slsmod in slsmods:
                    if isinstance(slsmod, dict):
                        # This value is a match option
                        for val in six.itervalues(slsmod):
                            if not val:
                                errors.append(
                                    u'Improperly formatted top file matcher '
                                    u'in saltenv {0}: {1} file'.format(
                                        slsmod,
                                        val
                                    )
                                )
                    elif isinstance(slsmod, six.string_types):
                        # This is a sls module
                        if not slsmod:
                            errors.append(
                                u'Environment {0} contains an empty sls '
                                u'index'.format(saltenv)
                            )

        return errors

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        try:
            tops = self.get_tops()
        except SaltRenderError as err:
            log.error(u'Unable to render top file: ' + str(err.error))
            return {}
        return self.merge_tops(tops)

    def top_matches(self, top):
        '''
        Search through the top high data for matches and return the states
        that this minion needs to execute.

        Returns:
        {'saltenv': ['state1', 'state2', ...]}
        '''
        matches = DefaultOrderedDict(OrderedDict)
        # pylint: disable=cell-var-from-loop
        for saltenv, body in six.iteritems(top):
            if self.opts[u'environment']:
                if saltenv != self.opts[u'environment']:
                    continue
            for match, data in six.iteritems(body):
                def _filter_matches(_match, _data, _opts):
                    if isinstance(_data, six.string_types):
                        _data = [_data]
                    if self.matcher.confirm_top(
                            _match,
                            _data,
                            _opts
                            ):
                        if saltenv not in matches:
                            matches[saltenv] = []
                        for item in _data:
                            if u'subfilter' in item:
                                _tmpdata = item.pop(u'subfilter')
                                for match, data in six.iteritems(_tmpdata):
                                    _filter_matches(match, data, _opts)
                            if isinstance(item, six.string_types):
                                matches[saltenv].append(item)
                            elif isinstance(item, dict):
                                env_key, inc_sls = item.popitem()
                                if env_key not in self.avail:
                                    continue
                                if env_key not in matches:
                                    matches[env_key] = []
                                matches[env_key].append(inc_sls)
                _filter_matches(match, data, self.opts[u'nodegroups'])
        ext_matches = self._master_tops()
        for saltenv in ext_matches:
            top_file_matches = matches.get(saltenv, [])
            if self.opts[u'master_tops_first']:
                first = ext_matches[saltenv]
                second = top_file_matches
            else:
                first = top_file_matches
                second = ext_matches[saltenv]
            matches[saltenv] = first + [x for x in second if x not in first]

        # pylint: enable=cell-var-from-loop
        return matches

    def _master_tops(self):
        '''
        Get results from the master_tops system. Override this function if the
        execution of the master_tops needs customization.
        '''
        return self.client.master_tops()

    def load_dynamic(self, matches):
        '''
        If autoload_dynamic_modules is True then automatically load the
        dynamic modules
        '''
        if not self.opts[u'autoload_dynamic_modules']:
            return
        syncd = self.state.functions[u'saltutil.sync_all'](list(matches),
                                                          refresh=False)
        if syncd[u'grains']:
            self.opts[u'grains'] = salt.loader.grains(self.opts)
            self.state.opts[u'pillar'] = self.state._gather_pillar()
        self.state.module_refresh()

    def render_state(self, sls, saltenv, mods, matches, local=False):
        '''
        Render a state file and retrieve all of the include states
        '''
        errors = []
        if not local:
            state_data = self.client.get_state(sls, saltenv)
            fn_ = state_data.get(u'dest', False)
        else:
            fn_ = sls
            if not os.path.isfile(fn_):
                errors.append(
                    u'Specified SLS {0} on local filesystem cannot '
                    u'be found.'.format(sls)
                )
        if not fn_:
            errors.append(
                u'Specified SLS {0} in saltenv {1} is not '
                u'available on the salt master or through a configured '
                u'fileserver'.format(sls, saltenv)
            )
        state = None
        try:
            state = compile_template(fn_,
                                     self.state.rend,
                                     self.state.opts[u'renderer'],
                                     self.state.opts[u'renderer_blacklist'],
                                     self.state.opts[u'renderer_whitelist'],
                                     saltenv,
                                     sls,
                                     rendered_sls=mods
                                     )
        except SaltRenderError as exc:
            msg = u'Rendering SLS \'{0}:{1}\' failed: {2}'.format(
                saltenv, sls, exc
            )
            log.critical(msg)
            errors.append(msg)
        except Exception as exc:
            msg = u'Rendering SLS {0} failed, render error: {1}'.format(
                sls, exc
            )
            log.critical(
                msg,
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            errors.append(u'{0}\n{1}'.format(msg, traceback.format_exc()))
        try:
            mods.add(u'{0}:{1}'.format(saltenv, sls))
        except AttributeError:
            pass
        if state:
            if not isinstance(state, dict):
                errors.append(
                    u'SLS {0} does not render to a dictionary'.format(sls)
                )
            else:
                include = []
                if u'include' in state:
                    if not isinstance(state[u'include'], list):
                        err = (u'Include Declaration in SLS {0} is not formed '
                               u'as a list'.format(sls))
                        errors.append(err)
                    else:
                        include = state.pop(u'include')

                self._handle_extend(state, sls, saltenv, errors)
                self._handle_exclude(state, sls, saltenv, errors)
                self._handle_state_decls(state, sls, saltenv, errors)

                for inc_sls in include:
                    # inc_sls may take the form of:
                    #   'sls.to.include' <- same as {<saltenv>: 'sls.to.include'}
                    #   {<env_key>: 'sls.to.include'}
                    #   {'_xenv': 'sls.to.resolve'}
                    xenv_key = u'_xenv'

                    if isinstance(inc_sls, dict):
                        env_key, inc_sls = inc_sls.popitem()
                    else:
                        env_key = saltenv

                    if env_key not in self.avail:
                        msg = (u'Nonexistent saltenv \'{0}\' found in include '
                               u'of \'{1}\' within SLS \'{2}:{3}\''
                               .format(env_key, inc_sls, saltenv, sls))
                        log.error(msg)
                        errors.append(msg)
                        continue

                    if inc_sls.startswith(u'.'):
                        match = re.match(r'^(\.+)(.*)$', inc_sls)  # future lint: disable=non-unicode-string
                        if match:
                            levels, include = match.groups()
                        else:
                            msg = (u'Badly formatted include {0} found in include '
                                    u'in SLS \'{2}:{3}\''
                                    .format(inc_sls, saltenv, sls))
                            log.error(msg)
                            errors.append(msg)
                            continue
                        level_count = len(levels)
                        p_comps = sls.split(u'.')
                        if state_data.get(u'source', u'').endswith(u'/init.sls'):
                            p_comps.append(u'init')
                        if level_count > len(p_comps):
                            msg = (u'Attempted relative include of \'{0}\' '
                                   u'within SLS \'{1}:{2}\' '
                                   u'goes beyond top level package '
                                   .format(inc_sls, saltenv, sls))
                            log.error(msg)
                            errors.append(msg)
                            continue
                        inc_sls = u'.'.join(p_comps[:-level_count] + [include])

                    if env_key != xenv_key:
                        if matches is None:
                            matches = []
                        # Resolve inc_sls in the specified environment
                        if env_key in matches or fnmatch.filter(self.avail[env_key], inc_sls):
                            resolved_envs = [env_key]
                        else:
                            resolved_envs = []
                    else:
                        # Resolve inc_sls in the subset of environment matches
                        resolved_envs = [
                            aenv for aenv in matches
                            if fnmatch.filter(self.avail[aenv], inc_sls)
                        ]

                    # An include must be resolved to a single environment, or
                    # the include must exist in the current environment
                    if len(resolved_envs) == 1 or saltenv in resolved_envs:
                        # Match inc_sls against the available states in the
                        # resolved env, matching wildcards in the process. If
                        # there were no matches, then leave inc_sls as the
                        # target so that the next recursion of render_state
                        # will recognize the error.
                        sls_targets = fnmatch.filter(
                            self.avail[saltenv],
                            inc_sls
                        ) or [inc_sls]

                        for sls_target in sls_targets:
                            r_env = resolved_envs[0] if len(resolved_envs) == 1 else saltenv
                            mod_tgt = u'{0}:{1}'.format(r_env, sls_target)
                            if mod_tgt not in mods:
                                nstate, err = self.render_state(
                                    sls_target,
                                    r_env,
                                    mods,
                                    matches
                                )
                                if nstate:
                                    self.merge_included_states(state, nstate, errors)
                                    state.update(nstate)
                                if err:
                                    errors.extend(err)
                    else:
                        msg = u''
                        if not resolved_envs:
                            msg = (u'Unknown include: Specified SLS {0}: {1} is not available on the salt '
                                   u'master in saltenv(s): {2} '
                                   ).format(env_key,
                                            inc_sls,
                                            u', '.join(matches) if env_key == xenv_key else env_key)
                        elif len(resolved_envs) > 1:
                            msg = (u'Ambiguous include: Specified SLS {0}: {1} is available on the salt master '
                                   u'in multiple available saltenvs: {2}'
                                   ).format(env_key,
                                            inc_sls,
                                            u', '.join(resolved_envs))
                        log.critical(msg)
                        errors.append(msg)
                try:
                    self._handle_iorder(state)
                except TypeError:
                    log.critical(u'Could not render SLS %s. Syntax error detected.', sls)
        else:
            state = {}
        return state, errors

    def _handle_iorder(self, state):
        '''
        Take a state and apply the iorder system
        '''
        if self.opts[u'state_auto_order']:
            for name in state:
                for s_dec in state[name]:
                    if not isinstance(s_dec, six.string_types):
                        # PyDSL OrderedDict?
                        continue

                    if not isinstance(state[name], dict):
                        # Include's or excludes as lists?
                        continue
                    if not isinstance(state[name][s_dec], list):
                        # Bad syntax, let the verify seq pick it up later on
                        continue

                    found = False
                    if s_dec.startswith(u'_'):
                        continue

                    for arg in state[name][s_dec]:
                        if isinstance(arg, dict):
                            if len(arg) > 0:
                                if next(six.iterkeys(arg)) == u'order':
                                    found = True
                    if not found:
                        if not isinstance(state[name][s_dec], list):
                            # quite certainly a syntax error, managed elsewhere
                            continue
                        state[name][s_dec].append(
                                {u'order': self.iorder}
                                )
                        self.iorder += 1
        return state

    def _handle_state_decls(self, state, sls, saltenv, errors):
        '''
        Add sls and saltenv components to the state
        '''
        for name in state:
            if not isinstance(state[name], dict):
                if name == u'__extend__':
                    continue
                if name == u'__exclude__':
                    continue

                if isinstance(state[name], six.string_types):
                    # Is this is a short state, it needs to be padded
                    if u'.' in state[name]:
                        comps = state[name].split(u'.')
                        state[name] = {u'__sls__': sls,
                                       u'__env__': saltenv,
                                       comps[0]: [comps[1]]}
                        continue
                errors.append(
                    u'ID {0} in SLS {1} is not a dictionary'.format(name, sls)
                )
                continue
            skeys = set()
            for key in list(state[name]):
                if key.startswith(u'_'):
                    continue
                if not isinstance(state[name][key], list):
                    continue
                if u'.' in key:
                    comps = key.split(u'.')
                    # Salt doesn't support state files such as:
                    #
                    #     /etc/redis/redis.conf:
                    #       file.managed:
                    #         - source: salt://redis/redis.conf
                    #         - user: redis
                    #         - group: redis
                    #         - mode: 644
                    #       file.comment:
                    #           - regex: ^requirepass
                    if comps[0] in skeys:
                        errors.append(
                            u'ID \'{0}\' in SLS \'{1}\' contains multiple state '
                            u'declarations of the same type'.format(name, sls)
                        )
                        continue
                    state[name][comps[0]] = state[name].pop(key)
                    state[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)
            if u'__sls__' not in state[name]:
                state[name][u'__sls__'] = sls
            if u'__env__' not in state[name]:
                state[name][u'__env__'] = saltenv

    def _handle_extend(self, state, sls, saltenv, errors):
        '''
        Take the extend dec out of state and apply to the highstate global
        dec
        '''
        if u'extend' in state:
            ext = state.pop(u'extend')
            if not isinstance(ext, dict):
                errors.append((u'Extension value in SLS \'{0}\' is not a '
                               u'dictionary').format(sls))
                return
            for name in ext:
                if not isinstance(ext[name], dict):
                    errors.append((u'Extension name \'{0}\' in SLS \'{1}\' is '
                                   u'not a dictionary'
                                   .format(name, sls)))
                    continue
                if u'__sls__' not in ext[name]:
                    ext[name][u'__sls__'] = sls
                if u'__env__' not in ext[name]:
                    ext[name][u'__env__'] = saltenv
                for key in list(ext[name]):
                    if key.startswith(u'_'):
                        continue
                    if not isinstance(ext[name][key], list):
                        continue
                    if u'.' in key:
                        comps = key.split(u'.')
                        ext[name][comps[0]] = ext[name].pop(key)
                        ext[name][comps[0]].append(comps[1])
            state.setdefault(u'__extend__', []).append(ext)

    def _handle_exclude(self, state, sls, saltenv, errors):
        '''
        Take the exclude dec out of the state and apply it to the highstate
        global dec
        '''
        if u'exclude' in state:
            exc = state.pop(u'exclude')
            if not isinstance(exc, list):
                err = (u'Exclude Declaration in SLS {0} is not formed '
                       u'as a list'.format(sls))
                errors.append(err)
            state.setdefault(u'__exclude__', []).extend(exc)

    def render_highstate(self, matches):
        '''
        Gather the state files and render them into a single unified salt
        high data structure.
        '''
        highstate = self.building_highstate
        all_errors = []
        mods = set()
        statefiles = []
        for saltenv, states in six.iteritems(matches):
            for sls_match in states:
                try:
                    statefiles = fnmatch.filter(self.avail[saltenv], sls_match)
                except KeyError:
                    all_errors.extend(
                        [u'No matching salt environment for environment '
                         u'\'{0}\' found'.format(saltenv)]
                    )
                # if we did not found any sls in the fileserver listing, this
                # may be because the sls was generated or added later, we can
                # try to directly execute it, and if it fails, anyway it will
                # return the former error
                if not statefiles:
                    statefiles = [sls_match]

                for sls in statefiles:
                    r_env = u'{0}:{1}'.format(saltenv, sls)
                    if r_env in mods:
                        continue
                    state, errors = self.render_state(
                        sls, saltenv, mods, matches)
                    if state:
                        self.merge_included_states(highstate, state, errors)
                    for i, error in enumerate(errors[:]):
                        if u'is not available' in error:
                            # match SLS foobar in environment
                            this_sls = u'SLS {0} in saltenv'.format(
                                sls_match)
                            if this_sls in error:
                                errors[i] = (
                                    u'No matching sls found for \'{0}\' '
                                    u'in env \'{1}\''.format(sls_match, saltenv))
                    all_errors.extend(errors)

        self.clean_duplicate_extends(highstate)
        return highstate, all_errors

    def clean_duplicate_extends(self, highstate):
        if u'__extend__' in highstate:
            highext = []
            for items in (six.iteritems(ext) for ext in highstate[u'__extend__']):
                for item in items:
                    if item not in highext:
                        highext.append(item)
            highstate[u'__extend__'] = [{t[0]: t[1]} for t in highext]

    def merge_included_states(self, highstate, state, errors):
        # The extend members can not be treated as globally unique:
        if u'__extend__' in state:
            highstate.setdefault(u'__extend__',
                                 []).extend(state.pop(u'__extend__'))
        if u'__exclude__' in state:
            highstate.setdefault(u'__exclude__',
                                 []).extend(state.pop(u'__exclude__'))
        for id_ in state:
            if id_ in highstate:
                if highstate[id_] != state[id_]:
                    errors.append((
                            u'Detected conflicting IDs, SLS'
                            u' IDs need to be globally unique.\n    The'
                            u' conflicting ID is \'{0}\' and is found in SLS'
                            u' \'{1}:{2}\' and SLS \'{3}:{4}\'').format(
                                    id_,
                                    highstate[id_][u'__env__'],
                                    highstate[id_][u'__sls__'],
                                    state[id_][u'__env__'],
                                    state[id_][u'__sls__'])
                    )
        try:
            highstate.update(state)
        except ValueError:
            errors.append(
                u'Error when rendering state with contents: {0}'.format(state)
            )

    def _check_pillar(self, force=False):
        '''
        Check the pillar for errors, refuse to run the state if there are
        errors in the pillar and return the pillar errors
        '''
        if force:
            return True
        if u'_errors' in self.state.opts[u'pillar']:
            return False
        return True

    def matches_whitelist(self, matches, whitelist):
        '''
        Reads over the matches and returns a matches dict with just the ones
        that are in the whitelist
        '''
        if not whitelist:
            return matches
        ret_matches = {}
        if not isinstance(whitelist, list):
            whitelist = whitelist.split(u',')
        for env in matches:
            for sls in matches[env]:
                if sls in whitelist:
                    ret_matches[env] = ret_matches[env] if env in ret_matches else []
                    ret_matches[env].append(sls)
        return ret_matches

    def call_highstate(self, exclude=None, cache=None, cache_name=u'highstate',
                       force=False, whitelist=None, orchestration_jid=None):
        '''
        Run the sequence to execute the salt highstate for this minion
        '''
        # Check that top file exists
        tag_name = u'no_|-states_|-states_|-None'
        ret = {tag_name: {
                u'result': False,
                u'comment': u'No states found for this minion',
                u'name': u'No States',
                u'changes': {},
                u'__run_num__': 0,
        }}
        cfn = os.path.join(
                self.opts[u'cachedir'],
                u'{0}.cache.p'.format(cache_name)
        )

        if cache:
            if os.path.isfile(cfn):
                with salt.utils.files.fopen(cfn, u'rb') as fp_:
                    high = self.serial.load(fp_)
                    return self.state.call_high(high, orchestration_jid)
        # File exists so continue
        err = []
        try:
            top = self.get_top()
        except SaltRenderError as err:
            ret[tag_name][u'comment'] = u'Unable to render top file: '
            ret[tag_name][u'comment'] += str(err.error)
            return ret
        except Exception:
            trb = traceback.format_exc()
            err.append(trb)
            return err
        err += self.verify_tops(top)
        matches = self.top_matches(top)
        if not matches:
            msg = u'No Top file or master_tops data matches found.'
            ret[tag_name][u'comment'] = msg
            return ret
        matches = self.matches_whitelist(matches, whitelist)
        self.load_dynamic(matches)
        if not self._check_pillar(force):
            err += [u'Pillar failed to render with the following messages:']
            err += self.state.opts[u'pillar'][u'_errors']
        else:
            high, errors = self.render_highstate(matches)
            if exclude:
                if isinstance(exclude, six.string_types):
                    exclude = exclude.split(u',')
                if u'__exclude__' in high:
                    high[u'__exclude__'].extend(exclude)
                else:
                    high[u'__exclude__'] = exclude
            err += errors
        if err:
            return err
        if not high:
            return ret
        cumask = os.umask(0o77)
        try:
            if salt.utils.platform.is_windows():
                # Make sure cache file isn't read-only
                self.state.functions[u'cmd.run'](
                    [u'attrib', u'-R', cfn],
                    python_shell=False,
                    output_loglevel=u'quiet')
            with salt.utils.files.fopen(cfn, u'w+b') as fp_:
                try:
                    self.serial.dump(high, fp_)
                except TypeError:
                    # Can't serialize pydsl
                    pass
        except (IOError, OSError):
            log.error(u'Unable to write to "state.highstate" cache file %s', cfn)

        os.umask(cumask)
        return self.state.call_high(high, orchestration_jid)

    def compile_highstate(self):
        '''
        Return just the highstate or the errors
        '''
        err = []
        top = self.get_top()
        err += self.verify_tops(top)
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)
        err += errors

        if err:
            return err

        return high

    def compile_low_chunks(self):
        '''
        Compile the highstate but don't run it, return the low chunks to
        see exactly what the highstate will execute
        '''
        top = self.get_top()
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)

        # If there is extension data reconcile it
        high, ext_errors = self.state.reconcile_extend(high)
        errors += ext_errors

        # Verify that the high data is structurally sound
        errors += self.state.verify_high(high)
        high, req_in_errors = self.state.requisite_in(high)
        errors += req_in_errors
        high = self.state.apply_exclude(high)

        if errors:
            return errors

        # Compile and verify the raw chunks
        chunks = self.state.compile_high_data(high)

        return chunks

    def compile_state_usage(self):
        '''
        Return all used and unused states for the minion based on the top match data
        '''
        err = []
        top = self.get_top()
        err += self.verify_tops(top)

        if err:
            return err

        matches = self.top_matches(top)
        state_usage = {}

        for saltenv, states in self.avail.items():
            env_usage = {
                u'used': [],
                u'unused': [],
                u'count_all': 0,
                u'count_used': 0,
                u'count_unused': 0
            }

            env_matches = matches.get(saltenv)

            for state in states:
                env_usage[u'count_all'] += 1
                if state in env_matches:
                    env_usage[u'count_used'] += 1
                    env_usage[u'used'].append(state)
                else:
                    env_usage[u'count_unused'] += 1
                    env_usage[u'unused'].append(state)

            state_usage[saltenv] = env_usage

        return state_usage


class HighState(BaseHighState):
    '''
    Generate and execute the salt "High State". The High State is the
    compound state derived from a group of template files stored on the
    salt master or in the local cache.
    '''
    # a stack of active HighState objects during a state.highstate run
    stack = []

    def __init__(
            self,
            opts,
            pillar_override=None,
            jid=None,
            pillar_enc=None,
            proxy=None,
            context=None,
            mocked=False,
            loader=u'states',
            initial_pillar=None):
        self.opts = opts
        self.client = salt.fileclient.get_file_client(self.opts)
        BaseHighState.__init__(self, opts)
        self.state = State(self.opts,
                           pillar_override,
                           jid,
                           pillar_enc,
                           proxy=proxy,
                           context=context,
                           mocked=mocked,
                           loader=loader,
                           initial_pillar=initial_pillar)
        self.matcher = salt.minion.Matcher(self.opts)
        self.proxy = proxy

        # tracks all pydsl state declarations globally across sls files
        self._pydsl_all_decls = {}

        # a stack of current rendering Sls objects, maintained and used by the pydsl renderer.
        self._pydsl_render_stack = []

    def push_active(self):
        self.stack.append(self)

    @classmethod
    def clear_active(cls):
        # Nuclear option
        #
        # Blow away the entire stack. Used primarily by the test runner but also
        # useful in custom wrappers of the HighState class, to reset the stack
        # to a fresh state.
        cls.stack = []

    @classmethod
    def pop_active(cls):
        cls.stack.pop()

    @classmethod
    def get_active(cls):
        try:
            return cls.stack[-1]
        except IndexError:
            return None


class MasterState(State):
    '''
    Create a State object for master side compiling
    '''
    def __init__(self, opts, minion):
        State.__init__(self, opts)

    def load_modules(self, data=None, proxy=None):
        '''
        Load the modules into the state
        '''
        log.info(u'Loading fresh modules for state activity')
        # Load a modified client interface that looks like the interface used
        # from the minion, but uses remote execution
        #
        self.functions = salt.client.FunctionWrapper(
                self.opts,
                self.opts[u'id']
                )
        # Load the states, but they should not be used in this class apart
        # from inspection
        self.utils = salt.loader.utils(self.opts)
        self.serializers = salt.loader.serializers(self.opts)
        self.states = salt.loader.states(self.opts, self.functions, self.utils, self.serializers)
        self.rend = salt.loader.render(self.opts, self.functions, states=self.states)


class MasterHighState(HighState):
    '''
    Execute highstate compilation from the master
    '''
    def __init__(self, master_opts, minion_opts, grains, id_,
                 saltenv=None):
        # Force the fileclient to be local
        opts = copy.deepcopy(minion_opts)
        opts[u'file_client'] = u'local'
        opts[u'file_roots'] = master_opts[u'master_roots']
        opts[u'renderer'] = master_opts[u'renderer']
        opts[u'state_top'] = master_opts[u'state_top']
        opts[u'id'] = id_
        opts[u'grains'] = grains
        HighState.__init__(self, opts)


class RemoteHighState(object):
    '''
    Manage gathering the data from the master
    '''
    def __init__(self, opts, grains):
        self.opts = opts
        self.grains = grains
        self.serial = salt.payload.Serial(self.opts)
        # self.auth = salt.crypt.SAuth(opts)
        self.channel = salt.transport.Channel.factory(self.opts[u'master_uri'])

    def compile_master(self):
        '''
        Return the state data from the master
        '''
        load = {u'grains': self.grains,
                u'opts': self.opts,
                u'cmd': u'_master_state'}
        try:
            return self.channel.send(load, tries=3, timeout=72000)
        except SaltReqTimeoutError:
            return {}
