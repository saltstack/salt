'''
A simple way of setting the output format for data from modules
'''
# Import Python libs
import yaml
import pprint

# Conditionally import the json module
try:
    import json
    JSON = True
except ImportError:
    JSON = False

# Import Salt libs
import salt.utils

__all__ = ('get_outputter',)

def remove_colors():
    '''
    Acces all of the utility colors and change them to empy strings
    '''

class Outputter(object):
    '''
    Class for outputting data to the screen.
    '''
    supports = None

    @classmethod
    def check(klass, name):
       # Don't advertise Outputter classes for optional modules
       if hasattr(klass, "enabled") and not klass.enabled:
           return False
       return klass.supports == name

    def __call__(self, data, **kwargs):
        pprint.pprint(data)

class HighStateOutputter(Outputter):
    '''
    Not a command line option, the HighStateOutputter is only meant to be used
    with the state.highstate function, or a function that returns highstate
    return data
    '''
    supports = 'highstate'
    def __call__(self, data, **kwargs):
        colors = salt.utils.get_colors(kwargs.get('color'))
        for host in data:
            hcolor = colors['GREEN']
            hstrs = []
            for tname, ret in data[host].items():
                tcolor = colors['GREEN']
                if not ret['result']:
                    hcolor = colors['RED']
                    tcolor = colors['RED']
                comps = tname.split('.')
                hstrs.append('    {0}State: - {1}{2[ENDC]}'.format(
                    tcolor,
                    comps[0],
                    colors
                    ))
                hstrs.append('    {0}Name:      {1}{2[ENDC]}'.format(
                    tcolor,
                    comps[1],
                    colors
                    ))
                hstrs.append('    {0}Function:  {1}{2[ENDC]}'.format(
                    tcolor,
                    comps[2],
                    colors
                    ))
                hstrs.append('        {0}Result:    {1}{2[ENDC]}'.format(
                    tcolor,
                    str(ret['result']),
                    colors
                    ))
                hstrs.append('        {0}Comment:   {1}{2[ENDC]}'.format(
                    tcolor,
                    ret['comment'],
                    colors
                    ))
                hstrs.append('        {0}Changes:   {1}{2[ENDC]}'.format(
                    tcolor,
                    pprint.pformat(ret['changes']),
                    colors
                    ))
            print '{0}{1}:{2[ENDC]}'.format(
                hcolor,
                host,
                colors)
            for hstr in hstrs:
                print hstr
            

class RawOutputter(Outputter):
    '''
    Raw output. This calls repr() on the returned data.
    '''
    supports = "raw"
    def __call__(self, data, **kwargs):
        print data

class TxtOutputter(Outputter):
    '''
    Plain text output. Primarily for returning output from
    shell commands in the exact same way they would output
    on the shell when ran directly.
    '''
    supports = "txt"
    def __call__(self, data, **kwargs):
        if hasattr(data, "keys"):
            for key in data.keys():
                value = data[key]
                for line in value.split('\n'):
                    print "{0}: {1}".format(key, line)
        else:
            # For non-dictionary data, just use print
            RawOutputter()(data)

class JSONOutputter(Outputter):
    '''
    JSON output.
    '''
    supports = "json"
    enabled  = JSON

    def __call__(self, data, **kwargs):
        try:
            # A good kwarg might be: indent=4
            ret = json.dumps(data, **kwargs)
        except TypeError:
            # Return valid json for unserializable objects
            ret = json.dumps({})
        print ret

class YamlOutputter(Outputter):
    '''
    Yaml output. All of the cool kids are doing it.
    '''
    supports = "yaml"

    def __call__(self, data,  **kwargs):
        print yaml.dump(data, **kwargs)

def get_outputter(name=None):
    '''
    Factory function for returning the right output class.

    Usage:
        printout = get_outputter("txt")
        printout(ret)
    '''
    # Return an actual instance of the correct output class
    for i in Outputter.__subclasses__():
        if i.check(name):
            return i()
    return Outputter()
