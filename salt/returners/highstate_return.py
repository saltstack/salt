# -*- coding: utf-8 -*-
'''
Return the results of a highstate (or any other state function that returns
data in a compatible format) via an HTML email or HTML file.

.. versionadded:: Nitrogen

Similar results can be achieved by using smtp returner with a custom template,
except an attempt at writing such a template for the complex data structure
returned by highstate function had proven to be a challenge, not to mention
that smtp module doesn't support sending HTML mail at the moment.

The main goal of this returner was producing an easy to read email similar
to the output of highstate outputter used by the CLI.

This returner could be very useful during scheduled executions,
but could also be useful for communicating the results of a manual execution.

Returner configuration is controlled in a standart fashion either via
highstate group or an alternatively named group.

.. code-block:: bash

    salt '*' state.highstate --return highstate

To use the alternative configuration, append '--return_config config-name'

.. code-block:: bash

    salt '*' state.highstate --return highstate --return_config simple

Here is an example of what configuration might look like:

.. code-block:: yaml

    simple.highstate:
      report_failures: True
      report_changes: True
      report_everything: False
      failure_function: pillar.items
      success_function: pillar.items
      report_format: html
      report_delivery: smtp
      smtp_success_subject: 'success minion {id} on host {host}'
      smtp_failure_subject: 'failure minion {id} on host {host}'
      smtp_server: smtp.example.com
      smtp_recipients: saltusers@example.com, devops@example.com
      smtp_sender: salt@example.com

The *report_failures*, *report_changes*, and *report_everything* flags provide
filtering of the results. If you want an email to be sent every time, then
*reprot_everything* is your choice. If you want to be notified only when
changes were successfully made use *report_changes*. And *report_failures* will
generate an email if there were failures.

The configuration allows you to run salt module function in case of
success (*success_function*) or failure (*failure_function*).

Any salt function, including ones defined in _module folder of your salt
repo could be used here. Their output will be displayed under the 'extra'
heading of the email.

Supported values for *report_format* are html, json, and yaml. The later two
are typically used for debugging purposes, but could be used for applying
a template at some later stage.

The values for *report_delivery* are smtp or file. In case of file delivery
the only other applicable option is *file_output*.

In case of smtp delivery, smtp_* options demonstrated by the example above
could be used to customize the email.

As you might have noticed success and failure subject contain {id} and {host}
values. Any other grain name could be used. As opposed to using
{{grains['id']}}, which will be rendered by the master and contain master's
values at the time of pillar generation, these will contain minion values at
the time of execution.

'''
from __future__ import absolute_import, print_function

import logging
import json
import smtplib
import cgi
from email.mime.text import MIMEText

import yaml
from salt.ext.six.moves import range
from salt.ext.six.moves import StringIO

import salt.returners

log = logging.getLogger(__name__)

__virtualname__ = 'highstate'


def __virtual__():
    '''
    Return our name
    '''
    return __virtualname__


def _get_options(ret):
    '''
    Return options
    '''
    attrs = {
        'report_everything': 'report_everything',
        'report_changes': 'report_changes',
        'report_failures': 'report_failures',
        'failure_function': 'failure_function',
        'success_function': 'success_function',
        'report_format': 'report_format',
        'report_delivery': 'report_delivery',
        'file_output': 'file_output',
        'smtp_sender': 'smtp_sender',
        'smtp_recipients': 'smtp_recipients',
        'smtp_failure_subject': 'smtp_failure_subject',
        'smtp_success_subject': 'smtp_success_subject',
        'smtp_server': 'smtp_server'
    }

    _options = salt.returners.get_returner_options(
        __virtualname__,
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__)

    return _options

#
# Most email readers to not support <style> tag.
# The following dict and a function provide a primitive styler
# sufficient for our needs.
#
_STYLES = {
    '_table': 'border-collapse:collapse;width:100%;',
    '_td': 'vertical-align:top;'
           'font-family:Helvetica,Arial,sans-serif;font-size:9pt;',
    'unchanged': 'color:blue;',
    'changed': 'color:green',
    'failed': 'color:red;',
    'first': 'border-top:0;border-left:1px solid #9e9e9e;',
    'first_first': 'border-top:0;border-left:0;',
    'notfirst_first': 'border-left:0;border-top:1px solid #9e9e9e;',
    'other': 'border-top:1px solid #9e9e9e;border-left:1px solid #9e9e9e;',
    'name': 'width:70pt;',
    'container': 'padding:0;'
}


def _lookup_style(element, names):
    '''
    Lookup style by either element name or the list of classes
    '''
    return _STYLES.get('_'+element, '') + \
        ''.join([_STYLES.get(name, '') for name in names])


def _generate_html_table(data, out, level=0, extra_style=''):
    '''
    Generate a single table of data
    '''
    print('<table style="{0}">'.format(
        _lookup_style('table', ['table' + str(level)])), file=out)

    firstone = True

    row_style = 'row' + str(level)
    cell_style = 'cell' + str(level)

    for subdata in data:
        first_style = 'first_first' if firstone else 'notfirst_first'
        second_style = 'first' if firstone else 'other'

        if isinstance(subdata, dict):
            if '__style__' in subdata:
                new_extra_style = subdata['__style__']
                del subdata['__style__']
            else:
                new_extra_style = extra_style
            if len(subdata) == 1:
                name = subdata.keys()[0]
                value = subdata.values()[0]
                print('<tr style="{0}">'.format(
                    _lookup_style('tr', [row_style])
                ), file=out)
                print('<td style="{0}">{1}</td>'.format(
                    _lookup_style(
                        'td',
                        [cell_style, first_style, 'name', new_extra_style]
                    ),
                    name
                ), file=out)
                if isinstance(value, list):
                    print('<td style="{0}">'.format(
                        _lookup_style(
                            'td',
                            [
                                cell_style,
                                second_style,
                                'container',
                                new_extra_style
                            ]
                        )
                    ), file=out)
                    _generate_html_table(
                        value,
                        out,
                        level + 1,
                        new_extra_style
                    )
                    print('</td>', file=out)
                else:
                    print('<td style="{0}">{1}</td>'.format(
                        _lookup_style(
                            'td',
                            [
                                cell_style,
                                second_style,
                                'value',
                                new_extra_style
                            ]
                        ),
                        cgi.escape(str(value))
                    ), file=out)
                print('</tr>', file=out)
        elif isinstance(subdata, list):
            print('<tr style="{0}">'.format(
                _lookup_style('tr', [row_style])
            ), file=out)
            print('<td style="{0}">'.format(
                _lookup_style(
                    'td',
                    [cell_style, first_style, 'container', extra_style]
                )
            ), file=out)
            _generate_html_table(subdata, out, level + 1, extra_style)
            print('</td>', file=out)
            print('</tr>', file=out)
        else:
            print('<tr style="{0}">'.format(
                _lookup_style('tr', [row_style])
            ), file=out)
            print('<td style="{0}">{1}</td>'.format(
                _lookup_style(
                    'td',
                    [cell_style, first_style, 'value', extra_style]
                ),
                cgi.escape(str(subdata))
            ), file=out)
            print('</tr>', file=out)
        firstone = False
    print('</table>', file=out)


def _generate_html(data, out):
    '''
    Generate report data as HTML
    '''
    print('<html>', file=out)
    print('<body>', file=out)
    _generate_html_table(data, out, 0)
    print('</body>', file=out)
    print('</html>', file=out)


def _dict_to_name_value(data):
    '''
    Convert a dictionary to a list of dictionaries to facilitate ordering
    '''
    if isinstance(data, dict):
        sorted_data = sorted(data.items(), key=lambda s: s[0])
        result = []
        for name, value in sorted_data:
            if isinstance(value, dict):
                result.append({name: _dict_to_name_value(value)})
            else:
                result.append({name: value})
    else:
        result = data
    return result


def _generate_states_report(sorted_data):
    '''
    Generate states report
    '''
    states = []
    for state, data in sorted_data:
        module, stateid, name, function = \
            [x.rstrip('_').lstrip('-') for x in state.split('|')]
        module_function = '.'.join((module, function))
        result = data.get('result', '')
        single = [
            {'function': module_function},
            {'name': name},
            {'result': result},
            {'duration': data.get('duration', 0.0)},
            {'comment': data.get('comment', '')}
        ]

        if not result:
            style = 'failed'
        else:
            changes = data.get('changes', {})
            if changes and isinstance(changes, dict):
                single.append({'changes': _dict_to_name_value(changes)})
                style = 'changed'
            else:
                style = 'unchanged'

        started = data.get('start_time', '')
        if started:
            single.append({'started': started})

        states.append({stateid: single, '__style__': style})
    return states


def _generate_report(ret, setup):
    '''
    Generate report dictionary
    '''

    retdata = ret.get('return', {})

    sorted_data = sorted(
        retdata.items(),
        key=lambda s: s[1].get('__run_num__', 0)
    )

    total = 0
    failed = 0
    changed = 0
    duration = 0.0

    # gather stats
    for _, data in sorted_data:
        if not data.get('result', True):
            failed += 1
        total += 1

        try:
            duration += float(data.get('duration', 0.0))
        except ValueError:
            pass

        if data.get('changes', {}):
            changed += 1

    unchanged = total - failed - changed

    log.debug('highstate total: {0}'.format(total))
    log.debug('highstate failed: {0}'.format(failed))
    log.debug('highstate unchanged: {0}'.format(unchanged))
    log.debug('highstate changed: {0}'.format(changed))

    # generate report if required
    if setup.get('report_everything', False) or \
       (setup.get('report_changes', True) and changed != 0) or \
       (setup.get('report_failures', True) and failed != 0):

        report = [
            {'stats': [
                {'total': total},
                {'failed': failed, '__style__': 'failed'},
                {'unchanged': unchanged, '__style__': 'unchanged'},
                {'changed': changed, '__style__': 'changed'},
                {'duration': duration}
            ]},
            {'job': [
                {'function': ret.get('fun', '')},
                {'arguments': ret.get('fun_args', '')},
                {'jid': ret.get('jid', '')},
                {'success': ret.get('success', True)},
                {'retcode': ret.get('retcode', 0)}
            ]},
            {'states': _generate_states_report(sorted_data)}
        ]

        if failed:
            function = setup.get('failure_function', None)
        else:
            function = setup.get('success_function', None)

        if function:
            func_result = __salt__[function]()
            report.insert(
                0,
                {'extra': [{function: _dict_to_name_value(func_result)}]}
            )

    else:
        report = []

    return report, failed


def _sprinkle(config_str):
    '''
    Sprinkle with grains of salt, that is
    convert 'test {id} test {host} ' types of strings
    '''
    parts = [x for sub in config_str.split('{') for x in sub.split('}')]
    for i in range(1, len(parts), 2):
        parts[i] = str(__grains__.get(parts[i], ''))
    return ''.join(parts)


def _produce_output(report, failed, setup):
    '''
    Produce output from the report dictionary generated by _generate_report
    '''
    report_format = setup.get('report_format', 'yaml')

    log.debug('highstate output format: {0}'.format(report_format))

    if report_format == 'json':
        report_text = json.dumps(report)
    elif report_format == 'yaml':
        string_file = StringIO()
        yaml.safe_dump(report, string_file, default_flow_style=False)
        string_file.seek(0)
        report_text = string_file.read()
    else:
        string_file = StringIO()
        _generate_html(report, string_file)
        string_file.seek(0)
        report_text = string_file.read()

    report_delivery = setup.get('report_delivery', 'file')

    log.debug('highstate report_delivery: {0}'.format(report_delivery))

    if report_delivery == 'file':
        output_file = _sprinkle(setup.get('file_output', '/tmp/test.rpt'))
        with open(output_file, 'w') as out:
            out.write(report_text)
    else:
        msg = MIMEText(report_text, report_format)

        sender = setup.get('smtp_sender', '')
        recipients = setup.get('smtp_recipients', '')

        if failed:
            subject = setup.get('smtp_failure_subject', 'Installation failure')
        else:
            subject = setup.get('smtp_success_subject', 'Installation success')

        subject = _sprinkle(subject)

        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipients

        smtp = smtplib.SMTP(host=setup.get('smtp_server', ''))
        smtp.sendmail(
            sender,
            [x.strip() for x in recipients.split(',')], msg.as_string())
        smtp.quit()


def returner(ret):
    '''
    Check highstate return information and possibly fire off an email
    or save a file.
    '''
    setup = _get_options(ret)

    log.debug('highstate setup {0}'.format(setup))

    report, failed = _generate_report(ret, setup)
    if report:
        _produce_output(report, failed, setup)


def __test_html():
    '''
    HTML generation test only used when called from the command line:
        python ./highstate.py
    Typical options for generating the report file:
    highstate:
        report_format: yaml
        report_delivery: file
        file_output: '/srv/salt/_returners/test.rpt'
    '''
    with open('test.rpt', 'r') as input_file:
        data_text = input_file.read()
    data = yaml.safe_load(data_text)

    string_file = StringIO()
    _generate_html(data, string_file)
    string_file.seek(0)
    result = string_file.read()

    with open('test.html', 'w') as output:
        output.write(result)


if __name__ == '__main__':
    __test_html()
