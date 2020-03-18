# -*- coding: utf-8 -*-
'''
The State Compiler is used to execute states in Salt. A state is unlike
an execution module in that instead of just executing a command, it
ensures that a certain state is present on the system.

The data sent to the state calls is as follows:
    { 'state': '<state module name>',
      'fun': '<state function name>',
      'name': '<the name argument passed to all states>'
      'argn': '<arbitrary argument, can have many of these>'
      }
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
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
import salt.utils.data
import salt.utils.decorators.state
import salt.utils.dictupdate
import salt.utils.event
import salt.utils.files
import salt.utils.hashutils
import salt.utils.immutabletypes as immutabletypes
import salt.utils.msgpack
import salt.utils.platform
import salt.utils.process
import salt.utils.url
import salt.syspaths as syspaths
import salt.transport.client
from salt.serializers.msgpack import serialize as msgpack_serialize, deserialize as msgpack_deserialize
from salt.template import compile_template, compile_template_str
from salt.exceptions import (
    SaltRenderError,
    SaltReqTimeoutError
)
from salt.utils.odict import OrderedDict, DefaultOrderedDict
# Explicit late import to avoid circular import. DO NOT MOVE THIS.
import salt.utils.yamlloader as yamlloader

# Import third party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import map, range, reload_module
# pylint: enable=import-error,no-name-in-module,redefined-builtin

log = logging.getLogger(__name__)


# These are keywords passed to state module functions which are to be used
# by salt in this state module and not on the actual state module function
STATE_REQUISITE_KEYWORDS = frozenset([
    'onchanges',
    'onchanges_any',
    'onfail',
    'onfail_any',
    'onfail_stop',
    'prereq',
    'prerequired',
    'watch',
    'watch_any',
    'require',
    'require_any',
    'listen',
    ])
STATE_REQUISITE_IN_KEYWORDS = frozenset([
    'onchanges_in',
    'onfail_in',
    'prereq_in',
    'watch_in',
    'require_in',
    'listen_in',
    ])
STATE_RUNTIME_KEYWORDS = frozenset([
    'fun',
    'state',
    'check_cmd',
    'failhard',
    'onlyif',
    'unless',
    'retry',
    'order',
    'parallel',
    'prereq',
    'prereq_in',
    'prerequired',
    'reload_modules',
    'reload_grains',
    'reload_pillar',
    'runas',
    'runas_password',
    'fire_event',
    'saltenv',
    'use',
    'use_in',
    '__env__',
    '__sls__',
    '__id__',
    '__orchestration_jid__',
    '__pub_user',
    '__pub_arg',
    '__pub_jid',
    '__pub_fun',
    '__pub_tgt',
    '__pub_ret',
    '__pub_pid',
    '__pub_tgt_type',
    '__prereq__',
    ])

STATE_INTERNAL_KEYWORDS = STATE_REQUISITE_KEYWORDS.union(STATE_REQUISITE_IN_KEYWORDS).union(STATE_RUNTIME_KEYWORDS)


def _odict_hashable(self):
    return id(self)


OrderedDict.__hash__ = _odict_hashable


def split_low_tag(tag):
    '''
    Take a low tag and split it back into the low dict that it came from
    '''
    state, id_, name, fun = tag.split('_|-')

    return {'state': state,
            '__id__': id_,
            'name': name,
            'fun': fun}


def _gen_tag(low):
    '''
    Generate the running dict tag string from the low data structure
    '''
    return '{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(low)


def _clean_tag(tag):
    '''
    Make tag name safe for filenames
    '''
    return salt.utils.files.safe_filename_leaf(tag)


def _l_tag(name, id_):
    low = {'name': 'listen_{0}'.format(name),
           '__id__': 'listen_{0}'.format(id_),
           'state': 'Listen_Error',
           'fun': 'Listen_Error'}
    return _gen_tag(low)


def _calculate_fake_duration():
    '''
    Generate a NULL duration for when states do not run
    but we want the results to be consistent.
    '''
    utc_start_time = datetime.datetime.utcnow()
    local_start_time = utc_start_time - \
        (datetime.datetime.utcnow() - datetime.datetime.now())
    utc_finish_time = datetime.datetime.utcnow()
    start_time = local_start_time.time().isoformat()
    delta = (utc_finish_time - utc_start_time)
    # duration in milliseconds.microseconds
    duration = (delta.seconds * 1000000 + delta.microseconds) / 1000.0

    return start_time, duration


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
    if '.' in reqfirst:
        return {reqfirst.split('.')[0]: req[reqfirst]}
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
    elif state == 'sls':
        for nid, item in six.iteritems(high):
            if item['__sls__'] == name:
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
        try:
            sls_tgt = item['__sls__']
        except TypeError:
            if nid != '__exclude__':
                log.error(
                    'Invalid non-dict item \'%s\' in high data. Value: %r',
                    nid, item
                )
            continue
        else:
            if sls_tgt == sls:
                for st_ in item:
                    if st_.startswith('__'):
                        continue
                    ret.append((nid, st_))
    return ret


def format_log(ret):
    '''
    Format the state into a log message
    '''
    msg = ''
    if isinstance(ret, dict):
        # Looks like the ret may be a valid state return
        if 'changes' in ret:
            # Yep, looks like a valid state return
            chg = ret['changes']
            if not chg:
                if ret['comment']:
                    msg = ret['comment']
                else:
                    msg = 'No changes made for {0[name]}'.format(ret)
            elif isinstance(chg, dict):
                if 'diff' in chg:
                    if isinstance(chg['diff'], six.string_types):
                        msg = 'File changed:\n{0}'.format(chg['diff'])
                if all([isinstance(x, dict) for x in six.itervalues(chg)]):
                    if all([('old' in x and 'new' in x)
                            for x in six.itervalues(chg)]):
                        msg = 'Made the following changes:\n'
                        for pkg in chg:
                            old = chg[pkg]['old']
                            if not old and old not in (False, None):
                                old = 'absent'
                            new = chg[pkg]['new']
                            if not new and new not in (False, None):
                                new = 'absent'
                            # This must be able to handle unicode as some package names contain
                            # non-ascii characters like "Français" or "Español". See Issue #33605.
                            msg += '\'{0}\' changed from \'{1}\' to \'{2}\'\n'.format(pkg, old, new)
            if not msg:
                msg = six.text_type(ret['changes'])
            if ret['result'] is True or ret['result'] is None:
                log.info(msg)
            else:
                log.error(msg)
    else:
        # catch unhandled data
        log.info(six.text_type(ret))


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
    if cdata['args']:
        name = cdata['args'][0]
    else:
        name = cdata['kwargs']['name']
    return {'name': name,
            'comment': 'Not called, mocked',
            'changes': {},
            'result': True}


class StateError(Exception):
    '''
    Custom exception class.
    '''


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
                                self.opts['renderer'],
                                self.opts['renderer_blacklist'],
                                self.opts['renderer_whitelist'],
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
                    if '.' in high[name]:
                        comps = high[name].split('.')
                        if len(comps) >= 2:
                            # Merge the comps
                            comps[1] = '.'.join(comps[1:len(comps)])
                        high[name] = {
                            # '__sls__': template,
                            # '__env__': None,
                            comps[0]: [comps[1]]
                        }
                        continue
                    continue
            skeys = set()
            for key in sorted(high[name]):
                if key.startswith('_'):
                    continue
                if not isinstance(high[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
                    if len(comps) >= 2:
                        # Merge the comps
                        comps[1] = '.'.join(comps[1:len(comps)])
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
            errors.append('High data is not a dictionary and is invalid')
        reqs = OrderedDict()
        for name, body in six.iteritems(high):
            if name.startswith('__'):
                continue
            if not isinstance(name, six.string_types):
                errors.append(
                    'ID \'{0}\' in SLS \'{1}\' is not formed as a string, but '
                    'is a {2}'.format(
                        name,
                        body['__sls__'],
                        type(name).__name__
                    )
                )
            if not isinstance(body, dict):
                err = ('The type {0} in {1} is not formatted as a dictionary'
                       .format(name, body))
                errors.append(err)
                continue
            for state in body:
                if state.startswith('__'):
                    continue
                if not isinstance(body[state], list):
                    errors.append(
                        'State \'{0}\' in SLS \'{1}\' is not formed as a list'
                        .format(name, body['__sls__'])
                    )
                else:
                    fun = 0
                    if '.' in state:
                        fun += 1
                    for arg in body[state]:
                        if isinstance(arg, six.string_types):
                            fun += 1
                            if ' ' in arg.strip():
                                errors.append(('The function "{0}" in state '
                                '"{1}" in SLS "{2}" has '
                                'whitespace, a function with whitespace is '
                                'not supported, perhaps this is an argument '
                                'that is missing a ":"').format(
                                    arg,
                                    name,
                                    body['__sls__']))
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            #
                            # Add the requires to the reqs dict and check them
                            # all for recursive requisites.
                            argfirst = next(iter(arg))
                            if argfirst in ('require', 'watch', 'prereq', 'onchanges'):
                                if not isinstance(arg[argfirst], list):
                                    errors.append(('The {0}'
                                    ' statement in state \'{1}\' in SLS \'{2}\' '
                                    'needs to be formed as a list').format(
                                        argfirst,
                                        name,
                                        body['__sls__']
                                        ))
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    reqs[name] = {'state': state}
                                    for req in arg[argfirst]:
                                        if isinstance(req, six.string_types):
                                            req = {'id': req}
                                        if not isinstance(req, dict):
                                            err = ('Requisite declaration {0}'
                                            ' in SLS {1} is not formed as a'
                                            ' single key dictionary').format(
                                                req,
                                                body['__sls__'])
                                            errors.append(err)
                                            continue
                                        req_key = next(iter(req))
                                        req_val = req[req_key]
                                        if '.' in req_key:
                                            errors.append((
                                                'Invalid requisite type \'{0}\' '
                                                'in state \'{1}\', in SLS '
                                                '\'{2}\'. Requisite types must '
                                                'not contain dots, did you '
                                                'mean \'{3}\'?'.format(
                                                    req_key,
                                                    name,
                                                    body['__sls__'],
                                                    req_key[:req_key.find('.')]
                                                )
                                            ))
                                        if not ishashable(req_val):
                                            errors.append((
                                                'Illegal requisite "{0}", '
                                                'is SLS {1}\n'
                                                ).format(
                                                    six.text_type(req_val),
                                                    body['__sls__']))
                                            continue

                                        # Check for global recursive requisites
                                        reqs[name][req_val] = req_key
                                        # I am going beyond 80 chars on
                                        # purpose, this is just too much
                                        # of a pain to deal with otherwise
                                        if req_val in reqs:
                                            if name in reqs[req_val]:
                                                if reqs[req_val][name] == state:
                                                    if reqs[req_val]['state'] == reqs[name][req_val]:
                                                        err = ('A recursive '
                                                        'requisite was found, SLS '
                                                        '"{0}" ID "{1}" ID "{2}"'
                                                        ).format(
                                                                body['__sls__'],
                                                                name,
                                                                req_val
                                                                )
                                                        errors.append(err)
                                # Make sure that there is only one key in the
                                # dict
                                if len(list(arg)) != 1:
                                    errors.append(('Multiple dictionaries '
                                    'defined in argument of state \'{0}\' in SLS'
                                    ' \'{1}\'').format(
                                        name,
                                        body['__sls__']))
                    if not fun:
                        if state == 'require' or state == 'watch':
                            continue
                        errors.append(('No function declared in state \'{0}\' in'
                            ' SLS \'{1}\'').format(state, body['__sls__']))
                    elif fun > 1:
                        errors.append(
                            'Too many functions declared in state \'{0}\' in '
                            'SLS \'{1}\''.format(state, body['__sls__'])
                        )
        return errors

    def order_chunks(self, chunks):
        '''
        Sort the chunk list verifying that the chunks follow the order
        specified in the order options.
        '''
        cap = 1
        for chunk in chunks:
            if 'order' in chunk:
                if not isinstance(chunk['order'], int):
                    continue

                chunk_order = chunk['order']
                if chunk_order > cap - 1 and chunk_order > 0:
                    cap = chunk_order + 100
        for chunk in chunks:
            if 'order' not in chunk:
                chunk['order'] = cap
                continue

            if not isinstance(chunk['order'], (int, float)):
                if chunk['order'] == 'last':
                    chunk['order'] = cap + 1000000
                elif chunk['order'] == 'first':
                    chunk['order'] = 0
                else:
                    chunk['order'] = cap
            if 'name_order' in chunk:
                chunk['order'] = chunk['order'] + chunk.pop('name_order') / 10000.0
            if chunk['order'] < 0:
                chunk['order'] = cap + 1000000 + chunk['order']
            chunk['name'] = salt.utils.data.decode(chunk['name'])
        chunks.sort(key=lambda chunk: (chunk['order'], '{0[state]}{0[name]}{0[fun]}'.format(chunk)))
        return chunks

    def compile_high_data(self, high):
        '''
        "Compile" the high data as it is retrieved from the CLI or YAML into
        the individual state executor structures
        '''
        chunks = []
        for name, body in six.iteritems(high):
            if name.startswith('__'):
                continue
            for state, run in six.iteritems(body):
                funcs = set()
                names = []
                if state.startswith('__'):
                    continue
                chunk = {'state': state,
                         'name': name}
                if '__sls__' in body:
                    chunk['__sls__'] = body['__sls__']
                if '__env__' in body:
                    chunk['__env__'] = body['__env__']
                chunk['__id__'] = name
                for arg in run:
                    if isinstance(arg, six.string_types):
                        funcs.add(arg)
                        continue
                    if isinstance(arg, dict):
                        for key, val in six.iteritems(arg):
                            if key == 'names':
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
                            live['name'] = low_name
                            list(map(live.update, entry[low_name]))
                        else:
                            live['name'] = entry
                        live['name_order'] = name_order
                        name_order = name_order + 1
                        for fun in funcs:
                            live['fun'] = fun
                            chunks.append(live)
                else:
                    live = copy.deepcopy(chunk)
                    for fun in funcs:
                        live['fun'] = fun
                        chunks.append(live)
        chunks = self.order_chunks(chunks)
        return chunks

    def apply_exclude(self, high):
        '''
        Read in the __exclude__ list and remove all excluded objects from the
        high data
        '''
        if '__exclude__' not in high:
            return high
        ex_sls = set()
        ex_id = set()
        exclude = high.pop('__exclude__')
        for exc in exclude:
            if isinstance(exc, six.string_types):
                # The exclude statement is a string, assume it is an sls
                ex_sls.add(exc)
            if isinstance(exc, dict):
                # Explicitly declared exclude
                if len(exc) != 1:
                    continue
                key = next(six.iterkeys(exc))
                if key == 'sls':
                    ex_sls.add(exc['sls'])
                elif key == 'id':
                    ex_id.add(exc['id'])
        # Now the excludes have been simplified, use them
        if ex_sls:
            # There are sls excludes, find the associtaed ids
            for name, body in six.iteritems(high):
                if name.startswith('__'):
                    continue
                if body.get('__sls__', '') in ex_sls:
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
            loader='states',
            initial_pillar=None):
        self.states_loader = loader
        if 'grains' not in opts:
            opts['grains'] = salt.loader.grains(opts)
        self.opts = opts
        self.proxy = proxy
        self._pillar_override = pillar_override
        if pillar_enc is not None:
            try:
                pillar_enc = pillar_enc.lower()
            except AttributeError:
                pillar_enc = six.text_type(pillar_enc).lower()
        self._pillar_enc = pillar_enc
        log.debug('Gathering pillar data for state run')
        if initial_pillar and not self._pillar_override:
            self.opts['pillar'] = initial_pillar
        else:
            # Compile pillar data
            self.opts['pillar'] = self._gather_pillar()
            # Reapply overrides on top of compiled pillar
            if self._pillar_override:
                self.opts['pillar'] = salt.utils.dictupdate.merge(
                    self.opts['pillar'],
                    self._pillar_override,
                    self.opts.get('pillar_source_merging_strategy', 'smart'),
                    self.opts.get('renderer', 'yaml'),
                    self.opts.get('pillar_merge_lists', False))
        log.debug('Finished gathering pillar data for state run')
        self.state_con = context or {}
        self.load_modules()
        self.active = set()
        self.mod_init = set()
        self.pre = {}
        self.__run_num = 0
        self.jid = jid
        self.instance_id = six.text_type(id(self))
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
                        renderers=getattr(self, 'rend', None),
                        opts=self.opts,
                        valid_rend=self.opts['decrypt_pillar_renderers'])
                except Exception as exc:  # pylint: disable=broad-except
                    log.error('Failed to decrypt pillar override: %s', exc)

            if isinstance(self._pillar_override, six.string_types):
                # This can happen if an entire pillar dictionary was passed as
                # a single encrypted string. The override will have been
                # decrypted above, and should now be a stringified dictionary.
                # Use the YAML loader to convert that to a Python dictionary.
                try:
                    self._pillar_override = yamlloader.load(
                        self._pillar_override,
                        Loader=yamlloader.SaltYamlSafeLoader)
                except Exception as exc:  # pylint: disable=broad-except
                    log.error('Failed to load CLI pillar override')
                    log.exception(exc)

            if not isinstance(self._pillar_override, dict):
                log.error('Pillar override was not passed as a dictionary')
                self._pillar_override = None

        pillar = salt.pillar.get_pillar(
                self.opts,
                self.opts['grains'],
                self.opts['id'],
                self.opts['saltenv'],
                pillar_override=self._pillar_override,
                pillarenv=self.opts.get('pillarenv'))
        return pillar.compile_pillar()

    def _mod_init(self, low):
        '''
        Check the module initialization function, if this is the first run
        of a state package that has a mod_init function, then execute the
        mod_init function in the state module.
        '''
        # ensure that the module is loaded
        try:
            self.states['{0}.{1}'.format(low['state'], low['fun'])]  # pylint: disable=W0106
        except KeyError:
            return
        minit = '{0}.mod_init'.format(low['state'])
        if low['state'] not in self.mod_init:
            if minit in self.states._dict:
                mret = self.states[minit](low)
                if not mret:
                    return
                self.mod_init.add(low['state'])

    def _mod_aggregate(self, low, running, chunks):
        '''
        Execute the aggregation systems to runtime modify the low chunk
        '''
        agg_opt = self.functions['config.option']('state_aggregate')
        if 'aggregate' in low:
            agg_opt = low['aggregate']
        if agg_opt is True:
            agg_opt = [low['state']]
        elif not isinstance(agg_opt, list):
            return low
        if low['state'] in agg_opt and not low.get('__agg__'):
            agg_fun = '{0}.mod_aggregate'.format(low['state'])
            if agg_fun in self.states:
                try:
                    low = self.states[agg_fun](low, chunks, running)
                    low['__agg__'] = True
                except TypeError:
                    log.error('Failed to execute aggregate for state %s', low['state'])
        return low

    def _run_check(self, low_data):
        '''
        Check that unless doesn't return 0, and that onlyif returns a 0.
        '''
        ret = {'result': False, 'comment': []}
        cmd_opts = {}

        if 'shell' in self.opts['grains']:
            cmd_opts['shell'] = self.opts['grains'].get('shell')

        if 'onlyif' in low_data:
            _ret = self._run_check_onlyif(low_data, cmd_opts)
            ret['result'] = _ret['result']
            ret['comment'].append(_ret['comment'])
            if 'skip_watch' in _ret:
                ret['skip_watch'] = _ret['skip_watch']

        if 'unless' in low_data:
            _ret = self._run_check_unless(low_data, cmd_opts)
            # If either result is True, the returned result should be True
            ret['result'] = _ret['result'] or ret['result']
            ret['comment'].append(_ret['comment'])
            if 'skip_watch' in _ret:
                # If either result is True, the returned result should be True
                ret['skip_watch'] = _ret['skip_watch'] or ret['skip_watch']

        return ret

    def _run_check_function(self, entry):
        """Format slot args and run unless/onlyif function."""
        fun = entry.pop('fun')
        args = entry.pop('args') if 'args' in entry else []
        cdata = {
            'args': args,
            'kwargs': entry
        }
        self.format_slots(cdata)
        return self.functions[fun](*cdata['args'], **cdata['kwargs'])

    def _run_check_onlyif(self, low_data, cmd_opts):
        '''
        Check that unless doesn't return 0, and that onlyif returns a 0.
        '''
        ret = {'result': False}

        if not isinstance(low_data['onlyif'], list):
            low_data_onlyif = [low_data['onlyif']]
        else:
            low_data_onlyif = low_data['onlyif']

        def _check_cmd(cmd):
            if cmd != 0 and ret['result'] is False:
                ret.update({'comment': 'onlyif condition is false',
                            'skip_watch': True,
                            'result': True})
            elif cmd == 0:
                ret.update({'comment': 'onlyif condition is true', 'result': False})

        for entry in low_data_onlyif:
            if isinstance(entry, six.string_types):
                cmd = self.functions['cmd.retcode'](
                    entry, ignore_retcode=True, python_shell=True, **cmd_opts)
                log.debug('Last command return code: %s', cmd)
                _check_cmd(cmd)
            elif isinstance(entry, dict):
                if 'fun' not in entry:
                    ret['comment'] = 'no `fun` argument in onlyif: {0}'.format(entry)
                    log.warning(ret['comment'])
                    return ret

                result = self._run_check_function(entry)
                if self.state_con.get('retcode', 0):
                    _check_cmd(self.state_con['retcode'])
                elif not result:
                    ret.update({'comment': 'onlyif condition is false',
                                'skip_watch': True,
                                'result': True})
                else:
                    ret.update({'comment': 'onlyif condition is true',
                                'result': False})

            else:
                ret.update({'comment': 'onlyif execution failed, bad type passed', 'result': False})
        return ret

    def _run_check_unless(self, low_data, cmd_opts):
        '''
        Check that unless doesn't return 0, and that onlyif returns a 0.
        '''
        ret = {'result': False}

        if not isinstance(low_data['unless'], list):
            low_data_unless = [low_data['unless']]
        else:
            low_data_unless = low_data['unless']

        def _check_cmd(cmd):
            if cmd == 0 and ret['result'] is False:
                ret.update({'comment': 'unless condition is true',
                            'skip_watch': True,
                            'result': True})
            elif cmd != 0:
                ret.update({'comment': 'unless condition is false', 'result': False})

        for entry in low_data_unless:
            if isinstance(entry, six.string_types):
                cmd = self.functions['cmd.retcode'](entry, ignore_retcode=True, python_shell=True, **cmd_opts)
                log.debug('Last command return code: %s', cmd)
                _check_cmd(cmd)
            elif isinstance(entry, dict):
                if 'fun' not in entry:
                    ret['comment'] = 'no `fun` argument in unless: {0}'.format(entry)
                    log.warning(ret['comment'])
                    return ret

                result = self._run_check_function(entry)
                if self.state_con.get('retcode', 0):
                    _check_cmd(self.state_con['retcode'])
                elif result:
                    ret.update({'comment': 'unless condition is true',
                                'skip_watch': True,
                                'result': True})
                else:
                    ret.update({'comment': 'unless condition is false',
                                'result': False})
            else:
                ret.update({'comment': 'unless condition is false, bad type passed', 'result': False})

        # No reason to stop, return ret
        return ret

    def _run_check_cmd(self, low_data):
        '''
        Alter the way a successful state run is determined
        '''
        ret = {'result': False}
        cmd_opts = {}
        if 'shell' in self.opts['grains']:
            cmd_opts['shell'] = self.opts['grains'].get('shell')
        for entry in low_data['check_cmd']:
            cmd = self.functions['cmd.retcode'](
                entry, ignore_retcode=True, python_shell=True, **cmd_opts)
            log.debug('Last command return code: %s', cmd)
            if cmd == 0 and ret['result'] is False:
                ret.update({'comment': 'check_cmd determined the state succeeded', 'result': True})
            elif cmd != 0:
                ret.update({'comment': 'check_cmd determined the state failed', 'result': False})
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
        if self.states_loader == 'thorium':
            self.states = salt.loader.thorium(self.opts, self.functions, {})  # TODO: Add runners, proxy?
        else:
            self.states = salt.loader.states(self.opts, self.functions, self.utils,
                                             self.serializers, context=self.state_con, proxy=self.proxy)

    def load_modules(self, data=None, proxy=None):
        '''
        Load the modules into the state
        '''
        log.info('Loading fresh modules for state activity')
        self.utils = salt.loader.utils(self.opts)
        self.functions = salt.loader.minion_mods(self.opts, self.state_con,
                                                 utils=self.utils,
                                                 proxy=self.proxy)
        if isinstance(data, dict):
            if data.get('provider', False):
                if isinstance(data['provider'], six.string_types):
                    providers = [{data['state']: data['provider']}]
                elif isinstance(data['provider'], list):
                    providers = data['provider']
                else:
                    providers = {}
                for provider in providers:
                    for mod in provider:
                        funcs = salt.loader.raw_mod(self.opts,
                                provider[mod],
                                self.functions)
                        if funcs:
                            for func in funcs:
                                f_key = '{0}{1}'.format(
                                        mod,
                                        func[func.rindex('.'):]
                                        )
                                self.functions[f_key] = funcs[func]
        self.serializers = salt.loader.serializers(self.opts)
        self._load_states()
        self.rend = salt.loader.render(self.opts, self.functions,
                                       states=self.states, proxy=self.proxy, context=self.state_con)

    def module_refresh(self):
        '''
        Refresh all the modules
        '''
        log.debug('Refreshing modules...')
        if self.opts['grains'].get('os') != 'MacOS':
            # In case a package has been installed into the current python
            # process 'site-packages', the 'site' module needs to be reloaded in
            # order for the newly installed package to be importable.
            try:
                reload_module(site)
            except RuntimeError:
                log.error('Error encountered during module reload. Modules were not reloaded.')
            except TypeError:
                log.error('Error encountered during module reload. Modules were not reloaded.')
        self.load_modules()
        if not self.opts.get('local', False) and self.opts.get('multiprocessing', True):
            self.functions['saltutil.refresh_modules']()

    def check_refresh(self, data, ret):
        '''
        Check to see if the modules for this state instance need to be updated,
        only update if the state is a file or a package and if it changed
        something. If the file function is managed check to see if the file is a
        possible module type, e.g. a python, pyx, or .so. Always refresh if the
        function is recurse, since that can lay down anything.
        '''
        _reload_modules = False
        if data.get('reload_grains', False):
            log.debug('Refreshing grains...')
            self.opts['grains'] = salt.loader.grains(self.opts)
            _reload_modules = True

        if data.get('reload_pillar', False):
            log.debug('Refreshing pillar...')
            self.opts['pillar'] = self._gather_pillar()
            _reload_modules = True

        if not ret['changes']:
            if data.get('force_reload_modules', False):
                self.module_refresh()
            return

        if data.get('reload_modules', False) or _reload_modules:
            # User explicitly requests a reload
            self.module_refresh()
            return

        if data['state'] == 'file':
            if data['fun'] == 'managed':
                if data['name'].endswith(
                    ('.py', '.pyx', '.pyo', '.pyc', '.so')):
                    self.module_refresh()
            elif data['fun'] == 'recurse':
                self.module_refresh()
            elif data['fun'] == 'symlink':
                if 'bin' in data['name']:
                    self.module_refresh()
        elif data['state'] in ('pkg', 'ports'):
            self.module_refresh()

    def verify_data(self, data):
        '''
        Verify the data, return an error statement if something is wrong
        '''
        errors = []
        if 'state' not in data:
            errors.append('Missing "state" data')
        if 'fun' not in data:
            errors.append('Missing "fun" data')
        if 'name' not in data:
            errors.append('Missing "name" data')
        if data['name'] and not isinstance(data['name'], six.string_types):
            errors.append(
                'ID \'{0}\' {1}is not formed as a string, but is a {2}'.format(
                    data['name'],
                    'in SLS \'{0}\' '.format(data['__sls__'])
                        if '__sls__' in data else '',
                    type(data['name']).__name__
                )
            )
        if errors:
            return errors
        full = data['state'] + '.' + data['fun']
        if full not in self.states:
            if '__sls__' in data:
                errors.append(
                    'State \'{0}\' was not found in SLS \'{1}\''.format(
                        full,
                        data['__sls__']
                        )
                    )
                reason = self.states.missing_fun_string(full)
                if reason:
                    errors.append('Reason: {0}'.format(reason))
            else:
                errors.append(
                        'Specified state \'{0}\' was not found'.format(
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
                        'Missing parameter {0} for state {1}'.format(
                            aspec.args[ind],
                            full
                        )
                    )
        # If this chunk has a recursive require, then it will cause a
        # recursive loop when executing, check for it
        reqdec = ''
        if 'require' in data:
            reqdec = 'require'
        if 'watch' in data:
            # Check to see if the service has a mod_watch function, if it does
            # not, then just require
            # to just require extend the require statement with the contents
            # of watch so that the mod_watch function is not called and the
            # requisite capability is still used
            if '{0}.mod_watch'.format(data['state']) not in self.states:
                if 'require' in data:
                    data['require'].extend(data.pop('watch'))
                else:
                    data['require'] = data.pop('watch')
                reqdec = 'require'
            else:
                reqdec = 'watch'
        if reqdec:
            for req in data[reqdec]:
                reqfirst = next(iter(req))
                if data['state'] == reqfirst:
                    if (fnmatch.fnmatch(data['name'], req[reqfirst])
                            or fnmatch.fnmatch(data['__id__'], req[reqfirst])):
                        err = ('Recursive require detected in SLS {0} for'
                               ' require {1} in ID {2}').format(
                                   data['__sls__'],
                                   req,
                                   data['__id__'])
                        errors.append(err)
        return errors

    def verify_high(self, high):
        '''
        Verify that the high data is viable and follows the data structure
        '''
        errors = []
        if not isinstance(high, dict):
            errors.append('High data is not a dictionary and is invalid')
        reqs = OrderedDict()
        for name, body in six.iteritems(high):
            try:
                if name.startswith('__'):
                    continue
            except AttributeError:
                pass
            if not isinstance(name, six.string_types):
                errors.append(
                    'ID \'{0}\' in SLS \'{1}\' is not formed as a string, but '
                    'is a {2}. It may need to be quoted.'.format(
                        name, body['__sls__'], type(name).__name__)
                )
            if not isinstance(body, dict):
                err = ('The type {0} in {1} is not formatted as a dictionary'
                       .format(name, body))
                errors.append(err)
                continue
            for state in body:
                if state.startswith('__'):
                    continue
                if body[state] is None:
                    errors.append(
                        'ID \'{0}\' in SLS \'{1}\' contains a short declaration '
                        '({2}) with a trailing colon. When not passing any '
                        'arguments to a state, the colon must be omitted.'
                        .format(name, body['__sls__'], state)
                    )
                    continue
                if not isinstance(body[state], list):
                    errors.append(
                        'State \'{0}\' in SLS \'{1}\' is not formed as a list'
                        .format(name, body['__sls__'])
                    )
                else:
                    fun = 0
                    if '.' in state:
                        fun += 1
                    for arg in body[state]:
                        if isinstance(arg, six.string_types):
                            fun += 1
                            if ' ' in arg.strip():
                                errors.append(('The function "{0}" in state '
                                '"{1}" in SLS "{2}" has '
                                'whitespace, a function with whitespace is '
                                'not supported, perhaps this is an argument '
                                'that is missing a ":"').format(
                                    arg,
                                    name,
                                    body['__sls__']))
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            #
                            # Add the requires to the reqs dict and check them
                            # all for recursive requisites.
                            argfirst = next(iter(arg))
                            if argfirst == 'names':
                                if not isinstance(arg[argfirst], list):
                                    errors.append(
                                        'The \'names\' argument in state '
                                        '\'{0}\' in SLS \'{1}\' needs to be '
                                        'formed as a list'
                                        .format(name, body['__sls__'])
                                    )
                            if argfirst in ('require', 'watch', 'prereq', 'onchanges'):
                                if not isinstance(arg[argfirst], list):
                                    errors.append(
                                        'The {0} statement in state \'{1}\' in '
                                        'SLS \'{2}\' needs to be formed as a '
                                        'list'.format(argfirst,
                                                      name,
                                                      body['__sls__'])
                                    )
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    reqs[name] = OrderedDict(state=state)
                                    for req in arg[argfirst]:
                                        if isinstance(req, six.string_types):
                                            req = {'id': req}
                                        if not isinstance(req, dict):
                                            err = ('Requisite declaration {0}'
                                            ' in SLS {1} is not formed as a'
                                            ' single key dictionary').format(
                                                req,
                                                body['__sls__'])
                                            errors.append(err)
                                            continue
                                        req_key = next(iter(req))
                                        req_val = req[req_key]
                                        if '.' in req_key:
                                            errors.append(
                                                'Invalid requisite type \'{0}\' '
                                                'in state \'{1}\', in SLS '
                                                '\'{2}\'. Requisite types must '
                                                'not contain dots, did you '
                                                'mean \'{3}\'?'.format(
                                                    req_key,
                                                    name,
                                                    body['__sls__'],
                                                    req_key[:req_key.find('.')]
                                                )
                                            )
                                        if not ishashable(req_val):
                                            errors.append((
                                                'Illegal requisite "{0}", '
                                                'please check your syntax.\n'
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
                                                    if reqs[req_val]['state'] == reqs[name][req_val]:
                                                        err = ('A recursive '
                                                        'requisite was found, SLS '
                                                        '"{0}" ID "{1}" ID "{2}"'
                                                        ).format(
                                                                body['__sls__'],
                                                                name,
                                                                req_val
                                                                )
                                                        errors.append(err)
                                # Make sure that there is only one key in the
                                # dict
                                if len(list(arg)) != 1:
                                    errors.append(
                                        'Multiple dictionaries defined in '
                                        'argument of state \'{0}\' in SLS \'{1}\''
                                        .format(name, body['__sls__'])
                                    )
                    if not fun:
                        if state == 'require' or state == 'watch':
                            continue
                        errors.append(
                            'No function declared in state \'{0}\' in SLS \'{1}\''
                            .format(state, body['__sls__'])
                        )
                    elif fun > 1:
                        errors.append(
                            'Too many functions declared in state \'{0}\' in '
                            'SLS \'{1}\''.format(state, body['__sls__'])
                        )
        return errors

    def verify_chunks(self, chunks):
        '''
        Verify the chunks in a list of low data structures
        '''
        err = []
        for chunk in chunks:
            err.extend(self.verify_data(chunk))
        return err

    def order_chunks(self, chunks):
        '''
        Sort the chunk list verifying that the chunks follow the order
        specified in the order options.
        '''
        cap = 1
        for chunk in chunks:
            if 'order' in chunk:
                if not isinstance(chunk['order'], int):
                    continue

                chunk_order = chunk['order']
                if chunk_order > cap - 1 and chunk_order > 0:
                    cap = chunk_order + 100
        for chunk in chunks:
            if 'order' not in chunk:
                chunk['order'] = cap
                continue

            if not isinstance(chunk['order'], (int, float)):
                if chunk['order'] == 'last':
                    chunk['order'] = cap + 1000000
                elif chunk['order'] == 'first':
                    chunk['order'] = 0
                else:
                    chunk['order'] = cap
            if 'name_order' in chunk:
                chunk['order'] = chunk['order'] + chunk.pop('name_order') / 10000.0
            if chunk['order'] < 0:
                chunk['order'] = cap + 1000000 + chunk['order']
        chunks.sort(key=lambda chunk: (chunk['order'], '{0[state]}{0[name]}{0[fun]}'.format(chunk)))
        return chunks

    def compile_high_data(self, high, orchestration_jid=None):
        '''
        "Compile" the high data as it is retrieved from the CLI or YAML into
        the individual state executor structures
        '''
        chunks = []
        for name, body in six.iteritems(high):
            if name.startswith('__'):
                continue
            for state, run in six.iteritems(body):
                funcs = set()
                names = []
                if state.startswith('__'):
                    continue
                chunk = {'state': state,
                         'name': name}
                if orchestration_jid is not None:
                    chunk['__orchestration_jid__'] = orchestration_jid
                if '__sls__' in body:
                    chunk['__sls__'] = body['__sls__']
                if '__env__' in body:
                    chunk['__env__'] = body['__env__']
                chunk['__id__'] = name
                for arg in run:
                    if isinstance(arg, six.string_types):
                        funcs.add(arg)
                        continue
                    if isinstance(arg, dict):
                        for key, val in six.iteritems(arg):
                            if key == 'names':
                                for _name in val:
                                    if _name not in names:
                                        names.append(_name)
                            elif key == 'state':
                                # Don't pass down a state override
                                continue
                            elif (key == 'name' and
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
                            live['name'] = low_name
                            list(map(live.update, entry[low_name]))
                        else:
                            live['name'] = entry
                        live['name_order'] = name_order
                        name_order += 1
                        for fun in funcs:
                            live['fun'] = fun
                            chunks.append(live)
                else:
                    live = copy.deepcopy(chunk)
                    for fun in funcs:
                        live['fun'] = fun
                        chunks.append(live)
        chunks = self.order_chunks(chunks)
        return chunks

    def reconcile_extend(self, high):
        '''
        Pull the extend data and add it to the respective high data
        '''
        errors = []
        if '__extend__' not in high:
            return high, errors
        ext = high.pop('__extend__')
        for ext_chunk in ext:
            for name, body in six.iteritems(ext_chunk):
                if name not in high:
                    state_type = next(
                        x for x in body if not x.startswith('__')
                    )
                    # Check for a matching 'name' override in high data
                    ids = find_name(name, state_type, high)
                    if len(ids) != 1:
                        errors.append(
                            'Cannot extend ID \'{0}\' in \'{1}:{2}\'. It is not '
                            'part of the high state.\n'
                            'This is likely due to a missing include statement '
                            'or an incorrectly typed ID.\nEnsure that a '
                            'state with an ID of \'{0}\' is available\nin '
                            'environment \'{1}\' and to SLS \'{2}\''.format(
                                name,
                                body.get('__env__', 'base'),
                                body.get('__sls__', 'base'))
                            )
                        continue
                    else:
                        name = ids[0][0]

                for state, run in six.iteritems(body):
                    if state.startswith('__'):
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
                                if (argfirst == 'name' and
                                    next(iter(high[name][state][hind])) == 'names'):
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
        if '__exclude__' not in high:
            return high
        ex_sls = set()
        ex_id = set()
        exclude = high.pop('__exclude__')
        for exc in exclude:
            if isinstance(exc, six.string_types):
                # The exclude statement is a string, assume it is an sls
                ex_sls.add(exc)
            if isinstance(exc, dict):
                # Explicitly declared exclude
                if len(exc) != 1:
                    continue
                key = next(six.iterkeys(exc))
                if key == 'sls':
                    ex_sls.add(exc['sls'])
                elif key == 'id':
                    ex_id.add(exc['id'])
        # Now the excludes have been simplified, use them
        if ex_sls:
            # There are sls excludes, find the associated ids
            for name, body in six.iteritems(high):
                if name.startswith('__'):
                    continue
                sls = body.get('__sls__', '')
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
        req_in = {'require_in', 'watch_in', 'onfail_in', 'onchanges_in', 'use', 'use_in', 'prereq', 'prereq_in'}
        req_in_all = req_in.union({'require', 'watch', 'onfail', 'onfail_stop', 'onchanges'})
        extend = {}
        errors = []
        for id_, body in six.iteritems(high):
            if not isinstance(body, dict):
                continue
            for state, run in six.iteritems(body):
                if state.startswith('__'):
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
                        rkey = key.split('_')[0]
                        items = arg[key]
                        if isinstance(items, dict):
                            # Formatted as a single req_in
                            for _state, name in six.iteritems(items):

                                # Not a use requisite_in
                                found = False
                                if name not in extend:
                                    extend[name] = OrderedDict()
                                if '.' in _state:
                                    errors.append(
                                        'Invalid requisite in {0}: {1} for '
                                        '{2}, in SLS \'{3}\'. Requisites must '
                                        'not contain dots, did you mean \'{4}\'?'
                                        .format(
                                            rkey,
                                            _state,
                                            name,
                                            body['__sls__'],
                                            _state[:_state.find('.')]
                                        )
                                    )
                                    _state = _state.split('.')[0]
                                if _state not in extend[name]:
                                    extend[name][_state] = []
                                extend[name]['__env__'] = body['__env__']
                                extend[name]['__sls__'] = body['__sls__']
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
                                    if ind in high:
                                        _ind_high = [x for x
                                                     in high[ind]
                                                     if not x.startswith('__')]
                                        ind = {_ind_high[0]: ind}
                                    else:
                                        found = False
                                        for _id in iter(high):
                                            for state in [state for state
                                                          in iter(high[_id])
                                                          if not state.startswith('__')]:
                                                for j in iter(high[_id][state]):
                                                    if isinstance(j, dict) and 'name' in j:
                                                        if j['name'] == ind:
                                                            ind = {state: _id}
                                                            found = True
                                        if not found:
                                            continue
                                if len(ind) < 1:
                                    continue
                                pstate = next(iter(ind))
                                pname = ind[pstate]
                                if pstate == 'sls':
                                    # Expand hinges here
                                    hinges = find_sls_ids(pname, high)
                                else:
                                    hinges.append((pname, pstate))
                                if '.' in pstate:
                                    errors.append(
                                        'Invalid requisite in {0}: {1} for '
                                        '{2}, in SLS \'{3}\'. Requisites must '
                                        'not contain dots, did you mean \'{4}\'?'
                                        .format(
                                            rkey,
                                            pstate,
                                            pname,
                                            body['__sls__'],
                                            pstate[:pstate.find('.')]
                                        )
                                    )
                                    pstate = pstate.split(".")[0]
                                for tup in hinges:
                                    name, _state = tup
                                    if key == 'prereq_in':
                                        # Add prerequired to origin
                                        if id_ not in extend:
                                            extend[id_] = OrderedDict()
                                        if state not in extend[id_]:
                                            extend[id_][state] = []
                                        extend[id_][state].append(
                                                {'prerequired': [{_state: name}]}
                                                )
                                    if key == 'prereq':
                                        # Add prerequired to prereqs
                                        ext_ids = find_name(name, _state, high)
                                        for ext_id, _req_state in ext_ids:
                                            if ext_id not in extend:
                                                extend[ext_id] = OrderedDict()
                                            if _req_state not in extend[ext_id]:
                                                extend[ext_id][_req_state] = []
                                            extend[ext_id][_req_state].append(
                                                    {'prerequired': [{state: id_}]}
                                                    )
                                        continue
                                    if key == 'use_in':
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
                                                if next(six.iterkeys(arg)) == 'name':
                                                    continue
                                                if next(six.iterkeys(arg)) == 'names':
                                                    continue
                                                extend[ext_id][_req_state].append(arg)
                                        continue
                                    if key == 'use':
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
                                                if next(six.iterkeys(arg)) == 'name':
                                                    continue
                                                if next(six.iterkeys(arg)) == 'names':
                                                    continue
                                                extend[id_][state].append(arg)
                                        continue
                                    found = False
                                    if name not in extend:
                                        extend[name] = OrderedDict()
                                    if _state not in extend[name]:
                                        extend[name][_state] = []
                                    extend[name]['__env__'] = body['__env__']
                                    extend[name]['__sls__'] = body['__sls__']
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
        high['__extend__'] = []
        for key, val in six.iteritems(extend):
            high['__extend__'].append({key: val})
        req_in_high, req_in_errors = self.reconcile_extend(high)
        errors.extend(req_in_errors)
        return req_in_high, errors

    def _call_parallel_target(self, name, cdata, low):
        '''
        The target function to call that will create the parallel thread/process
        '''
        # we need to re-record start/end duration here because it is impossible to
        # correctly calculate further down the chain
        utc_start_time = datetime.datetime.utcnow()

        tag = _gen_tag(low)
        try:
            ret = self.states[cdata['full']](*cdata['args'],
                                             **cdata['kwargs'])
        except Exception as exc:  # pylint: disable=broad-except
            log.debug('An exception occurred in this state: %s', exc,
                      exc_info_on_loglevel=logging.DEBUG)
            trb = traceback.format_exc()
            ret = {
                'result': False,
                'name': name,
                'changes': {},
                'comment': 'An exception occurred in this state: {0}'.format(trb)
            }

        utc_finish_time = datetime.datetime.utcnow()
        delta = (utc_finish_time - utc_start_time)
        # duration in milliseconds.microseconds
        duration = (delta.seconds * 1000000 + delta.microseconds) / 1000.0
        ret['duration'] = duration

        troot = os.path.join(self.opts['cachedir'], self.jid)
        tfile = os.path.join(
            troot,
            salt.utils.hashutils.sha1_digest(tag))
        if not os.path.isdir(troot):
            try:
                os.makedirs(troot)
            except OSError:
                # Looks like the directory was created between the check
                # and the attempt, we are safe to pass
                pass
        with salt.utils.files.fopen(tfile, 'wb+') as fp_:
            fp_.write(msgpack_serialize(ret))

    def call_parallel(self, cdata, low):
        '''
        Call the state defined in the given cdata in parallel
        '''
        # There are a number of possibilities to not have the cdata
        # populated with what we might have expected, so just be smart
        # enough to not raise another KeyError as the name is easily
        # guessable and fallback in all cases to present the real
        # exception to the user
        name = (cdata.get('args') or [None])[0] or cdata['kwargs'].get('name')
        if not name:
            name = low.get('name', low.get('__id__'))

        proc = salt.utils.process.Process(
                target=self._call_parallel_target,
                args=(name, cdata, low))
        proc.start()
        ret = {'name': name,
                'result': None,
                'changes': {},
                'comment': 'Started in a separate process',
                'proc': proc}
        return ret

    @salt.utils.decorators.state.OutputUnifier('content_check', 'unify')
    def call(self, low, chunks=None, running=None, retries=1):
        '''
        Call a state directly with the low data structure, verify data
        before processing.
        '''
        utc_start_time = datetime.datetime.utcnow()
        local_start_time = utc_start_time - (datetime.datetime.utcnow() - datetime.datetime.now())
        log.info('Running state [%s] at time %s',
            low['name'].strip() if isinstance(low['name'], six.string_types)
                else low['name'],
            local_start_time.time().isoformat()
        )
        errors = self.verify_data(low)
        if errors:
            ret = {
                'result': False,
                'name': low['name'],
                'changes': {},
                'comment': '',
                }
            for err in errors:
                ret['comment'] += '{0}\n'.format(err)
            ret['__run_num__'] = self.__run_num
            self.__run_num += 1
            format_log(ret)
            self.check_refresh(low, ret)
            return ret
        else:
            ret = {'result': False, 'name': low['name'], 'changes': {}}

        self.state_con['runas'] = low.get('runas', None)

        if low['state'] == 'cmd' and 'password' in low:
            self.state_con['runas_password'] = low['password']
        else:
            self.state_con['runas_password'] = low.get('runas_password', None)

        if not low.get('__prereq__'):
            log.info(
                'Executing state %s.%s for [%s]',
                low['state'],
                low['fun'],
                low['name'].strip() if isinstance(low['name'], six.string_types)
                    else low['name']
            )

        if 'provider' in low:
            self.load_modules(low)

        state_func_name = '{0[state]}.{0[fun]}'.format(low)
        cdata = salt.utils.args.format_call(
            self.states[state_func_name],
            low,
            initial_ret={'full': state_func_name},
            expected_extra_kws=STATE_INTERNAL_KEYWORDS
        )
        inject_globals = {
            # Pass a copy of the running dictionary, the low state chunks and
            # the current state dictionaries.
            # We pass deep copies here because we don't want any misbehaving
            # state module to change these at runtime.
            '__low__': immutabletypes.freeze(low),
            '__running__': immutabletypes.freeze(running) if running else {},
            '__instance_id__': self.instance_id,
            '__lowstate__': immutabletypes.freeze(chunks) if chunks else {}
        }

        if '__env__' in low:
            inject_globals['__env__'] = six.text_type(low['__env__'])

        if self.inject_globals:
            inject_globals.update(self.inject_globals)

        if low.get('__prereq__'):
            test = sys.modules[self.states[cdata['full']].__module__].__opts__['test']
            sys.modules[self.states[cdata['full']].__module__].__opts__['test'] = True
        try:
            # Let's get a reference to the salt environment to use within this
            # state call.
            #
            # If the state function accepts an 'env' keyword argument, it
            # allows the state to be overridden(we look for that in cdata). If
            # that's not found in cdata, we look for what we're being passed in
            # the original data, namely, the special dunder __env__. If that's
            # not found we default to 'base'
            if ('unless' in low and '{0[state]}.mod_run_check'.format(low) not in self.states) or \
                    ('onlyif' in low and '{0[state]}.mod_run_check'.format(low) not in self.states):
                ret.update(self._run_check(low))

            if not self.opts.get('lock_saltenv', False):
                # NOTE: Overriding the saltenv when lock_saltenv is blocked in
                # salt/modules/state.py, before we ever get here, but this
                # additional check keeps use of the State class outside of the
                # salt/modules/state.py from getting around this setting.
                if 'saltenv' in low:
                    inject_globals['__env__'] = six.text_type(low['saltenv'])
                elif isinstance(cdata['kwargs'].get('env', None), six.string_types):
                    # User is using a deprecated env setting which was parsed by
                    # format_call.
                    # We check for a string type since module functions which
                    # allow setting the OS environ also make use of the "env"
                    # keyword argument, which is not a string
                    inject_globals['__env__'] = six.text_type(cdata['kwargs']['env'])

            if '__env__' not in inject_globals:
                # Let's use the default environment
                inject_globals['__env__'] = 'base'

            if '__orchestration_jid__' in low:
                inject_globals['__orchestration_jid__'] = \
                    low['__orchestration_jid__']

            if 'result' not in ret or ret['result'] is False:
                self.states.inject_globals = inject_globals
                if self.mocked:
                    ret = mock_ret(cdata)
                else:
                    # Execute the state function
                    if not low.get('__prereq__') and low.get('parallel'):
                        # run the state call in parallel, but only if not in a prereq
                        ret = self.call_parallel(cdata, low)
                    else:
                        self.format_slots(cdata)
                        ret = self.states[cdata['full']](*cdata['args'],
                                                         **cdata['kwargs'])
                self.states.inject_globals = {}
            if 'check_cmd' in low and '{0[state]}.mod_run_check_cmd'.format(low) not in self.states:
                ret.update(self._run_check_cmd(low))
        except Exception as exc:  # pylint: disable=broad-except
            log.debug('An exception occurred in this state: %s', exc,
                      exc_info_on_loglevel=logging.DEBUG)
            trb = traceback.format_exc()
            # There are a number of possibilities to not have the cdata
            # populated with what we might have expected, so just be smart
            # enough to not raise another KeyError as the name is easily
            # guessable and fallback in all cases to present the real
            # exception to the user
            name = (cdata.get('args') or [None])[0] or cdata['kwargs'].get('name')
            if not name:
                name = low.get('name', low.get('__id__'))

            ret = {
                'result': False,
                'name': name,
                'changes': {},
                'comment': 'An exception occurred in this state: {0}'.format(trb)
            }
        finally:
            if low.get('__prereq__'):
                sys.modules[self.states[cdata['full']].__module__].__opts__['test'] = test

            self.state_con.pop('runas', None)
            self.state_con.pop('runas_password', None)

        if not isinstance(ret, dict):
            return ret

        # If format_call got any warnings, let's show them to the user
        if 'warnings' in cdata:
            ret.setdefault('warnings', []).extend(cdata['warnings'])

        if 'provider' in low:
            self.load_modules()

        if low.get('__prereq__'):
            low['__prereq__'] = False
            return ret

        ret['__sls__'] = low.get('__sls__')
        ret['__run_num__'] = self.__run_num
        self.__run_num += 1
        format_log(ret)
        self.check_refresh(low, ret)
        utc_finish_time = datetime.datetime.utcnow()
        timezone_delta = datetime.datetime.utcnow() - datetime.datetime.now()
        local_finish_time = utc_finish_time - timezone_delta
        local_start_time = utc_start_time - timezone_delta
        ret['start_time'] = local_start_time.time().isoformat()
        delta = (utc_finish_time - utc_start_time)
        # duration in milliseconds.microseconds
        duration = (delta.seconds * 1000000 + delta.microseconds) / 1000.0
        ret['duration'] = duration
        ret['__id__'] = low['__id__']
        log.info(
            'Completed state [%s] at time %s (duration_in_ms=%s)',
            low['name'].strip() if isinstance(low['name'], six.string_types)
                else low['name'],
            local_finish_time.time().isoformat(),
            duration
        )
        if 'retry' in low:
            low['retry'] = self.verify_retry_data(low['retry'])
            if not sys.modules[self.states[cdata['full']].__module__].__opts__['test']:
                if low['retry']['until'] != ret['result']:
                    if low['retry']['attempts'] > retries:
                        interval = low['retry']['interval']
                        if low['retry']['splay'] != 0:
                            interval = interval + random.randint(0, low['retry']['splay'])
                        log.info(
                            'State result does not match retry until value, '
                            'state will be re-run in %s seconds', interval
                        )
                        self.functions['test.sleep'](interval)
                        retry_ret = self.call(low, chunks, running, retries=retries+1)
                        orig_ret = ret
                        ret = retry_ret
                        ret['comment'] = '\n'.join(
                                [(
                                     'Attempt {0}: Returned a result of "{1}", '
                                     'with the following comment: "{2}"'.format(
                                         retries,
                                         orig_ret['result'],
                                         orig_ret['comment'])
                                 ),
                                 '' if not ret['comment'] else ret['comment']])
                        ret['duration'] = ret['duration'] + orig_ret['duration'] + (interval * 1000)
                        if retries == 1:
                            ret['start_time'] = orig_ret['start_time']
            else:
                ret['comment'] = '  '.join(
                        ['' if not ret['comment'] else ret['comment'],
                         ('The state would be retried every {1} seconds '
                          '(with a splay of up to {3} seconds) '
                          'a maximum of {0} times or until a result of {2} '
                          'is returned').format(low['retry']['attempts'],
                                                low['retry']['interval'],
                                                low['retry']['until'],
                                                low['retry']['splay'])])
        return ret

    def __eval_slot(self, slot):
        log.debug('Evaluating slot: %s', slot)
        fmt = slot.split(':', 2)
        if len(fmt) != 3:
            log.warning('Malformed slot: %s', slot)
            return slot
        if fmt[1] != 'salt':
            log.warning('Malformed slot: %s', slot)
            log.warning('Only execution modules are currently supported in slots. This means slot '
                        'should start with "__slot__:salt:"')
            return slot
        fun, args, kwargs = salt.utils.args.parse_function(fmt[2])
        if not fun or fun not in self.functions:
            log.warning('Malformed slot: %s', slot)
            log.warning('Execution module should be specified in a function call format: '
                        'test.arg(\'arg\', kw=\'kwarg\')')
            return slot
        log.debug('Calling slot: %s(%s, %s)', fun, args, kwargs)
        slot_return = self.functions[fun](*args, **kwargs)

        # Given input  __slot__:salt:test.arg(somekey="value").not.exist ~ /appended
        # slot_text should be __slot...).not.exist
        # append_data should be ~ /appended
        slot_text = fmt[2].split('~')[0]
        append_data = fmt[2].split('~', 1)[1:]
        log.debug('slot_text: %s', slot_text)
        log.debug('append_data: %s', append_data)

        # Support parsing slot dict response
        # return_get should result in a kwargs.nested.dict path by getting
        # everything after first closing paren: )
        return_get = None
        try:
            return_get = slot_text[slot_text.rindex(')')+1:]
        except ValueError:
            pass
        if return_get:
            #remove first period
            return_get = return_get.split('.', 1)[1].strip()
            log.debug('Searching slot result %s for %s', slot_return, return_get)
            slot_return = salt.utils.data.traverse_dict_and_list(slot_return,
                                                                 return_get,
                                                                 default=None,
                                                                 delimiter='.'
                                                                )

        if append_data:
            if isinstance(slot_return, six.string_types):
                # Append text to slot string result
                append_data = ' '.join(append_data).strip()
                log.debug('appending to slot result: %s', append_data)
                slot_return += append_data
            else:
                log.error('Ignoring slot append, slot result is not a string')

        return slot_return

    def format_slots(self, cdata):
        '''
        Read in the arguments from the low level slot syntax to make a last
        minute runtime call to gather relevant data for the specific routine

        Will parse strings, first level of dictionary values, and strings and
        first level dict values inside of lists
        '''
        # __slot__:salt.cmd.run(foo, bar, baz=qux)
        SLOT_TEXT = '__slot__:'
        ctx = (('args', enumerate(cdata['args'])),
               ('kwargs', cdata['kwargs'].items()))
        for atype, avalues in ctx:
            for ind, arg in avalues:
                arg = salt.utils.data.decode(arg, keep=True)
                if isinstance(arg, dict):
                    # Search dictionary values for __slot__:
                    for key, value in arg.items():
                        try:
                            if value.startswith(SLOT_TEXT):
                                log.trace("Slot processsing dict value %s", value)
                                cdata[atype][ind][key] = self.__eval_slot(value)
                        except AttributeError:
                            # Not a string/slot
                            continue
                elif isinstance(arg, list):
                    for idx, listvalue in enumerate(arg):
                        log.trace("Slot processing list value: %s", listvalue)
                        if isinstance(listvalue, dict):
                            # Search dict values in list for __slot__:
                            for key, value in listvalue.items():
                                try:
                                    if value.startswith(SLOT_TEXT):
                                        log.trace("Slot processsing nested dict value %s", value)
                                        cdata[atype][ind][idx][key] = self.__eval_slot(value)
                                except AttributeError:
                                    # Not a string/slot
                                    continue
                        if isinstance(listvalue, six.text_type):
                            # Search strings in a list for __slot__:
                            if listvalue.startswith(SLOT_TEXT):
                                log.trace("Slot processsing nested string %s", listvalue)
                                cdata[atype][ind][idx] = self.__eval_slot(listvalue)
                elif isinstance(arg, six.text_type) \
                        and arg.startswith(SLOT_TEXT):
                    # Search strings for __slot__:
                    log.trace("Slot processsing %s", arg)
                    cdata[atype][ind] = self.__eval_slot(arg)
                else:
                    # Not a slot, skip it
                    continue

    def verify_retry_data(self, retry_data):
        '''
        verifies the specified retry data
        '''
        retry_defaults = {
                'until': True,
                'attempts': 2,
                'splay': 0,
                'interval': 30,
        }
        expected_data = {
            'until': bool,
            'attempts': int,
            'interval': int,
            'splay': int,
        }
        validated_retry_data = {}
        if isinstance(retry_data, dict):
            for expected_key, value_type in six.iteritems(expected_data):
                if expected_key in retry_data:
                    if isinstance(retry_data[expected_key], value_type):
                        validated_retry_data[expected_key] = retry_data[expected_key]
                    else:
                        log.warning(
                            'An invalid value was passed for the retry %s, '
                            'using default value \'%s\'',
                            expected_key, retry_defaults[expected_key]
                        )
                        validated_retry_data[expected_key] = retry_defaults[expected_key]
                else:
                    validated_retry_data[expected_key] = retry_defaults[expected_key]
        else:
            log.warning(('State is set to retry, but a valid dict for retry '
                         'configuration was not found.  Using retry defaults'))
            validated_retry_data = retry_defaults
        return validated_retry_data

    def call_chunks(self, chunks):
        '''
        Iterate over a list of chunks and call them, checking for requires.
        '''
        # Check for any disabled states
        disabled = {}
        if 'state_runs_disabled' in self.opts['grains']:
            for low in chunks[:]:
                state_ = '{0}.{1}'.format(low['state'], low['fun'])
                for pat in self.opts['grains']['state_runs_disabled']:
                    if fnmatch.fnmatch(state_, pat):
                        comment = (
                                    'The state function "{0}" is currently disabled by "{1}", '
                                    'to re-enable, run state.enable {1}.'
                                  ).format(
                                    state_,
                                    pat,
                                  )
                        _tag = _gen_tag(low)
                        disabled[_tag] = {'changes': {},
                                          'result': False,
                                          'comment': comment,
                                          '__run_num__': self.__run_num,
                                          '__sls__': low['__sls__']}
                        self.__run_num += 1
                        chunks.remove(low)
                        break
        running = {}
        for low in chunks:
            if '__FAILHARD__' in running:
                running.pop('__FAILHARD__')
                return running
            tag = _gen_tag(low)
            if tag not in running:
                # Check if this low chunk is paused
                action = self.check_pause(low)
                if action == 'kill':
                    break
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
        if self.opts.get('test', False):
            return False
        if low.get('failhard', self.opts['failhard']) and tag in running:
            if running[tag]['result'] is None:
                return False
            return not running[tag]['result']
        return False

    def check_pause(self, low):
        '''
        Check to see if this low chunk has been paused
        '''
        if not self.jid:
            # Can't pause on salt-ssh since we can't track continuous state
            return
        pause_path = os.path.join(self.opts['cachedir'], 'state_pause', self.jid)
        start = time.time()
        if os.path.isfile(pause_path):
            try:
                while True:
                    tries = 0
                    with salt.utils.files.fopen(pause_path, 'rb') as fp_:
                        try:
                            pdat = msgpack_deserialize(fp_.read())
                        except salt.utils.msgpack.exceptions.UnpackValueError:
                            # Reading race condition
                            if tries > 10:
                                # Break out if there are a ton of read errors
                                return
                            tries += 1
                            time.sleep(1)
                            continue
                        id_ = low['__id__']
                        key = ''
                        if id_ in pdat:
                            key = id_
                        elif '__all__' in pdat:
                            key = '__all__'
                        if key:
                            if 'duration' in pdat[key]:
                                now = time.time()
                                if now - start > pdat[key]['duration']:
                                    return 'run'
                            if 'kill' in pdat[key]:
                                return 'kill'
                        else:
                            return 'run'
                        time.sleep(1)
            except Exception as exc:  # pylint: disable=broad-except
                log.error('Failed to read in pause data for file located at: %s', pause_path)
                return 'run'
        return 'run'

    def reconcile_procs(self, running):
        '''
        Check the running dict for processes and resolve them
        '''
        retset = set()
        for tag in running:
            proc = running[tag].get('proc')
            if proc:
                if not proc.is_alive():
                    ret_cache = os.path.join(
                        self.opts['cachedir'],
                        self.jid,
                        salt.utils.hashutils.sha1_digest(tag))
                    if not os.path.isfile(ret_cache):
                        ret = {'result': False,
                               'comment': 'Parallel process failed to return',
                               'name': running[tag]['name'],
                               'changes': {}}
                    try:
                        with salt.utils.files.fopen(ret_cache, 'rb') as fp_:
                            ret = msgpack_deserialize(fp_.read())
                    except (OSError, IOError):
                        ret = {'result': False,
                               'comment': 'Parallel cache failure',
                               'name': running[tag]['name'],
                               'changes': {}}
                    running[tag].update(ret)
                    running[tag].pop('proc')
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
        if 'watch' in low:
            if '{0}.mod_watch'.format(low['state']) not in self.states:
                if 'require' in low:
                    low['require'].extend(low.pop('watch'))
                else:
                    low['require'] = low.pop('watch')
            else:
                present = True
        if 'watch_any' in low:
            if '{0}.mod_watch'.format(low['state']) not in self.states:
                if 'require_any' in low:
                    low['require_any'].extend(low.pop('watch_any'))
                else:
                    low['require_any'] = low.pop('watch_any')
            else:
                present = True
        if 'require' in low:
            present = True
        if 'require_any' in low:
            present = True
        if 'prerequired' in low:
            present = True
        if 'prereq' in low:
            present = True
        if 'onfail' in low:
            present = True
        if 'onfail_any' in low:
            present = True
        if 'onchanges' in low:
            present = True
        if 'onchanges_any' in low:
            present = True
        if not present:
            return 'met', ()
        self.reconcile_procs(running)
        reqs = {
                'require': [],
                'require_any': [],
                'watch': [],
                'watch_any': [],
                'prereq': [],
                'onfail': [],
                'onfail_any': [],
                'onchanges': [],
                'onchanges_any': []}
        if pre:
            reqs['prerequired'] = []
        for r_state in reqs:
            if r_state in low and low[r_state] is not None:
                for req in low[r_state]:
                    if isinstance(req, six.string_types):
                        req = {'id': req}
                    req = trim_req(req)
                    found = False
                    for chunk in chunks:
                        req_key = next(iter(req))
                        req_val = req[req_key]
                        if req_val is None:
                            continue
                        if req_key == 'sls':
                            # Allow requisite tracking of entire sls files
                            if fnmatch.fnmatch(chunk['__sls__'], req_val):
                                found = True
                                reqs[r_state].append(chunk)
                            continue
                        try:
                            if isinstance(req_val, six.string_types):
                                if (fnmatch.fnmatch(chunk['name'], req_val) or
                                    fnmatch.fnmatch(chunk['__id__'], req_val)):
                                    if req_key == 'id' or chunk['state'] == req_key:
                                        found = True
                                        reqs[r_state].append(chunk)
                            else:
                                raise KeyError
                        except KeyError as exc:
                            raise SaltRenderError(
                                'Could not locate requisite of [{0}] present in state with name [{1}]'.format(
                                    req_key, chunk['name']))
                        except TypeError:
                            # On Python 2, the above req_val, being an OrderedDict, will raise a KeyError,
                            # however on Python 3 it will raise a TypeError
                            # This was found when running tests.unit.test_state.StateCompilerTestCase.test_render_error_on_invalid_requisite
                            raise SaltRenderError(
                                'Could not locate requisite of [{0}] present in state with name [{1}]'.format(
                                    req_key, chunk['name']))
                    if not found:
                        return 'unmet', ()
        fun_stats = set()
        for r_state, chunks in six.iteritems(reqs):
            req_stats = set()
            if r_state.startswith('prereq') and not r_state.startswith('prerequired'):
                run_dict = self.pre
            else:
                run_dict = running

            while True:
                if self.reconcile_procs(run_dict):
                    break
                time.sleep(0.01)

            for chunk in chunks:
                tag = _gen_tag(chunk)
                if tag not in run_dict:
                    req_stats.add('unmet')
                    continue
                if r_state.startswith('onfail'):
                    if run_dict[tag]['result'] is True:
                        req_stats.add('onfail')  # At least one state is OK
                        continue
                else:
                    if run_dict[tag]['result'] is False:
                        req_stats.add('fail')
                        continue
                if r_state.startswith('onchanges'):
                    if not run_dict[tag]['changes']:
                        req_stats.add('onchanges')
                    else:
                        req_stats.add('onchangesmet')
                    continue
                if r_state.startswith('watch') and run_dict[tag]['changes']:
                    req_stats.add('change')
                    continue
                if r_state.startswith('prereq') and run_dict[tag]['result'] is None:
                    if not r_state.startswith('prerequired'):
                        req_stats.add('premet')
                if r_state.startswith('prereq') and not run_dict[tag]['result'] is None:
                    if not r_state.startswith('prerequired'):
                        req_stats.add('pre')
                else:
                    if run_dict[tag].get('__state_ran__', True):
                        req_stats.add('met')
            if r_state.endswith('_any'):
                if 'met' in req_stats or 'change' in req_stats:
                    if 'fail' in req_stats:
                        req_stats.remove('fail')
                if 'onchangesmet' in req_stats:
                    if 'onchanges' in req_stats:
                        req_stats.remove('onchanges')
                    if 'fail' in req_stats:
                        req_stats.remove('fail')
                if 'onfail' in req_stats:
                    if 'fail' in req_stats:
                        req_stats.remove('onfail')
            fun_stats.update(req_stats)

        if 'unmet' in fun_stats:
            status = 'unmet'
        elif 'fail' in fun_stats:
            status = 'fail'
        elif 'pre' in fun_stats:
            if 'premet' in fun_stats:
                status = 'met'
            else:
                status = 'pre'
        elif 'onfail' in fun_stats and 'met' not in fun_stats:
            status = 'onfail'  # all onfail states are OK
        elif 'onchanges' in fun_stats and 'onchangesmet' not in fun_stats:
            status = 'onchanges'
        elif 'change' in fun_stats:
            status = 'change'
        else:
            status = 'met'

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
        if not self.opts.get('local') and (self.opts.get('state_events', True) or fire_event):
            if not self.opts.get('master_uri'):
                ev_func = lambda ret, tag, preload=None: salt.utils.event.get_master_event(
                    self.opts, self.opts['sock_dir'], listen=False).fire_event(ret, tag)
            else:
                ev_func = self.functions['event.fire_master']

            ret = {'ret': chunk_ret}
            if fire_event is True:
                tag = salt.utils.event.tagify(
                        [self.jid, self.opts['id'], six.text_type(chunk_ret['name'])], 'state_result'
                        )
            elif isinstance(fire_event, six.string_types):
                tag = salt.utils.event.tagify(
                        [self.jid, self.opts['id'], six.text_type(fire_event)], 'state_result'
                        )
            else:
                tag = salt.utils.event.tagify(
                        [self.jid, 'prog', self.opts['id'], six.text_type(chunk_ret['__run_num__'])], 'job'
                        )
                ret['len'] = length
            preload = {'jid': self.jid}
            ev_func(ret, tag, preload=preload)

    def call_chunk(self, low, running, chunks):
        '''
        Check if a chunk has any requires, execute the requires and then
        the chunk
        '''
        low = self._mod_aggregate(low, running, chunks)
        self._mod_init(low)
        tag = _gen_tag(low)
        if not low.get('prerequired'):
            self.active.add(tag)
        requisites = ['require',
                      'require_any',
                      'watch',
                      'watch_any',
                      'prereq',
                      'onfail',
                      'onfail_any',
                      'onchanges',
                      'onchanges_any']
        if not low.get('__prereq__'):
            requisites.append('prerequired')
            status, reqs = self.check_requisite(low, running, chunks, pre=True)
        else:
            status, reqs = self.check_requisite(low, running, chunks)
        if status == 'unmet':
            lost = {}
            reqs = []
            for requisite in requisites:
                lost[requisite] = []
                if requisite not in low:
                    continue
                for req in low[requisite]:
                    if isinstance(req, six.string_types):
                        req = {'id': req}
                    req = trim_req(req)
                    found = False
                    req_key = next(iter(req))
                    req_val = req[req_key]
                    for chunk in chunks:
                        if req_val is None:
                            continue
                        if req_key == 'sls':
                            # Allow requisite tracking of entire sls files
                            if fnmatch.fnmatch(chunk['__sls__'], req_val):
                                if requisite == 'prereq':
                                    chunk['__prereq__'] = True
                                reqs.append(chunk)
                                found = True
                            continue
                        if (fnmatch.fnmatch(chunk['name'], req_val) or
                            fnmatch.fnmatch(chunk['__id__'], req_val)):
                            if req_key == 'id' or chunk['state'] == req_key:
                                if requisite == 'prereq':
                                    chunk['__prereq__'] = True
                                elif requisite == 'prerequired':
                                    chunk['__prerequired__'] = True
                                reqs.append(chunk)
                                found = True
                    if not found:
                        lost[requisite].append(req)
            if lost['require'] or lost['watch'] or lost['prereq'] \
                        or lost['onfail'] or lost['onchanges'] \
                        or lost.get('prerequired'):
                comment = 'The following requisites were not found:\n'
                for requisite, lreqs in six.iteritems(lost):
                    if not lreqs:
                        continue
                    comment += \
                        '{0}{1}:\n'.format(' ' * 19, requisite)
                    for lreq in lreqs:
                        req_key = next(iter(lreq))
                        req_val = lreq[req_key]
                        comment += \
                            '{0}{1}: {2}\n'.format(' ' * 23, req_key, req_val)
                if low.get('__prereq__'):
                    run_dict = self.pre
                else:
                    run_dict = running
                start_time, duration = _calculate_fake_duration()
                run_dict[tag] = {'changes': {},
                                 'result': False,
                                 'duration': duration,
                                 'start_time': start_time,
                                 'comment': comment,
                                 '__run_num__': self.__run_num,
                                 '__sls__': low['__sls__']}
                self.__run_num += 1
                self.event(run_dict[tag], len(chunks), fire_event=low.get('fire_event'))
                return running
            for chunk in reqs:
                # Check to see if the chunk has been run, only run it if
                # it has not been run already
                ctag = _gen_tag(chunk)
                if ctag not in running:
                    if ctag in self.active:
                        if chunk.get('__prerequired__'):
                            # Prereq recusive, run this chunk with prereq on
                            if tag not in self.pre:
                                low['__prereq__'] = True
                                self.pre[ctag] = self.call(low, chunks, running)
                                return running
                            else:
                                return running
                        elif ctag not in running:
                            log.error('Recursive requisite found')
                            running[tag] = {
                                    'changes': {},
                                    'result': False,
                                    'comment': 'Recursive requisite found',
                                    '__run_num__': self.__run_num,
                                    '__sls__': low['__sls__']}
                        self.__run_num += 1
                        self.event(running[tag], len(chunks), fire_event=low.get('fire_event'))
                        return running
                    running = self.call_chunk(chunk, running, chunks)
                    if self.check_failhard(chunk, running):
                        running['__FAILHARD__'] = True
                        return running
            if low.get('__prereq__'):
                status, reqs = self.check_requisite(low, running, chunks)
                self.pre[tag] = self.call(low, chunks, running)
                if not self.pre[tag]['changes'] and status == 'change':
                    self.pre[tag]['changes'] = {'watch': 'watch'}
                    self.pre[tag]['result'] = None
            else:
                running = self.call_chunk(low, running, chunks)
            if self.check_failhard(chunk, running):
                running['__FAILHARD__'] = True
                return running
        elif status == 'met':
            if low.get('__prereq__'):
                self.pre[tag] = self.call(low, chunks, running)
            else:
                running[tag] = self.call(low, chunks, running)
        elif status == 'fail':
            # if the requisite that failed was due to a prereq on this low state
            # show the normal error
            if tag in self.pre:
                running[tag] = self.pre[tag]
                running[tag]['__run_num__'] = self.__run_num
                running[tag]['__sls__'] = low['__sls__']
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
                        if req_ret['result'] is False:
                            # use SLS.ID for the key-- so its easier to find
                            key = '{sls}.{_id}'.format(sls=req_low['__sls__'],
                                                        _id=req_low['__id__'])
                            failed_requisites.add(key)

                _cmt = 'One or more requisite failed: {0}'.format(
                    ', '.join(six.text_type(i) for i in failed_requisites)
                )
                start_time, duration = _calculate_fake_duration()
                running[tag] = {
                    'changes': {},
                    'result': False,
                    'duration': duration,
                    'start_time': start_time,
                    'comment': _cmt,
                    '__run_num__': self.__run_num,
                    '__sls__': low['__sls__']
                }
                self.pre[tag] = running[tag]
            self.__run_num += 1
        elif status == 'change' and not low.get('__prereq__'):
            ret = self.call(low, chunks, running)
            if not ret['changes'] and not ret.get('skip_watch', False):
                low = low.copy()
                low['sfun'] = low['fun']
                low['fun'] = 'mod_watch'
                low['__reqs__'] = reqs
                ret = self.call(low, chunks, running)
            running[tag] = ret
        elif status == 'pre':
            start_time, duration = _calculate_fake_duration()
            pre_ret = {'changes': {},
                       'result': True,
                       'duration': duration,
                       'start_time': start_time,
                       'comment': 'No changes detected',
                       '__run_num__': self.__run_num,
                       '__sls__': low['__sls__']}
            running[tag] = pre_ret
            self.pre[tag] = pre_ret
            self.__run_num += 1
        elif status == 'onfail':
            start_time, duration = _calculate_fake_duration()
            running[tag] = {'changes': {},
                            'result': True,
                            'duration': duration,
                            'start_time': start_time,
                            'comment': 'State was not run because onfail req did not change',
                            '__state_ran__': False,
                            '__run_num__': self.__run_num,
                            '__sls__': low['__sls__']}
            self.__run_num += 1
        elif status == 'onchanges':
            start_time, duration = _calculate_fake_duration()
            running[tag] = {'changes': {},
                            'result': True,
                            'duration': duration,
                            'start_time': start_time,
                            'comment': 'State was not run because none of the onchanges reqs changed',
                            '__state_ran__': False,
                            '__run_num__': self.__run_num,
                            '__sls__': low['__sls__']}
            self.__run_num += 1
        else:
            if low.get('__prereq__'):
                self.pre[tag] = self.call(low, chunks, running)
            else:
                running[tag] = self.call(low, chunks, running)
        if tag in running:
            self.event(running[tag], len(chunks), fire_event=low.get('fire_event'))
        return running

    def call_listen(self, chunks, running):
        '''
        Find all of the listen routines and call the associated mod_watch runs
        '''
        listeners = []
        crefs = {}
        for chunk in chunks:
            crefs[(chunk['state'], chunk['__id__'], chunk['name'])] = chunk
            if 'listen' in chunk:
                listeners.append({(chunk['state'], chunk['__id__'], chunk['name']): chunk['listen']})
            if 'listen_in' in chunk:
                for l_in in chunk['listen_in']:
                    for key, val in six.iteritems(l_in):
                        listeners.append({(key, val, 'lookup'): [{chunk['state']: chunk['__id__']}]})
        mod_watchers = []
        errors = {}
        for l_dict in listeners:
            for key, val in six.iteritems(l_dict):
                for listen_to in val:
                    if not isinstance(listen_to, dict):
                        found = False
                        for chunk in chunks:
                            if chunk['__id__'] == listen_to or \
                               chunk['name'] == listen_to:
                                listen_to = {chunk['state']: chunk['__id__']}
                                found = True
                        if not found:
                            continue
                    for lkey, lval in six.iteritems(listen_to):
                        if not any(lkey == cref[0] and lval in cref for cref in crefs):
                            rerror = {_l_tag(lkey, lval):
                                      {
                                          'comment': 'Referenced state {0}: {1} does not exist'.format(lkey, lval),
                                          'name': 'listen_{0}:{1}'.format(lkey, lval),
                                          'result': False,
                                          'changes': {}
                                      }}
                            errors.update(rerror)
                            continue
                        to_tags = [
                            _gen_tag(data) for cref, data in six.iteritems(crefs) if lkey == cref[0] and lval in cref
                        ]
                        for to_tag in to_tags:
                            if to_tag not in running:
                                continue
                            if running[to_tag]['changes']:
                                if not any(key[0] == cref[0] and key[1] in cref for cref in crefs):
                                    rerror = {_l_tag(key[0], key[1]):
                                                 {'comment': 'Referenced state {0}: {1} does not exist'.format(key[0], key[1]),
                                                  'name': 'listen_{0}:{1}'.format(key[0], key[1]),
                                                  'result': False,
                                                  'changes': {}}}
                                    errors.update(rerror)
                                    continue

                                new_chunks = [data for cref, data in six.iteritems(crefs) if key[0] == cref[0] and key[1] in cref]
                                for chunk in new_chunks:
                                    low = chunk.copy()
                                    low['sfun'] = chunk['fun']
                                    low['fun'] = 'mod_watch'
                                    low['__id__'] = 'listener_{0}'.format(low['__id__'])
                                    for req in STATE_REQUISITE_KEYWORDS:
                                        if req in low:
                                            low.pop(req)
                                    mod_watchers.append(low)
        ret = self.call_chunks(mod_watchers)
        running.update(ret)
        for err in errors:
            errors[err]['__run_num__'] = self.__run_num
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
        errors.extend(ext_errors)
        errors.extend(self.verify_high(high))
        if errors:
            return errors
        high, req_in_errors = self.requisite_in(high)
        errors.extend(req_in_errors)
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
                get_accumulator_dir(self.opts['cachedir']),
                self.instance_id
            )
            try:
                os.remove(accum_data_path)
                log.debug('Deleted accumulator data file %s', accum_data_path)
            except OSError:
                log.debug('File %s does not exist, no need to cleanup', accum_data_path)
        _cleanup_accumulator_data()
        if self.jid is not None:
            pause_path = os.path.join(self.opts['cachedir'], 'state_pause', self.jid)
            if os.path.isfile(pause_path):
                try:
                    os.remove(pause_path)
                except OSError:
                    # File is not present, all is well
                    pass

        return ret

    def render_template(self, high, template):
        errors = []
        if not high:
            return high, errors

        if not isinstance(high, dict):
            errors.append(
                'Template {0} does not render to a dictionary'.format(template)
            )
            return high, errors

        invalid_items = ('include', 'exclude', 'extends')
        for item in invalid_items:
            if item in high:
                errors.append(
                    'The \'{0}\' declaration found on \'{1}\' is invalid when '
                    'rendering single templates'.format(item, template)
                )
                return high, errors

        for name in high:
            if not isinstance(high[name], dict):
                if isinstance(high[name], six.string_types):
                    # Is this is a short state, it needs to be padded
                    if '.' in high[name]:
                        comps = high[name].split('.')
                        high[name] = {
                            # '__sls__': template,
                            # '__env__': None,
                            comps[0]: [comps[1]]
                        }
                        continue

                    errors.append(
                        'ID {0} in template {1} is not a dictionary'.format(
                            name, template
                        )
                    )
                    continue
            skeys = set()
            for key in sorted(high[name]):
                if key.startswith('_'):
                    continue
                if high[name][key] is None:
                    errors.append(
                        'ID \'{0}\' in template {1} contains a short '
                        'declaration ({2}) with a trailing colon. When not '
                        'passing any arguments to a state, the colon must be '
                        'omitted.'.format(name, template, key)
                    )
                    continue
                if not isinstance(high[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
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
                            'ID \'{0}\' in template \'{1}\' contains multiple '
                            'state declarations of the same type'
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
                                self.opts['renderer'],
                                self.opts['renderer_blacklist'],
                                self.opts['renderer_whitelist'])
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
                                    self.opts['renderer'],
                                    self.opts['renderer_blacklist'],
                                    self.opts['renderer_whitelist'])
        if not high:
            return high
        high, errors = self.render_template(high, '<template-str>')
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
        if 'local_state' in opts:
            if opts['local_state']:
                return opts
        mopts = self.client.master_opts()
        if not isinstance(mopts, dict):
            # An error happened on the master
            opts['renderer'] = 'jinja|yaml'
            opts['failhard'] = False
            opts['state_top'] = salt.utils.url.create('top.sls')
            opts['nodegroups'] = {}
            opts['file_roots'] = {'base': [syspaths.BASE_FILE_ROOTS_DIR]}
        else:
            opts['renderer'] = mopts['renderer']
            opts['failhard'] = mopts.get('failhard', False)
            if mopts['state_top'].startswith('salt://'):
                opts['state_top'] = mopts['state_top']
            elif mopts['state_top'].startswith('/'):
                opts['state_top'] = salt.utils.url.create(mopts['state_top'][1:])
            else:
                opts['state_top'] = salt.utils.url.create(mopts['state_top'])
            opts['state_top_saltenv'] = mopts.get('state_top_saltenv', None)
            opts['nodegroups'] = mopts.get('nodegroups', {})
            opts['state_auto_order'] = mopts.get(
                'state_auto_order',
                opts['state_auto_order'])
            opts['file_roots'] = mopts['file_roots']
            opts['top_file_merging_strategy'] = mopts.get('top_file_merging_strategy',
                                                           opts.get('top_file_merging_strategy'))
            opts['env_order'] = mopts.get('env_order', opts.get('env_order', []))
            opts['default_top'] = mopts.get('default_top', opts.get('default_top'))
            opts['state_events'] = mopts.get('state_events')
            opts['state_aggregate'] = mopts.get('state_aggregate', opts.get('state_aggregate', False))
            opts['jinja_env'] = mopts.get('jinja_env', {})
            opts['jinja_sls_env'] = mopts.get('jinja_sls_env', {})
            opts['jinja_lstrip_blocks'] = mopts.get('jinja_lstrip_blocks', False)
            opts['jinja_trim_blocks'] = mopts.get('jinja_trim_blocks', False)
        return opts

    def _get_envs(self):
        '''
        Pull the file server environments out of the master options
        '''
        envs = ['base']
        if 'file_roots' in self.opts:
            envs.extend([x for x in list(self.opts['file_roots'])
                         if x not in envs])
        env_order = self.opts.get('env_order', [])
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
        merging_strategy = self.opts['top_file_merging_strategy']
        if merging_strategy == 'same' and not self.opts['saltenv']:
            if not self.opts['default_top']:
                raise SaltRenderError(
                    'top_file_merging_strategy set to \'same\', but no '
                    'default_top configuration option was set'
                )

        if self.opts['saltenv']:
            contents = self.client.cache_file(
                self.opts['state_top'],
                self.opts['saltenv']
            )
            if contents:
                found = 1
                tops[self.opts['saltenv']] = [
                    compile_template(
                        contents,
                        self.state.rend,
                        self.state.opts['renderer'],
                        self.state.opts['renderer_blacklist'],
                        self.state.opts['renderer_whitelist'],
                        saltenv=self.opts['saltenv']
                    )
                ]
            else:
                tops[self.opts['saltenv']] = [{}]

        else:
            found = 0
            state_top_saltenv = self.opts.get('state_top_saltenv', False)
            if state_top_saltenv \
                    and not isinstance(state_top_saltenv, six.string_types):
                state_top_saltenv = six.text_type(state_top_saltenv)

            for saltenv in [state_top_saltenv] if state_top_saltenv \
                    else self._get_envs():
                contents = self.client.cache_file(
                    self.opts['state_top'],
                    saltenv
                )
                if contents:
                    found = found + 1
                    tops[saltenv].append(
                        compile_template(
                            contents,
                            self.state.rend,
                            self.state.opts['renderer'],
                            self.state.opts['renderer_blacklist'],
                            self.state.opts['renderer_whitelist'],
                            saltenv=saltenv
                        )
                    )
                else:
                    tops[saltenv].append({})
                    log.debug('No contents loaded for saltenv \'%s\'', saltenv)

            if found > 1 and merging_strategy == 'merge' and not self.opts.get('env_order', None):
                log.warning(
                    'top_file_merging_strategy is set to \'%s\' and '
                    'multiple top files were found. Merging order is not '
                    'deterministic, it may be desirable to either set '
                    'top_file_merging_strategy to \'same\' or use the '
                    '\'env_order\' configuration parameter to specify the '
                    'merging order.', merging_strategy
                )

        if found == 0:
            log.debug(
                'No contents found in top file. If this is not expected, '
                'verify that the \'file_roots\' specified in \'etc/master\' '
                'are accessible. The \'file_roots\' configuration is: %s',
                repr(self.state.opts['file_roots'])
            )

        # Search initial top files for includes
        for saltenv, ctops in six.iteritems(tops):
            for ctop in ctops:
                if 'include' not in ctop:
                    continue
                for sls in ctop['include']:
                    include[saltenv].append(sls)
                ctop.pop('include')
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
                                ).get('dest', False),
                                self.state.rend,
                                self.state.opts['renderer'],
                                self.state.opts['renderer_blacklist'],
                                self.state.opts['renderer_whitelist'],
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
        merging_strategy = self.opts['top_file_merging_strategy']
        try:
            merge_attr = '_merge_tops_{0}'.format(merging_strategy)
            merge_func = getattr(self, merge_attr)
            if not hasattr(merge_func, '__call__'):
                msg = '\'{0}\' is not callable'.format(merge_attr)
                log.error(msg)
                raise TypeError(msg)
        except (AttributeError, TypeError):
            log.warning(
                'Invalid top_file_merging_strategy \'%s\', falling back to '
                '\'merge\'', merging_strategy
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
        base_tops = tops.pop('base', DefaultOrderedDict(OrderedDict))
        for ctop in base_tops:
            for saltenv, targets in six.iteritems(ctop):
                if saltenv == 'include':
                    continue
                try:
                    for tgt in targets:
                        top[saltenv][tgt] = ctop[saltenv][tgt]
                except TypeError:
                    raise SaltRenderError('Unable to render top file. No targets found.')

        for cenv, ctops in six.iteritems(tops):
            for ctop in ctops:
                for saltenv, targets in six.iteritems(ctop):
                    if saltenv == 'include':
                        continue
                    elif saltenv != cenv:
                        log.debug(
                            'Section for saltenv \'%s\' in the \'%s\' '
                            'saltenv\'s top file will be ignored, as the '
                            'top_file_merging_strategy is set to \'merge\' '
                            'and the saltenvs do not match',
                            saltenv, cenv
                        )
                        continue
                    elif saltenv in top:
                        log.debug(
                            'Section for saltenv \'%s\' in the \'%s\' '
                            'saltenv\'s top file will be ignored, as this '
                            'saltenv was already defined in the \'base\' top '
                            'file', saltenv, cenv
                        )
                        continue
                    try:
                        for tgt in targets:
                            top[saltenv][tgt] = ctop[saltenv][tgt]
                    except TypeError:
                        raise SaltRenderError('Unable to render top file. No targets found.')
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
                default_top = self.opts['default_top']
                fallback_tops = tops.get(default_top, [])
                if all([x == {} for x in fallback_tops]):
                    # Nothing in the fallback top file
                    log.error(
                        'The \'%s\' saltenv has no top file, and the fallback '
                        'saltenv specified by default_top (%s) also has no '
                        'top file', cenv, default_top
                    )
                    continue

                for ctop in fallback_tops:
                    for saltenv, targets in six.iteritems(ctop):
                        if saltenv != cenv:
                            continue
                        log.debug(
                            'The \'%s\' saltenv has no top file, using the '
                            'default_top saltenv (%s)', cenv, default_top
                        )
                        for tgt in targets:
                            top[saltenv][tgt] = ctop[saltenv][tgt]
                        break
                    else:
                        log.error(
                            'The \'%s\' saltenv has no top file, and no '
                            'matches were found in the top file for the '
                            'default_top saltenv (%s)', cenv, default_top
                        )

                continue

            else:
                for ctop in ctops:
                    for saltenv, targets in six.iteritems(ctop):
                        if saltenv == 'include':
                            continue
                        elif saltenv != cenv:
                            log.debug(
                                'Section for saltenv \'%s\' in the \'%s\' '
                                'saltenv\'s top file will be ignored, as the '
                                'top_file_merging_strategy is set to \'same\' '
                                'and the saltenvs do not match',
                                saltenv, cenv
                            )
                            continue

                        try:
                            for tgt in targets:
                                top[saltenv][tgt] = ctop[saltenv][tgt]
                        except TypeError:
                            raise SaltRenderError('Unable to render top file. No targets found.')
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
                    if saltenv == 'include':
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
                        raise SaltRenderError('Unable to render top file. No targets found.')
        return top

    def verify_tops(self, tops):
        '''
        Verify the contents of the top file data
        '''
        errors = []
        if not isinstance(tops, dict):
            errors.append('Top data was not formed as a dict')
            # No further checks will work, bail out
            return errors
        for saltenv, matches in six.iteritems(tops):
            if saltenv == 'include':
                continue
            if not isinstance(saltenv, six.string_types):
                errors.append(
                    'Environment {0} in top file is not formed as a '
                    'string'.format(saltenv)
                )
            if saltenv == '':
                errors.append('Empty saltenv statement in top file')
            if not isinstance(matches, dict):
                errors.append(
                    'The top file matches for saltenv {0} are not '
                    'formatted as a dict'.format(saltenv)
                )
            for slsmods in six.itervalues(matches):
                if not isinstance(slsmods, list):
                    errors.append('Malformed topfile (state declarations not '
                                  'formed as a list)')
                    continue
                for slsmod in slsmods:
                    if isinstance(slsmod, dict):
                        # This value is a match option
                        for val in six.itervalues(slsmod):
                            if not val:
                                errors.append(
                                    'Improperly formatted top file matcher '
                                    'in saltenv {0}: {1} file'.format(
                                        slsmod,
                                        val
                                    )
                                )
                    elif isinstance(slsmod, six.string_types):
                        # This is a sls module
                        if not slsmod:
                            errors.append(
                                'Environment {0} contains an empty sls '
                                'index'.format(saltenv)
                            )

        return errors

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        try:
            tops = self.get_tops()
        except SaltRenderError as err:
            log.error('Unable to render top file: %s', err.error)
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
            if self.opts['saltenv']:
                if saltenv != self.opts['saltenv']:
                    continue
            for match, data in six.iteritems(body):
                def _filter_matches(_match, _data, _opts):
                    if isinstance(_data, six.string_types):
                        _data = [_data]
                    if self.matchers['confirm_top.confirm_top'](
                            _match,
                            _data,
                            _opts
                            ):
                        if saltenv not in matches:
                            matches[saltenv] = []
                        for item in _data:
                            if 'subfilter' in item:
                                _tmpdata = item.pop('subfilter')
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
                _filter_matches(match, data, self.opts['nodegroups'])
        ext_matches = self._master_tops()
        for saltenv in ext_matches:
            top_file_matches = matches.get(saltenv, [])
            if self.opts.get('master_tops_first'):
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
        if not self.opts['autoload_dynamic_modules']:
            return
        syncd = self.state.functions['saltutil.sync_all'](list(matches),
                                                          refresh=False)
        if syncd['grains']:
            self.opts['grains'] = salt.loader.grains(self.opts)
            self.state.opts['pillar'] = self.state._gather_pillar()
        self.state.module_refresh()

    def render_state(self, sls, saltenv, mods, matches, local=False):
        '''
        Render a state file and retrieve all of the include states
        '''
        errors = []
        if not local:
            state_data = self.client.get_state(sls, saltenv)
            fn_ = state_data.get('dest', False)
        else:
            fn_ = sls
            if not os.path.isfile(fn_):
                errors.append(
                    'Specified SLS {0} on local filesystem cannot '
                    'be found.'.format(sls)
                )
        state = None
        if not fn_:
            errors.append(
                'Specified SLS {0} in saltenv {1} is not '
                'available on the salt master or through a configured '
                'fileserver'.format(sls, saltenv)
            )
        else:
            try:
                state = compile_template(fn_,
                                         self.state.rend,
                                         self.state.opts['renderer'],
                                         self.state.opts['renderer_blacklist'],
                                         self.state.opts['renderer_whitelist'],
                                         saltenv,
                                         sls,
                                         rendered_sls=mods
                                         )
            except SaltRenderError as exc:
                msg = 'Rendering SLS \'{0}:{1}\' failed: {2}'.format(
                    saltenv, sls, exc
                )
                log.critical(msg)
                errors.append(msg)
            except Exception as exc:  # pylint: disable=broad-except
                msg = 'Rendering SLS {0} failed, render error: {1}'.format(
                    sls, exc
                )
                log.critical(
                    msg,
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
                errors.append('{0}\n{1}'.format(msg, traceback.format_exc()))
            try:
                mods.add('{0}:{1}'.format(saltenv, sls))
            except AttributeError:
                pass

        if state:
            if not isinstance(state, dict):
                errors.append(
                    'SLS {0} does not render to a dictionary'.format(sls)
                )
            else:
                include = []
                if 'include' in state:
                    if not isinstance(state['include'], list):
                        err = ('Include Declaration in SLS {0} is not formed '
                               'as a list'.format(sls))
                        errors.append(err)
                    else:
                        include = state.pop('include')

                self._handle_extend(state, sls, saltenv, errors)
                self._handle_exclude(state, sls, saltenv, errors)
                self._handle_state_decls(state, sls, saltenv, errors)

                for inc_sls in include:
                    # inc_sls may take the form of:
                    #   'sls.to.include' <- same as {<saltenv>: 'sls.to.include'}
                    #   {<env_key>: 'sls.to.include'}
                    #   {'_xenv': 'sls.to.resolve'}
                    xenv_key = '_xenv'

                    if isinstance(inc_sls, dict):
                        env_key, inc_sls = inc_sls.popitem()
                    else:
                        env_key = saltenv

                    if env_key not in self.avail:
                        msg = ('Nonexistent saltenv \'{0}\' found in include '
                               'of \'{1}\' within SLS \'{2}:{3}\''
                               .format(env_key, inc_sls, saltenv, sls))
                        log.error(msg)
                        errors.append(msg)
                        continue

                    if inc_sls.startswith('.'):
                        match = re.match(r'^(\.+)(.*)$', inc_sls)
                        if match:
                            levels, include = match.groups()
                        else:
                            msg = ('Badly formatted include {0} found in include '
                                    'in SLS \'{2}:{3}\''
                                    .format(inc_sls, saltenv, sls))
                            log.error(msg)
                            errors.append(msg)
                            continue
                        level_count = len(levels)
                        p_comps = sls.split('.')
                        if state_data.get('source', '').endswith('/init.sls'):
                            p_comps.append('init')
                        if level_count > len(p_comps):
                            msg = ('Attempted relative include of \'{0}\' '
                                   'within SLS \'{1}:{2}\' '
                                   'goes beyond top level package '
                                   .format(inc_sls, saltenv, sls))
                            log.error(msg)
                            errors.append(msg)
                            continue
                        inc_sls = '.'.join(p_comps[:-level_count] + [include])

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
                            mod_tgt = '{0}:{1}'.format(r_env, sls_target)
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
                        msg = ''
                        if not resolved_envs:
                            msg = ('Unknown include: Specified SLS {0}: {1} is not available on the salt '
                                   'master in saltenv(s): {2} '
                                   ).format(env_key,
                                            inc_sls,
                                            ', '.join(matches) if env_key == xenv_key else env_key)
                        elif len(resolved_envs) > 1:
                            msg = ('Ambiguous include: Specified SLS {0}: {1} is available on the salt master '
                                   'in multiple available saltenvs: {2}'
                                   ).format(env_key,
                                            inc_sls,
                                            ', '.join(resolved_envs))
                        log.critical(msg)
                        errors.append(msg)
                try:
                    self._handle_iorder(state)
                except TypeError:
                    log.critical('Could not render SLS %s. Syntax error detected.', sls)
        else:
            state = {}
        return state, errors

    def _handle_iorder(self, state):
        '''
        Take a state and apply the iorder system
        '''
        if self.opts['state_auto_order']:
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
                    if s_dec.startswith('_'):
                        continue

                    for arg in state[name][s_dec]:
                        if isinstance(arg, dict):
                            if len(arg) > 0:
                                if next(six.iterkeys(arg)) == 'order':
                                    found = True
                    if not found:
                        if not isinstance(state[name][s_dec], list):
                            # quite certainly a syntax error, managed elsewhere
                            continue
                        state[name][s_dec].append(
                                {'order': self.iorder}
                                )
                        self.iorder += 1
        return state

    def _handle_state_decls(self, state, sls, saltenv, errors):
        '''
        Add sls and saltenv components to the state
        '''
        for name in state:
            if not isinstance(state[name], dict):
                if name == '__extend__':
                    continue
                if name == '__exclude__':
                    continue

                if isinstance(state[name], six.string_types):
                    # Is this is a short state, it needs to be padded
                    if '.' in state[name]:
                        comps = state[name].split('.')
                        state[name] = {'__sls__': sls,
                                       '__env__': saltenv,
                                       comps[0]: [comps[1]]}
                        continue
                errors.append(
                    'ID {0} in SLS {1} is not a dictionary'.format(name, sls)
                )
                continue
            skeys = set()
            for key in list(state[name]):
                if key.startswith('_'):
                    continue
                if not isinstance(state[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
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
                            'ID \'{0}\' in SLS \'{1}\' contains multiple state '
                            'declarations of the same type'.format(name, sls)
                        )
                        continue
                    state[name][comps[0]] = state[name].pop(key)
                    state[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)
            if '__sls__' not in state[name]:
                state[name]['__sls__'] = sls
            if '__env__' not in state[name]:
                state[name]['__env__'] = saltenv

    def _handle_extend(self, state, sls, saltenv, errors):
        '''
        Take the extend dec out of state and apply to the highstate global
        dec
        '''
        if 'extend' in state:
            ext = state.pop('extend')
            if not isinstance(ext, dict):
                errors.append(('Extension value in SLS \'{0}\' is not a '
                               'dictionary').format(sls))
                return
            for name in ext:
                if not isinstance(ext[name], dict):
                    errors.append(('Extension name \'{0}\' in SLS \'{1}\' is '
                                   'not a dictionary'
                                   .format(name, sls)))
                    continue
                if '__sls__' not in ext[name]:
                    ext[name]['__sls__'] = sls
                if '__env__' not in ext[name]:
                    ext[name]['__env__'] = saltenv
                for key in list(ext[name]):
                    if key.startswith('_'):
                        continue
                    if not isinstance(ext[name][key], list):
                        continue
                    if '.' in key:
                        comps = key.split('.')
                        ext[name][comps[0]] = ext[name].pop(key)
                        ext[name][comps[0]].append(comps[1])
            state.setdefault('__extend__', []).append(ext)

    def _handle_exclude(self, state, sls, saltenv, errors):
        '''
        Take the exclude dec out of the state and apply it to the highstate
        global dec
        '''
        if 'exclude' in state:
            exc = state.pop('exclude')
            if not isinstance(exc, list):
                err = ('Exclude Declaration in SLS {0} is not formed '
                       'as a list'.format(sls))
                errors.append(err)
            state.setdefault('__exclude__', []).extend(exc)

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
                if saltenv in self.avail:
                    statefiles = fnmatch.filter(self.avail[saltenv], sls_match)
                elif '__env__' in self.avail:
                    statefiles = fnmatch.filter(self.avail['__env__'], sls_match)
                else:
                    all_errors.append(
                        'No matching salt environment for environment '
                        '\'{0}\' found'.format(saltenv)
                    )
                # if we did not found any sls in the fileserver listing, this
                # may be because the sls was generated or added later, we can
                # try to directly execute it, and if it fails, anyway it will
                # return the former error
                if not statefiles:
                    statefiles = [sls_match]

                for sls in statefiles:
                    r_env = '{0}:{1}'.format(saltenv, sls)
                    if r_env in mods:
                        continue
                    state, errors = self.render_state(
                        sls, saltenv, mods, matches)
                    if state:
                        self.merge_included_states(highstate, state, errors)
                    for i, error in enumerate(errors[:]):
                        if 'is not available' in error:
                            # match SLS foobar in environment
                            this_sls = 'SLS {0} in saltenv'.format(
                                sls_match)
                            if this_sls in error:
                                errors[i] = (
                                    'No matching sls found for \'{0}\' '
                                    'in env \'{1}\''.format(sls_match, saltenv))
                    all_errors.extend(errors)

        self.clean_duplicate_extends(highstate)
        return highstate, all_errors

    def clean_duplicate_extends(self, highstate):
        if '__extend__' in highstate:
            highext = []
            for items in (six.iteritems(ext) for ext in highstate['__extend__']):
                for item in items:
                    if item not in highext:
                        highext.append(item)
            highstate['__extend__'] = [{t[0]: t[1]} for t in highext]

    def merge_included_states(self, highstate, state, errors):
        # The extend members can not be treated as globally unique:
        if '__extend__' in state:
            highstate.setdefault('__extend__',
                                 []).extend(state.pop('__extend__'))
        if '__exclude__' in state:
            highstate.setdefault('__exclude__',
                                 []).extend(state.pop('__exclude__'))
        for id_ in state:
            if id_ in highstate:
                if highstate[id_] != state[id_]:
                    errors.append((
                            'Detected conflicting IDs, SLS'
                            ' IDs need to be globally unique.\n    The'
                            ' conflicting ID is \'{0}\' and is found in SLS'
                            ' \'{1}:{2}\' and SLS \'{3}:{4}\'').format(
                                    id_,
                                    highstate[id_]['__env__'],
                                    highstate[id_]['__sls__'],
                                    state[id_]['__env__'],
                                    state[id_]['__sls__'])
                    )
        try:
            highstate.update(state)
        except ValueError:
            errors.append(
                'Error when rendering state with contents: {0}'.format(state)
            )

    def _check_pillar(self, force=False):
        '''
        Check the pillar for errors, refuse to run the state if there are
        errors in the pillar and return the pillar errors
        '''
        if force:
            return True
        if '_errors' in self.state.opts['pillar']:
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
            whitelist = whitelist.split(',')
        for env in matches:
            for sls in matches[env]:
                if sls in whitelist:
                    ret_matches[env] = ret_matches[env] if env in ret_matches else []
                    ret_matches[env].append(sls)
        return ret_matches

    def call_highstate(self, exclude=None, cache=None, cache_name='highstate',
                       force=False, whitelist=None, orchestration_jid=None):
        '''
        Run the sequence to execute the salt highstate for this minion
        '''
        # Check that top file exists
        tag_name = 'no_|-states_|-states_|-None'
        ret = {tag_name: {
                'result': False,
                'comment': 'No states found for this minion',
                'name': 'No States',
                'changes': {},
                '__run_num__': 0,
        }}
        cfn = os.path.join(
                self.opts['cachedir'],
                '{0}.cache.p'.format(cache_name)
        )

        if cache:
            if os.path.isfile(cfn):
                with salt.utils.files.fopen(cfn, 'rb') as fp_:
                    high = self.serial.load(fp_)
                    return self.state.call_high(high, orchestration_jid)
        # File exists so continue
        err = []
        try:
            top = self.get_top()
        except SaltRenderError as err:
            ret[tag_name]['comment'] = 'Unable to render top file: '
            ret[tag_name]['comment'] += six.text_type(err.error)
            return ret
        except Exception:  # pylint: disable=broad-except
            trb = traceback.format_exc()
            err.append(trb)
            return err
        err += self.verify_tops(top)
        matches = self.top_matches(top)
        if not matches:
            msg = ('No Top file or master_tops data matches found. Please see '
                   'master log for details.')
            ret[tag_name]['comment'] = msg
            return ret
        matches = self.matches_whitelist(matches, whitelist)
        self.load_dynamic(matches)
        if not self._check_pillar(force):
            err += ['Pillar failed to render with the following messages:']
            err += self.state.opts['pillar']['_errors']
        else:
            high, errors = self.render_highstate(matches)
            if exclude:
                if isinstance(exclude, six.string_types):
                    exclude = exclude.split(',')
                if '__exclude__' in high:
                    high['__exclude__'].extend(exclude)
                else:
                    high['__exclude__'] = exclude
            err += errors
        if err:
            return err
        if not high:
            return ret
        with salt.utils.files.set_umask(0o077):
            try:
                if salt.utils.platform.is_windows():
                    # Make sure cache file isn't read-only
                    self.state.functions['cmd.run'](
                        ['attrib', '-R', cfn],
                        python_shell=False,
                        output_loglevel='quiet')
                with salt.utils.files.fopen(cfn, 'w+b') as fp_:
                    try:
                        self.serial.dump(high, fp_)
                    except TypeError:
                        # Can't serialize pydsl
                        pass
            except (IOError, OSError):
                log.error('Unable to write to "state.highstate" cache file %s', cfn)

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
                'used': [],
                'unused': [],
                'count_all': 0,
                'count_used': 0,
                'count_unused': 0
            }

            env_matches = matches.get(saltenv)

            for state in states:
                env_usage['count_all'] += 1
                if state in env_matches:
                    env_usage['count_used'] += 1
                    env_usage['used'].append(state)
                else:
                    env_usage['count_unused'] += 1
                    env_usage['unused'].append(state)

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
            loader='states',
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
        self.matchers = salt.loader.matchers(self.opts)
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
        log.info('Loading fresh modules for state activity')
        # Load a modified client interface that looks like the interface used
        # from the minion, but uses remote execution
        #
        self.functions = salt.client.FunctionWrapper(
                self.opts,
                self.opts['id']
                )
        # Load the states, but they should not be used in this class apart
        # from inspection
        self.utils = salt.loader.utils(self.opts)
        self.serializers = salt.loader.serializers(self.opts)
        self.states = salt.loader.states(self.opts, self.functions, self.utils, self.serializers)
        self.rend = salt.loader.render(self.opts, self.functions, states=self.states, context=self.state_con)


class MasterHighState(HighState):
    '''
    Execute highstate compilation from the master
    '''
    def __init__(self, master_opts, minion_opts, grains, id_,
                 saltenv=None):
        # Force the fileclient to be local
        opts = copy.deepcopy(minion_opts)
        opts['file_client'] = 'local'
        opts['file_roots'] = master_opts['master_roots']
        opts['renderer'] = master_opts['renderer']
        opts['state_top'] = master_opts['state_top']
        opts['id'] = id_
        opts['grains'] = grains
        HighState.__init__(self, opts)


class RemoteHighState(object):
    '''
    Manage gathering the data from the master
    '''
    # XXX: This class doesn't seem to be used anywhere
    def __init__(self, opts, grains):
        self.opts = opts
        self.grains = grains
        self.serial = salt.payload.Serial(self.opts)
        # self.auth = salt.crypt.SAuth(opts)
        self.channel = salt.transport.client.ReqChannel.factory(self.opts['master_uri'])
        self._closing = False

    def compile_master(self):
        '''
        Return the state data from the master
        '''
        load = {'grains': self.grains,
                'opts': self.opts,
                'cmd': '_master_state'}
        try:
            return self.channel.send(load, tries=3, timeout=72000)
        except SaltReqTimeoutError:
            return {}

    def destroy(self):
        if self._closing:
            return

        self._closing = True
        self.channel.close()

    # pylint: disable=W1701
    def __del__(self):
        self.destroy()
    # pylint: enable=W1701
