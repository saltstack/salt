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
import inspect
# Import Salt modules
import salt.loader

class State(object):
    '''
    Class used to execute salt states
    '''
    def __init__(self, opts):
        self.opts = opts
        self.states = salt.loader.states(opts)

    def verify_data(self, data):
        '''
        Verify the data, return an error statement if something is wrong
        '''
        errors = []
        if not data.has_key('state')\
                or not data.has_key('fun')\
                or not data.has_key('name'):
            return ret
        for fun in data['fun']:
            full = data['state'] + '.' + fun
            if not self.states.has_key(full):
                errors.append('Specified state ' + full + ' is unavailable.')
                continue
            aspec = inspect.getargspec(self.states[full])
            for ind in range(len(aspec[0]) - len(aspec[3])):
                if not data.has_key(aspec[0]):
                    errors.append('Missing paramater ' + aspec[0]\
                                + ' for state ' + full)
        return errors

    def format_call(self, data):
        '''
        Formats the data into a list of dicts used to acctually call the state,
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
        ret['full'] = data['state'] + '.' + fun
        ret['args'] = []
        aspec = inspect.getargspec(self.states[full])
        kwargs = {}
        for ind in range(len(aspec[0] - 1, 0, -1)):
            def_minus = len(aspec[0]) - ind
            if len(aspec[3]) - def_minus > -1:
                minus = def_minus + 1
                kwargs[aspec[0][ind]] = aspec[3][-minus]
        for arg in kwargs:
            if data.has_key(arg):
                kwargs[arg] = data['arg']
        for arg in aspec[0]:
            ret['args'].append(kwargs[arg])
        return data

    def call(self, data):
        '''
        Call a state
        '''
        ret = {'changes': None,
               'result': False,
               'comment': ''}
        errors = self.verify_data(data)
        if errors:
            for line in errors:
                ret['comment'] += line + '\n'
                sys.stderr.write(line + '\n')
            return ret
        cdata = self.format_call(data)
        return self.states[cdata['full']](*cdata['args'])
