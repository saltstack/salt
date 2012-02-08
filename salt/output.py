'''
A simple way of setting the output format for data from modules
'''

import json
import pprint

import yaml
try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
except:
    pass

import salt.utils

__all__ = ('get_outputter',)


def remove_colors():
    '''
    Access all of the utility colors and change them to empty strings
    '''
    pass


class Outputter(object):
    '''
    Class for outputting data to the screen.
    '''
    supports = None

    @classmethod
    def check(cls, name):
        # Don't advertise Outputter classes for optional modules
        if hasattr(cls, 'enabled') and not cls.enabled:
            return False
        return cls.supports == name

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
            if isinstance(data[host], list):
                # Errors have been detected, list them in RED!
                hcolor = colors['RED_BOLD']
                hstrs.append(('    {0}Data failed to compile:{1[ENDC]}'
                              .format(hcolor, colors)))
                for err in data[host]:
                    hstrs.append(('{0}----------\n    {1}{2[ENDC]}'
                                  .format(hcolor, err, colors)))
            if isinstance(data[host], dict):
                # Everything rendered as it should display the output
                for tname, ret in data[host].items():
                    tcolor = colors['GREEN']
                    if ret['changes']:
                        tcolor = colors['CYAN']
                    if not ret['result']:
                        hcolor = colors['RED']
                        tcolor = colors['RED']
                    comps = tname.split('_|-')
                    hstrs.append(('{0}----------\n    State: - {1}{2[ENDC]}'
                                  .format(tcolor, comps[0], colors)))
                    hstrs.append('    {0}Name:      {1}{2[ENDC]}'.format(
                        tcolor,
                        comps[2],
                        colors
                        ))
                    hstrs.append('    {0}Function:  {1}{2[ENDC]}'.format(
                        tcolor,
                        comps[-1],
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
                    changes = '        Changes:   '
                    for key in ret['changes']:
                        if isinstance(ret['changes'][key], str):
                            changes += (key + ': ' + ret['changes'][key] +
                                        '\n                   ')
                        elif isinstance(ret['changes'][key], dict):
                            changes += (key + ': ' +
                                        pprint.pformat(ret['changes'][key]) +
                                        '\n                   ')
                        else:
                            changes += (key + ': ' +
                                        pprint.pformat(ret['changes'][key]) +
                                        '\n                   ')
                    hstrs.append(('{0}{1}{2[ENDC]}'
                                  .format(tcolor, changes, colors)))
            print('{0}{1}:{2[ENDC]}'.format(hcolor, host, colors))
            for hstr in hstrs:
                print hstr


class RawOutputter(Outputter):
    '''
    Raw output. This calls repr() on the returned data.
    '''
    supports = 'raw'

    def __call__(self, data, **kwargs):
        print data


class TxtOutputter(Outputter):
    '''
    Plain text output. Primarily for returning output from
    shell commands in the exact same way they would output
    on the shell when ran directly.
    '''
    supports = 'txt'

    def __call__(self, data, **kwargs):
        if hasattr(data, 'keys'):
            for key in data.keys():
                value = data[key]
                # Don't blow up on non-strings
                try:
                    for line in value.split('\n'):
                        print '{0}: {1}'.format(key, line)
                except AttributeError:
                    print '{0}: {1}'.format(key, value)
        else:
            # For non-dictionary data, just use print
            RawOutputter()(data)


class JSONOutputter(Outputter):
    '''
    JSON output.
    '''
    supports = 'json'

    def __call__(self, data, **kwargs):
        if hasattr(self, 'indent'):
            kwargs.update({'indent': self.indent})
        try:
            # A good kwarg might be: indent=4
            if 'color' in kwargs:
                kwargs.pop('color')
            ret = json.dumps(data, **kwargs)
        except TypeError:
            # Return valid json for unserializable objects
            ret = json.dumps({})
        print ret


class YamlOutputter(Outputter):
    '''
    Yaml output. All of the cool kids are doing it.
    '''
    supports = 'yaml'

    def __call__(self, data, **kwargs):
        if 'color' in kwargs:
            kwargs.pop('color')
        print yaml.dump(data, **kwargs)


def get_outputter(name=None):
    '''
    Factory function for returning the right output class.

    Usage:
        printout = get_outputter("txt")
        printout(ret)
    '''
    # Return an actual instance of the correct output class
    for i in Outputter.__subclasses__():  # FIXME: class Outputter has no
        if i.check(name):                 # __subclasses__ member
            return i()
    return Outputter()
