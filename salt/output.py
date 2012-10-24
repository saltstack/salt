'''
A simple way of setting the output format for data from modules
'''

# Import Python libs
import json
import pprint
import logging
import traceback

# Import third party libs
import yaml
try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
except Exception:
    pass

# Import Salt libs
import salt.utils
from salt._compat import string_types
from salt.exceptions import SaltException

__all__ = ('get_outputter', 'get_printout')

log = logging.getLogger(__name__)

def strip_clean(returns):
    '''
    Check for the state_verbose option and strip out the result=True
    and changes={} members of the state return list.
    '''
    rm_tags = []
    for tag in returns:
        if returns[tag]['result'] and not returns[tag]['changes']:
            rm_tags.append(tag)
    for tag in rm_tags:
        returns.pop(tag)
    return returns

def get_printout(ret, out, opts, indent=None):
    '''
    Return the proper printout
    '''
    if isinstance(ret, list) or isinstance(ret, dict):
        if opts['raw_out']:
            return get_outputter('raw')
        elif opts['json_out']:
            printout = get_outputter('json')
            if printout and indent is not None:
                printout.indent = indent
            return printout
        elif opts.get('text_out', False):
            return get_outputter('txt')
        elif opts['yaml_out']:
            return get_outputter('yaml')
        elif out is not None:
            return get_outputter(out)
        return None
    # Pretty print any salt exceptions
    elif isinstance(ret, SaltException):
        return get_outputter('txt')

def display_output(ret, out, opts):
    '''
    Display the output of a command in the terminal
    '''
    printout = get_printout(ret, out, opts)
    printout(ret, color=not bool(opts['no_color']), **opts)


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
    Not a command line option, the HighStateOutputter is only meant to
    be used with the state.highstate function, or a function that returns
    highstate return data
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
                # Strip out the result: True, without changes returns if
                # state_verbose is False
                if not kwargs.get('state_verbose', False):
                    data[host] = strip_clean(data[host])
                # Verify that the needed data is present
                for tname, info in data[host].items():
                    if not '__run_num__' in info:
                        err = ('The State execution failed to record the order '
                               'in which all states were executed. The state '
                               'return missing data is:')
                        print(err)
                        pprint.pprint(info)
                # Everything rendered as it should display the output
                for tname in sorted(
                        data[host],
                        key=lambda k: data[host][k].get('__run_num__', 0)):
                    ret = data[host][tname]
                    tcolor = colors['GREEN']
                    if ret['changes']:
                        tcolor = colors['CYAN']
                    if ret['result'] is False:
                        hcolor = colors['RED']
                        tcolor = colors['RED']
                    if ret['result'] is None:
                        hcolor = colors['YELLOW']
                        tcolor = colors['YELLOW']
                    comps = tname.split('_|-')
                    if kwargs.get('state_output', 'full').lower() == 'terse':
                        # Print this chunk in a terse way and continue in the
                        # loop
                        msg = (' {0}Name: {1} - Function: {2} - Result: {3}{4}'
                                ).format(
                                        tcolor,
                                        comps[2],
                                        comps[-1],
                                        str(ret['result']),
                                        colors['ENDC']
                                        )
                        hstrs.append(msg)
                        continue

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
                        if isinstance(ret['changes'][key], string_types):
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
            print(('{0}{1}:{2[ENDC]}'.format(hcolor, host, colors)))
            for hstr in hstrs:
                print(hstr)


class RawOutputter(Outputter):
    '''
    Raw output. This calls repr() on the returned data.
    '''
    supports = 'raw'

    def __call__(self, data, **kwargs):
        print(data)


class TxtOutputter(Outputter):
    '''
    Plain text output. Primarily for returning output from shell commands
    in the exact same way they would output on the shell when ran directly.
    '''
    supports = 'txt'

    def __call__(self, data, **kwargs):
        if hasattr(data, 'keys'):
            for key in data:
                value = data[key]
                # Don't blow up on non-strings
                try:
                    for line in value.split('\n'):
                        print('{0}: {1}'.format(key, line))
                except AttributeError:
                    print('{0}: {1}'.format(key, value))
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
            ret = json.dumps(data)
        except TypeError:
            log.debug(traceback.format_exc())
            # Return valid json for unserializable objects
            ret = json.dumps({})
        print(ret)


class YamlOutputter(Outputter):
    '''
    Yaml output. All of the cool kids are doing it.
    '''
    supports = 'yaml'

    def __call__(self, data, **kwargs):
        if 'color' in kwargs:
            kwargs.pop('color')
        print(yaml.dump(data))


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
