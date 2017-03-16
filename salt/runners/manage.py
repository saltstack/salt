# -*- coding: utf-8 -*-
'''
General management functions for salt, tools like seeing what hosts are up
and what hosts are down
'''

# Import python libs
from __future__ import absolute_import, print_function
import os
import operator
import re
import subprocess
import tempfile
import time
import logging
import uuid

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves.urllib.request import urlopen as _urlopen  # pylint: disable=no-name-in-module,import-error

# Import salt libs
import salt.key
import salt.utils
import salt.utils.minions
import salt.client
import salt.client.ssh
import salt.wheel
import salt.version
from salt.utils.event import tagify
from salt.exceptions import SaltClientError, SaltSystemExit
FINGERPRINT_REGEX = re.compile(r'^([a-f0-9]{2}:){15}([a-f0-9]{2})$')

log = logging.getLogger(__name__)


def _ping(tgt, expr_form, timeout, gather_job_timeout):
    client = salt.client.get_local_client(__opts__['conf_file'])
    pub_data = client.run_job(tgt, 'test.ping', (), expr_form, '', timeout, '')

    if not pub_data:
        return pub_data

    returned = set()
    for fn_ret in client.get_cli_event_returns(
            pub_data['jid'],
            pub_data['minions'],
            client._get_timeout(timeout),
            tgt,
            expr_form,
            gather_job_timeout=gather_job_timeout):

        if fn_ret:
            for mid, _ in six.iteritems(fn_ret):
                returned.add(mid)

    not_returned = set(pub_data['minions']) - returned

    return list(returned), list(not_returned)


def status(output=True, tgt='*', expr_form='glob', timeout=None, gather_job_timeout=None):
    '''
    Print the status of all known salt minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.status
        salt-run manage.status timeout=5 gather_job_timeout=10
        salt-run manage.status tgt="webservers" expr_form="nodegroup"
    '''
    ret = {}

    if not timeout:
        timeout = __opts__['timeout']
    if not gather_job_timeout:
        gather_job_timeout = __opts__['gather_job_timeout']

    ret['up'], ret['down'] = _ping(tgt, expr_form, timeout, gather_job_timeout)
    return ret


def key_regen():
    '''
    This routine is used to regenerate all keys in an environment. This is
    invasive! ALL KEYS IN THE SALT ENVIRONMENT WILL BE REGENERATED!!

    The key_regen routine sends a command out to minions to revoke the master
    key and remove all minion keys, it then removes all keys from the master
    and prompts the user to restart the master. The minions will all reconnect
    and keys will be placed in pending.

    After the master is restarted and minion keys are in the pending directory
    execute a salt-key -A command to accept the regenerated minion keys.

    The master *must* be restarted within 60 seconds of running this command or
    the minions will think there is something wrong with the keys and abort.

    Only Execute this runner after upgrading minions and master to 0.15.1 or
    higher!

    CLI Example:

    .. code-block:: bash

        salt-run manage.key_regen
    '''
    client = salt.client.get_local_client(__opts__['conf_file'])
    try:
        client.cmd('*', 'saltutil.regen_keys')
    except SaltClientError as client_error:
        print(client_error)
        return False

    for root, _, files in os.walk(__opts__['pki_dir']):
        for fn_ in files:
            path = os.path.join(root, fn_)
            try:
                os.remove(path)
            except os.error:
                pass
    msg = ('The minion and master keys have been deleted.  Restart the Salt\n'
           'Master within the next 60 seconds!!!\n\n'
           'Wait for the minions to reconnect.  Once the minions reconnect\n'
           'the new keys will appear in pending and will need to be re-\n'
           'accepted by running:\n'
           '    salt-key -A\n\n'
           'Be advised that minions not currently connected to the master\n'
           'will not be able to reconnect and may require manual\n'
           'regeneration via a local call to\n'
           '    salt-call saltutil.regen_keys')
    return msg


def down(removekeys=False, tgt='*', expr_form='glob'):
    '''
    Print a list of all the down or unresponsive salt minions
    Optionally remove keys of down minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.down
        salt-run manage.down removekeys=True
        salt-run manage.down tgt="webservers" expr_form="nodegroup"

    '''
    ret = status(output=False, tgt=tgt, expr_form=expr_form).get('down', [])
    for minion in ret:
        if removekeys:
            wheel = salt.wheel.Wheel(__opts__)
            wheel.call_func('key.delete', match=minion)
    return ret


def up(tgt='*', expr_form='glob', timeout=None, gather_job_timeout=None):  # pylint: disable=C0103
    '''
    Print a list of all of the minions that are up

    CLI Example:

    .. code-block:: bash

        salt-run manage.up
        salt-run manage.up timeout=5 gather_job_timeout=10
        salt-run manage.up tgt="webservers" expr_form="nodegroup"
    '''
    ret = status(
        output=False,
        tgt=tgt,
        expr_form=expr_form,
        timeout=timeout,
        gather_job_timeout=gather_job_timeout
    ).get('up', [])
    return ret


def list_state(subset=None, show_ipv4=False, state=None):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    state : 'available'
        Show minions being in specific state that is one of 'available', 'joined',
        'allowed', 'alived' or 'reaped'.

    CLI Example:

    .. code-block:: bash

        salt-run manage.list_state
    '''
    conf_file = __opts__['conf_file']
    opts = salt.config.client_config(conf_file)
    if opts['transport'] == 'raet':
        event = salt.utils.raetevent.PresenceEvent(__opts__, __opts__['sock_dir'], state=state)
        data = event.get_event(wait=60, tag=tagify('present', 'presence'))
        key = 'present' if state is None else state
        if not data or key not in data:
            minions = []
        else:
            minions = data[key]
            if subset:
                minions = [m for m in minions if m in subset]
    else:
        # Always return 'present' for 0MQ for now
        # TODO: implement other states spport for 0MQ
        ckminions = salt.utils.minions.CkMinions(__opts__)
        minions = ckminions.connected_ids(show_ipv4=show_ipv4, subset=subset, include_localhost=True)

    connected = dict(minions) if show_ipv4 else sorted(minions)

    return connected


def list_not_state(subset=None, show_ipv4=False, state=None):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    state : 'available'
        Show minions being in specific state that is one of 'available', 'joined',
        'allowed', 'alived' or 'reaped'.

    CLI Example:

    .. code-block:: bash

        salt-run manage.list_not_state
    '''
    connected = list_state(subset=None, show_ipv4=show_ipv4, state=state)

    key = salt.key.get_key(__opts__)
    keys = key.list_keys()

    # TODO: Need better way to handle key/node name difference for raet
    # In raet case node name is '<name>_<kind>' meanwhile the key name
    # is just '<name>'. So append '_minion' to the name to match.
    appen_kind = isinstance(key, salt.key.RaetKey)

    not_connected = []
    for minion in keys[key.ACC]:
        if appen_kind:
            minion += '_minion'
        if minion not in connected and (subset is None or minion in subset):
            not_connected.append(minion)

    return not_connected


def present(subset=None, show_ipv4=False):
    '''
    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.present
    '''
    return list_state(subset=subset, show_ipv4=show_ipv4)


def not_present(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.5.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_present
    '''
    return list_not_state(subset=subset, show_ipv4=show_ipv4)


def joined(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.joined
    '''
    return list_state(subset=subset, show_ipv4=show_ipv4, state='joined')


def not_joined(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_joined
    '''
    return list_not_state(subset=subset, show_ipv4=show_ipv4, state='joined')


def allowed(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.allowed
    '''
    return list_state(subset=subset, show_ipv4=show_ipv4, state='allowed')


def not_allowed(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_allowed
    '''
    return list_not_state(subset=subset, show_ipv4=show_ipv4, state='allowed')


def alived(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.alived
    '''
    return list_state(subset=subset, show_ipv4=show_ipv4, state='alived')


def not_alived(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_alived
    '''
    return list_not_state(subset=subset, show_ipv4=show_ipv4, state='alived')


def reaped(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.reaped
    '''
    return list_state(subset=subset, show_ipv4=show_ipv4, state='reaped')


def not_reaped(subset=None, show_ipv4=False):
    '''
    .. versionadded:: 2015.8.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ipv4 : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_reaped
    '''
    return list_not_state(subset=subset, show_ipv4=show_ipv4, state='reaped')


def get_stats(estate=None, stack='road'):
    '''
    Print the stack stats

    estate : None
        The name of the target estate. Master stats would be requested by default

    stack : 'road'
        Show stats on either road or lane stack
        Allowed values are 'road' or 'lane'.

    CLI Example:

    .. code-block:: bash

        salt-run manage.get_stats [estate=alpha_minion] [stack=lane]
    '''
    conf_file = __opts__['conf_file']
    opts = salt.config.client_config(conf_file)
    if opts['transport'] == 'raet':
        tag = tagify(stack, 'stats')
        event = salt.utils.raetevent.StatsEvent(__opts__, __opts__['sock_dir'], tag=tag, estate=estate)
        stats = event.get_event(wait=60, tag=tag)
    else:
        #TODO: implement 0MQ analog
        stats = 'Not implemented'

    return stats


def road_stats(estate=None):
    '''
    Print the estate road stack stats

    estate : None
        The name of the target estate. Master stats would be requested by default

    CLI Example:

    .. code-block:: bash

        salt-run manage.road_stats [estate=alpha_minion]
    '''
    return get_stats(estate=estate, stack='road')


def lane_stats(estate=None):
    '''
    Print the estate manor lane stack stats

    estate : None
        The name of the target estate. Master stats would be requested by default

    CLI Example:

    .. code-block:: bash

        salt-run manage.lane_stats [estate=alpha_minion]
    '''
    return get_stats(estate=estate, stack='lane')


def safe_accept(target, expr_form='glob'):
    '''
    Accept a minion's public key after checking the fingerprint over salt-ssh

    CLI Example:

    .. code-block:: bash

        salt-run manage.safe_accept my_minion
        salt-run manage.safe_accept minion1,minion2 expr_form=list
    '''
    salt_key = salt.key.Key(__opts__)
    ssh_client = salt.client.ssh.client.SSHClient()

    ret = ssh_client.cmd(target, 'key.finger', expr_form=expr_form)

    failures = {}
    for minion, finger in six.iteritems(ret):
        if not FINGERPRINT_REGEX.match(finger):
            failures[minion] = finger
        else:
            fingerprints = salt_key.finger(minion)
            accepted = fingerprints.get('minions', {})
            pending = fingerprints.get('minions_pre', {})
            if minion in accepted:
                del ret[minion]
                continue
            elif minion not in pending:
                failures[minion] = ("Minion key {0} not found by salt-key"
                                    .format(minion))
            elif pending[minion] != finger:
                failures[minion] = ("Minion key {0} does not match the key in "
                                    "salt-key: {1}"
                                    .format(finger, pending[minion]))
            else:
                subprocess.call(["salt-key", "-qya", minion])

        if minion in failures:
            del ret[minion]

    if failures:
        print('safe_accept failed on the following minions:')
        for minion, message in six.iteritems(failures):
            print(minion)
            print('-' * len(minion))
            print(message)
            print('')

    __jid_event__.fire_event({'message': 'Accepted {0:d} keys'.format(len(ret))}, 'progress')
    return ret, failures


def versions():
    '''
    Check the version of active minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.versions
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    try:
        minions = client.cmd('*', 'test.version', timeout=__opts__['timeout'])
    except SaltClientError as client_error:
        print(client_error)
        return ret

    labels = {
        -1: 'Minion requires update',
        0: 'Up to date',
        1: 'Minion newer than master',
        2: 'Master',
    }

    version_status = {}

    master_version = salt.version.__saltstack_version__

    for minion in minions:
        minion_version = salt.version.SaltStackVersion.parse(minions[minion])
        ver_diff = cmp(minion_version, master_version)

        if ver_diff not in version_status:
            version_status[ver_diff] = {}
        version_status[ver_diff][minion] = minion_version.string

    # Add version of Master to output
    version_status[2] = master_version.string

    for key in version_status:
        if key == 2:
            ret[labels[key]] = version_status[2]
        else:
            for minion in sorted(version_status[key]):
                ret.setdefault(labels[key], {})[minion] = version_status[key][minion]
    return ret


def bootstrap(version='develop',
              script=None,
              hosts='',
              root_user=False,
              script_args='',
              roster='flat',
              ssh_user=None,
              ssh_password=None,
              ssh_priv_key=None,
              tmp_dir='/tmp/.bootstrap',
              http_backend='tornado'):
    '''
    Bootstrap minions with salt-bootstrap

    version : develop
        Git tag of version to install

    script : https://bootstrap.saltstack.com
        URL containing the script to execute

    hosts
        Comma-separated hosts [example: hosts='host1.local,host2.local']. These
        hosts need to exist in the specified roster.

    root_user : False
        Prepend ``root@`` to each host. Default changed in Salt 2016.11.0 from ``True``
        to ``False``.

        .. versionchanged:: 2016.11.0

        .. deprecated:: 2016.11.0

    script_args
        Any additional arguments that you want to pass to the script.

        .. versionadded:: 2016.11.0

    roster : flat
        The roster to use for Salt SSH. More information about roster files can
        be found in :ref:`Salt's Roster Documentation <ssh-roster>`.

        A full list of roster types, see the :ref:`builtin roster modules <all-salt.roster>`
        documentation.

        .. versionadded:: 2016.11.0

    ssh_user
        If ``user`` isn't found in the ``roster``, a default SSH user can be set here.
        Keep in mind that ``ssh_user`` will not override the roster ``user`` value if
        it is already defined.

        .. versionadded:: 2016.11.0

    ssh_password
        If ``passwd`` isn't found in the ``roster``, a default SSH password can be set
        here. Keep in mind that ``ssh_password`` will not override the roster ``passwd``
        value if it is already defined.

        .. versionadded:: 2016.11.0

    ssh_privkey
        If ``priv`` isn't found in the ``roster``, a default SSH private key can be set
        here. Keep in mind that ``ssh_password`` will not override the roster ``passwd``
        value if it is already defined.

        .. versionadded:: 2016.11.0

    tmp_dir : /tmp/.bootstrap
        The temporary directory to download the bootstrap script in. This
        directory will have ``-<uuid4>`` appended to it. For example:
        ``/tmp/.bootstrap-a19a728e-d40a-4801-aba9-d00655c143a7/``

        .. versionadded:: 2016.11.0

    http_backend : tornado
        The backend library to use to download the script. If you need to use
        a ``file:///`` URL, then you should set this to ``urllib2``.

        .. versionadded:: 2016.11.0


    CLI Example:

    .. code-block:: bash

        salt-run manage.bootstrap hosts='host1,host2'
        salt-run manage.bootstrap hosts='host1,host2' version='v0.17'
        salt-run manage.bootstrap hosts='host1,host2' version='v0.17' \
            script='https://bootstrap.saltstack.com/develop'
        salt-run manage.bootstrap hosts='ec2-user@host1,ec2-user@host2' \
            root_user=False

    '''
    dep_warning = (
        'Starting with Salt 2016.11.0, manage.bootstrap now uses Salt SSH to '
        'connect, and requires a roster entry. Please ensure that a roster '
        'entry exists for this host. Non-roster hosts will no longer be '
        'supported starting with Salt Oxygen.'
    )
    if root_user is True:
        salt.utils.warn_until('Oxygen', dep_warning)

    if script is None:
        script = 'https://bootstrap.saltstack.com'

    client_opts = __opts__.copy()
    if roster is not None:
        client_opts['roster'] = roster

    if ssh_user is not None:
        client_opts['ssh_user'] = ssh_user

    if ssh_password is not None:
        client_opts['ssh_passwd'] = ssh_password

    if ssh_priv_key is not None:
        client_opts['ssh_priv'] = ssh_priv_key

    for host in hosts.split(','):
        client_opts['tgt'] = host
        client_opts['selected_target_option'] = 'glob'
        tmp_dir = '{0}-{1}/'.format(tmp_dir.rstrip('/'), uuid.uuid4())
        deploy_command = os.path.join(tmp_dir, 'deploy.sh')
        try:
            client_opts['argv'] = ['file.makedirs', tmp_dir, 'mode=0700']
            salt.client.ssh.SSH(client_opts).run()
            client_opts['argv'] = [
                'http.query',
                script,
                'backend={0}'.format(http_backend),
                'text_out={0}'.format(deploy_command)
            ]
            client = salt.client.ssh.SSH(client_opts).run()
            client_opts['argv'] = [
                'cmd.run',
                ' '.join(['sh', deploy_command, script_args]),
                'python_shell=False'
            ]
            salt.client.ssh.SSH(client_opts).run()
            client_opts['argv'] = ['file.remove', tmp_dir]
            salt.client.ssh.SSH(client_opts).run()
        except SaltSystemExit as exc:
            if 'No hosts found with target' in str(exc):
                log.warning('The host {0} was not found in the Salt SSH roster '
                            'system. Attempting to log in without Salt SSH.')
                salt.utils.warn_until('Oxygen', dep_warning)
                ret = subprocess.call([
                    'ssh',
                    ('root@' if root_user else '') + host,
                    'python -c \'import urllib; '
                    'print urllib.urlopen('
                    '"' + script + '"'
                    ').read()\' | sh -s -- git ' + version
                ])
                return ret
            else:
                log.error(str(exc))


def bootstrap_psexec(hosts='', master=None, version=None, arch='win32',
                     installer_url=None, username=None, password=None):
    '''
    Bootstrap Windows minions via PsExec.

    hosts
        Comma separated list of hosts to deploy the Windows Salt minion.

    master
        Address of the Salt master passed as an argument to the installer.

    version
        Point release of installer to download. Defaults to the most recent.

    arch
        Architecture of installer to download. Defaults to win32.

    installer_url
        URL of minion installer executable. Defaults to the latest version from
        https://repo.saltstack.com/windows/

    username
        Optional user name for login on remote computer.

    password
        Password for optional username. If omitted, PsExec will prompt for one
        to be entered for each host.

    CLI Example:

    .. code-block:: bash

        salt-run manage.bootstrap_psexec hosts='host1,host2'
        salt-run manage.bootstrap_psexec hosts='host1,host2' version='0.17' username='DOMAIN\\Administrator'
        salt-run manage.bootstrap_psexec hosts='host1,host2' installer_url='http://exampledomain/salt-installer.exe'
    '''

    if not installer_url:
        base_url = 'https://repo.saltstack.com/windows/'
        source = _urlopen(base_url).read()
        salty_rx = re.compile('>(Salt-Minion-(.+?)-(.+)-Setup.exe)</a></td><td align="right">(.*?)\\s*<')
        source_list = sorted([[path, ver, plat, time.strptime(date, "%d-%b-%Y %H:%M")]
                              for path, ver, plat, date in salty_rx.findall(source)],
                             key=operator.itemgetter(3), reverse=True)
        if version:
            source_list = [s for s in source_list if s[1] == version]
        if arch:
            source_list = [s for s in source_list if s[2] == arch]

        if not source_list:
            return -1

        version = source_list[0][1]
        arch = source_list[0][2]
        installer_url = base_url + source_list[0][0]

    # It's no secret that Windows is notoriously command-line hostile.
    # Win 7 and newer can use PowerShell out of the box, but to reach
    # all those XP and 2K3 machines we must suppress our gag-reflex
    # and use VB!

    # The following script was borrowed from an informative article about
    # downloading exploit payloads for malware. Nope, no irony here.
    # http://www.greyhathacker.net/?p=500
    vb_script = '''strFileURL = "{0}"
strHDLocation = "{1}"
Set objXMLHTTP = CreateObject("MSXML2.XMLHTTP")
objXMLHTTP.open "GET", strFileURL, false
objXMLHTTP.send()
If objXMLHTTP.Status = 200 Then
Set objADOStream = CreateObject("ADODB.Stream")
objADOStream.Open
objADOStream.Type = 1
objADOStream.Write objXMLHTTP.ResponseBody
objADOStream.Position = 0
objADOStream.SaveToFile strHDLocation
objADOStream.Close
Set objADOStream = Nothing
End if
Set objXMLHTTP = Nothing
Set objShell = CreateObject("WScript.Shell")
objShell.Exec("{1}{2}")'''

    vb_saltexec = 'saltinstall.exe'
    vb_saltexec_args = ' /S /minion-name=%COMPUTERNAME%'
    if master:
        vb_saltexec_args += ' /master={0}'.format(master)

    # One further thing we need to do; the Windows Salt minion is pretty
    # self-contained, except for the Microsoft Visual C++ 2008 runtime.
    # It's tiny, so the bootstrap will attempt a silent install.
    vb_vcrunexec = 'vcredist.exe'
    if arch == 'AMD64':
        vb_vcrun = vb_script.format(
                'http://download.microsoft.com/download/d/2/4/d242c3fb-da5a-4542-ad66-f9661d0a8d19/vcredist_x64.exe',
                vb_vcrunexec,
                ' /q')
    else:
        vb_vcrun = vb_script.format(
                'http://download.microsoft.com/download/d/d/9/dd9a82d0-52ef-40db-8dab-795376989c03/vcredist_x86.exe',
                vb_vcrunexec,
                ' /q')

    vb_salt = vb_script.format(installer_url, vb_saltexec, vb_saltexec_args)

    # PsExec doesn't like extra long arguments; save the instructions as a batch
    # file so we can fire it over for execution.

    # First off, change to the local temp directory, stop salt-minion (if
    # running), and remove the master's public key.
    # This is to accommodate for reinstalling Salt over an old or broken build,
    # e.g. if the master address is changed, the salt-minion process will fail
    # to authenticate and quit; which means infinite restarts under Windows.
    batch = 'cd /d %TEMP%\nnet stop salt-minion\ndel c:\\salt\\conf\\pki\\minion\\minion_master.pub\n'

    # Speaking of command-line hostile, cscript only supports reading a script
    # from a file. Glue it together line by line.
    for x, y in ((vb_vcrunexec, vb_vcrun), (vb_saltexec, vb_salt)):
        vb_lines = y.split('\n')
        batch += '\ndel ' + x + '\n@echo ' + vb_lines[0] + '  >' + \
                 x + '.vbs\n@echo ' + \
                 ('  >>' + x + '.vbs\n@echo ').join(vb_lines[1:]) + \
                 '  >>' + x + '.vbs\ncscript.exe /NoLogo ' + x + '.vbs'

    batch_path = tempfile.mkstemp(suffix='.bat')[1]
    with salt.utils.fopen(batch_path, 'wb') as batch_file:
        batch_file.write(batch)

    for host in hosts.split(","):
        argv = ['psexec', '\\\\' + host]
        if username:
            argv += ['-u', username]
            if password:
                argv += ['-p', password]
        argv += ['-h', '-c', batch_path]
        subprocess.call(argv)
