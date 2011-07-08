'''
A simple way of setting the output format for data from modules
'''
import yaml
import pprint

# Conditionally import the json module
try:
    import json
    JSON = True
except ImportError:
    JSON = False

__all__ = ('get_outputter',)

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
