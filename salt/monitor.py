#!/usr/bin/env python2

'''
The salt monitor daemon.

The monitor reads configuration from the 'monitor' entry in
/etc/salt/minion and loops forever running the configured commands at
a user specified interval.

An example configuration is:

    monitor:
      # run every 10 seconds
      - run: status.diskusage /
        every:
          second: 10
        foreach fs, stats:
          - if stats.available * 100 / stats.total > 90:
            - alert.send 'disk usage is above 90% on $fs'

      # run backups every Sunday at 3:27 AM
      - run: backup.backup
        at:
          weekday: sun
          hour: 3
          minute: 27

The configuration is expressed in YAML and must conform to this syntax:

    - run: <salt-command>

      id: <cmd-id>

      # execute command on an interval
      every:
        day:    <number>
        hour:   <number>
        minute: <number>
        second: <number>

      # execute command at precise date and time
      at:
        month:   <cronlist> # [1-12] or 'jan'-'dec' or 'january'-'december'
        day:     <cronlist> # [1-31]
        weekday: <cronlist> # [1-7] or 'mon'-'sun' or 'monday' - 'sunday'
        hour:    <cronlist> # [0-23]
        minute:  <cronlist> # [0-59]
        second:  <cronlist> # [0-59]

      # iterate over a sorted result dict; result, <key>, and <value>
      # are available within the foreach scope
      foreach <key>, <value>:
        # run commands unconditionally
        - <salt-command>

        # run commands for each item in the list or set result
        - foreach <value>:
          - <salt-commands>

        # run commands if condition is true
        - <condition>:
          - <salt-commands>

        # use if/elif/else logic to select commands to run
        - if <condition>:
          - <salt-commands>
        - elif <condition>:
          - <salt-commands>
        - else:
          - <salt-commands>

      # run command if condition is true; only 'result' is available
      if <condition>:
        - <salt-commands>

where:
    cmd-id = the command identifier used in error and log messages;
             defaults to 'monitor-#' where # is the command's position in
             /etc/salt/minion
    salt-command = a shell-like commands line of the command and arguments
    salt-commands = salt commands on separate lines and prefixed with '-'
    number = a integer or floating point number
    key = an arbitrary python identifier used when iterating over the
            dict returned by the salt command
    value = an arbitrary python identifier used when iterating over the
            dict returned by the salt command
    condition = a python expression with optional shell-like $var/${var}
                references.  The variables available include 'result'
                (the result returned from the salt command) and <key>
                and <value> selected by the user.
    cronlist = a list cron items, includes single value (1),
               range (1-3), range plus step (1-3/2), wildcard range (*),
               wildcard range plus step (*/2).  Months and weekdays can
               also be expressed with their locale's full name (monday) or
               abbreviation (mon); names are automatically lowercased.
               Use whitespace and/or commas to separate items.

The 'foreach' statement automatically sorts dicts and sets results.
If the <value> variable is a dict, foreach automatically wraps <value>
with an AttrDict that allows you to reference the dict contents as
object attributes.  For example, a wrapped value={'foo':1} allows you
to write value.foo or value['foo'].

You must use the shell-like $var and ${expr} references to pass
result, <key>, and <value> data to the salt commands.  For example,
if we had 'foreach k, v:' and wanted to pass the value in k, we'd
write '- mysaltcmd $v'.  If you're trying to pass an element of the
reference, you need to enclose everything in {}s, e.g. use ${v['stuff']}
or ${v.stuff}.  You can also include a python expression in the {}.
For example, ${(v.stuff/10)+100}.

Salt command arguments can be enclosed in single or double quotes
to preserve spaces.  For instance, saltcmd 'hi, world' "bob's stuff".

Caveat: since the config is expressed in YAML you cannot use ':' in
any salt argument or any expression.
'''

# Import python modules
import logging
import os
import re
import shlex
import threading
import time

# Import salt libs
import salt.config
import salt.cron
import salt.minion

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 10

def _indent(lines, num_spaces=4):
    '''
    Indent each line in an array of lines.

    >>> _indent(['a','b','c'], 2)
    ['  a', '  b', '  c']
    '''
    indent = ' ' * num_spaces
    result = []
    for line in lines:
        result.append(indent + line)
    return result

class MonitorCommand(object):
    '''
    A single monitor command.
    '''
    def __init__(self, cmdid, src, context, sleeper=None):
        self.cmdid   = cmdid
        self.code    = compile(src, '<monitor-config>', 'exec')
        self.sleeper = sleeper
        self.context = context

    def run(self):
        log.trace('start thread for %s', self.cmdid)
        if self.sleeper is None:
            exec self.code in self.context
        else:
            while True:
                exec self.code in self.context
                duration = self.sleeper.next()
                log.trace('%s: sleep %s seconds', self.cmdid, duration)
                time.sleep(duration)

class Monitor(salt.minion.SMinion):
    '''
    The monitor daemon.
    '''
    def __init__(self, opts):
        salt.minion.SMinion.__init__(self, opts)

        if 'monitor' in self.opts:
            self.commands = Loader(self.opts, self.functions).load()
        else:
            log.warning('monitor not configured in /etc/salt/minion')
            self.commands = []

    def start(self):
        log.debug('starting monitor with {} command{}'.format(
                   len(self.commands),
                   '' if len(self.commands) == 1 else 's'))
        if self.commands:
            for cmd in self.commands:
                threading.Thread(target=cmd.run).start()
        else:
            log.error('no monitor commands to run')

class Loader(object):
    '''
    Load the monitor commands from /etc/salt/minion.
    '''
    TOKEN_PATTERN = re.compile(
                r'''(  (?:\\\\)           # match escaped backslash
                     | (?:\\\$)           # match escaped dollar
                     | [{}]               # match braces
                     | (?:\$[A-Za-z_]\w*) # match simple $var
                     | (?:\$\{[^}]+\})    # match expr: ${var}, ${var['name']}
                    )''',
                re.VERBOSE)

    def __init__(self, config, functions):
        self.config    = config
        self.functions = functions
        self.context   = globals().copy()
        self.context['functions'] = self.functions

    def load(self):
        '''
        Load the monitor configuration.
        '''
        monitorcfg = self.config.get('monitor')
        self.functions = self.functions
        self.cron_parser = salt.cron.CronParser()
        self.default_interval = self.config.get('monitor.default_interval',
                                           {'seconds' : DEFAULT_INTERVAL_SECONDS})
        results = []
        for cmdnum, cmdconfig in enumerate(monitorcfg, 1):
            try:
                log.trace(cmdconfig)
                cmdid = cmdconfig.get('id', 'monitor-{}'.format(cmdnum))
                src = self._expand_command(cmdid, cmdconfig)
                sleeper = self._create_sleeper(cmdconfig)
                results.append(MonitorCommand(cmdid, src, self.context, sleeper))
                log.trace("generated command source:\n%s", src)
            except ValueError, ex:
                log.error( 'ignore monitor command #{} {!r}: {}'.format(
                                        cmdnum,
                                        cmdconfig.get('run', '<unknown>'),
                                        ex ) )
        return results

    def _create_sleeper(self, cmdconfig):
        '''
        Create an iterator that generates a sequence of sleep times
        until the next specified event.
        '''
        if 'every' in cmdconfig:
            sleep_type = 'interval'
            cron_dict = cmdconfig['every']
        elif 'at' in cmdconfig:
            sleep_type = 'cron'
            cron_dict = cmdconfig['at']
        else:
            sleep_type = 'interval'
            cron_dict = self.default_interval
        result = self.cron_parser.create_sleeper(sleep_type, cron_dict)
        return result

    def _expand_references(self, text, expand_to_string=False):
        '''
        Expand the $var, ${var}, and ${expression} references in a string.
        The implementation is a little tricky becasue we allow the user
        to escape dollar signs and backslashes with a backslash (e.g. \$, \\)
        and we need to invisibly escape the braces ({}) used by str.format().
        '''
        fmt = ''
        refs = []
        if len(text) > 1 and text[0] in '\'"' and text[0] == text[-1]:
            is_string = True
            text = text[1:-1]
        else:
            is_string = expand_to_string
        for matched in self.TOKEN_PATTERN.split(text):
            if len(matched) == 0:
                pass
            elif len(matched) > 1 and matched.startswith('$'):
                if matched.startswith('${') and matched.endswith('}'):
                    # handle ${var} reference
                    refs.append(matched[2:-1])
                else:
                    # handle $var reference
                    refs.append(matched[1:])
                fmt += '{}'
            else:
                # handle plain text
                fmt += matched.replace('\\$', '$') \
                              .replace('\\\\', '\\') \
                              .replace('{', '\1') \
                              .replace('}', '\2')

        if fmt == '{}' and len(refs) == 1:
            result = 'str({})'.format(refs[0]) if is_string else refs[0]
        elif len(refs) == 0:
            fmt = fmt.replace('\1', '{').replace('\2', '}')
            result = repr(fmt) if is_string else fmt
        else:
            fmt = fmt.replace('\1', '{{').replace('\2', '}}')
            result = repr(fmt) + '.format(' + ', '.join(refs) + ')' \
                        if is_string else fmt.format(*refs)
        return result

    def _expand_call(self, line):
        '''
        Translate one shell-like command line into a python function call.
        For example, "echo 'the key is $key'"
            becomes "functions['echo']('the key is {}'.format(key))"
        '''
        if isinstance(line, dict):
            raise ValueError('cannot use ":" in salt command line')
        lexer = shlex.shlex(line)
        lexer.whitespace_split = True
        cmd = []
        is_command_name = True
        try:
            for token in lexer:
                cmd.append(self._expand_references(token, not is_command_name))
                is_command_name = False
        except ValueError, ex:
            ex.args = (ex.args[0] + ', line: ' + line,)
            raise
        if len(cmd) == 0:
            raise ValueError('missing salt command, line: ' + line)
        cmdname, cmdargs = cmd[0], cmd[1:]
        if cmdname not in self.functions:
            raise ValueError('no such function: ' + cmdname)
        result = 'functions[\'{}\']({})'.format(cmdname, ', '.join(cmdargs))
        return result

    def _expand_conditional(self, condition, actions):
        '''
        Translate one if/elif/else dict into an array of python lines.
        '''
        condition = condition.strip().replace('\t', ' ')
        condition = self._expand_references(condition)
        if not condition.startswith(('if ', 'elif ', 'else')):
            condition = 'if ' + condition
        if not condition.endswith(':'):
            condition += ':'
        result = [condition]
        if actions:
            for action in actions:
                result.append('    ' + self._expand_call(action))
        else:
            result.append('    pass')
        return result

    def _expand_foreach(self, params, value):
        '''
        Translate one foreach dict into an array of python lines.
        There are two forms of foreach:
           - "foreach key, value" for dicts
           - "foreach value" for lists and sets
        The user selects the parameter names for key and value.
        For example, "foreach k, v:", "foreach key, value:", or
        "foreach filesystem, stats:".  The user can use either
        the python variable name (e.g. key or k) or the shell-ish name
        (e.g. $key, ${key}, $k, ${key}).
        '''
        names = [self._expand_references(param) for param in params]
        result = []
        if len(names) == 0:
            raise ValueError('foreach missing parameter(s)')
        elif len(names) == 1:
            # foreach over a list or set
            result += [
                'if isinstance(result, set):',
                '    result = sorted(result)',
                'for {} in result:'.format(*names),
                ]
        elif len(names) == 2:
            # foreach over a dict
            result += [
                'class AttrDict(dict):',
                '    __getattr__ = dict.__getitem__',
                'if not isinstance(result, dict):',
                '    raise ValueError(\'result is not a dict\')',
                'result = AttrDict(result)',
                'for {}, {} in sorted(result.iteritems()):'.format(*names),
                ]
        else:
            raise ValueError('foreach has too many paramters: {}'.format(
                               ', '.join(names)))
        vname = names[-1]
        result += ['    if isinstance({}, dict):'.format(vname),
                   '        {0} = AttrDict({0})'.format(vname)]
        for statement in value:
            if isinstance(statement, basestring):
                result.append('    ' + self._expand_call(statement))
            elif isinstance(statement, dict):
                condition, actions = statement.items()[0]
                result += _indent(self._expand_conditional(condition, actions))
        return result

    def _expand_command(self, cmdid, cmd_dict):
        '''
        Translate one command/response dict into an array of python lines.
        '''
        raw_cmd = cmd_dict['run']
        cmd = self._expand_call(raw_cmd)
        result = ['log.trace("{}: run: {}")'.format(cmdid, raw_cmd),
                  'result = ' + cmd,
                  'log.trace("{}: result: %s",result)'.format(cmdid)]
        for key, value in cmd_dict.iteritems():
            key = key.strip().replace('\t', ' ')
            if key.startswith('foreach '):
                params = key[8:].strip().replace(',', ' ').split()
                result += self._expand_foreach(params, value)
            elif key.startswith('if '):
                result += self._expand_conditional(key, value)
        return '\n'.join(result)
