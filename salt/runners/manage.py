"""
General management functions for salt, tools like seeing what hosts are up
and what hosts are down
"""


import logging
import operator
import os
import re
import subprocess
import tempfile
import time
import urllib.request
import uuid

import salt.client
import salt.client.ssh
import salt.key
import salt.utils.compat
import salt.utils.files
import salt.utils.minions
import salt.utils.path
import salt.utils.versions
import salt.version
import salt.wheel
from salt.exceptions import SaltClientError, SaltSystemExit

FINGERPRINT_REGEX = re.compile(r"^([a-f0-9]{2}:){15}([a-f0-9]{2})$")

log = logging.getLogger(__name__)


def _ping(tgt, tgt_type, timeout, gather_job_timeout):
    with salt.client.get_local_client(__opts__["conf_file"]) as client:
        pub_data = client.run_job(
            tgt, "test.ping", (), tgt_type, "", timeout, "", listen=True
        )

        if not pub_data:
            return pub_data

        log.debug(
            "manage runner will ping the following minion(s): %s",
            ", ".join(sorted(pub_data["minions"])),
        )

        returned = set()
        for fn_ret in client.get_cli_event_returns(
            pub_data["jid"],
            pub_data["minions"],
            client._get_timeout(timeout),
            tgt,
            tgt_type,
            gather_job_timeout=gather_job_timeout,
        ):

            if fn_ret:
                for mid, _ in fn_ret.items():
                    log.debug("minion '%s' returned from ping", mid)
                    returned.add(mid)

        not_returned = sorted(set(pub_data["minions"]) - returned)
        returned = sorted(returned)

        return returned, not_returned


def status(
    output=True, tgt="*", tgt_type="glob", timeout=None, gather_job_timeout=None
):
    """
    .. versionchanged:: 2017.7.0

        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Print the status of all known salt minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.status
        salt-run manage.status tgt="webservers" tgt_type="nodegroup"
        salt-run manage.status timeout=5 gather_job_timeout=10
    """
    ret = {}

    if not timeout:
        timeout = __opts__["timeout"]
    if not gather_job_timeout:
        gather_job_timeout = __opts__["gather_job_timeout"]

    res = _ping(tgt, tgt_type, timeout, gather_job_timeout)
    ret["up"], ret["down"] = ([], []) if not res else res
    return ret


def key_regen():
    """
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
    """
    client = salt.client.get_local_client(__opts__["conf_file"])
    try:
        client.cmd("*", "saltutil.regen_keys")
    except SaltClientError as client_error:
        print(client_error)
        return False

    for root, _, files in salt.utils.path.os_walk(__opts__["pki_dir"]):
        for fn_ in files:
            path = os.path.join(root, fn_)
            try:
                os.remove(path)
            except os.error:
                pass
    msg = (
        "The minion and master keys have been deleted.  Restart the Salt\n"
        "Master within the next 60 seconds!!!\n\n"
        "Wait for the minions to reconnect.  Once the minions reconnect\n"
        "the new keys will appear in pending and will need to be re-\n"
        "accepted by running:\n"
        "    salt-key -A\n\n"
        "Be advised that minions not currently connected to the master\n"
        "will not be able to reconnect and may require manual\n"
        "regeneration via a local call to\n"
        "    salt-call saltutil.regen_keys"
    )
    return msg


def down(
    removekeys=False, tgt="*", tgt_type="glob", timeout=None, gather_job_timeout=None
):
    """
    .. versionchanged:: 2017.7.0

        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Print a list of all the down or unresponsive salt minions
    Optionally remove keys of down minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.down
        salt-run manage.down removekeys=True
        salt-run manage.down tgt="webservers" tgt_type="nodegroup"
    """
    ret = status(
        output=False,
        tgt=tgt,
        tgt_type=tgt_type,
        timeout=timeout,
        gather_job_timeout=gather_job_timeout,
    ).get("down", [])
    for minion in ret:
        if removekeys:
            wheel = salt.wheel.Wheel(__opts__)
            wheel.call_func("key.delete", match=minion)
    return ret


def up(
    tgt="*", tgt_type="glob", timeout=None, gather_job_timeout=None
):  # pylint: disable=C0103
    """
    .. versionchanged:: 2017.7.0

        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Print a list of all of the minions that are up

    CLI Example:

    .. code-block:: bash

        salt-run manage.up
        salt-run manage.up tgt="webservers" tgt_type="nodegroup"
        salt-run manage.up timeout=5 gather_job_timeout=10
    """
    ret = status(
        output=False,
        tgt=tgt,
        tgt_type=tgt_type,
        timeout=timeout,
        gather_job_timeout=gather_job_timeout,
    ).get("up", [])
    return ret


def list_state(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.list_state
    """
    # Always return 'present' for 0MQ for now
    # TODO: implement other states support for 0MQ
    ckminions = salt.utils.minions.CkMinions(__opts__)
    minions = ckminions.connected_ids(show_ip=show_ip, subset=subset)

    connected = dict(minions) if show_ip else sorted(minions)

    return connected


def list_not_state(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.list_not_state
    """
    connected = list_state(subset=None, show_ip=show_ip)

    with salt.key.get_key(__opts__) as key:
        keys = key.list_keys()

        not_connected = []
        for minion in keys[key.ACC]:
            if minion not in connected and (subset is None or minion in subset):
                not_connected.append(minion)

        return not_connected


def present(subset=None, show_ip=False):
    """
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.present
    """
    return list_state(subset=subset, show_ip=show_ip)


def not_present(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_present
    """
    return list_not_state(subset=subset, show_ip=show_ip)


def joined(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.joined
    """
    return list_state(subset=subset, show_ip=show_ip)


def not_joined(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_joined
    """
    return list_not_state(subset=subset, show_ip=show_ip)


def allowed(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.allowed
    """
    return list_state(subset=subset, show_ip=show_ip)


def not_allowed(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_allowed
    """
    return list_not_state(subset=subset, show_ip=show_ip)


def alived(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.alived
    """
    return list_state(subset=subset, show_ip=show_ip)


def not_alived(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_alived
    """
    return list_not_state(subset=subset, show_ip=show_ip)


def reaped(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are up according to Salt's presence
    detection (no commands will be sent to minions)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.reaped
    """
    return list_state(subset=subset, show_ip=show_ip)


def not_reaped(subset=None, show_ip=False):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2019.2.0

    Print a list of all minions that are NOT up according to Salt's presence
    detection (no commands will be sent)

    subset : None
        Pass in a CIDR range to filter minions by IP address.

    show_ip : False
        Also show the IP address each minion is connecting from.

    CLI Example:

    .. code-block:: bash

        salt-run manage.not_reaped
    """
    return list_not_state(subset=subset, show_ip=show_ip)


def safe_accept(target, tgt_type="glob"):
    """
    .. versionchanged:: 2017.7.0

        The ``expr_form`` argument has been renamed to ``tgt_type``, earlier
        releases must use ``expr_form``.

    Accept a minion's public key after checking the fingerprint over salt-ssh

    CLI Example:

    .. code-block:: bash

        salt-run manage.safe_accept my_minion
        salt-run manage.safe_accept minion1,minion2 tgt_type=list
    """
    ssh_client = salt.client.ssh.client.SSHClient()
    ret = ssh_client.cmd(target, "key.finger", tgt_type=tgt_type)

    failures = {}
    for minion, finger in ret.items():
        if not FINGERPRINT_REGEX.match(finger):
            failures[minion] = finger
        else:
            with salt.key.Key(__opts__) as salt_key:
                fingerprints = salt_key.finger(minion)
            accepted = fingerprints.get("minions", {})
            pending = fingerprints.get("minions_pre", {})
            if minion in accepted:
                del ret[minion]
                continue
            elif minion not in pending:
                failures[minion] = "Minion key {} not found by salt-key".format(minion)
            elif pending[minion] != finger:
                failures[
                    minion
                ] = "Minion key {} does not match the key in salt-key: {}".format(
                    finger, pending[minion]
                )
            else:
                subprocess.call(["salt-key", "-qya", minion])

        if minion in failures:
            del ret[minion]

    if failures:
        print("safe_accept failed on the following minions:")
        for minion, message in failures.items():
            print(minion)
            print("-" * len(minion))
            print(message)
            print("")

    __jid_event__.fire_event(
        {"message": "Accepted {:d} keys".format(len(ret))}, "progress"
    )
    return ret, failures


def versions():
    """
    Check the version of active minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.versions
    """
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])
    try:
        minions = client.cmd("*", "test.version", timeout=__opts__["timeout"])
    except SaltClientError as client_error:
        print(client_error)
        return ret

    labels = {
        -2: "Minion offline",
        -1: "Minion requires update",
        0: "Up to date",
        1: "Minion newer than master",
        2: "Master",
    }

    version_status = {}

    master_version = salt.version.__saltstack_version__

    for minion in minions:
        if not minions[minion]:
            minion_version = False
            ver_diff = -2
        else:
            minion_version = salt.version.SaltStackVersion.parse(minions[minion])
            ver_diff = salt.utils.compat.cmp(minion_version, master_version)

        if ver_diff not in version_status:
            version_status[ver_diff] = {}
        if minion_version:
            version_status[ver_diff][minion] = minion_version.string
        else:
            version_status[ver_diff][minion] = minion_version

    # Add version of Master to output
    version_status[2] = master_version.string

    for key in version_status:
        if key == 2:
            ret[labels[key]] = version_status[2]
        else:
            for minion in sorted(version_status[key]):
                ret.setdefault(labels[key], {})[minion] = version_status[key][minion]
    return ret


def bootstrap(
    version="develop",
    script=None,
    hosts="",
    script_args="",
    roster="flat",
    ssh_user=None,
    ssh_password=None,
    ssh_priv_key=None,
    tmp_dir="/tmp/.bootstrap",
    http_backend="tornado",
):
    """
    Bootstrap minions with salt-bootstrap

    version : develop
        Git tag of version to install

    script : https://bootstrap.saltstack.com
        URL containing the script to execute

    hosts
        Comma-separated hosts [example: hosts='host1.local,host2.local']. These
        hosts need to exist in the specified roster.

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
        salt-run manage.bootstrap hosts='host1,host2' version='v0.17' script='https://bootstrap.saltstack.com/develop'
    """
    if script is None:
        script = "https://bootstrap.saltstack.com"

    client_opts = __opts__.copy()
    if roster is not None:
        client_opts["roster"] = roster

    if ssh_user is not None:
        client_opts["ssh_user"] = ssh_user

    if ssh_password is not None:
        client_opts["ssh_passwd"] = ssh_password

    if ssh_priv_key is not None:
        client_opts["ssh_priv"] = ssh_priv_key

    for host in hosts.split(","):
        client_opts["tgt"] = host
        client_opts["selected_target_option"] = "glob"
        tmp_dir = "{}-{}/".format(tmp_dir.rstrip("/"), uuid.uuid4())
        deploy_command = os.path.join(tmp_dir, "deploy.sh")
        try:
            client_opts["argv"] = ["file.makedirs", tmp_dir, "mode=0700"]
            salt.client.ssh.SSH(client_opts).run()
            client_opts["argv"] = [
                "http.query",
                script,
                "backend={}".format(http_backend),
                "text_out={}".format(deploy_command),
            ]
            salt.client.ssh.SSH(client_opts).run()
            client_opts["argv"] = [
                "cmd.run",
                " ".join(["sh", deploy_command, script_args]),
                "python_shell=False",
            ]
            salt.client.ssh.SSH(client_opts).run()
            client_opts["argv"] = ["file.remove", tmp_dir]
            salt.client.ssh.SSH(client_opts).run()
        except SaltSystemExit as exc:
            log.error(str(exc))


def bootstrap_psexec(
    hosts="",
    master=None,
    version=None,
    arch="win32",
    installer_url=None,
    username=None,
    password=None,
):
    """
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
        https://repo.saltproject.io/windows/

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
    """

    if not installer_url:
        base_url = "https://repo.saltproject.io/windows/"
        source = urllib.request.urlopen(base_url).read()
        salty_rx = re.compile(
            '>(Salt-Minion-(.+?)-(.+)-Setup.exe)</a></td><td align="right">(.*?)\\s*<'
        )
        source_list = sorted(
            [
                [path, ver, plat, time.strptime(date, "%d-%b-%Y %H:%M")]
                for path, ver, plat, date in salty_rx.findall(source)
            ],
            key=operator.itemgetter(3),
            reverse=True,
        )
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
    vb_script = """strFileURL = "{0}"
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
objShell.Exec("{1}{2}")"""

    vb_saltexec = "saltinstall.exe"
    vb_saltexec_args = " /S /minion-name=%COMPUTERNAME%"
    if master:
        vb_saltexec_args += " /master={}".format(master)

    # One further thing we need to do; the Windows Salt minion is pretty
    # self-contained, except for the Microsoft Visual C++ 2008 runtime.
    # It's tiny, so the bootstrap will attempt a silent install.
    vb_vcrunexec = "vcredist.exe"
    if arch == "AMD64":
        vb_vcrun = vb_script.format(
            "http://download.microsoft.com/download/d/2/4/d242c3fb-da5a-4542-ad66-f9661d0a8d19/vcredist_x64.exe",
            vb_vcrunexec,
            " /q",
        )
    else:
        vb_vcrun = vb_script.format(
            "http://download.microsoft.com/download/d/d/9/dd9a82d0-52ef-40db-8dab-795376989c03/vcredist_x86.exe",
            vb_vcrunexec,
            " /q",
        )

    vb_salt = vb_script.format(installer_url, vb_saltexec, vb_saltexec_args)

    # PsExec doesn't like extra long arguments; save the instructions as a batch
    # file so we can fire it over for execution.

    # First off, change to the local temp directory, stop salt-minion (if
    # running), and remove the master's public key.
    # This is to accommodate for reinstalling Salt over an old or broken build,
    # e.g. if the master address is changed, the salt-minion process will fail
    # to authenticate and quit; which means infinite restarts under Windows.
    batch = (
        "cd /d %TEMP%\nnet stop salt-minion\ndel"
        " c:\\salt\\conf\\pki\\minion\\minion_master.pub\n"
    )

    # Speaking of command-line hostile, cscript only supports reading a script
    # from a file. Glue it together line by line.
    for x, y in ((vb_vcrunexec, vb_vcrun), (vb_saltexec, vb_salt)):
        vb_lines = y.split("\n")
        batch += (
            "\ndel "
            + x
            + "\n@echo "
            + vb_lines[0]
            + "  >"
            + x
            + ".vbs\n@echo "
            + ("  >>" + x + ".vbs\n@echo ").join(vb_lines[1:])
            + "  >>"
            + x
            + ".vbs\ncscript.exe /NoLogo "
            + x
            + ".vbs"
        )

    batch_path = tempfile.mkstemp(suffix=".bat")[1]
    with salt.utils.files.fopen(batch_path, "wb") as batch_file:
        batch_file.write(batch)

    for host in hosts.split(","):
        argv = ["psexec", "\\\\" + host]
        if username:
            argv += ["-u", username]
            if password:
                argv += ["-p", password]
        argv += ["-h", "-c", batch_path]
        subprocess.call(argv)
