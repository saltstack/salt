'''
The return data from the Highstate command is a standard data structure
which is parsed by the highstate outputter to deliver a clean and readable
set of information about the HighState run on minions.

Two configurations can be set to modify the highstate outputter. These values
can be set in the master config to change the output of the ``salt`` command or
set in the minion config to change the output of the ``salt-call`` command.

state_verbose:
    By default `state_verbose` is set to `True`, setting this to `False` will
    instruct the highstate outputter to omit displaying anything in green, this
    means that nothing with a result of True and no changes will not be printed
state_output:
    The highstate outputter has two output modes, `full` and `terse`. The
    default is set to full, which will display many lines of detailed
    information for each executed chunk. If the `state_output` option is
    set to `terse` then the output is greatly simplified and shown in only one
    line
'''

# Import python libs
import pprint

# Import salt libs
import salt.utils
from salt._compat import string_types


def output(data):
    '''
    The HighState Outputter is only meant to
    be used with the state.highstate function, or a function that returns
    highstate return data.
    '''
    colors = salt.utils.get_colors(__opts__.get('color'))
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
            if not __opts__.get('state_verbose', False):
                data[host] = _strip_clean(data[host])
            # Verify that the needed data is present
            for tname, info in data[host].items():
                if not '__run_num__' in info:
                    err = ('The State execution failed to record the order '
                           'in which all states were executed. The state '
                           'return missing data is:')
                    hstrs.insert(0, pprint.pformat(info))
                    hstrs.insert(0, err)
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
                if __opts__.get('state_output', 'full').lower() == 'terse':
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
        hstrs.insert(0, ('{0}{1}:{2[ENDC]}'.format(hcolor, host, colors)))
        return '\n'.join(hstrs)


def _strip_clean(returns):
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

