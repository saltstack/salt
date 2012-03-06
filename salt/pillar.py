'''
Render the pillar data
'''

# Import python libs
import os
import copy
import collections

# Import Salt libs
import salt.loader
import salt.fileclient
import salt.minion

class Pillar(object):
    '''
    Read over the pillar top files and render the pillar data
    '''
    def __init__(self, opts, grains, id_):
        # use the local file client
        self.opts = self.__gen_opts(opts, grains, id_)
        self.client = salt.fileclient.get_file_client(self.opts)
        self.matcher = salt.minion.Matcher(self.opts)
        self.rend = salt.loader.render(opts, {})

    def __gen_opts(self, opts, grains, id_):
        '''
        The options need to be altered to conform to the file client
        '''
        opts = copy.deepcopy(opts)
        opts['file_roots'] = opts['pillar_roots']
        opts['file_client'] = 'local'
        opts['grains'] = grains
        opts['id'] = id_
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
            envs.update(self.opts['file_roots'].keys())
        return envs

    def template_shebang(self, template):
        '''
        Check the template shebang line and return the renderer
        '''
        # Open up the first line of the sls template
        line = ''
        with open(template, 'r') as f:
            line = f.readline()
        # Check if it starts with a shebang
        if line.startswith('#!'):
            # pull out the shebang data
            trend = line.strip()[2:]
            # If the specified renderer exists, use it, or fallback
            if trend in self.rend:
                return trend
        return self.opts['renderer']

    def compile_template(self, template, env='', sls=''):
        '''
        Take the path to a template and return the high data structure
        derived from the template.
        '''
        # Template was specified incorrectly
        if not isinstance(template, basestring):
            return {}
        # Template does not exists
        if not os.path.isfile(template):
            return {}
        # Template is an empty file
        if salt.utils.is_empty(template):
            return {}
        # Template is nothing but whitespace
        if not open(template).read().strip():
            return {}

        return self.rend[self.template_shebang(template)](template, env, sls)

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
                    self.compile_template(
                        self.client.cache_file(
                            self.opts['state_top'],
                            self.opts['environment']
                            ),
                        self.opts['environment']
                        )
                    ]
        else:
            for env in self._get_envs():
                tops[env].append(
                        self.compile_template(
                            self.client.cache_file(
                                self.opts['state_top'],
                                env
                                ),
                            env
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
                            self.compile_template(
                                self.client.get_state(
                                    sls,
                                    env
                                    ),
                                env
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
                        for comp in ctop[env][tgt]:
                            if isinstance(comp, dict):
                                cmatches.append(comp)
                            if isinstance(comp, basestring):
                                cstates.add(comp)
                        for comp in top[env][tgt]:
                            if isinstance(comp, dict):
                                matches.append(comp)
                            if isinstance(comp, basestring):
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
                        if isinstance(item, basestring):
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
            state = self.compile_template(fn_, env, sls)
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
 

    def compile_pillar(self):
        '''
        Render the pillar dta and return
        '''
        top = self.get_top()
        matches = self.top_matches(top)
        pillar, errors = self.render_pillar(matches)
        if errors:
            return errors
        return pillar
