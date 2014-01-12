# -*- coding: utf-8 -*-
'''
Management of debconf selections
================================

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

.. note::
    Due to how PyYAML imports nested dicts (see :doc:`here
    </topics/troubleshooting/yaml_idiosyncrasies>`), the values in the ``data``
    dict must be indented four spaces instead of two.
'''


# Define the module's virtual name
__virtualname__ = 'debconf'


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    if __grains__['os_family'] != 'Debian':
        return False
    # Check that debconf was loaded
    if 'debconf.show' not in __salt__:
        return False

    return __virtualname__


def set_file(name, source, **kwargs):
    '''
    Set debconf selections from a file

    .. code-block:: yaml

        <state_id>:
          debconf.set_file:
            - source: salt://pathto/pkg.selections

        <state_id>:
          debconf.set_file:
            - source: salt://pathto/pkg.selections?saltenv=myenvironment

    source:
        The location of the file containing the package selections
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Debconf selections would have been set.'
        return ret

    if __salt__['debconf.set_file'](source, **kwargs):
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
         # For debconf data, valid booleans are 'true' and 'false';
         # But str()'ing the args['value'] will result in 'True' and 'False'
         # which will be ignored and overridden by a dpkg-reconfigure.

         # So we should manually set these values to lowercase ones,
         # before any str() call is performed.

        if args['type'] == 'boolean':
            args['value'] = 'true' if args['value'] else 'false'

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
                    if args['type'] == 'password':
                        ret['changes'][key] = '(password hidden)'
                    else:
                        ret['changes'][key] = ('{0}').format(args['value'])
                else:
                    ret['result'] = False
                    ret['comment'] = 'Some settings failed to be applied.'
                    ret['changes'][key] = 'Failed to set!'

    if not ret['changes']:
        ret['comment'] = 'All specified answers are already set'

    return ret
