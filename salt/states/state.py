'''
This module is similar to the built-in cmd state module except that rather
than always resulting in a changed state, the state of a command or script
execution is determined by the command or the script itself.

This allows a state to watch for changes in another state that executes
a command or script.

This is done using a simple protocol similar to the one used by Ansible's
modules. Here's how it works:

If there's nothing in the stdout of the command, then assume no changes.
Otherwise, the stdout must be either in JSON or its `last` non-empty line
must be a string of key=value pairs delimited by spaces(no spaces on the
sides of '=').

If it's JSON then it must be a JSON object(ie, {}). 
If it's key=value pairs then quoting may be used to include spaces.
(Python's shlex module is used to parse the key=value string)

Two special keys or attributes are recognized in the output::

  changed: bool (ie, 'yes', 'no', 'true', 'false', case-insensitive)
  comment: str  (ie, any string)

So, only if 'changed' is true then assume the command execution has changed
the state, and any other key values or attributes in the output will be set
as part of the changes.

If there's a comment then it will be used as the comment of the state.

Here's an example of how one might write a shell script for use by this state
function::

  #!/bin/bash
  #
  echo "Working hard..."

  # writing the state line
  echo  # an empty line here so the next line will be the last.
  echo "changed=yes comment=\"something's changed!\" whatever=123"


And an example salt files using this module::

    Run myscript:
      state.run:
        - name: /path/to/myscript
        - cwd: /
    
    Run only if myscript changed something:
      cmd.wait:
        - name: echo hello
        - cwd: /
        - watch:
          - state: Run myscript


Note that instead of using `cmd.wait` in the example, `state.wait` can be
used, and in which case it can then be watched by some other states.
'''

# Import python libs
import json
import shlex
import copy
import logging

# Import Salt libs
import salt.state
log = logging.getLogger(__name__)


def run(name, **kws):
    return _reinterpreted_state(_delegate_to_state('cmd.run', name, **kws))


def script(name, **kws):
    return _reinterpreted_state(_delegate_to_state('cmd.script', name, **kws))


def wait(name, **kws):
    return _reinterpreted_state(_delegate_to_state('cmd.wait', name, **kws))


def wait_script(name, **kws):
    return _reinterpreted_state(_delegate_to_state('cmd.wait_script', name, **kws))


# basically just a copy & paste from the salt built-in cmd state module.
def mod_watch(name, **kwargs):
    '''
    Execute a cmd function based on a watch call
    '''
    if kwargs['sfun'] == 'wait' or kwargs['sfun'] == 'run':
        return run(name, **kwargs)
    elif kwargs['sfun'] == 'wait_script' or kwargs['sfun'] == 'script':
        return script(name, **kwargs)


def _delegate_to_state(func, name, **kws):
    '''
    Delegate execution to a state function with arguments(name+kws).
    '''

    # eg, _delegate_to_state("cmd.run", "echo hello", cwd="/")

    state_name, state_func = func.split('.', 1)

    # the following code fragment is copied and modified from salt's
    # modules.state.single()
    kws.update(dict(state=state_name, fun=state_func, name=name))
    opts = copy.copy(__opts__)
    st_ = salt.state.State(opts)
    err = st_.verify_data(kws)
    if err:
        log.error(str(err))
        raise Exception('Failed verifying state input!')
    return st_.call(kws)


def _reinterpreted_state(state):
    '''
    Re-interpret the state return by salt.sate.run using our protocol.
    '''
    ret = state['changes']
    state['changes'] = {}
    state['comment'] = ''

    out = ret.get('stdout')
    if not out:
        if ret.get('stderr'):
            state['comment'] = ret['stderr'] 
        return state

    is_json = False
    try:
        d = json.loads(out)
        if not isinstance(d, dict):
            return _failout(state,
                       'script JSON output must be a JSON object(ie, {})!')
        is_json = True
    except Exception:
        idx = out.rstrip().rfind('\n')
        if idx != -1:
            out = out[idx+1:]
        d = {}
        try:
            for item in shlex.split(out):
                k, v = item.split('=')
                d[k] = v
        except ValueError:
            return _failout(state,
                'Failed parsing script output! '
                'Stdout must be JSON or a line of name=value pairs.')

    changed = _is_true(d.get('changed', 'no'))
    
    if 'comment' in d:
        state['comment'] = d['comment']
        del d['comment']

    if changed:
        for k in ret:
            d.setdefault(k, ret[k])

        # if stdout is the state output in json, don't show it.
        # otherwise it contains the one line name=value pairs, strip it.
        d['stdout'] = '' if is_json else d.get('stdout', '')[:idx]
        state['changes'] = d

    #FIXME: if it's not changed but there's stdout and/or stderr then those
    #       won't be shown as the function output. (though, they will be shown
    #       inside INFO logs).
    return state        


def _failout(state, msg):
    state['comment'] = msg
    state['result'] = False
    return state


def _is_true(v):
    if v and str(v).lower() in ('true', 'yes', '1'):
        return True
    elif str(v).lower() in ('false', 'no', '0'):
        return False
    raise ValueError('Failed parsing boolean value: {0}'.format(v))


def _no_op(name, **kws):
    '''
    No-op state to support state config via the stateconf renderer.
    '''
    return dict(name=name, result=True, changes={}, comment='')

config = _no_op
