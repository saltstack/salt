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
from salt._compat import string_types
from salt.template import compile_template
from salt.utils.dictupdate import update
from salt.version import __version__

log = logging.getLogger(__name__)


def get_pillar(opts, grains, id_, env=None, ext=None):
    '''
    Return the correct pillar driver based on the file_client option
    '''
    return {
            'remote': RemotePillar,
            'local': Pillar
            }.get(opts['file_client'], Pillar)(opts, grains, id_, env, ext)


class RemotePillar(object):
    '''
    Get the pillar from the master
    '''
    def __init__(self, opts, grains, id_, env, ext=None):
        self.opts = opts
        self.opts['environment'] = env
        self.ext = ext
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
                'ver': '2',
                'cmd': '_pillar'}
        if self.ext:
            load['ext'] = self.ext
        ret = self.sreq.send('aes', self.auth.crypticle.dumps(load), 3, 7200)
        key = self.auth.get_keys()
        aes = key.private_decrypt(ret['key'], 4)
        pcrypt = salt.crypt.Crypticle(self.opts, aes)
        return pcrypt.loads(ret['pillar'])


class Pillar(object):
    '''
    Read over the pillar top files and render the pillar data
    '''
    def __init__(self, opts, grains, id_, env, ext=None):
        # use the local file client
        self.opts = self.__gen_opts(opts, grains, id_, env, ext)
        self.client = salt.fileclient.get_file_client(self.opts)
        if opts.get('file_client', '') == 'local':
            opts['grains'] = grains
            self.functions = salt.loader.minion_mods(opts)
        else:
            self.functions = salt.loader.minion_mods(self.opts)
        self.matcher = salt.minion.Matcher(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)
        self.ext_pillars = salt.loader.pillars(self.opts, self.functions)

    def __valid_ext(self, ext):
        '''
        Check to see if the on demand external pillar is allowed
        '''
        if not isinstance(ext, dict):
            return {}
        valid = set(('libvirt',))
        if any(key not in valid for key in ext):
            return {}
        return ext

    def __gen_opts(self, opts_in, grains, id_, env=None, ext=None):
        '''
        The options need to be altered to conform to the file client
        '''
        opts = dict(opts_in)
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
        except Exception as exc:
            errors.append(
                    ('Rendering Primary Top file failed, render error:\n{0}'
                        .format(exc)))

        # Search initial top files for includes
        for env, ctops in tops.items():
            for ctop in ctops:
                if 'include' not in ctop:
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
                    try:
                        tops[env].append(
                                compile_template(
                                    self.client.get_state(
                                        sls,
                                        env
                                        ).get('dest', False),
                                    self.rend,
                                    self.opts['renderer'],
                                    env=env
                                    )
                                )
                    except Exception as exc:
                        errors.append(
                                ('Rendering Top file {0} failed, render error'
                                 ':\n{1}').format(sls, exc))
                    done[env].append(sls)
            for env in pops:
                if env in include:
                    include.pop(env)

        return tops, errors

    def merge_tops(self, tops):
        '''
        Cleanly merge the top files
        '''
        top = collections.defaultdict(dict)
        for ctops in tops.values():
            for ctop in ctops:
                for env, targets in ctop.items():
                    if env == 'include':
                        continue
                    for tgt in targets:
                        if tgt not in top[env]:
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
        tops, errors = self.get_tops()
        return self.merge_tops(tops), errors

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
                if env != self.opts['environment']:
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
        return matches

    def render_pstate(self, sls, env, mods):
        '''
        Collect a single pillar sls file and render it
        '''
        err = ''
        errors = []
        fn_ = self.client.get_state(sls, env).get('dest', False)
        if not fn_:
            msg = ('Specified SLS {0!r} in environment {1!r} is not'
                   ' available on the salt master').format(sls, env)
            log.error(msg)
            errors.append(msg)
        state = None
        try:
            state = compile_template(
                fn_, self.rend, self.opts['renderer'], env, sls)
        except Exception as exc:
            msg = 'Rendering SLS {0!r} failed, render error:\n{1}'.format(
                sls, exc
            )
            log.error(msg)
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
                    pillar.update(pstate)

        return pillar, errors

    def ext_pillar(self, pillar):
        '''
        Render the external pillar data
        '''
        if not 'ext_pillar' in self.opts:
            return  {}
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
            mopts['saltversion'] = __version__
            pillar['master'] = mopts
        if errors:
            for error in errors:
                log.critical('Pillar render error: {0}'.format(error))
            pillar['_errors'] = errors
        return pillar
