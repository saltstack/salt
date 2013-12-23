# -*- coding: utf-8 -*-
'''
Render the pillar data
'''

# Import python libs
import os
import collections
import logging

# Import salt libs
import salt.loader
import salt.fileclient
import salt.minion
import salt.crypt
import salt.transport
from salt._compat import string_types
from salt.template import compile_template
from salt.utils.dictupdate import update
from salt.utils.odict import OrderedDict
from salt.version import __version__


log = logging.getLogger(__name__)


def get_pillar(opts, grains, id_, saltenv=None, ext=None, env=None):
    '''
    Return the correct pillar driver based on the file_client option
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    return {
            'remote': RemotePillar,
            'local': Pillar
            }.get(opts['file_client'], Pillar)(opts, grains, id_, saltenv, ext)


class RemotePillar(object):
    '''
    Get the pillar from the master
    '''
    def __init__(self, opts, grains, id_, saltenv, ext=None):
        self.opts = opts
        self.opts['environment'] = saltenv
        self.ext = ext
        self.grains = grains
        self.id_ = id_
        self.serial = salt.payload.Serial(self.opts)
        self.sreq = salt.transport.Channel.factory(opts)
        # self.auth = salt.crypt.SAuth(opts)

    def compile_pillar(self):
        '''
        Return the pillar data from the master
        '''
        load = {'id': self.id_,
                'grains': self.grains,
                'saltenv': self.opts['environment'],
                'ver': '2',
                'cmd': '_pillar'}
        if self.ext:
            load['ext'] = self.ext
        # ret = self.sreq.send(load, tries=3, timeout=7200)
        ret_pillar = self.sreq.crypted_transfer_decode_dictentry(load, dictkey='pillar', tries=3, timeout=7200)

        # key = self.auth.get_keys()
        # aes = key.private_decrypt(ret['key'], 4)
        # pcrypt = salt.crypt.Crypticle(self.opts, aes)
        # ret_pillar = pcrypt.loads(ret['pillar'])

        if not isinstance(ret_pillar, dict):
            log.error(
                'Got a bad pillar from master, type {0}, expecting dict: '
                '{1}'.format(type(ret_pillar).__name__, ret_pillar)
            )
            return {}
        return ret_pillar


class Pillar(object):
    '''
    Read over the pillar top files and render the pillar data
    '''
    def __init__(self, opts, grains, id_, saltenv, ext=None):
        # Store the file_roots path so we can restore later. Issue 5449
        self.actual_file_roots = opts['file_roots']
        # use the local file client
        self.opts = self.__gen_opts(opts, grains, id_, saltenv, ext)
        self.client = salt.fileclient.get_file_client(self.opts)
        if opts.get('file_client', '') == 'local':
            opts['grains'] = grains
            self.functions = salt.loader.minion_mods(opts)
        else:
            self.functions = salt.loader.minion_mods(self.opts)
        self.matcher = salt.minion.Matcher(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)
        # Fix self.opts['file_roots'] so that ext_pillars know the real
        # location of file_roots. Issue 5951
        ext_pillar_opts = dict(self.opts)
        ext_pillar_opts['file_roots'] = self.actual_file_roots
        self.ext_pillars = salt.loader.pillars(ext_pillar_opts, self.functions)

    def __valid_ext(self, ext):
        '''
        Check to see if the on demand external pillar is allowed
        '''
        if not isinstance(ext, dict):
            return {}
        valid = set(('libvirt', 'virtkey'))
        if any(key not in valid for key in ext):
            return {}
        return ext

    def __gen_opts(self, opts_in, grains, id_, saltenv=None, ext=None, env=None):
        '''
        The options need to be altered to conform to the file client
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env
        opts = dict(opts_in)
        opts['file_roots'] = opts['pillar_roots']
        opts['file_client'] = 'local'
        if not grains:
            opts['grains'] = {}
        else:
            opts['grains'] = grains
        opts['id'] = id_
        if 'environment' not in opts:
            opts['environment'] = saltenv
        if opts['state_top'].startswith('salt://'):
            opts['state_top'] = opts['state_top']
        elif opts['state_top'].startswith('/'):
            opts['state_top'] = os.path.join('salt://', opts['state_top'][1:])
        else:
            opts['state_top'] = os.path.join('salt://', opts['state_top'])
        if self.__valid_ext(ext):
            if 'ext_pillar' in opts:
                opts['ext_pillar'].append(ext)
            else:
                opts['ext_pillar'] = [ext]
        return opts

    def _get_envs(self):
        '''
        Pull the file server environments out of the master options
        '''
        envs = set(['base'])
        if 'file_roots' in self.opts:
            envs.update(list(self.opts['file_roots']))
        return envs

    def get_tops(self):
        '''
        Gather the top files
        '''
        tops = collections.defaultdict(list)
        include = collections.defaultdict(list)
        done = collections.defaultdict(list)
        errors = []
        # Gather initial top files
        try:
            if self.opts['environment']:
                tops[self.opts['environment']] = [
                        compile_template(
                            self.client.cache_file(
                                self.opts['state_top'],
                                self.opts['environment']
                                ),
                            self.rend,
                            self.opts['renderer'],
                            self.opts['environment']
                            )
                        ]
            else:
                for saltenv in self._get_envs():
                    tops[saltenv].append(
                            compile_template(
                                self.client.cache_file(
                                    self.opts['state_top'],
                                    saltenv
                                    ),
                                self.rend,
                                self.opts['renderer'],
                                saltenv=saltenv
                                )
                            )
        except Exception as exc:
            errors.append(
                    ('Rendering Primary Top file failed, render error:\n{0}'
                        .format(exc)))

        # Search initial top files for includes
        for saltenv, ctops in tops.items():
            for ctop in ctops:
                if 'include' not in ctop:
                    continue
                for sls in ctop['include']:
                    include[saltenv].append(sls)
                ctop.pop('include')
        # Go through the includes and pull out the extra tops and add them
        while include:
            pops = []
            for saltenv, states in include.items():
                pops.append(saltenv)
                if not states:
                    continue
                for sls in states:
                    if sls in done[saltenv]:
                        continue
                    try:
                        tops[saltenv].append(
                                compile_template(
                                    self.client.get_state(
                                        sls,
                                        saltenv
                                        ).get('dest', False),
                                    self.rend,
                                    self.opts['renderer'],
                                    saltenv=saltenv
                                    )
                                )
                    except Exception as exc:
                        errors.append(
                                ('Rendering Top file {0} failed, render error'
                                 ':\n{1}').format(sls, exc))
                    done[saltenv].append(sls)
            for saltenv in pops:
                if saltenv in include:
                    include.pop(saltenv)

        return tops, errors

    def merge_tops(self, tops):
        '''
        Cleanly merge the top files
        '''
        top = collections.defaultdict(dict)
        orders = collections.defaultdict(dict)
        for ctops in tops.values():
            for ctop in ctops:
                for saltenv, targets in ctop.items():
                    if saltenv == 'include':
                        continue
                    for tgt in targets:
                        matches = []
                        states = OrderedDict()
                        orders[saltenv][tgt] = 0
                        for comp in ctop[saltenv][tgt]:
                            if isinstance(comp, dict):
                                if 'match' in comp:
                                    matches.append(comp)
                                if 'order' in comp:
                                    order = comp['order']
                                    if not isinstance(order, int):
                                        try:
                                            order = int(order)
                                        except ValueError:
                                            order = 0
                                    orders[saltenv][tgt] = order
                            if isinstance(comp, string_types):
                                states[comp] = True
                        top[saltenv][tgt] = matches
                        top[saltenv][tgt].extend(list(states.keys()))
        return self.sort_top_targets(top, orders)

    def sort_top_targets(self, top, orders):
        '''
        Returns the sorted high data from the merged top files
        '''
        sorted_top = collections.defaultdict(OrderedDict)
        for saltenv, targets in top.items():
            sorted_targets = sorted(targets.keys(),
                    key=lambda target: orders[saltenv][target])
            for target in sorted_targets:
                sorted_top[saltenv][target] = targets[target]
        return sorted_top

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        tops, errors = self.get_tops()
        return self.merge_tops(tops), errors

    def top_matches(self, top):
        '''
        Search through the top high data for matches and return the states
        that this minion needs to execute.

        Returns:
        {'saltenv': ['state1', 'state2', ...]}
        '''
        matches = {}
        for saltenv, body in top.items():
            if self.opts['environment']:
                if saltenv != self.opts['environment']:
                    continue
            for match, data in body.items():
                if self.matcher.confirm_top(
                        match,
                        data,
                        self.opts.get('nodegroups', {}),
                        ):
                    if saltenv not in matches:
                        matches[saltenv] = []
                    for item in data:
                        if isinstance(item, string_types):
                            matches[saltenv].append(item)
        return matches

    def render_pstate(self, sls, saltenv, mods, defaults=None):
        '''
        Collect a single pillar sls file and render it
        '''
        if defaults is None:
            defaults = {}
        err = ''
        errors = []
        fn_ = self.client.get_state(sls, saltenv).get('dest', False)
        if not fn_:
            msg = ('Specified SLS {0!r} in environment {1!r} is not'
                   ' available on the salt master').format(sls, saltenv)
            log.error(msg)
            errors.append(msg)
        state = None
        try:
            state = compile_template(
                fn_, self.rend, self.opts['renderer'], saltenv, sls, **defaults)
        except Exception as exc:
            msg = 'Rendering SLS {0!r} failed, render error:\n{1}'.format(
                sls, exc
            )
            log.critical(msg)
            errors.append(msg)
        mods.add(sls)
        nstate = None
        if state:
            if not isinstance(state, dict):
                msg = 'SLS {0!r} does not render to a dictionary'.format(sls)
                log.error(msg)
                errors.append(msg)
            else:
                if 'include' in state:
                    if not isinstance(state['include'], list):
                        msg = ('Include Declaration in SLS {0!r} is not '
                               'formed as a list'.format(sls))
                        log.error(msg)
                        errors.append(msg)
                    else:
                        for sub_sls in state.pop('include'):
                            if isinstance(sub_sls, dict):
                                sub_sls, v = sub_sls.iteritems().next()
                                defaults = v.get('defaults', {})
                                key = v.get('key', None)
                            else:
                                key = None
                            if sub_sls not in mods:
                                nstate, mods, err = self.render_pstate(
                                        sub_sls,
                                        saltenv,
                                        mods,
                                        defaults
                                        )
                            if nstate:
                                if key:
                                    state[key] = nstate
                                else:
                                    state.update(nstate)
                            if err:
                                errors += err
        return state, mods, errors

    def render_pillar(self, matches):
        '''
        Extract the sls pillar files from the matches and render them into the
        pillar
        '''
        pillar = {}
        errors = []
        for saltenv, pstates in matches.items():
            mods = set()
            for sls in pstates:
                pstate, mods, err = self.render_pstate(sls, saltenv, mods)

                if err:
                    errors += err

                if pstate is not None:
                    if not isinstance(pstate, dict):
                        log.error(
                            'The rendered pillar sls file, {0!r} state did '
                            'not return the expected data format. This is '
                            'a sign of a malformed pillar sls file. Returned '
                            'errors: {1}'.format(
                                sls,
                                ', '.join(['{0!r}'.format(e) for e in errors])
                            )
                        )
                        continue
                    update(pillar, pstate)

        return pillar, errors

    def ext_pillar(self, pillar):
        '''
        Render the external pillar data
        '''
        if not 'ext_pillar' in self.opts:
            return {}
        if not isinstance(self.opts['ext_pillar'], list):
            log.critical('The "ext_pillar" option is malformed')
            return {}
        for run in self.opts['ext_pillar']:
            if not isinstance(run, dict):
                log.critical('The "ext_pillar" option is malformed')
                return {}
            for key, val in run.items():
                if key not in self.ext_pillars:
                    err = ('Specified ext_pillar interface {0} is '
                           'unavailable').format(key)
                    log.critical(err)
                    continue
                try:
                    try:
                        # try the new interface, which includes the minion ID
                        # as first argument
                        if isinstance(val, dict):
                            ext = self.ext_pillars[key](self.opts['id'], pillar, **val)
                        elif isinstance(val, list):
                            ext = self.ext_pillars[key](self.opts['id'], pillar, *val)
                        else:
                            ext = self.ext_pillars[key](self.opts['id'], pillar, val)
                        update(pillar, ext)

                    except TypeError as e:
                        if e.message.startswith('ext_pillar() takes exactly '):
                            log.warning('Deprecation warning: ext_pillar "{0}"'
                                        ' needs to accept minion_id as first'
                                        ' argument'.format(key))
                        else:
                            raise

                        if isinstance(val, dict):
                            ext = self.ext_pillars[key](pillar, **val)
                        elif isinstance(val, list):
                            ext = self.ext_pillars[key](pillar, *val)
                        else:
                            ext = self.ext_pillars[key](pillar, val)
                        update(pillar, ext)

                except Exception as exc:
                    log.exception(
                            'Failed to load ext_pillar {0}: {1}'.format(
                                key,
                                exc
                                )
                            )
        return pillar

    def compile_pillar(self):
        '''
        Render the pillar data and return
        '''
        top, terrors = self.get_top()
        matches = self.top_matches(top)
        pillar, errors = self.render_pillar(matches)
        self.ext_pillar(pillar)
        errors.extend(terrors)
        if self.opts.get('pillar_opts', True):
            mopts = dict(self.opts)
            if 'grains' in mopts:
                mopts.pop('grains')
            if 'aes' in mopts:
                mopts.pop('aes')
            # Restore the actual file_roots path. Issue 5449
            mopts['file_roots'] = self.actual_file_roots
            mopts['saltversion'] = __version__
            pillar['master'] = mopts
        if errors:
            for error in errors:
                log.critical('Pillar render error: {0}'.format(error))
            pillar['_errors'] = errors
        return pillar
