'''
The module used to execute states in salt. A state is unlike a module execution
in that instead of just executing a command it ensure that a certian state is
present on the system.

The data sent to the state calls is as follows:
    { 'state': '<state module name>',
      'fun': '<state function name>',
      'name': '<the name argument passed to all states>'
      'argn': '<arbitrairy argument, can have many of these>'
      }
'''
# Import python modules
import sys
import os
import copy
import inspect
# Import Salt modules
import salt.loader

class State(object):
    '''
    Class used to execute salt states
    '''
    def __init__(self, opts):
        if not opts.has_key('grains'):
            opts['grains'] = salt.loader.grains()
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
            errors.append('Specified state ' + full + ' is unavailable.')
        else:
            aspec = inspect.getargspec(self.states[full])
            arglen = 0
            deflen = 0
            if type(aspec[0]) == type(list()):
                arglen = len(aspec[0])
            if type(aspec[3]) == type(list()):
                arglen = len(aspec[3])
            for ind in range(arglen - deflen):
                if not data.has_key(aspec[0][ind]):
                    errors.append('Missing paramater ' + aspec[0][ind]\
                                + ' for state ' + full)
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
        Formats low data into a list of dicts used to acctually call the state,
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
        if type(aspec[3]) == type(list()):
            arglen = len(aspec[3])
        kwargs = {}
        for ind in range(arglen - 1, 0, -1):
            def_minus = arglen - ind
            if deflen - def_minus > -1:
                minus = def_minus + 1
                kwargs[aspec[0][ind]] = aspec[3][-minus]
        for arg in kwargs:
            if data.has_key(arg):
                kwargs[arg] = data['arg']
        for arg in aspec[0]:
            if kwargs.has_key(arg):
                ret['args'].append(kwargs[arg])
            else:
                ret['args'].append(data[arg])
        return ret

    def compile_high_data(self, high):
        '''
        "Compile" the high data as it is retireved from the cli or yaml into
        the individual state executor structures
        '''
        chunks = []
        for name, body in high.items():
            for state, run in body.items():
                chunk = {'state': state,
                         'name': name}
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
        return chunks

    def compile_template(self, template):
        '''
        Take the path to a template and return the high data structure derived from the
        template.
        '''
        if not os.path.isfile(template):
            return {}
        return self.rend[self.opts['renderer']](template)

    def compile_template_str(self, template):
        '''
        Take the path to a template and return the high data structure derived from the
        template.
        '''
        fn_ = tempfile.mkstemp()[1]
        open(fn_, 'w+').write(template)
        high = self.rend[self.opts['renderer']](fn_)
        os.remove(fn_)
        return high

    def call(self, data):
        '''
        Call a state directly with the low data structure, verify data before processing
        '''
        ret = {'changes': None,
               'result': False,
               'comment': ''}
        cdata = self.format_call(data)
        return self.states[cdata['full']](*cdata['args'])

    def call_high(self, high):
        '''
        Process a high data call and ensure the defined states.
        '''
        err = []
        rets = []
        chunks = self.compile_high_data(high)
        errors = self.verify_chunks(chunks)
        if errors:
            for err in errors:
                sys.stderr.write(err + '\n')
                sys.exit(2)
        for chunk in chunks:
            ret = self.call(chunk)
            print ret
            rets.append(ret)
        return rets

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
