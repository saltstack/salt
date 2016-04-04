# -*- coding: utf-8 -*-
'''
Render the pillar data
'''

# Import python libs
from __future__ import absolute_import
import copy
import os
import collections
import logging
import tornado.gen

# Import salt libs
import salt.loader
import salt.fileclient
import salt.minion
import salt.crypt
import salt.transport
import salt.utils.url
import salt.utils.cache
from salt.exceptions import SaltClientError
from salt.template import compile_template
from salt.utils.dictupdate import merge
from salt.utils.odict import OrderedDict
from salt.version import __version__

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


def get_pillar(opts, grains, minion_id, saltenv=None, ext=None, funcs=None,
               pillar=None, pillarenv=None):
    '''
    Return the correct pillar driver based on the file_client option
    '''
    ptype = {
        'remote': RemotePillar,
        'local': Pillar
    }.get(opts['file_client'], Pillar)
    # If local pillar and we're caching, run through the cache system first
    log.info('Determining pillar cache')
    if opts['pillar_cache']:
        log.info('Compiling pillar from cache')
        log.debug('get_pillar using pillar cache with ext: {0}'.format(ext))
        return PillarCache(opts, grains, minion_id, saltenv, ext=ext, functions=funcs,
                pillar=pillar, pillarenv=pillarenv)
    return ptype(opts, grains, minion_id, saltenv, ext, functions=funcs,
                 pillar=pillar, pillarenv=pillarenv)


# TODO: migrate everyone to this one!
def get_async_pillar(opts, grains, minion_id, saltenv=None, ext=None, funcs=None,
               pillar=None, pillarenv=None):
    '''
    Return the correct pillar driver based on the file_client option
    '''
    ptype = {
        'remote': AsyncRemotePillar,
        'local': AsyncPillar,
    }.get(opts['file_client'], AsyncPillar)
    return ptype(opts, grains, minion_id, saltenv, ext, functions=funcs,
                 pillar=pillar, pillarenv=pillarenv)


class AsyncRemotePillar(object):
    '''
    Get the pillar from the master
    '''
    def __init__(self, opts, grains, minion_id, saltenv, ext=None, functions=None,
                 pillar=None, pillarenv=None):
        self.opts = opts
        self.opts['environment'] = saltenv
        self.ext = ext
        self.grains = grains
        self.minion_id = minion_id
        self.channel = salt.transport.client.AsyncReqChannel.factory(opts)
        if pillarenv is not None or 'pillarenv' not in self.opts:
            self.opts['pillarenv'] = pillarenv
        self.pillar_override = {}
        if pillar is not None:
            if isinstance(pillar, dict):
                self.pillar_override = pillar
            else:
                log.error('Pillar data must be a dictionary')

    @tornado.gen.coroutine
    def compile_pillar(self):
        '''
        Return a future which will contain the pillar data from the master
        '''
        load = {'id': self.minion_id,
                'grains': self.grains,
                'saltenv': self.opts['environment'],
                'pillarenv': self.opts['pillarenv'],
                'pillar_override': self.pillar_override,
                'ver': '2',
                'cmd': '_pillar'}
        if self.ext:
            load['ext'] = self.ext
        try:
            ret_pillar = yield self.channel.crypted_transfer_decode_dictentry(
                load,
                dictkey='pillar',
            )
        except:
            log.exception('Exception getting pillar:')
            raise SaltClientError('Exception getting pillar.')

        if not isinstance(ret_pillar, dict):
            msg = ('Got a bad pillar from master, type {0}, expecting dict: '
                   '{1}').format(type(ret_pillar).__name__, ret_pillar)
            log.error(msg)
            # raise an exception! Pillar isn't empty, we can't sync it!
            raise SaltClientError(msg)
        raise tornado.gen.Return(ret_pillar)


class RemotePillar(object):
    '''
    Get the pillar from the master
    '''
    def __init__(self, opts, grains, minion_id, saltenv, ext=None, functions=None,
                 pillar=None, pillarenv=None):
        self.opts = opts
        self.opts['environment'] = saltenv
        self.ext = ext
        self.grains = grains
        self.minion_id = minion_id
        self.channel = salt.transport.Channel.factory(opts)
        if pillarenv is not None or 'pillarenv' not in self.opts:
            self.opts['pillarenv'] = pillarenv
        self.pillar_override = {}
        if pillar is not None:
            if isinstance(pillar, dict):
                self.pillar_override = pillar
            else:
                log.error('Pillar data must be a dictionary')

    def compile_pillar(self):
        '''
        Return the pillar data from the master
        '''
        load = {'id': self.minion_id,
                'grains': self.grains,
                'saltenv': self.opts['environment'],
                'pillarenv': self.opts['pillarenv'],
                'pillar_override': self.pillar_override,
                'ver': '2',
                'cmd': '_pillar'}
        if self.ext:
            load['ext'] = self.ext
        ret_pillar = self.channel.crypted_transfer_decode_dictentry(load,
                                                                    dictkey='pillar',
                                                                    )

        if not isinstance(ret_pillar, dict):
            log.error(
                'Got a bad pillar from master, type {0}, expecting dict: '
                '{1}'.format(type(ret_pillar).__name__, ret_pillar)
            )
            return {}
        return ret_pillar


class PillarCache(object):
    '''
    Return a cached pillar if it exists, otherwise cache it.

    Pillar caches are structed in two diminensions: minion_id with a dict of saltenvs.
    Each saltenv contains a pillar dict

    Example data structure:

    ```
    {'minion_1':
        {'base': {'pilar_key_1' 'pillar_val_1'}
    }
    '''
    # TODO ABC?
    def __init__(self, opts, grains, minion_id, saltenv, ext=None, functions=None,
            pillar=None, pillarenv=None):
        # Yes, we need all of these because we need to route to the Pillar object
        # if we have no cache. This is another refactor target.

        # Go ahead and assign these because they may be needed later
        self.opts = opts
        self.grains = grains
        self.minion_id = minion_id
        self.ext = ext
        self.functions = functions
        self.pillar = pillar
        self.pillarenv = pillarenv

        if saltenv is None:
            self.saltenv = 'base'
        else:
            self.saltenv = saltenv

        # Determine caching backend
        self.cache = salt.utils.cache.CacheFactory.factory(
                self.opts['pillar_cache_backend'],
                self.opts['pillar_cache_ttl'],
                minion_cache_path=self._minion_cache_path(minion_id))

    def _minion_cache_path(self, minion_id):
        '''
        Return the path to the cache file for the minion.

        Used only for disk-based backends
        '''
        return os.path.join(self.opts['cachedir'], 'pillar_cache', minion_id)

    def fetch_pillar(self):
        '''
        In the event of a cache miss, we need to incur the overhead of caching
        a new pillar.
        '''
        log.debug('Pillar cache getting external pillar with ext: {0}'.format(self.ext))
        fresh_pillar = Pillar(self.opts,
                                 self.grains,
                                 self.minion_id,
                                 self.saltenv,
                                 ext=self.ext,
                                 functions=self.functions,
                                 pillar=self.pillar,
                                 pillarenv=self.pillarenv)
        return fresh_pillar.compile_pillar()  # FIXME We are not yet passing pillar_dirs in here

    def compile_pillar(self, *args, **kwargs):  # Will likely just be pillar_dirs
        log.debug('Scanning pillar cache for information about minion {0} and saltenv {1}'.format(self.minion_id, self.saltenv))
        log.debug('Scanning cache: {0}'.format(self.cache._dict))
        # Check the cache!
        if self.minion_id in self.cache:  # Keyed by minion_id
            # TODO Compare grains, etc?
            if self.saltenv in self.cache[self.minion_id]:
                # We have a cache hit! Send it back.
                log.debug('Pillar cache hit for minion {0} and saltenv {1}'.format(self.minion_id, self.saltenv))
                return self.cache[self.minion_id][self.saltenv]
            else:
                # We found the minion but not the env. Store it.
                fresh_pillar = self.fetch_pillar()
                self.cache[self.minion_id][self.saltenv] = fresh_pillar
                log.debug('Pillar cache miss for saltenv {0} for minion {1}'.format(self.saltenv, self.minion_id))
                return fresh_pillar
        else:
            # We haven't seen this minion yet in the cache. Store it.
            fresh_pillar = self.fetch_pillar()
            self.cache[self.minion_id] = {self.saltenv: fresh_pillar}
            log.debug('Pillar cache miss for minion {0}'.format(self.minion_id))
            log.debug('Current pillar cache: {0}'.format(self.cache._dict))  # FIXME hack!
            return fresh_pillar


class Pillar(object):
    '''
    Read over the pillar top files and render the pillar data
    '''
    def __init__(self, opts, grains, minion_id, saltenv, ext=None, functions=None,
                 pillar=None, pillarenv=None):
        self.minion_id = minion_id
        # Store the file_roots path so we can restore later. Issue 5449
        self.actual_file_roots = opts['file_roots']
        # use the local file client
        self.opts = self.__gen_opts(opts, grains, saltenv=saltenv, ext=ext, pillarenv=pillarenv)
        self.client = salt.fileclient.get_file_client(self.opts, True)

        if opts.get('file_client', '') == 'local':
            opts['grains'] = grains

        # if we didn't pass in functions, lets load them
        if functions is None:
            utils = salt.loader.utils(opts)
            if opts.get('file_client', '') == 'local':
                self.functions = salt.loader.minion_mods(opts, utils=utils)
            else:
                self.functions = salt.loader.minion_mods(self.opts, utils=utils)
        else:
            self.functions = functions

        self.matcher = salt.minion.Matcher(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)
        ext_pillar_opts = copy.deepcopy(self.opts)
        # Fix self.opts['file_roots'] so that ext_pillars know the real
        # location of file_roots. Issue 5951
        ext_pillar_opts['file_roots'] = self.actual_file_roots
        # Keep the incoming opts ID intact, ie, the master id
        if 'id' in opts:
            ext_pillar_opts['id'] = opts['id']
        self.merge_strategy = 'smart'
        if opts.get('pillar_source_merging_strategy'):
            self.merge_strategy = opts['pillar_source_merging_strategy']

        self.ext_pillars = salt.loader.pillars(ext_pillar_opts, self.functions)
        self.ignored_pillars = {}
        self.pillar_override = {}
        if pillar is not None:
            if isinstance(pillar, dict):
                self.pillar_override = pillar
            else:
                log.error('Pillar data must be a dictionary')

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

    def __gen_opts(self, opts_in, grains, saltenv=None, ext=None, pillarenv=None):
        '''
        The options need to be altered to conform to the file client
        '''
        opts = copy.deepcopy(opts_in)
        opts['file_roots'] = opts['pillar_roots']
        opts['file_client'] = 'local'
        if not grains:
            opts['grains'] = {}
        else:
            opts['grains'] = grains
        if 'environment' not in opts:
            opts['environment'] = saltenv
        opts['id'] = self.minion_id
        if 'pillarenv' not in opts:
            opts['pillarenv'] = pillarenv
        if opts['state_top'].startswith('salt://'):
            opts['state_top'] = opts['state_top']
        elif opts['state_top'].startswith('/'):
            opts['state_top'] = salt.utils.url.create(opts['state_top'][1:])
        else:
            opts['state_top'] = salt.utils.url.create(opts['state_top'])
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
            if self.opts['pillarenv']:
                tops[self.opts['pillarenv']] = [
                        compile_template(
                            self.client.cache_file(
                                self.opts['state_top'],
                                self.opts['pillarenv']
                                ),
                            self.rend,
                            self.opts['renderer'],
                            self.opts['pillarenv'],
                            _pillar_rend=True
                            )
                        ]
            else:
                for saltenv in self._get_envs():
                    top = self.client.cache_file(
                            self.opts['state_top'],
                            saltenv
                            )
                    if top:
                        tops[saltenv].append(
                                compile_template(
                                    top,
                                    self.rend,
                                    self.opts['renderer'],
                                    saltenv=saltenv,
                                    _pillar_rend=True
                                    )
                                )
        except Exception as exc:
            errors.append(
                    ('Rendering Primary Top file failed, render error:\n{0}'
                        .format(exc)))
            log.error('Pillar rendering failed for minion {0}: '.format(self.minion_id),
                    exc_info=True)

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
                                    saltenv=saltenv,
                                    _pillar_rend=True
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
        top = collections.defaultdict(OrderedDict)
        orders = collections.defaultdict(OrderedDict)
        for ctops in six.itervalues(tops):
            for ctop in ctops:
                for saltenv, targets in six.iteritems(ctop):
                    if saltenv == 'include':
                        continue
                    for tgt in targets:
                        matches = []
                        states = OrderedDict()
                        orders[saltenv][tgt] = 0
                        ignore_missing = False
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
                                if comp.get('ignore_missing', False):
                                    ignore_missing = True
                            if isinstance(comp, six.string_types):
                                states[comp] = True
                        if ignore_missing:
                            if saltenv not in self.ignored_pillars:
                                self.ignored_pillars[saltenv] = []
                            self.ignored_pillars[saltenv].extend(states.keys())
                        top[saltenv][tgt] = matches
                        top[saltenv][tgt].extend(states)
        return self.sort_top_targets(top, orders)

    def sort_top_targets(self, top, orders):
        '''
        Returns the sorted high data from the merged top files
        '''
        sorted_top = collections.defaultdict(OrderedDict)
        # pylint: disable=cell-var-from-loop
        for saltenv, targets in six.iteritems(top):
            sorted_targets = sorted(targets,
                    key=lambda target: orders[saltenv][target])
            for target in sorted_targets:
                sorted_top[saltenv][target] = targets[target]
        # pylint: enable=cell-var-from-loop
        return sorted_top

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        tops, errors = self.get_tops()
        try:
            merged_tops = self.merge_tops(tops)
        except TypeError as err:
            merged_tops = OrderedDict()
            errors.append('Error encountered while render pillar top file.')
        return merged_tops, errors

    def top_matches(self, top):
        '''
        Search through the top high data for matches and return the states
        that this minion needs to execute.

        Returns:
        {'saltenv': ['state1', 'state2', ...]}
        '''
        matches = {}
        for saltenv, body in six.iteritems(top):
            if self.opts['pillarenv']:
                if saltenv != self.opts['pillarenv']:
                    continue
            for match, data in six.iteritems(body):
                if self.matcher.confirm_top(
                        match,
                        data,
                        self.opts.get('nodegroups', {}),
                        ):
                    if saltenv not in matches:
                        matches[saltenv] = env_matches = []
                    else:
                        env_matches = matches[saltenv]
                    for item in data:
                        if isinstance(item, six.string_types) and item not in env_matches:
                            env_matches.append(item)
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
            if sls in self.ignored_pillars.get(saltenv, []):
                log.debug('Skipping ignored and missing SLS \'{0}\' in'
                          ' environment \'{1}\''.format(sls, saltenv))
                return None, mods, errors
            elif self.opts['pillar_roots'].get(saltenv):
                msg = ('Specified SLS \'{0}\' in environment \'{1}\' is not'
                       ' available on the salt master').format(sls, saltenv)
                log.error(msg)
                errors.append(msg)
            else:
                log.debug(
                    'Specified SLS \'%s\' in environment \'%s\' was not '
                    'found. This could be because SLS \'%s\' is in an '
                    'environment other than \'%s\', but \'%s\' is included in '
                    'that environment\'s Pillar top file. It could also be '
                    'due to environment \'%s\' not being defined in '
                    '"pillar_roots"',
                    sls, saltenv, sls, saltenv, saltenv, saltenv
                )
                # return state, mods, errors
                return None, mods, errors
        state = None
        try:
            state = compile_template(fn_,
                                     self.rend,
                                     self.opts['renderer'],
                                     saltenv,
                                     sls,
                                     _pillar_rend=True,
                                     **defaults)
        except Exception as exc:
            msg = 'Rendering SLS \'{0}\' failed, render error:\n{1}'.format(
                sls, exc
            )
            log.critical(msg)
            if self.opts.get('pillar_safe_render_error', True):
                errors.append(
                    'Rendering SLS \'{0}\' failed. Please see master log for '
                    'details.'.format(sls)
                )
            else:
                errors.append(msg)
        mods.add(sls)
        nstate = None
        if state:
            if not isinstance(state, dict):
                msg = 'SLS \'{0}\' does not render to a dictionary'.format(sls)
                log.error(msg)
                errors.append(msg)
            else:
                if 'include' in state:
                    if not isinstance(state['include'], list):
                        msg = ('Include Declaration in SLS \'{0}\' is not '
                               'formed as a list'.format(sls))
                        log.error(msg)
                        errors.append(msg)
                    else:
                        for sub_sls in state.pop('include'):
                            if isinstance(sub_sls, dict):
                                sub_sls, v = next(six.iteritems(sub_sls))
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
                                        nstate = {
                                            key: nstate
                                        }

                                    state = merge(
                                        state,
                                        nstate,
                                        self.merge_strategy,
                                        self.opts.get('renderer', 'yaml'),
                                        self.opts.get('pillar_merge_lists', False))

                                if err:
                                    errors += err
        return state, mods, errors

    def render_pillar(self, matches, errors=None):
        '''
        Extract the sls pillar files from the matches and render them into the
        pillar
        '''
        pillar = copy.copy(self.pillar_override)
        if errors is None:
            errors = []
        for saltenv, pstates in six.iteritems(matches):
            mods = set()
            for sls in pstates:
                pstate, mods, err = self.render_pstate(sls, saltenv, mods)

                if err:
                    errors += err

                if pstate is not None:
                    if not isinstance(pstate, dict):
                        log.error(
                            'The rendered pillar sls file, \'{0}\' state did '
                            'not return the expected data format. This is '
                            'a sign of a malformed pillar sls file. Returned '
                            'errors: {1}'.format(
                                sls,
                                ', '.join(
                                    ['\'{0}\''.format(e) for e in errors]
                                )
                            )
                        )
                        continue
                    pillar = merge(
                        pillar,
                        pstate,
                        self.merge_strategy,
                        self.opts.get('renderer', 'yaml'),
                        self.opts.get('pillar_merge_lists', False))

        return pillar, errors

    def _external_pillar_data(self, pillar, val, pillar_dirs, key):
        '''
        Builds actual pillar data structure and updates the ``pillar`` variable
        '''
        ext = None

        if isinstance(val, dict):
            ext = self.ext_pillars[key](self.minion_id, pillar, **val)
        elif isinstance(val, list):
            if key == 'git':
                ext = self.ext_pillars[key](self.minion_id,
                                            val,
                                            pillar_dirs)
            else:
                ext = self.ext_pillars[key](self.minion_id,
                                            pillar,
                                            *val)
        else:
            if key == 'git':
                ext = self.ext_pillars[key](self.minion_id,
                                            val,
                                            pillar_dirs)
            else:
                ext = self.ext_pillars[key](self.minion_id,
                                            pillar,
                                            val)
        return ext

    def ext_pillar(self, pillar, pillar_dirs, errors=None):
        '''
        Render the external pillar data
        '''
        if errors is None:
            errors = []
        if 'ext_pillar' not in self.opts:
            return pillar, errors
        if not isinstance(self.opts['ext_pillar'], list):
            errors.append('The "ext_pillar" option is malformed')
            log.critical(errors[-1])
            return pillar, errors
        ext = None
        # Bring in CLI pillar data
        pillar.update(self.pillar_override)
        for run in self.opts['ext_pillar']:
            if not isinstance(run, dict):
                errors.append('The "ext_pillar" option is malformed')
                log.critical(errors[-1])
                return {}, errors
            if run.keys()[0] in self.opts.get('exclude_ext_pillar', []):
                continue
            for key, val in six.iteritems(run):
                if key not in self.ext_pillars:
                    log.critical(
                        'Specified ext_pillar interface {0} is '
                        'unavailable'.format(key)
                    )
                    continue
                try:
                    ext = self._external_pillar_data(pillar,
                                                        val,
                                                        pillar_dirs,
                                                        key)
                except Exception as exc:
                    errors.append('Failed to load ext_pillar {0}: {1}'.format(
                        key, exc))
            if ext:
                pillar = merge(
                    pillar,
                    ext,
                    self.merge_strategy,
                    self.opts.get('renderer', 'yaml'),
                    self.opts.get('pillar_merge_lists', False))
                ext = None
        return pillar, errors

    def compile_pillar(self, ext=True, pillar_dirs=None):
        '''
        Render the pillar data and return
        '''
        top, top_errors = self.get_top()
        if ext:
            if self.opts.get('pillar_roots_override_ext_pillar', False) or self.opts.get('ext_pillar_first', False):
                salt.utils.warn_until('Nitrogen',
                     'The \'ext_pillar_first\' option has been deprecated and '
                     'replaced by \'pillar_roots_override_ext_pillar\'.'
                )
                self.opts['pillar'], errors = self.ext_pillar({}, pillar_dirs)
                matches = self.top_matches(top)
                pillar, errors = self.render_pillar(matches, errors=errors)
                if self.opts.get('pillar_roots_override_ext_pillar', False):
                    pillar = merge(self.opts['pillar'],
                                   pillar,
                                   self.merge_strategy,
                                   self.opts.get('renderer', 'yaml'),
                                   self.opts.get('pillar_merge_lists', False))
                else:
                    pillar = merge(pillar,
                                   self.opts['pillar'],
                                   self.merge_strategy,
                                   self.opts.get('renderer', 'yaml'),
                                   self.opts.get('pillar_merge_lists', False))
            else:
                matches = self.top_matches(top)
                pillar, errors = self.render_pillar(matches)
                pillar, errors = self.ext_pillar(
                    pillar, pillar_dirs, errors=errors)
        else:
            matches = self.top_matches(top)
            pillar, errors = self.render_pillar(matches)
        errors.extend(top_errors)
        if self.opts.get('pillar_opts', False):
            mopts = dict(self.opts)
            if 'grains' in mopts:
                mopts.pop('grains')
            # Restore the actual file_roots path. Issue 5449
            mopts['file_roots'] = self.actual_file_roots
            mopts['saltversion'] = __version__
            pillar['master'] = mopts
        if errors:
            for error in errors:
                log.critical('Pillar render error: {0}'.format(error))
            pillar['_errors'] = errors
        return pillar


# TODO: actually migrate from Pillar to AsyncPillar to allow for futures in
# ext_pillar etc.
class AsyncPillar(Pillar):
    @tornado.gen.coroutine
    def compile_pillar(self, ext=True, pillar_dirs=None):
        ret = super(AsyncPillar, self).compile_pillar(ext=ext, pillar_dirs=pillar_dirs)
        raise tornado.gen.Return(ret)
