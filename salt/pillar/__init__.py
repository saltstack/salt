'''
Render the pillar data
'''

# Import python libs
import os
import copy
import collections
import logging
import subprocess

# Import Salt libs
import salt.loader
import salt.fileclient
import salt.minion
import salt.crypt
from salt._compat import string_types
from salt.template import compile_template

# Import third party libs
import zmq
import yaml

log = logging.getLogger(__name__)


def get_pillar(opts, grains, id_, env=None):
    '''
    Return the correct pillar driver based on the file_client option
    '''
    try:
        return {
                'remote': RemotePillar,
                'local': Pillar
               }.get(opts['file_client'], 'local')(opts, grains, id_, env)
    except KeyError:
        return Pillar(opts, grains, id_, env)


class RemotePillar(object):
    '''
    Get the pillar from the master
    '''
    def __init__(self, opts, grains, id_, env):
        self.opts = opts
        self.opts['environment'] = env
        self.grains = grains
        self.id_ = id_
        self.serial = salt.payload.Serial(self.opts)
        self.sreq = salt.payload.SREQ(self.opts['master_uri'])
        self.auth = salt.crypt.SAuth(opts)

    def compile_pillar(self):
        '''
        Return the pillar data from the master
        '''
        load = {'id': self.id_,
                'grains': self.grains,
                'env': self.opts['environment'],
                'cmd': '_pillar'}
        return self.auth.crypticle.loads(
                self.sreq.send('aes', self.auth.crypticle.dumps(load), 3, 7200)
                )



class Pillar(object):
    '''
    Read over the pillar top files and render the pillar data
    '''
    def __init__(self, opts, grains, id_, env):
        # use the local file client
        self.opts = self.__gen_opts(opts, grains, id_, env)
        self.client = salt.fileclient.get_file_client(self.opts)
        self.matcher = salt.minion.Matcher(self.opts)
        self.functions = salt.loader.minion_mods(self.opts)
        self.rend = salt.loader.render(self.opts, self.functions)
        self.ext_pillars = salt.loader.pillars(self.opts, self.functions)

    def __gen_opts(self, opts, grains, id_, env=None):
        '''
        The options need to be altered to conform to the file client
        '''
        opts = copy.deepcopy(opts)
        opts['file_roots'] = opts['pillar_roots']
        opts['file_client'] = 'local'
        opts['grains'] = grains
        opts['id'] = id_
        if 'environment' not in opts:
            opts['environment'] = env
        if opts['state_top'].startswith('salt://'):
            opts['state_top'] = opts['state_top']
        elif opts['state_top'].startswith('/'):
            opts['state_top'] = os.path.join('salt://', opts['state_top'][1:])
        else:
            opts['state_top'] = os.path.join('salt://', opts['state_top'])
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
        # Gather initial top files
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
            for env in self._get_envs():
                tops[env].append(
                        compile_template(
                            self.client.cache_file(
                                self.opts['state_top'],
                                env
                                ),
                            self.rend,
                            self.opts['renderer'],
                            env=env
                            )
                        )

        # Search initial top files for includes
        for env, ctops in tops.items():
            for ctop in ctops:
                if not 'include' in ctop:
                    continue
                for sls in ctop['include']:
                    include[env].append(sls)
                ctop.pop('include')
        # Go through the includes and pull out the extra tops and add them
        while include:
            pops = []
            for env, states in include.items():
                pops.append(env)
                if not states:
                    continue
                for sls in states:
                    if sls in done[env]:
                        continue
                    tops[env].append(
                            compile_template(
                                self.client.get_state(
                                    sls,
                                    env
                                    ),
                                self.rend,
                                self.opts['renderer'],
                                env=env
                                )
                            )
                    done[env].append(sls)
            for env in pops:
                if env in include:
                    include.pop(env)

        return tops

    def merge_tops(self, tops):
        '''
        Cleanly merge the top files
        '''
        top = collections.defaultdict(dict)
        for sourceenv, ctops in tops.items():
            for ctop in ctops:
                for env, targets in ctop.items():
                    if env == 'include':
                        continue
                    for tgt in targets:
                        if not tgt in top[env]:
                            top[env][tgt] = ctop[env][tgt]
                            continue
                        matches = []
                        states = set()
                        for comp in top[env][tgt]:
                            if isinstance(comp, dict):
                                matches.append(comp)
                            if isinstance(comp, string_types):
                                states.add(comp)
                        top[env][tgt] = matches
                        top[env][tgt].extend(list(states))
        return top

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        tops = self.get_tops()
        return self.merge_tops(tops)

    def top_matches(self, top):
        '''
        Search through the top high data for matches and return the states
        that this minion needs to execute.

        Returns:
        {'env': ['state1', 'state2', ...]}
        '''
        matches = {}
        for env, body in top.items():
            if self.opts['environment']:
                if not env == self.opts['environment']:
                    continue
            for match, data in body.items():
                if self.matcher.confirm_top(
                        match,
                        data,
                        self.opts.get('nodegroups', {}),
                        ):
                    if env not in matches:
                        matches[env] = []
                    for item in data:
                        if isinstance(item, string_types):
                            matches[env].append(item)
        ext_matches = self.client.ext_nodes()
        for env in ext_matches:
            if env in matches:
                matches[env] = list(set(ext_matches[env]).union(matches[env]))
            else:
                matches[env] = ext_matches[env]
        return matches

    def render_pstate(self, sls, env, mods):
        '''
        Collect a single pillar sls file and render it
        '''
        err = ''
        errors = []
        fn_ = self.client.get_state(sls, env)
        if not fn_:
            errors.append(('Specified SLS {0} in environment {1} is not'
                           ' available on the salt master').format(sls, env))
        state = None
        try:
            state = compile_template(
                fn_, self.rend, self.opts['renderer'], env, sls)
        except Exception as exc:
            errors.append(('Rendering SLS {0} failed, render error:\n{1}'
                           .format(sls, exc)))
        mods.add(sls)
        nstate = None
        if state:
            if not isinstance(state, dict):
                errors.append(('SLS {0} does not render to a dictionary'
                               .format(sls)))
            else:
                if 'include' in state:
                    if not isinstance(state['include'], list):
                        err = ('Include Declaration in SLS {0} is not formed '
                               'as a list'.format(sls))
                        errors.append(err)
                    else:
                        for sub_sls in state.pop('include'):
                            if sub_sls not in mods:
                                nstate, mods, err = self.render_pstate(
                                        sub_sls,
                                        env,
                                        mods
                                        )
                            if nstate:
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
        for env, pstates in matches.items():
            mods = set()
            for sls in pstates:
                pstate, mods, err = self.render_pstate(sls, env, mods)
                if pstate:
                    pillar.update(pstate)
                if err:
                    errors += err
        return pillar, errors

    def ext_pillar(self):
        '''
        Render the external pillar data
        '''
        if not 'ext_pillar' in self.opts:
            return  {}
        if not isinstance(self.opts['ext_pillar'], list):
            log.critical('The "ext_pillar" option is malformed')
            return {}
        ext = {}
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
                    if isinstance(val, dict):
                        ext.update(self.ext_pillars[key](**val))
                    elif isinstance(val, list):
                        ext.update(self.ext_pillars[key](*val))
                    else:
                        ext.update(self.ext_pillars[key](val))
                except Exception as e:
                    log.critical('Failed to load ext_pillar {0}'.format(key))
        return ext

    def compile_pillar(self):
        '''
        Render the pillar dta and return
        '''
        top = self.get_top()
        matches = self.top_matches(top)
        pillar, errors = self.render_pillar(matches)
        pillar.update(self.ext_pillar())
        if errors:
            return errors
        return pillar
