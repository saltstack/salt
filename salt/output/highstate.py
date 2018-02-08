# -*- coding: utf-8 -*-
'''
Outputter for displaying results of state runs
==============================================

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
    The highstate outputter has six output modes,
    ``full``, ``terse``, ``mixed``, ``changes`` and ``filter``
    * The default is set to ``full``, which will display many lines of detailed
      information for each executed chunk.
    * If ``terse`` is used, then the output is greatly simplified and shown in
      only one line.
    * If ``mixed`` is used, then terse output will be used unless a state
      failed, in which case full output will be used.
    * If ``changes`` is used, then terse output will be used if there was no
      error and no changes, otherwise full output will be used.
    * If ``filter`` is used, then either or both of two different filters can be
      used: ``exclude`` or ``terse``.
        * for ``exclude``, state.highstate expects a list of states to be excluded (or ``None``)
          followed by ``True`` for terse output or ``False`` for regular output.
          Because of parsing nuances, if only one of these is used, it must still
          contain a comma. For instance: `exclude=True,`.
        * for ``terse``, state.highstate expects simply ``True`` or ``False``.
      These can be set as such from the command line, or in the Salt config as
      `state_output_exclude` or `state_output_terse`, respectively.
    The output modes have one modifier:
    ``full_id``, ``terse_id``, ``mixed_id``, ``changes_id`` and ``filter_id``
    If ``_id`` is used, then the corresponding form will be used, but the value for ``name``
    will be drawn from the state ID. This is useful for cases where the name
    value might be very long and hard to read.
state_tabular:
    If `state_output` uses the terse output, set this to `True` for an aligned
    output format.  If you wish to use a custom format, this can be set to a
    string.

Example usage:

If ``state_output: filter`` is set in the configuration file:

.. code-block:: bash

    salt '*' state.highstate exclude=None,True


means to exclude no states from the highstate and turn on terse output.

.. code-block:: bash

    salt twd state.highstate exclude=problemstate1,problemstate2,False


means to exclude states ``problemstate1`` and ``problemstate2``
from the highstate, and use regular output.

Example output for the above highstate call when ``top.sls`` defines only
one other state to apply to minion ``twd``:

.. code-block:: text

    twd:

    Summary for twd
    ------------
    Succeeded: 1 (changed=1)
    Failed:    0
    ------------
    Total states run:     1


Example output with no special settings in configuration files:

.. code-block:: text

    myminion:
    ----------
              ID: test.ping
        Function: module.run
          Result: True
         Comment: Module function test.ping executed
         Changes:
                  ----------
                  ret:
                      True

    Summary for myminion
    ------------
    Succeeded: 1
    Failed:    0
    ------------
    Total:     0
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import pprint
import textwrap

# Import salt libs
import salt.utils.color
import salt.utils.data
import salt.utils.stringutils
import salt.output

# Import 3rd-party libs
from salt.ext import six

import logging

log = logging.getLogger(__name__)


def output(data, **kwargs):  # pylint: disable=unused-argument
    '''
    The HighState Outputter is only meant to be used with the state.highstate
    function, or a function that returns highstate return data.
    '''
    # Discard retcode in dictionary as present in orchestrate data
    local_masters = [key for key in data.keys() if key.endswith('.local_master')]
    orchestrator_output = 'retcode' in data.keys() and len(local_masters) == 1

    if orchestrator_output:
        del data['retcode']

    # If additional information is passed through via the "data" dictionary to
    # the highstate outputter, such as "outputter" or "retcode", discard it.
    # We only want the state data that was passed through, if it is wrapped up
    # in the "data" key, as the orchestrate runner does. See Issue #31330,
    # pull request #27838, and pull request #27175 for more information.
    if 'data' in data:
        data = data.pop('data')

    ret = [
        _format_host(host, hostdata)[0]
        for host, hostdata in six.iteritems(data)
    ]
    if ret:
        return "\n".join(ret)
    log.error(
        'Data passed to highstate outputter is not a valid highstate return: %s',
        data
    )
    # We should not reach here, but if we do return empty string
    return ''


def _format_host(host, data):
    host = salt.utils.data.decode(host)

    colors = salt.utils.color.get_colors(
            __opts__.get('color'),
            __opts__.get('color_theme'))
    tabular = __opts__.get('state_tabular', False)
    rcounts = {}
    rdurations = []
    hcolor = colors['GREEN']
    hstrs = []
    nchanges = 0
    strip_colors = __opts__.get('strip_colors', True)

    if isinstance(data, int) or isinstance(data, six.string_types):
        # Data in this format is from saltmod.function,
        # so it is always a 'change'
        nchanges = 1
        hstrs.append(('{0}    {1}{2[ENDC]}'
                      .format(hcolor, data, colors)))
        hcolor = colors['CYAN']  # Print the minion name in cyan
    if isinstance(data, list):
        # Errors have been detected, list them in RED!
        hcolor = colors['LIGHT_RED']
        hstrs.append(('    {0}Data failed to compile:{1[ENDC]}'
                      .format(hcolor, colors)))
        for err in data:
            if strip_colors:
                err = salt.output.strip_esc_sequence(
                    salt.utils.data.decode(err)
                )
            hstrs.append(('{0}----------\n    {1}{2[ENDC]}'
                          .format(hcolor, err, colors)))
    if isinstance(data, dict):
        # Verify that the needed data is present
        data_tmp = {}
        for tname, info in six.iteritems(data):
            if isinstance(info, dict) and tname is not 'changes' and info and '__run_num__' not in info:
                err = ('The State execution failed to record the order '
                       'in which all states were executed. The state '
                       'return missing data is:')
                hstrs.insert(0, pprint.pformat(info))
                hstrs.insert(0, err)
            if isinstance(info, dict) and 'result' in info:
                data_tmp[tname] = info
        data = data_tmp
        # Everything rendered as it should display the output
        for tname in sorted(
                data,
                key=lambda k: data[k].get('__run_num__', 0)):
            ret = data[tname]
            # Increment result counts
            rcounts.setdefault(ret['result'], 0)
            rcounts[ret['result']] += 1
            rduration = ret.get('duration', 0)
            try:
                rdurations.append(float(rduration))
            except ValueError:
                rduration, _, _ = rduration.partition(' ms')
                try:
                    rdurations.append(float(rduration))
                except ValueError:
                    log.error('Cannot parse a float from duration {0}'
                              .format(ret.get('duration', 0)))

            tcolor = colors['GREEN']
            orchestration = ret.get('__orchestration__', False)
            schanged, ctext = _format_changes(ret['changes'], orchestration)
            if not ctext and 'pchanges' in ret:
                schanged, ctext = _format_changes(ret['pchanges'], orchestration)
            nchanges += 1 if schanged else 0

            # Skip this state if it was successful & diff output was requested
            if __opts__.get('state_output_diff', False) and \
               ret['result'] and not schanged:
                continue

            # Skip this state if state_verbose is False, the result is True and
            # there were no changes made
            if not __opts__.get('state_verbose', False) and \
               ret['result'] and not schanged:
                continue

            if schanged:
                tcolor = colors['CYAN']
            if ret['result'] is False:
                hcolor = colors['RED']
                tcolor = colors['RED']
            if ret['result'] is None:
                hcolor = colors['LIGHT_YELLOW']
                tcolor = colors['LIGHT_YELLOW']

            state_output = __opts__.get('state_output', 'full').lower()
            comps = tname.split('_|-')

            if state_output.endswith('_id'):
                # Swap in the ID for the name. Refs #35137
                comps[2] = comps[1]

            if state_output.startswith('filter'):
                # By default, full data is shown for all types. However, return
                # data may be excluded by setting state_output_exclude to a
                # comma-separated list of True, False or None, or including the
                # same list with the exclude option on the command line. For
                # now, this option must include a comma. For example:
                #     exclude=True,
                # The same functionality is also available for making return
                # data terse, instead of excluding it.
                cliargs = __opts__.get('arg', [])
                clikwargs = {}
                for item in cliargs:
                    if isinstance(item, dict) and '__kwarg__' in item:
                        clikwargs = item.copy()

                exclude = clikwargs.get(
                    'exclude', __opts__.get('state_output_exclude', [])
                )
                if isinstance(exclude, six.string_types):
                    exclude = six.text_type(exclude).split(',')

                terse = clikwargs.get(
                    'terse', __opts__.get('state_output_terse', [])
                )
                if isinstance(terse, six.string_types):
                    terse = six.text_type(terse).split(',')

                if six.text_type(ret['result']) in terse:
                    msg = _format_terse(tcolor, comps, ret, colors, tabular)
                    hstrs.append(msg)
                    continue
                if six.text_type(ret['result']) in exclude:
                    continue

            elif any((
                state_output.startswith('terse'),
                state_output.startswith('mixed') and ret['result'] is not False,  # only non-error'd
                state_output.startswith('changes') and ret['result'] and not schanged  # non-error'd non-changed
            )):
                # Print this chunk in a terse way and continue in the loop
                msg = _format_terse(tcolor, comps, ret, colors, tabular)
                hstrs.append(msg)
                continue

            state_lines = [
                '{tcolor}----------{colors[ENDC]}',
                '    {tcolor}      ID: {comps[1]}{colors[ENDC]}',
                '    {tcolor}Function: {comps[0]}.{comps[3]}{colors[ENDC]}',
                '    {tcolor}  Result: {ret[result]!s}{colors[ENDC]}',
                '    {tcolor} Comment: {comment}{colors[ENDC]}',
            ]
            if __opts__.get('state_output_profile', True) and 'start_time' in ret:
                state_lines.extend([
                    '    {tcolor} Started: {ret[start_time]!s}{colors[ENDC]}',
                    '    {tcolor}Duration: {ret[duration]!s}{colors[ENDC]}',
                ])
            # This isn't the prettiest way of doing this, but it's readable.
            if comps[1] != comps[2]:
                state_lines.insert(
                    3, '    {tcolor}    Name: {comps[2]}{colors[ENDC]}')
            # be sure that ret['comment'] is utf-8 friendly
            try:
                if not isinstance(ret['comment'], six.text_type):
                    ret['comment'] = six.text_type(ret['comment'])
            except UnicodeDecodeError:
                # If we got here, we're on Python 2 and ret['comment'] somehow
                # contained a str type with unicode content.
                ret['comment'] = salt.utils.stringutils.to_unicode(ret['comment'])
            try:
                comment = salt.utils.data.decode(ret['comment'])
                comment = comment.strip().replace(
                        '\n',
                        '\n' + ' ' * 14)
            except AttributeError:  # Assume comment is a list
                try:
                    comment = ret['comment'].join(' ').replace(
                        '\n',
                        '\n' + ' ' * 13)
                except AttributeError:
                    # Comment isn't a list either, just convert to string
                    comment = six.text_type(ret['comment'])
                    comment = comment.strip().replace(
                        '\n',
                        '\n' + ' ' * 14)
            # If there is a data attribute, append it to the comment
            if 'data' in ret:
                if isinstance(ret['data'], list):
                    for item in ret['data']:
                        comment = '{0} {1}'.format(comment, item)
                elif isinstance(ret['data'], dict):
                    for key, value in ret['data'].items():
                        comment = '{0}\n\t\t{1}: {2}'.format(comment, key, value)
                else:
                    comment = '{0} {1}'.format(comment, ret['data'])
            for detail in ['start_time', 'duration']:
                ret.setdefault(detail, '')
            if ret['duration'] != '':
                ret['duration'] = '{0} ms'.format(ret['duration'])
            svars = {
                'tcolor': tcolor,
                'comps': comps,
                'ret': ret,
                'comment': salt.utils.data.decode(comment),
                # This nukes any trailing \n and indents the others.
                'colors': colors
            }
            hstrs.extend([sline.format(**svars) for sline in state_lines])
            changes = '     Changes:   ' + ctext
            hstrs.append(('{0}{1}{2[ENDC]}'
                          .format(tcolor, changes, colors)))

            if 'warnings' in ret:
                rcounts.setdefault('warnings', 0)
                rcounts['warnings'] += 1
                wrapper = textwrap.TextWrapper(
                    width=80,
                    initial_indent=' ' * 14,
                    subsequent_indent=' ' * 14
                )
                hstrs.append(
                    '   {colors[LIGHT_RED]} Warnings: {0}{colors[ENDC]}'.format(
                        wrapper.fill('\n'.join(ret['warnings'])).lstrip(),
                        colors=colors
                    )
                )

        # Append result counts to end of output
        colorfmt = '{0}{1}{2[ENDC]}'
        rlabel = {True: 'Succeeded', False: 'Failed', None: 'Not Run', 'warnings': 'Warnings'}
        count_max_len = max([len(six.text_type(x)) for x in six.itervalues(rcounts)] or [0])
        label_max_len = max([len(x) for x in six.itervalues(rlabel)] or [0])
        line_max_len = label_max_len + count_max_len + 2  # +2 for ': '
        hstrs.append(
            colorfmt.format(
                colors['CYAN'],
                '\nSummary for {0}\n{1}'.format(host, '-' * line_max_len),
                colors
            )
        )

        def _counts(label, count):
            return '{0}: {1:>{2}}'.format(
                label,
                count,
                line_max_len - (len(label) + 2)
            )

        # Successful states
        changestats = []
        if None in rcounts and rcounts.get(None, 0) > 0:
            # test=True states
            changestats.append(
                colorfmt.format(
                    colors['LIGHT_YELLOW'],
                    'unchanged={0}'.format(rcounts.get(None, 0)),
                    colors
                )
            )
        if nchanges > 0:
            changestats.append(
                colorfmt.format(
                    colors['GREEN'],
                    'changed={0}'.format(nchanges),
                    colors
                )
            )
        if changestats:
            changestats = ' ({0})'.format(', '.join(changestats))
        else:
            changestats = ''
        hstrs.append(
            colorfmt.format(
                colors['GREEN'],
                _counts(
                    rlabel[True],
                    rcounts.get(True, 0) + rcounts.get(None, 0)
                ),
                colors
            ) + changestats
        )

        # Failed states
        num_failed = rcounts.get(False, 0)
        hstrs.append(
            colorfmt.format(
                colors['RED'] if num_failed else colors['CYAN'],
                _counts(rlabel[False], num_failed),
                colors
            )
        )

        num_warnings = rcounts.get('warnings', 0)
        if num_warnings:
            hstrs.append(
                colorfmt.format(
                    colors['LIGHT_RED'],
                    _counts(rlabel['warnings'], num_warnings),
                    colors
                )
            )
        totals = '{0}\nTotal states run: {1:>{2}}'.format('-' * line_max_len,
                                               sum(six.itervalues(rcounts)) - rcounts.get('warnings', 0),
                                               line_max_len - 7)
        hstrs.append(colorfmt.format(colors['CYAN'], totals, colors))

        if __opts__.get('state_output_profile', True):
            sum_duration = sum(rdurations)
            duration_unit = 'ms'
            # convert to seconds if duration is 1000ms or more
            if sum_duration > 999:
                sum_duration /= 1000
                duration_unit = 's'
            total_duration = 'Total run time: {0} {1}'.format(
                '{0:.3f}'.format(sum_duration).rjust(line_max_len - 5),
                duration_unit)
            hstrs.append(colorfmt.format(colors['CYAN'], total_duration, colors))

    if strip_colors:
        host = salt.output.strip_esc_sequence(host)
    hstrs.insert(0, ('{0}{1}:{2[ENDC]}'.format(hcolor, host, colors)))
    return '\n'.join(hstrs), nchanges > 0


def _nested_changes(changes):
    '''
    Print the changes data using the nested outputter
    '''
    ret = '\n'
    ret += salt.output.out_format(
            changes,
            'nested',
            __opts__,
            nested_indent=14)
    return ret


def _format_changes(changes, orchestration=False):
    '''
    Format the changes dict based on what the data is
    '''
    if not changes:
        return False, ''

    if orchestration:
        return True, _nested_changes(changes)

    if not isinstance(changes, dict):
        return True, 'Invalid Changes data: {0}'.format(changes)

    ret = changes.get('ret')
    if ret is not None and changes.get('out') == 'highstate':
        ctext = ''
        changed = False
        for host, hostdata in six.iteritems(ret):
            s, c = _format_host(host, hostdata)
            ctext += '\n' + '\n'.join((' ' * 14 + l) for l in s.splitlines())
            changed = changed or c
    else:
        changed = True
        ctext = _nested_changes(changes)
    return changed, ctext


def _format_terse(tcolor, comps, ret, colors, tabular):
    '''
    Terse formatting of a message.
    '''
    result = 'Clean'
    if ret['changes']:
        result = 'Changed'
    if ret['result'] is False:
        result = 'Failed'
    elif ret['result'] is None:
        result = 'Differs'
    if tabular is True:
        fmt_string = ''
        if 'warnings' in ret:
            fmt_string += '{c[LIGHT_RED]}Warnings:\n{w}{c[ENDC]}\n'.format(
                c=colors, w='\n'.join(ret['warnings'])
            )
        fmt_string += '{0}'
        if __opts__.get('state_output_profile', True) and 'start_time' in ret:
            fmt_string += '{6[start_time]!s} [{6[duration]!s:>7} ms] '
        fmt_string += '{2:>10}.{3:<10} {4:7}   Name: {1}{5}'
    elif isinstance(tabular, six.string_types):
        fmt_string = tabular
    else:
        fmt_string = ''
        if 'warnings' in ret:
            fmt_string += '{c[LIGHT_RED]}Warnings:\n{w}{c[ENDC]}'.format(
                c=colors, w='\n'.join(ret['warnings'])
            )
        fmt_string += ' {0} Name: {1} - Function: {2}.{3} - Result: {4}'
        if __opts__.get('state_output_profile', True) and 'start_time' in ret:
            fmt_string += ' Started: - {6[start_time]!s} Duration: {6[duration]!s} ms'
        fmt_string += '{5}'

    msg = fmt_string.format(tcolor,
                            comps[2],
                            comps[0],
                            comps[-1],
                            result,
                            colors['ENDC'],
                            ret)
    return msg
