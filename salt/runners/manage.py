# -*- coding: utf-8 -*-
'''
General management functions for salt, tools like seeing what hosts are up
and what hosts are down
'''

# Import python libs
import os
import operator
import re
import subprocess
import tempfile
import time
import urllib

# Import salt libs
import salt.key
import salt.client
import salt.output
import salt.utils.minions

FINGERPRINT_REGEX = re.compile(r'^([a-f0-9]{2}:){15}([a-f0-9]{2})$')


def status(output=True):
    '''
    Print the status of all known salt minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.status
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'test.ping', timeout=__opts__['timeout'])

    key = salt.key.Key(__opts__)
    keys = key.list_keys()

    ret = {}
    ret['up'] = sorted(minions)
    ret['down'] = sorted(set(keys['minions']) - set(minions))
    if output:
        salt.output.display_output(ret, '', __opts__)
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
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'saltutil.regen_keys')

    for root, dirs, files in os.walk(__opts__['pki_dir']):
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
    print(msg)


def down(removekeys=False):
    '''
    Print a list of all the down or unresponsive salt minions
    Optionally remove keys of down minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.down
        salt-run manage.down removekeys=True
    '''
    ret = status(output=False).get('down', [])
    for minion in ret:
        if removekeys:
            subprocess.call(["salt-key", "-qyd", minion])
        else:
            salt.output.display_output(minion, '', __opts__)
    return ret


def up():  # pylint: disable=C0103
    '''
    Print a list of all of the minions that are up

    CLI Example:

    .. code-block:: bash

        salt-run manage.up
    '''
    ret = status(output=False).get('up', [])
    for minion in ret:
        salt.output.display_output(minion, '', __opts__)
    return ret


def present():
    '''
    Print a list of all minions that are up according to Salt's presence
    detection, no commands will be sent

    CLI Example:

    .. code-block:: bash

        salt-run manage.present
    '''
    ckminions = salt.utils.minions.CkMinions(__opts__)
    connected = sorted(ckminions.connected_ids())
    salt.output.display_output(connected, '', __opts__)
    return connected


def safe_accept(target, expr_form='glob'):
    '''
    Accept a minion's public key after checking the fingerprint over salt-ssh

    CLI Example:

    .. code-block:: bash

        salt-run manage.safe_accept my_minion
        salt-run manage.safe_accept minion1,minion2 expr_form=list
    '''
    salt_key = salt.key.Key(__opts__)
    ssh_client = salt.client.SSHClient()

    ret = ssh_client.cmd(target, 'key.finger', expr_form=expr_form)

    failures = {}
    for minion, finger in ret.items():
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
        print "safe_accept failed on the following minions:"
        for minion, message in failures.iteritems():
            print minion
            print '-' * len(minion)
            print message
            print

    print "Accepted {0:d} keys".format(len(ret))
    return ret, failures


def versions():
    '''
    Check the version of active minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.versions
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'test.version', timeout=__opts__['timeout'])

    labels = {
        -1: 'Minion requires update',
        0: 'Up to date',
        1: 'Minion newer than master',
    }

    version_status = {}

    comps = salt.__version__.split('-')
    if len(comps) == 3:
        master_version = '-'.join(comps[0:2])
    else:
        master_version = salt.__version__
    for minion in minions:
        comps = minions[minion].split('-')
        if len(comps) == 3:
            minion_version = '-'.join(comps[0:2])
        else:
            minion_version = minions[minion]
        ver_diff = cmp(minion_version, master_version)

        if ver_diff not in version_status:
            version_status[ver_diff] = {}
        version_status[ver_diff][minion] = minion_version

    ret = {}
    for key in version_status:
        for minion in sorted(version_status[key]):
            ret.setdefault(labels[key], {})[minion] = version_status[key][minion]

    salt.output.display_output(ret, '', __opts__)
    return ret


def bootstrap(version="develop",
              script="http://bootstrap.saltstack.org",
              hosts=""):
    '''
    Bootstrap minions with salt-bootstrap

    Options:
        version: git tag of version to install [default: develop]
        script: Script to execute [default: http://bootstrap.saltstack.org]
        hosts: Comma separated hosts [example: hosts="host1.local,host2.local"]

    CLI Example:

    .. code-block:: bash

        salt-run manage.bootstrap hosts="host1,host2"
        salt-run manage.bootstrap hosts="host1,host2" version="v0.17"
        salt-run manage.bootstrap hosts="host1,host2" version="v0.17" script="https://raw.github.com/saltstack/salt-bootstrap/develop/bootstrap-salt.sh"

    '''
    for host in hosts.split(","):
        # Could potentially lean on salt-ssh utils to make
        # deployment easier on existing hosts (i.e. use sshpass,
        # or expect, pass better options to ssh etc)
        subprocess.call(["ssh", "root@" + host, "python -c 'import urllib; "
                        "print urllib.urlopen("
                        "\"" + script + "\""
                        ").read()' | sh -s -- git " + version])


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
        http://docs.saltstack.com/downloads

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
        base_url = 'http://docs.saltstack.com/downloads/'
        source = urllib.urlopen(base_url).read()
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
    vb = '''strFileURL = "{0}"
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
        vb_vcrun = vb.format('http://download.microsoft.com/download/d/2/4/d242c3fb-da5a-4542-ad66-f9661d0a8d19/vcredist_x64.exe', vb_vcrunexec, ' /q')
    else:
        vb_vcrun = vb.format('http://download.microsoft.com/download/d/d/9/dd9a82d0-52ef-40db-8dab-795376989c03/vcredist_x86.exe', vb_vcrunexec, ' /q')

    vb_salt = vb.format(installer_url, vb_saltexec, vb_saltexec_args)

    # PsExec doesn't like extra long arguments; save the instructions as a batch
    # file so we can fire it over for execution.

    # First off, change to the local temp directory, stop salt-minion (if
    # running), and remove the master's public key.
    # This is to accomodate for reinstalling Salt over an old or broken build,
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
    batch_file = open(batch_path, 'wb')
    batch_file.write(batch)
    batch_file.close()

    for host in hosts.split(","):
        argv = ['psexec', '\\\\' + host]
        if username:
            argv += ['-u', username]
            if password:
                argv += ['-p', password]
        argv += ['-h', '-c', batch_path]
        subprocess.call(argv)
