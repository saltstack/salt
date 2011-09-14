'''
The module used to execute states in salt. A state is unlike a module execution
in that instead of just executing a command it ensure that a certain state is
present on the system.

The data sent to the state calls is as follows:
    { 'state': '<state module name>',
      'fun': '<state function name>',
      'name': '<the name argument passed to all states>'
      'argn': '<arbitrairy argument, can have many of these>'
      }
'''
# Import python modules
import os
import copy
import inspect
import tempfile
import logging
# Import Salt modules
import salt.loader
import salt.minion

log = logging.getLogger(__name__)

def format_log(ret):
    '''
    Format the state into a log message
    '''
    msg = ''
    if type(ret) == type(dict()):
        # Looks like the ret may be a valid state return
        if ret.has_key('changes'):
            # Yep, looks like a valid state return
            chg = ret['changes']
            if not chg:
                msg = 'No changes made for {0[name]}'.format(ret)
            elif type(chg) == type(dict()):
                if chg.has_key('diff'):
                    if type(chg['diff']) == type(str()):
                        msg = 'File changed:\n{0}'.format(
                                chg['diff'])
                if type(chg[chg.keys()[0]]) == type(dict()):
                    if chg[chg.keys()[0]].has_key('new'):
                        # This is the return data from a package install
                        msg = 'Installed Packages:\n'
                        for pkg in chg:
                            old = 'absent'
                            if chg[pkg]['old']:
                                old = chg[pkg]['old']
                            msg += '{0} changed from {1} to {2}\n'.format(
                                    pkg, old, chg[pkg]['new'])
            if not msg:
                msg = str(ret['changes'])
            if ret['result']:
                log.info(msg)
            else:
                log.error(msg)
    else:
        # catch unhandled data
        log.info(str(ret))

class StateError(Exception): pass

class State(object):
    '''
    Class used to execute salt states
    '''
    def __init__(self, opts):
        if not opts.has_key('grains'):
            opts['grains'] = salt.loader.grains(opts)
        self.opts = opts
        self.functions = salt.loader.minion_mods(self.opts)
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)

    def verify_data(self, data):
        '''
        Verify the data, return an error statement if something is wrong
        '''
        errors = []
        if not data.has_key('state'):
            errors.append('Missing "state" data')
        if not data.has_key('fun'):
            errors.append('Missing "fun" data')
        if not data.has_key('name'):
            errors.append('Missing "name" data')
        if errors:
            return errors
        full = data['state'] + '.' + data['fun']
        if not self.states.has_key(full):
            if data.has_key('__sls__'):
                errors.append(
                    'State {0} found in sls {1} is unavailable'.format(
                        full,
                        data['__sls__']
                        )
                    )
            else:
                errors.append('Specified state ' + full + ' is unavailable.')
        else:
            aspec = inspect.getargspec(self.states[full])
            arglen = 0
            deflen = 0
            if type(aspec[0]) == type(list()):
                arglen = len(aspec[0])
            if type(aspec[3]) == type(tuple()):
                deflen = len(aspec[3])
            for ind in range(arglen - deflen):
                if not data.has_key(aspec[0][ind]):
                    errors.append('Missing paramater ' + aspec[0][ind]\
                                + ' for state ' + full)
        return errors

    def verify_high(self, high):
        '''
        Verify that the high data is viable and follows the data structure
        '''
        errors = []
        if not isinstance(high, dict):
            errors.append('High data is not a dictonary and is invalid')
        for name, body in high.items():
            if not isinstance(body, dict):
                err = 'The type {0} is not formated as a dictonary'.format(name)
                errors.append(err)
                continue
            for state, run in body.items():
                pass
        return errors

    def verify_chunks(self, chunks):
        '''
        Verify the chunks in a list of low data structures
        '''
        err = []
        for chunk in chunks:
            err += self.verify_data(chunk)
        return err

    def format_call(self, data):
        '''
        Formats low data into a list of dict's used to actually call the state,
        returns:
        {
        'full': 'module.function',
        'args': [arg[0], arg[1], ...]
        }
        used to call the function like this:
        self.states[ret['full']](*ret['args'])

        It is assumed that the passed data has already been verified with
        verify_data
        '''
        ret = {}
        ret['full'] = data['state'] + '.' + data['fun']
        ret['args'] = []
        aspec = inspect.getargspec(self.states[ret['full']])
        arglen = 0
        deflen = 0
        if type(aspec[0]) == type(list()):
            arglen = len(aspec[0])
        if type(aspec[3]) == type(tuple()):
            deflen = len(aspec[3])
        kwargs = {}
        for ind in range(arglen - 1, 0, -1):
            minus = arglen - ind
            if deflen - minus > -1:
                kwargs[aspec[0][ind]] = aspec[3][-minus]
        for arg in kwargs:
            if data.has_key(arg):
                kwargs[arg] = data[arg]
        for arg in aspec[0]:
            if kwargs.has_key(arg):
                ret['args'].append(kwargs[arg])
            else:
                ret['args'].append(data[arg])
        return ret

    def compile_high_data(self, high):
        '''
        "Compile" the high data as it is retrieved from the cli or yaml into
        the individual state executor structures
        '''
        chunks = []
        for name, body in high.items():
            for state, run in body.items():
                if state.startswith('__'):
                    continue
                chunk = {'state': state,
                         'name': name}
                if body.has_key('__sls__'):
                    chunk['__sls__'] = body['__sls__']
                funcs = set()
                names = set()
                for arg in run:
                    if type(arg) == type(str()):
                        funcs.add(arg)
                        continue
                    if type(arg) == type(dict()):
                        for key, val in arg.items():
                            if key == 'names':
                                names.update(val)
                                continue
                            else:
                                chunk.update(arg)
                if names:
                    for name in names:
                        live  = copy.deepcopy(chunk)
                        live['name'] = name
                        for fun in funcs:
                            live['fun'] = fun
                            chunks.append(live)
                else:
                    live  = copy.deepcopy(chunk)
                    for fun in funcs:
                        live['fun'] = fun
                        chunks.append(live)

        return sorted(chunks, key=lambda k: k['state'] + k['name'] + k['fun'])

    def compile_template(self, template):
        '''
        Take the path to a template and return the high data structure derived
        from the template.
        '''
        if not isinstance(template, str):
            return {}
        if not os.path.isfile(template):
            return {}
        return self.rend[self.opts['renderer']](template)

    def compile_template_str(self, template):
        '''
        Take the path to a template and return the high data structure derived
        from the template.
        '''
        fn_ = tempfile.mkstemp()[1]
        open(fn_, 'w+').write(template)
        high = self.rend[self.opts['renderer']](fn_)
        os.remove(fn_)
        return high

    def call(self, data):
        '''
        Call a state directly with the low data structure, verify data before
        processing.
        '''
        log.info(
                'Executing state {0[state]}.{0[fun]} for {0[name]}'.format(data)
                )
        cdata = self.format_call(data)
        ret = self.states[cdata['full']](*cdata['args'])
        format_log(ret)
        return ret

    def call_chunks(self, chunks):
        '''
        Iterate over a list of chunks and call them, checking for requires.
        '''
        running = {}
        for low in chunks:
            running = self.call_chunk(low, running, chunks)
        return running

    def check_requires(self, low, running, chunks):
        '''
        Look into the running data to see if the requirement has been met
        '''
        if not low.has_key('require'):
            return 'met'
        reqs = []
        status = 'unmet'
        for req in low['require']:
            for chunk in chunks:
                if chunk['name'] == req[req.keys()[0]]:
                    if chunk['state'] == req.keys()[0]:
                        reqs.append(chunk)
        fun_stats = []
        for req in reqs:
            tag = req['state'] + '.' + req['name'] + '.' + req['fun']
            if not running.has_key(tag):
                fun_stats.append('unmet')
            else:
                fun_stats.append('met' if running[tag]['result'] else 'fail')
        for stat in fun_stats:
            if stat == 'unmet':
                return stat
            elif stat == 'fail':
                return stat
        return 'met'

    def check_watchers(self, low, running, chunks):
        '''
        Look into the running data to see if the watched states have been run
        '''
        if not low.has_key('watch'):
            return 'nochange'
        reqs = []
        status = 'unmet'
        for req in low['watch']:
            for chunk in chunks:
                if chunk['name'] == req[req.keys()[0]]:
                    if chunk['state'] == req.keys()[0]:
                        reqs.append(chunk)
        fun_stats = []
        for req in reqs:
            tag = req['state'] + '.' + req['name'] + '.' + req['fun']
            if not running.has_key(tag):
                fun_stats.append('unmet')
            else:
                fun_stats.append('change' if running[tag]['changes'] else 'nochange')
        for stat in fun_stats:
            if stat == 'change':
                return stat
            elif stat == 'unmet':
                return stat
        return 'nochange'

    def call_chunk(self, low, running, chunks):
        '''
        Check if a chunk has any requires, execute the requires and then the
        chunk
        '''
        tag = low['state'] + '.' + low['name'] + '.' + low['fun']
        if low.has_key('require'):
            status = self.check_requires(low, running, chunks)
            if status == 'unmet':
                reqs = []
                for req in low['require']:
                    for chunk in chunks:
                        if chunk['name'] == req[req.keys()[0]]:
                            if chunk['state'] == req.keys()[0]:
                                reqs.append(chunk)
                for chunk in reqs:
                    running = self.call_chunk(chunk, running, chunks)
                running = self.call_chunk(low, running, chunks)
            elif status == 'met':
                running[tag] = self.call(low)
            elif status == 'fail':
                running[tag] = {'changes': {},
                                'result': False,
                                'comment': 'One or more require failed'}
        elif low.has_key('watch'):
            status = self.check_watchers(low, running, chunks)
            if status == 'unmet':
                reqs = []
                for req in low['watch']:
                    for chunk in chunks:
                        if chunk['name'] == req[req.keys()[0]]:
                            if chunk['state'] == req.keys()[0]:
                                reqs.append(chunk)
                for chunk in reqs:
                    running = self.call_chunk(chunk, running, chunks)
                running = self.call_chunk(low, running, chunks)
            elif status == 'nochange':
                running[tag] = self.call(low)
            elif status == 'change':
                ret = self.call(low)
                if not ret['changes']:
                    low['fun'] = 'watcher'
                    ret = self.call(low)
                running[tag] = ret
        else:
            running[tag] = self.call(low)
        return running

    def call_high(self, high):
        '''
        Process a high data call and ensure the defined states.
        '''
        err = []
        rets = []
        errors = self.verify_high(high)
        if errors:
            return errors
        chunks = self.compile_high_data(high)
        errors += self.verify_chunks(chunks)
        if errors:
            return errors
        return self.call_chunks(chunks)

    def call_template(self, template):
        '''
        Enforce the states in a template
        '''
        high = self.compile_template(template)
        if high:
            return self.call_high(high)
        return high

    def call_template_str(self, template):
        '''
        Enforce the states in a template, pass the template as a string
        '''
        high = self.compile_template_str(template)
        if high:
            return self.call_high(high)
        return high

class HighState(object):
    '''
    Generate and execute the salt "High State". The High State is the compound
    state derived from a group of template files stored on the salt master or
    in a the local cache.
    '''
    def __init__(self, opts):
        self.client = salt.minion.FileClient(opts)
        self.opts = self.__gen_opts(opts)
        self.state = State(self.opts)
        self.matcher = salt.minion.Matcher(self.opts)

    def __gen_opts(self, opts):
        '''
        The options used by the High State object are derived from options on
        the minion and the master, or just the minion if the high state call is
        entirely local.
        '''
        # If the state is intended to be applied locally, then the local opts
        # should have all of the needed data, otherwise overwrite the local
        # data items with data from the master
        if opts.has_key('local_state'):
            if opts['local_state']:
                return opts
        mopts = self.client.master_opts()
        opts['renderer'] = mopts['renderer']
        if mopts['state_top'].startswith('salt://'):
            opts['state_top'] = mopts['state_top']
        elif mopts['state_top'].startswith('/'):
            opts['state_top'] = os.path.join('salt://', mopts['state_top'][1:])
        else:
            opts['state_top'] = os.path.join('salt://', mopts['state_top'])
        return opts

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        top = self.client.cache_file(self.opts['state_top'], 'base')
        return self.state.compile_template(top)

    def top_matches(self, top):
        '''
        Search through the top high data for matches and return the states that
        this minion needs to execute. 

        Returns:
        {'env': ['state1', 'state2', ...]}
        '''
        matches = {}
        for env, body in top.items():
            for match, data in body.items():
                if self.matcher.confirm_top(match, data):
                    if not matches.has_key(env):
                        matches[env] = []
                    for item in data:
                        if type(item) == type(str()):
                            matches[env].append(item)
        return matches

    def gather_states(self, matches):
        '''
        Gather the template files from the master
        '''
        group = []
        for env, states in matches.items():
            for sls in states:
                state = self.client.get_state(sls, env)
                if state:
                    group.append(state)
        return group

    def render_state(self, sls, env, mods):
        '''
        Render a state file and retrive all of the include states
        '''
        errors = []
        fn_ = self.client.get_state(sls, env)
        state = None
        try:
            state = self.state.compile_template(fn_)
        except Exception as exc:
            errors.append('Rendering SLS {0} failed, render error:\n{1}'.format(sls, exc))
        mods.add(sls)
        nstate = None
        if state:
            if not isinstance(state, dict):
                errors.append('SLS {0} does not render to a dictonary'.format(sls))
            else:
                if state.has_key('include'):
                    for sub_sls in state.pop('include'):
                        if not list(mods).count(sub_sls):
                            nstate, mods, err = self.render_state(sub_sls, env, mods)
                        if nstate:
                            state.update(nstate)
                        if err:
                            errors += err
                for name in state:
                    if not isinstance(state[name], dict):
                        errors.append('Name {0} in sls {1} is not a dictonary'.format(name, sls))
                        continue
                    if not state[name].has_key('__sls__'):
                        state[name]['__sls__'] = sls
        return state, mods, errors

    def render_highstate(self, matches):
        '''
        Gather the state files and render them into a single unified salt high
        data structure. 
        '''
        highstate = {}
        errors = []
        for env, states in matches.items():
            mods = set()
            for sls in states:
                state, mods, err = self.render_state(sls, env, mods)
                if state:
                    highstate.update(state)
                if err:
                    errors += err
        return highstate, errors

    def call_highstate(self):
        '''
        Run the sequence to execute the salt highstate for this minion
        '''
        top = self.get_top()
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)
        if errors:
            return errors
        return self.state.call_high(high)
