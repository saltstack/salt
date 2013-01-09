'''
Management of debconf selections.
=================================

The debconfmod state module manages the enforcement of debconf selections,
this state can set those selections prior to package installation.

Available Functions
-------------------

The debconfmod state has two functions, the ``set`` and ``set_file`` functions

set
    Set debconf selections from the state itself

set_file
    Set debconf selections from a file

.. code-block:: yaml
    nullmailer-debconf:
      debconf.set:
        - name: nullmailer
        - data:
            'shared/mailname': {'type': 'string', 'value': 'server.domain.tld'}
            'nullmailer/relayhost': {'type': 'string', 'value': 'mail.domain.tld'}
    ferm-debconf:
      debconf.set:
        - name: ferm
        - data:
            'ferm/enable': {'type': 'boolean', 'value': True}
'''

from salt._compat import string_types

def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    if __grains__['os_family'] != 'Debian':
        return False

    return 'debconf'

def set_file(name, source):
    '''
    Set debconf selections from a file

    .. code-block:: yaml
        <state_id>:
          debconf.set_file:
            - source: salt://pathto/pkg.selections

    source:
        The location of the file containing the package selections
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Debconf selections were set.'
        return ret

    if __salt__['debconfmod.set_file'](source):
        ret['comment'] = 'Debconf selections were set.'
    else:
        ret['result'] = False
        ret['comment'] = 'Unable to set debconf selections from file.'

    return ret

def set(name, data):
    '''
    Set debconf selections

    .. code-block:: yaml
        <state_id>:
          debconf.set:
            - name: <name>
            - data:
                <question>: {'type': <type>, 'value': <value>}
                <question>: {'type': <type>, 'value': <value>}

        <state_id>:
          debconf.set:
            - name: <name>
            - data:
                <question>: {'type': <type>, 'value': <value>}
                <question>: {'type': <type>, 'value': <value>}

    name:
        The package name to set answers for.

    data:
        A set of questions/answers for debconf. Note that everything under
	this must be indented twice.

    question:
        The question the is being pre-answered

    type:
        The type of question that is being asked (string, boolean, select, etc.)

    value:
        The answer to the question
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    current = __salt__['debconf.show'](name)

    for (key, args) in data.iteritems():
        if current is not None and [key, args['type'], str(args['value'])] in current:
            if ret['comment'] is '':
                ret['comment'] = 'Unchanged answers: '
            ret['comment'] += ('{0} ').format(key)
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['changes'][key] = ('New value: {0}').format(args['value'])
            else:
                if __salt__['debconf.set'](name, key, args['type'], args['value']):
                    ret['changes'][key] = ('{0}').format(args['value'])
                else:
                    ret['result'] = False
                    ret['comment'] = 'Some settings failed to be applied.'
                    ret['changes'][key] = 'Failed to set!'

    if not ret['changes']:
        ret['comment'] = 'All specified answers are already set'

    return ret
