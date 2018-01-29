# -*- coding: utf-8 -*-
'''
Icinga2 state
=============

.. versionadded:: 2017.7.0

:depends:   - Icinga2 Python module
:configuration: See :py:mod:`salt.modules.icinga2` for setup instructions.

The icinga2 module is used to execute commands.
Its output may be stored in a file or in a grain.

.. code-block:: yaml

    command_id:
      icinga2.generate_ticket
        - name: domain.tld
        - output:  "/tmp/query_id.txt"
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os.path

# Import Salt libs
from salt.ext import six
import salt.utils.files
import salt.utils.stringutils


def __virtual__():
    '''
    Only load if the icinga2 module is available in __salt__
    '''
    return 'icinga2.generate_ticket' in __salt__


def generate_ticket(name, output=None, grain=None, key=None, overwrite=True):
    '''
    Generate an icinga2 ticket on the master.

    name
        The domain name for which this ticket will be generated

    output
        grain: output in a grain
        other: the file to store results
        None:  output to the result comment (default)

    grain:
        grain to store the output (need output=grain)

    key:
        the specified grain will be treated as a dictionary, the result
        of this state will be stored under the specified key.

    overwrite:
        The file or grain will be overwritten if it already exists (default)
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Checking if execution is needed.
    if output == 'grain':
        if grain and not key:
            if not overwrite and grain in __salt__['grains.ls']():
                ret['comment'] = 'No execution needed. Grain {0} already set'.format(grain)
                return ret
            elif __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Ticket generation would be executed, storing result in grain: {0}'.format(grain)
                return ret
        elif grain:
            if grain in __salt__['grains.ls']():
                grain_value = __salt__['grains.get'](grain)
            else:
                grain_value = {}
            if not overwrite and key in grain_value:
                ret['comment'] = 'No execution needed. Grain {0}:{1} already set'.format(grain, key)
                return ret
            elif __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Ticket generation would be executed, storing result in grain: {0}:{1}'.format(grain, key)
                return ret
        else:
            ret['result'] = False
            ret['comment'] = "Error: output type 'grain' needs the grain parameter\n"
            return ret
    elif output:
        if not overwrite and os.path.isfile(output):
            ret['comment'] = 'No execution needed. File {0} already set'.format(output)
            return ret
        elif __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Ticket generation would be executed, storing result in file: {0}'.format(output)
            return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Ticket generation would be executed, not storing result'
        return ret

    # Executing the command.
    ticket = __salt__['icinga2.generate_ticket'](name).strip()
    if ticket:
        ret['comment'] = six.text_type(ticket)

    if output == 'grain':
        if grain and not key:
            __salt__['grains.setval'](grain, ticket)
            ret['changes']['ticket'] = "Executed. Output into grain: {0}".format(grain)
        elif grain:
            if grain in __salt__['grains.ls']():
                grain_value = __salt__['grains.get'](grain)
            else:
                grain_value = {}
            grain_value[key] = ticket
            __salt__['grains.setval'](grain, grain_value)
            ret['changes']['ticket'] = "Executed. Output into grain: {0}:{1}".format(grain, key)
    elif output:
        ret['changes']['ticket'] = "Executed. Output into {0}".format(output)
        with salt.utils.files.fopen(output, 'w') as output_file:
            output_file.write(salt.utils.stringutils.to_str(ticket))
    else:
        ret['changes']['ticket'] = "Executed"

    return ret


def generate_cert(name):
    '''
    Generate an icinga2 certificate and key on the client.

    name
        The domain name for which this certificate and key will be generated
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    cert = "/etc/icinga2/pki/{0}.crt".format(name)
    key = "/etc/icinga2/pki/{0}.key".format(name)

    # Checking if execution is needed.
    if os.path.isfile(cert) and os.path.isfile(key):
        ret['comment'] = 'No execution needed. Cert: {0} and key: {1} already generated.'.format(cert, key)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Certificate and key generation would be executed'
        return ret

    # Executing the command.
    cert_save = __salt__['icinga2.generate_cert'](name)
    if not cert_save:
        ret['comment'] = "Certificate and key generated"
        ret['changes']['cert'] = "Executed. Certificate saved: {0}".format(cert)
        ret['changes']['key'] = "Executed. Key saved: {0}".format(key)
    return ret


def save_cert(name, master):
    '''
    Save the certificate on master icinga2 node.

    name
        The domain name for which this certificate will be saved

    master
        Icinga2 master node for which this certificate will be saved
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    cert = "/etc/icinga2/pki/trusted-master.crt"

    # Checking if execution is needed.
    if os.path.isfile(cert):
        ret['comment'] = 'No execution needed. Cert: {0} already saved.'.format(cert)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Certificate save for icinga2 master would be executed'
        return ret

    # Executing the command.
    cert_save = __salt__['icinga2.save_cert'](name, master)
    if not cert_save:
        ret['comment'] = "Certificate for icinga2 master saved"
        ret['changes']['cert'] = "Executed. Certificate saved: {0}".format(cert)
    return ret


def request_cert(name, master, ticket, port="5665"):
    '''
    Request CA certificate from master icinga2 node.

    name
        The domain name for which this certificate will be saved

    master
        Icinga2 master node for which this certificate will be saved

    ticket
        Authentication ticket generated on icinga2 master

    port
        Icinga2 port, defaults to 5665
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    cert = "/etc/icinga2/pki/ca.crt"

    # Checking if execution is needed.
    if os.path.isfile(cert):
        ret['comment'] = 'No execution needed. Cert: {0} already exists.'.format(cert)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Certificate request from icinga2 master would be executed'
        return ret

    # Executing the command.
    cert_request = __salt__['icinga2.request_cert'](name, master, ticket, port)
    if not cert_request:
        ret['comment'] = "Certificate request from icinga2 master executed"
        ret['changes']['cert'] = "Executed. Certificate requested: {0}".format(cert)
        return ret

    ret['comment'] = "FAILED. Certificate requested failed with exit code: {0}".format(cert_request)
    ret['result'] = False
    return ret


def node_setup(name, master, ticket):
    '''
    Setup the icinga2 node.

    name
        The domain name for which this certificate will be saved

    master
        Icinga2 master node for which this certificate will be saved

    ticket
        Authentication ticket generated on icinga2 master
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    cert = "/etc/icinga2/pki/{0}.crt.orig".format(name)
    key = "/etc/icinga2/pki/{0}.key.orig".format(name)

    # Checking if execution is needed.
    if os.path.isfile(cert) and os.path.isfile(cert):
        ret['comment'] = 'No execution needed. Node already configured.'
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Node setup will be executed.'
        return ret

    # Executing the command.
    node_setup = __salt__['icinga2.node_setup'](name, master, ticket)
    if not node_setup:
        ret['comment'] = "Node setup executed."
        ret['changes']['cert'] = "Node setup finished successfully."
        return ret

    ret['comment'] = "FAILED. Node setup failed with exit code: {0}".format(node_setup)
    ret['result'] = False
    return ret
