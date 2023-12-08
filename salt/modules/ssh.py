"""
Manage client ssh components

.. note::

    This module requires the use of MD5 hashing. Certain security audits may
    not permit the use of MD5. For those cases, this module should be disabled
    or removed.
"""

import base64
import binascii
import hashlib
import logging
import os
import re
import subprocess

import salt.utils.data
import salt.utils.decorators.path
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

DEFAULT_SSH_PORT = 22


def __virtual__():
    if not salt.utils.path.which("ssh"):
        return False, "The module requires the ssh binary."
    return True


def _refine_enc(enc):
    """
    Return the properly formatted ssh value for the authorized encryption key
    type. ecdsa defaults to 256 bits, must give full ecdsa enc schema string
    if using higher enc. If the type is not found, raise CommandExecutionError.
    """

    rsa = ["r", "rsa", "ssh-rsa"]
    dss = ["d", "dsa", "dss", "ssh-dss"]
    ecdsa = [
        "e",
        "ecdsa",
        "ecdsa-sha2-nistp521",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp256",
    ]
    ed25519 = ["ed25519", "ssh-ed25519"]
    also_allowed = [
        "rsa-sha2-512",
        "rsa-sha2-256",
        "rsa-sha2-512-cert-v01@openssh.com",
        "rsa-sha2-256-cert-v01@openssh.com",
        "ssh-rsa-cert-v01@openssh.com",
        "ecdsa-sha2-nistp256-cert-v01@openssh.com",
        "ecdsa-sha2-nistp384-cert-v01@openssh.com",
        "ecdsa-sha2-nistp521-cert-v01@openssh.com",
        "sk-ecdsa-sha2-nistp256@openssh.com",
        "sk-ecdsa-sha2-nistp256-cert-v01@openssh.com",
        "ssh-ed25519-cert-v01@openssh.com",
        "sk-ssh-ed25519@openssh.com",
        "sk-ssh-ed25519-cert-v01@openssh.com",
    ]

    if enc in rsa:
        return "ssh-rsa"
    elif enc in dss:
        return "ssh-dss"
    elif enc in ecdsa:
        # ecdsa defaults to ecdsa-sha2-nistp256
        # otherwise enc string is actual encoding string
        if enc in ["e", "ecdsa"]:
            return "ecdsa-sha2-nistp256"
        return enc
    elif enc in ed25519:
        return "ssh-ed25519"
    elif enc in also_allowed:
        return enc
    else:
        raise CommandExecutionError("Incorrect encryption key type '{}'.".format(enc))


def _format_auth_line(key, enc, comment, options):
    """
    Properly format user input.
    """
    line = ""
    if options:
        line += "{} ".format(",".join(options))
    line += "{} {} {}\n".format(enc, key, comment)
    return line


def _expand_authorized_keys_path(path, user, home):
    """
    Expand the AuthorizedKeysFile expression. Defined in man sshd_config(5)
    """
    converted_path = ""
    had_escape = False
    for char in path:
        if had_escape:
            had_escape = False
            if char == "%":
                converted_path += "%"
            elif char == "u":
                converted_path += user
            elif char == "h":
                converted_path += home
            else:
                error = 'AuthorizedKeysFile path: unknown token character "%{}"'.format(
                    char
                )
                raise CommandExecutionError(error)
            continue
        elif char == "%":
            had_escape = True
        else:
            converted_path += char
    if had_escape:
        error = "AuthorizedKeysFile path: Last character can't be escape character"
        raise CommandExecutionError(error)
    return converted_path


def _get_config_file(user, config):
    """
    Get absolute path to a user's ssh_config.
    """
    uinfo = __salt__["user.info"](user)
    if not uinfo:
        raise CommandExecutionError("User '{}' does not exist".format(user))
    home = uinfo["home"]
    config = _expand_authorized_keys_path(config, user, home)
    if not os.path.isabs(config):
        config = os.path.join(home, config)
    return config


def _replace_auth_key(
    user, key, enc="ssh-rsa", comment="", options=None, config=".ssh/authorized_keys"
):
    """
    Replace an existing key
    """

    auth_line = _format_auth_line(key, enc, comment, options or [])

    lines = []
    full = _get_config_file(user, config)

    try:
        # open the file for both reading AND writing
        with salt.utils.files.fopen(full, "r") as _fh:
            for line in _fh:
                # We don't need any whitespace-only containing lines or arbitrary doubled newlines
                line = salt.utils.stringutils.to_unicode(line.strip())
                if line == "":
                    continue
                line += "\n"

                if line.startswith("#"):
                    # Commented Line
                    lines.append(line)
                    continue
                comps = re.findall(
                    r"((.*)\s)?((?:sk-)?(?:ssh|ecdsa)-[a-z0-9@.-]+)\s([a-zA-Z0-9+/]+={0,2})(\s(.*))?",
                    line,
                )
                if comps and len(comps[0]) > 3 and comps[0][3] == key:
                    # Found our key, replace it
                    lines.append(auth_line)
                else:
                    lines.append(line)
            _fh.close()
            # Re-open the file writable after properly closing it
            with salt.utils.files.fopen(full, "wb") as _fh:
                # Write out any changes
                _fh.writelines(salt.utils.data.encode(lines))
    except OSError as exc:
        raise CommandExecutionError(
            "Problem reading or writing to key file: {}".format(exc)
        )


def _validate_keys(key_file, fingerprint_hash_type):
    """
    Return a dict containing validated keys in the passed file
    """
    ret = {}
    linere = re.compile(r"^(.*?)\s?((?:sk-)?(?:ssh\-|ecds)[\w@.-]+\s.+)$")

    try:
        with salt.utils.files.fopen(key_file, "r") as _fh:
            for line in _fh:
                # We don't need any whitespace-only containing lines or arbitrary doubled newlines
                line = salt.utils.stringutils.to_unicode(line.strip())
                if line == "":
                    continue
                line += "\n"

                if line.startswith("#"):
                    # Commented Line
                    continue

                # get "{options} key"
                search = re.search(linere, line)
                if not search:
                    # not an auth ssh key, perhaps a blank line
                    continue

                opts = search.group(1)
                comps = search.group(2).split()

                if len(comps) < 2:
                    # Not a valid line
                    continue

                if opts:
                    # It has options, grab them
                    options = opts.split(",")
                else:
                    options = []

                enc = comps[0]
                key = comps[1]
                comment = " ".join(comps[2:])
                fingerprint = _fingerprint(key, fingerprint_hash_type)
                if fingerprint is None:
                    continue

                ret[key] = {
                    "enc": enc,
                    "comment": comment,
                    "options": options,
                    "fingerprint": fingerprint,
                }
    except OSError:
        raise CommandExecutionError("Problem reading ssh key file {}".format(key_file))

    return ret


def _fingerprint(public_key, fingerprint_hash_type):
    """
    Return a public key fingerprint based on its base64-encoded representation

    The fingerprint string is formatted according to RFC 4716 (ch.4), that is,
    in the form "xx:xx:...:xx"

    If the key is invalid (incorrect base64 string), return None

    public_key
        The public key to return the fingerprint for

    fingerprint_hash_type
        The public key fingerprint hash type that the public key fingerprint
        was originally hashed with. This defaults to ``sha256`` if not specified.

        .. versionadded:: 2016.11.4
        .. versionchanged:: 2017.7.0

            default changed from ``md5`` to ``sha256``

    """
    if fingerprint_hash_type:
        hash_type = fingerprint_hash_type.lower()
    else:
        hash_type = "sha256"

    try:
        hash_func = getattr(hashlib, hash_type)
    except AttributeError:
        raise CommandExecutionError(
            "The fingerprint_hash_type {} is not supported.".format(hash_type)
        )

    try:
        raw_key = base64.b64decode(public_key, validate=True)  # pylint: disable=E1123
    except binascii.Error:
        return None

    ret = hash_func(raw_key).hexdigest()

    chunks = [ret[i : i + 2] for i in range(0, len(ret), 2)]
    return ":".join(chunks)


def _get_known_hosts_file(config=None, user=None):
    if user:
        config = config or ".ssh/known_hosts"
    else:
        config = config or "/etc/ssh/ssh_known_hosts"

    if os.path.isabs(config):
        full = config
    else:
        if user:
            uinfo = __salt__["user.info"](user)
            if not uinfo:
                return {
                    "status": "error",
                    "error": "User {} does not exist".format(user),
                }
            full = os.path.join(uinfo["home"], config)
        else:
            return {
                "status": "error",
                "error": "Cannot determine absolute path to file.",
            }

    return full


def host_keys(keydir=None, private=True, certs=True):
    """
    Return the minion's host keys

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.host_keys
        salt '*' ssh.host_keys keydir=/etc/ssh
        salt '*' ssh.host_keys keydir=/etc/ssh private=False
        salt '*' ssh.host_keys keydir=/etc/ssh certs=False
    """
    # TODO: support parsing sshd_config for the key directory
    if not keydir:
        if __grains__["kernel"] == "Linux":
            keydir = "/etc/ssh"
        else:
            # If keydir is None, os.listdir() will blow up
            raise SaltInvocationError("ssh.host_keys: Please specify a keydir")
    keys = {}
    fnre = re.compile(r"ssh_host_(?P<type>.+)_key(?P<pub>(?P<cert>-cert)?\.pub)?")
    for fn_ in os.listdir(keydir):
        m = fnre.match(fn_)
        if m:
            if not m.group("pub") and private is False:
                log.info("Skipping private key file %s as private is set to False", fn_)
                continue
            if m.group("cert") and certs is False:
                log.info("Skipping key file %s as certs is set to False", fn_)
                continue

            kname = m.group("type")
            if m.group("pub"):
                kname += m.group("pub")
            try:
                with salt.utils.files.fopen(os.path.join(keydir, fn_), "r") as _fh:
                    # As of RFC 4716 "a key file is a text file, containing a
                    # sequence of lines", although some SSH implementations
                    # (e.g. OpenSSH) manage their own format(s).  Please see
                    # #20708 for a discussion about how to handle SSH key files
                    # in the future
                    keys[kname] = salt.utils.stringutils.to_unicode(_fh.readline())
                    # only read the whole file if it is not in the legacy 1.1
                    # binary format
                    if keys[kname] != "SSH PRIVATE KEY FILE FORMAT 1.1\n":
                        keys[kname] += salt.utils.stringutils.to_unicode(_fh.read())
                    keys[kname] = keys[kname].strip()
            except OSError:
                keys[kname] = ""
    return keys


def auth_keys(user=None, config=".ssh/authorized_keys", fingerprint_hash_type=None):
    """
    Return the authorized keys for users

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.auth_keys
        salt '*' ssh.auth_keys root
        salt '*' ssh.auth_keys user=root
        salt '*' ssh.auth_keys user="[user1, user2]"
    """
    if not user:
        user = __salt__["user.list_users"]()

    old_output_when_one_user = False
    if not isinstance(user, list):
        user = [user]
        old_output_when_one_user = True

    keys = {}
    for u in user:
        full = None
        try:
            full = _get_config_file(u, config)
        except CommandExecutionError:
            pass

        if full and os.path.isfile(full):
            keys[u] = _validate_keys(full, fingerprint_hash_type)

    if old_output_when_one_user:
        if user[0] in keys:
            return keys[user[0]]
        else:
            return {}

    return keys


def check_key_file(
    user,
    source,
    config=".ssh/authorized_keys",
    saltenv="base",
    fingerprint_hash_type=None,
):
    """
    Check a keyfile from a source destination against the local keys and
    return the keys to change

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.check_key_file root salt://ssh/keyfile
    """
    keyfile = __salt__["cp.cache_file"](source, saltenv)
    if not keyfile:
        return {}
    s_keys = _validate_keys(keyfile, fingerprint_hash_type)
    if not s_keys:
        err = "No keys detected in {}. Is file properly formatted?".format(source)
        log.error(err)
        __context__["ssh_auth.error"] = err
        return {}
    else:
        ret = {}
        for key in s_keys:
            ret[key] = check_key(
                user,
                key,
                s_keys[key]["enc"],
                s_keys[key]["comment"],
                s_keys[key]["options"],
                config=config,
                fingerprint_hash_type=fingerprint_hash_type,
            )
        return ret


def check_key(
    user,
    key,
    enc,
    comment,
    options,
    config=".ssh/authorized_keys",
    cache_keys=None,
    fingerprint_hash_type=None,
):
    """
    Check to see if a key needs updating, returns "update", "add" or "exists"

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.check_key <user> <key> <enc> <comment> <options>
    """
    if cache_keys is None:
        cache_keys = []
    enc = _refine_enc(enc)
    current = auth_keys(
        user, config=config, fingerprint_hash_type=fingerprint_hash_type
    )
    nline = _format_auth_line(key, enc, comment, options)

    # Removing existing keys from the auth_keys isn't really a good idea
    # in fact
    #
    # as:
    #   - We can have non-salt managed keys in that file
    #   - We can have multiple states defining keys for an user
    #     and with such code only one state will win
    #     the remove all-other-keys war
    #
    # if cache_keys:
    #     for pub_key in set(current).difference(set(cache_keys)):
    #         rm_auth_key(user, pub_key)

    if key in current:
        cline = _format_auth_line(
            key, current[key]["enc"], current[key]["comment"], current[key]["options"]
        )
        if cline != nline:
            return "update"
    else:
        return "add"
    return "exists"


def rm_auth_key_from_file(
    user,
    source,
    config=".ssh/authorized_keys",
    saltenv="base",
    fingerprint_hash_type=None,
):
    """
    Remove an authorized key from the specified user's authorized key file,
    using a file as source

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.rm_auth_key_from_file <user> salt://ssh_keys/<user>.id_rsa.pub
    """
    lfile = __salt__["cp.cache_file"](source, saltenv)
    if not os.path.isfile(lfile):
        raise CommandExecutionError("Failed to pull key file from salt file server")

    s_keys = _validate_keys(lfile, fingerprint_hash_type)
    if not s_keys:
        err = "No keys detected in {}. Is file properly formatted?".format(source)
        log.error(err)
        __context__["ssh_auth.error"] = err
        return "fail"
    else:
        rval = ""
        for key in s_keys:
            rval += rm_auth_key(
                user, key, config=config, fingerprint_hash_type=fingerprint_hash_type
            )
        # Due to the ability for a single file to have multiple keys, it's
        # possible for a single call to this function to have both "replace"
        # and "new" as possible valid returns. I ordered the following as I
        # thought best.
        if "Key not removed" in rval:
            return "Key not removed"
        elif "Key removed" in rval:
            return "Key removed"
        else:
            return "Key not present"


def rm_auth_key(user, key, config=".ssh/authorized_keys", fingerprint_hash_type=None):
    """
    Remove an authorized key from the specified user's authorized key file

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.rm_auth_key <user> <key>
    """
    current = auth_keys(
        user, config=config, fingerprint_hash_type=fingerprint_hash_type
    )
    linere = re.compile(r"^(.*?)\s?((?:sk-)?(?:ssh\-|ecds)[\w@.-]+\s.+)$")
    if key in current:
        # Remove the key
        full = _get_config_file(user, config)

        # Return something sensible if the file doesn't exist
        if not os.path.isfile(full):
            return "Authorized keys file {} not present".format(full)

        lines = []
        try:
            # Read every line in the file to find the right ssh key
            # and then write out the correct one. Open the file once
            with salt.utils.files.fopen(full, "r") as _fh:
                for line in _fh:
                    # We don't need any whitespace-only containing lines or arbitrary doubled newlines
                    line = salt.utils.stringutils.to_unicode(line.strip())
                    if line == "":
                        continue
                    line += "\n"

                    if line.startswith("#"):
                        # Commented Line
                        lines.append(line)
                        continue

                    # get "{options} key"
                    search = re.search(linere, line)
                    if not search:
                        # not an auth ssh key, perhaps a blank line
                        continue

                    comps = search.group(2).split()

                    if len(comps) < 2:
                        # Not a valid line
                        lines.append(line)
                        continue

                    pkey = comps[1]

                    # This is the key we are "deleting", so don't put
                    # it in the list of keys to be re-added back
                    if pkey == key:
                        continue

                    lines.append(line)

            # Let the context manager do the right thing here and then
            # re-open the file in write mode to save the changes out.
            with salt.utils.files.fopen(full, "wb") as _fh:
                _fh.writelines(salt.utils.data.encode(lines))
        except OSError as exc:
            log.warning("Could not read/write key file: %s", exc)
            return "Key not removed"
        return "Key removed"
    # TODO: Should this function return a simple boolean?
    return "Key not present"


def set_auth_key_from_file(
    user,
    source,
    config=".ssh/authorized_keys",
    saltenv="base",
    fingerprint_hash_type=None,
):
    """
    Add a key to the authorized_keys file, using a file as the source.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_auth_key_from_file <user> salt://ssh_keys/<user>.id_rsa.pub
    """
    # TODO: add support for pulling keys from other file sources as well
    lfile = __salt__["cp.cache_file"](source, saltenv)
    if not os.path.isfile(lfile):
        raise CommandExecutionError("Failed to pull key file from salt file server")

    s_keys = _validate_keys(lfile, fingerprint_hash_type)
    if not s_keys:
        err = "No keys detected in {}. Is file properly formatted?".format(source)
        log.error(err)
        __context__["ssh_auth.error"] = err
        return "fail"
    else:
        rval = ""
        for key in s_keys:
            rval += set_auth_key(
                user,
                key,
                enc=s_keys[key]["enc"],
                comment=s_keys[key]["comment"],
                options=s_keys[key]["options"],
                config=config,
                cache_keys=list(s_keys.keys()),
                fingerprint_hash_type=fingerprint_hash_type,
            )
        # Due to the ability for a single file to have multiple keys, it's
        # possible for a single call to this function to have both "replace"
        # and "new" as possible valid returns. I ordered the following as I
        # thought best.
        if "fail" in rval:
            return "fail"
        elif "replace" in rval:
            return "replace"
        elif "new" in rval:
            return "new"
        else:
            return "no change"


def set_auth_key(
    user,
    key,
    enc="ssh-rsa",
    comment="",
    options=None,
    config=".ssh/authorized_keys",
    cache_keys=None,
    fingerprint_hash_type=None,
):
    """
    Add a key to the authorized_keys file. The "key" parameter must only be the
    string of text that is the encoded key. If the key begins with "ssh-rsa"
    or ends with user@host, remove those from the key before passing it to this
    function.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_auth_key <user> '<key>' enc='dsa'
    """
    if cache_keys is None:
        cache_keys = []
    if len(key.split()) > 1:
        return "invalid"

    enc = _refine_enc(enc)
    uinfo = __salt__["user.info"](user)
    if not uinfo:
        return "fail"

    # A 'valid key' to us pretty much means 'decodable as base64', which is
    # the same filtering done when reading the authorized_keys file. Apply
    # the same check to ensure we don't insert anything that will not
    # subsequently be read)
    key_is_valid = _fingerprint(key, fingerprint_hash_type) is not None
    if not key_is_valid:
        return "Invalid public key"

    status = check_key(
        user,
        key,
        enc,
        comment,
        options,
        config=config,
        cache_keys=cache_keys,
        fingerprint_hash_type=fingerprint_hash_type,
    )
    if status == "update":
        _replace_auth_key(user, key, enc, comment, options or [], config)
        return "replace"
    elif status == "exists":
        return "no change"
    else:
        auth_line = _format_auth_line(key, enc, comment, options)
        fconfig = _get_config_file(user, config)
        # Fail if the key lives under the user's homedir, and the homedir
        # doesn't exist
        udir = uinfo.get("home", "")
        if fconfig.startswith(udir) and not os.path.isdir(udir):
            return "fail"
        if not os.path.isdir(os.path.dirname(fconfig)):
            dpath = os.path.dirname(fconfig)
            os.makedirs(dpath)
            if not salt.utils.platform.is_windows():
                if os.geteuid() == 0:
                    os.chown(dpath, uinfo["uid"], uinfo["gid"])
                os.chmod(dpath, 448)
            # If SELINUX is available run a restorecon on the file
            rcon = salt.utils.path.which("restorecon")
            if rcon:
                cmd = [rcon, dpath]
                subprocess.call(cmd)

        if not os.path.isfile(fconfig):
            new_file = True
        else:
            new_file = False

        try:
            with salt.utils.files.fopen(fconfig, "ab+") as _fh:
                if new_file is False:
                    # Let's make sure we have a new line at the end of the file
                    _fh.seek(0, 2)
                    if _fh.tell() > 0:
                        # File isn't empty, check if last byte is a newline
                        # If not, add one
                        _fh.seek(-1, 2)
                        if _fh.read(1) != b"\n":
                            _fh.write(b"\n")
                _fh.write(salt.utils.stringutils.to_bytes(auth_line))
        except OSError as exc:
            msg = "Could not write to key file: {0}"
            raise CommandExecutionError(msg.format(exc))

        if new_file:
            if not salt.utils.platform.is_windows():
                if os.geteuid() == 0:
                    os.chown(fconfig, uinfo["uid"], uinfo["gid"])
                os.chmod(fconfig, 384)
            # If SELINUX is available run a restorecon on the file
            rcon = salt.utils.path.which("restorecon")
            if rcon:
                cmd = [rcon, fconfig]
                subprocess.call(cmd)
        return "new"


def _get_matched_host_line_numbers(lines, enc):
    """
    Helper function which parses ssh-keygen -F function output and yield line
    number of known_hosts entries with encryption key type matching enc,
    one by one.
    """
    enc = enc if enc else "rsa"
    for i, line in enumerate(lines):
        if i % 2 == 0:
            line_no = int(line.strip().split()[-1])
            line_enc = lines[i + 1].strip().split()[-2]
            if line_enc != enc:
                continue
            yield line_no


def _parse_openssh_output(lines, fingerprint_hash_type=None):
    """
    Helper function which parses ssh-keygen -F and ssh-keyscan function output
    and yield dict with keys information, one by one.
    """
    for line in lines:
        # We don't need any whitespace-only containing lines or arbitrary doubled newlines
        line = line.strip()
        if line == "":
            continue
        line += "\n"

        if line.startswith("#"):
            continue
        try:
            hostname, enc, key = line.split()
        except ValueError:  # incorrect format
            continue
        fingerprint = _fingerprint(key, fingerprint_hash_type=fingerprint_hash_type)
        if not fingerprint:
            continue
        yield {"hostname": hostname, "key": key, "enc": enc, "fingerprint": fingerprint}


@salt.utils.decorators.path.which("ssh-keygen")
def get_known_host_entries(
    user, hostname, config=None, port=None, fingerprint_hash_type=None
):
    """
    .. versionadded:: 2018.3.0

    Return information about known host entries from the configfile, if any.
    If there are no entries for a matching hostname, return None.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.get_known_host_entries <user> <hostname>
    """
    full = _get_known_hosts_file(config=config, user=user)

    if isinstance(full, dict):
        return full

    ssh_hostname = _hostname_and_port_to_ssh_hostname(hostname, port)
    cmd = ["ssh-keygen", "-F", ssh_hostname, "-f", full]
    lines = __salt__["cmd.run"](
        cmd, ignore_retcode=True, python_shell=False
    ).splitlines()
    known_host_entries = list(
        _parse_openssh_output(lines, fingerprint_hash_type=fingerprint_hash_type)
    )
    return known_host_entries if known_host_entries else None


@salt.utils.decorators.path.which("ssh-keyscan")
def recv_known_host_entries(
    hostname,
    enc=None,
    port=None,
    hash_known_hosts=True,
    timeout=5,
    fingerprint_hash_type=None,
):
    """
    .. versionadded:: 2018.3.0

    Retrieve information about host public keys from remote server

    hostname
        The name of the remote host (e.g. "github.com")

    enc
        Defines what type of key is being used, can be ed25519, ecdsa,
        ssh-rsa, ssh-dss or any other type as of openssh server version 8.7.

    port
        Optional parameter, denoting the port of the remote host on which an
        SSH daemon is running. By default the port 22 is used.

    hash_known_hosts : True
        Hash all hostnames and addresses in the known hosts file.

    timeout : int
        Set the timeout for connection attempts.  If ``timeout`` seconds have
        elapsed since a connection was initiated to a host or since the last
        time anything was read from that host, then the connection is closed
        and the host in question considered unavailable.  Default is 5 seconds.

    fingerprint_hash_type
        The fingerprint hash type that the public key fingerprints were
        originally hashed with. This defaults to ``sha256`` if not specified.

        .. versionadded:: 2016.11.4
        .. versionchanged:: 2017.7.0

            default changed from ``md5`` to ``sha256``

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.recv_known_host_entries <hostname> enc=<enc> port=<port>
    """
    # The following list of OSes have an old version of openssh-clients
    # and thus require the '-t' option for ssh-keyscan
    need_dash_t = ("CentOS-5",)

    cmd = ["ssh-keyscan"]
    if port:
        cmd.extend(["-p", port])
    if enc:
        cmd.extend(["-t", enc])
    if not enc and __grains__.get("osfinger") in need_dash_t:
        cmd.extend(["-t", "rsa"])
    if hash_known_hosts:
        cmd.append("-H")
    cmd.extend(["-T", str(timeout)])
    cmd.append(hostname)
    lines = None
    attempts = 5
    while not lines and attempts > 0:
        attempts = attempts - 1
        lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    known_host_entries = list(
        _parse_openssh_output(lines, fingerprint_hash_type=fingerprint_hash_type)
    )
    return known_host_entries if known_host_entries else None


def check_known_host(
    user=None,
    hostname=None,
    key=None,
    fingerprint=None,
    config=None,
    port=None,
    fingerprint_hash_type=None,
):
    """
    Check the record in known_hosts file, either by its value or by fingerprint
    (it's enough to set up either key or fingerprint, you don't need to set up
    both).

    If provided key or fingerprint doesn't match with stored value, return
    "update", if no value is found for a given host, return "add", otherwise
    return "exists".

    If neither key, nor fingerprint is defined, then additional validation is
    not performed.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.check_known_host <user> <hostname> key='AAAA...FAaQ=='
    """
    if not hostname:
        return {"status": "error", "error": "hostname argument required"}
    if not user:
        config = config or "/etc/ssh/ssh_known_hosts"
    else:
        config = config or ".ssh/known_hosts"

    known_host_entries = get_known_host_entries(
        user,
        hostname,
        config=config,
        port=port,
        fingerprint_hash_type=fingerprint_hash_type,
    )
    known_keys = [h["key"] for h in known_host_entries] if known_host_entries else []
    known_fingerprints = (
        [h["fingerprint"] for h in known_host_entries] if known_host_entries else []
    )

    if not known_host_entries:
        return "add"
    if key:
        return "exists" if key in known_keys else "update"
    elif fingerprint:
        return "exists" if fingerprint in known_fingerprints else "update"
    else:
        return "exists"


def rm_known_host(user=None, hostname=None, config=None, port=None):
    """
    Remove all keys belonging to hostname from a known_hosts file.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.rm_known_host <user> <hostname>
    """
    if not hostname:
        return {"status": "error", "error": "hostname argument required"}

    full = _get_known_hosts_file(config=config, user=user)

    if isinstance(full, dict):
        return full

    if not os.path.isfile(full):
        return {
            "status": "error",
            "error": "Known hosts file {} does not exist".format(full),
        }

    ssh_hostname = _hostname_and_port_to_ssh_hostname(hostname, port)
    cmd = ["ssh-keygen", "-R", ssh_hostname, "-f", full]
    cmd_result = __salt__["cmd.run"](cmd, python_shell=False)
    if not salt.utils.platform.is_windows():
        # ssh-keygen creates a new file, thus a chown is required.
        if os.geteuid() == 0 and user:
            uinfo = __salt__["user.info"](user)
            os.chown(full, uinfo["uid"], uinfo["gid"])
    return {"status": "removed", "comment": cmd_result}


def set_known_host(
    user=None,
    hostname=None,
    fingerprint=None,
    key=None,
    port=None,
    enc=None,
    config=None,
    hash_known_hosts=True,
    timeout=5,
    fingerprint_hash_type=None,
):
    """
    Download SSH public key from remote host "hostname", optionally validate
    its fingerprint against "fingerprint" variable and save the record in the
    known_hosts file.

    If such a record does already exists in there, do nothing.

    user
        The user who owns the ssh authorized keys file to modify

    hostname
        The name of the remote host (e.g. "github.com")

    fingerprint
        The fingerprint of the key which must be present in the known_hosts
        file (optional if key specified)

    key
        The public key which must be presented in the known_hosts file
        (optional if fingerprint specified)

    port
        optional parameter, denoting the port of the remote host, which will be
        used in case, if the public key will be requested from it. By default
        the port 22 is used.

    enc
        Defines what type of key is being used, can be ed25519, ecdsa,
        ssh-rsa, ssh-dss or any other type as of openssh server version 8.7.

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/known_hosts". If no user is specified,
        defaults to "/etc/ssh/ssh_known_hosts". If present, must be an
        absolute path when a user is not specified.

    hash_known_hosts : True
        Hash all hostnames and addresses in the known hosts file.

    timeout : int
        Set the timeout for connection attempts.  If ``timeout`` seconds have
        elapsed since a connection was initiated to a host or since the last
        time anything was read from that host, then the connection is closed
        and the host in question considered unavailable.  Default is 5 seconds.

        .. versionadded:: 2016.3.0

    fingerprint_hash_type
        The public key fingerprint hash type that the public key fingerprint
        was originally hashed with. This defaults to ``sha256`` if not specified.

        .. versionadded:: 2016.11.4
        .. versionchanged:: 2017.7.0

            default changed from ``md5`` to ``sha256``

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_known_host <user> fingerprint='xx:xx:..:xx' enc='ssh-rsa' config='.ssh/known_hosts'
    """
    if not hostname:
        return {"status": "error", "error": "hostname argument required"}

    if port is not None and port != DEFAULT_SSH_PORT and hash_known_hosts:
        return {
            "status": "error",
            "error": (
                "argument port can not be used in "
                "conjunction with argument hash_known_hosts"
            ),
        }

    update_required = False
    check_required = False
    stored_host_entries = get_known_host_entries(
        user,
        hostname,
        config=config,
        port=port,
        fingerprint_hash_type=fingerprint_hash_type,
    )
    stored_keys = [h["key"] for h in stored_host_entries] if stored_host_entries else []
    stored_fingerprints = (
        [h["fingerprint"] for h in stored_host_entries] if stored_host_entries else []
    )

    if not stored_host_entries:
        update_required = True
    elif fingerprint and fingerprint not in stored_fingerprints:
        update_required = True
    elif key and key not in stored_keys:
        update_required = True
    elif key is None and fingerprint is None:
        check_required = True

    if not update_required and not check_required:
        return {"status": "exists", "keys": stored_keys}

    if not key:
        remote_host_entries = recv_known_host_entries(
            hostname,
            enc=enc,
            port=port,
            hash_known_hosts=hash_known_hosts,
            timeout=timeout,
            fingerprint_hash_type=fingerprint_hash_type,
        )
        # pylint: disable=not-an-iterable
        known_keys = (
            [h["key"] for h in remote_host_entries] if remote_host_entries else []
        )
        known_fingerprints = (
            [h["fingerprint"] for h in remote_host_entries]
            if remote_host_entries
            else []
        )
        # pylint: enable=not-an-iterable
        if not remote_host_entries:
            return {"status": "error", "error": "Unable to receive remote host keys"}

        if fingerprint and fingerprint not in known_fingerprints:
            return {
                "status": "error",
                "error": (
                    "Remote host public keys found but none of their "
                    "fingerprints match the one you have provided"
                ),
            }

        if check_required:
            for key in known_keys:
                if key in stored_keys:
                    return {"status": "exists", "keys": stored_keys}

    full = _get_known_hosts_file(config=config, user=user)

    if isinstance(full, dict):
        return full

    if os.path.isfile(full):
        origmode = os.stat(full).st_mode

        # remove existing known_host entry with matching hostname and encryption key type
        # use ssh-keygen -F to find the specific line(s) for this host + enc combo
        ssh_hostname = _hostname_and_port_to_ssh_hostname(hostname, port)
        cmd = ["ssh-keygen", "-F", ssh_hostname, "-f", full]
        lines = __salt__["cmd.run"](
            cmd, ignore_retcode=True, python_shell=False
        ).splitlines()
        remove_lines = list(_get_matched_host_line_numbers(lines, enc))

        if remove_lines:
            try:
                with salt.utils.files.fopen(full, "r+") as ofile:
                    known_hosts_lines = salt.utils.data.decode(list(ofile))
                    # Delete from last line to first to avoid invalidating earlier indexes
                    for line_no in sorted(remove_lines, reverse=True):
                        del known_hosts_lines[line_no - 1]
                    # Write out changed known_hosts file
                    ofile.seek(0)
                    ofile.truncate()
                    ofile.writelines(
                        salt.utils.data.decode(known_hosts_lines, to_str=True)
                    )
            except OSError as exception:
                raise CommandExecutionError(
                    "Couldn't remove old entry(ies) from known hosts file: '{}'".format(
                        exception
                    )
                )
    else:
        origmode = None

    # set up new value
    if key:
        remote_host_entries = [{"hostname": hostname, "enc": enc, "key": key}]

    lines = []
    for entry in remote_host_entries:
        if (
            hash_known_hosts
            or port in [DEFAULT_SSH_PORT, None]
            or ":" in entry["hostname"]
        ):
            line = "{hostname} {enc} {key}\n".format(**entry)
        else:
            entry["port"] = port
            line = "[{hostname}]:{port} {enc} {key}\n".format(**entry)
        lines.append(line)

    # ensure ~/.ssh exists
    ssh_dir = os.path.dirname(full)
    if user:
        uinfo = __salt__["user.info"](user)

    try:
        log.debug('Ensuring ssh config dir "%s" exists', ssh_dir)
        os.makedirs(ssh_dir)
    except OSError as exc:
        if exc.args[1] == "Permission denied":
            log.error("Unable to create directory %s: %s", ssh_dir, exc.args[1])
        elif exc.args[1] == "File exists":
            log.debug("%s already exists, no need to create it", ssh_dir)
    else:
        # set proper ownership/permissions
        if user:
            os.chown(ssh_dir, uinfo["uid"], uinfo["gid"])
            os.chmod(ssh_dir, 0o700)

    # write line to known_hosts file
    try:
        with salt.utils.files.fopen(full, "ab") as ofile:
            ofile.writelines(salt.utils.data.encode(lines))
    except OSError as exception:
        raise CommandExecutionError(
            "Couldn't append to known hosts file: '{}'".format(exception)
        )

    if not salt.utils.platform.is_windows():
        if os.geteuid() == 0 and user:
            os.chown(full, uinfo["uid"], uinfo["gid"])
        if origmode:
            os.chmod(full, origmode)
        else:
            os.chmod(full, 0o600)

    if key and hash_known_hosts:
        cmd_result = __salt__["ssh.hash_known_hosts"](user=user, config=full)

    rval = {"status": "updated", "old": stored_host_entries, "new": remote_host_entries}
    return rval


def user_keys(user=None, pubfile=None, prvfile=None):
    """

    Return the user's ssh keys on the minion

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.user_keys
        salt '*' ssh.user_keys user=user1
        salt '*' ssh.user_keys user=user1 pubfile=/home/user1/.ssh/id_rsa.pub prvfile=/home/user1/.ssh/id_rsa
        salt '*' ssh.user_keys user=user1 prvfile=False
        salt '*' ssh.user_keys user="['user1','user2'] pubfile=id_rsa.pub prvfile=id_rsa

    As you can see you can tell Salt not to read from the user's private (or
    public) key file by setting the file path to ``False``. This can be useful
    to prevent Salt from publishing private data via Salt Mine or others.
    """
    if not user:
        user = __salt__["user.list_users"]()

    if not isinstance(user, list):
        # only one so convert to list
        user = [user]

    keys = {}
    for u in user:
        keys[u] = {}
        userinfo = __salt__["user.info"](u)

        if "home" not in userinfo:
            # no home directory, skip
            continue

        userKeys = []

        if pubfile:
            userKeys.append(pubfile)
        elif pubfile is not False:
            # Add the default public keys
            userKeys += ["id_rsa.pub", "id_dsa.pub", "id_ecdsa.pub", "id_ed25519.pub"]

        if prvfile:
            userKeys.append(prvfile)
        elif prvfile is not False:
            # Add the default private keys
            userKeys += ["id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"]

        for key in userKeys:
            if key.startswith("/"):
                keyname = os.path.basename(key)
                fn_ = key
            else:
                # if not full path, assume key is in .ssh
                # in user's home directory
                keyname = key
                fn_ = "{}/.ssh/{}".format(userinfo["home"], key)

            if os.path.exists(fn_):
                try:
                    with salt.utils.files.fopen(fn_, "r") as _fh:
                        keys[u][keyname] = "".join(
                            salt.utils.data.decode(_fh.readlines())
                        ).strip()
                except OSError:
                    pass

    # clean up any empty items
    _keys = {}
    for key in keys:
        if keys[key]:
            _keys[key] = keys[key]
    return _keys


@salt.utils.decorators.path.which("ssh-keygen")
def hash_known_hosts(user=None, config=None):
    """

    Hash all the hostnames in the known hosts file.

    .. versionadded:: 2014.7.0

    user
        hash known hosts of this user

    config
        path to known hosts file: can be absolute or relative to user's home
        directory

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.hash_known_hosts

    """
    full = _get_known_hosts_file(config=config, user=user)

    if isinstance(full, dict):
        return full  # full contains error information

    if not os.path.isfile(full):
        return {
            "status": "error",
            "error": "Known hosts file {} does not exist".format(full),
        }
    origmode = os.stat(full).st_mode
    cmd = ["ssh-keygen", "-H", "-f", full]
    cmd_result = __salt__["cmd.run"](cmd, python_shell=False)
    os.chmod(full, origmode)
    if not salt.utils.platform.is_windows():
        # ssh-keygen creates a new file, thus a chown is required.
        if os.geteuid() == 0 and user:
            uinfo = __salt__["user.info"](user)
            os.chown(full, uinfo["uid"], uinfo["gid"])
    return {"status": "updated", "comment": cmd_result}


def _hostname_and_port_to_ssh_hostname(hostname, port=DEFAULT_SSH_PORT):
    if not port or port == DEFAULT_SSH_PORT:
        return hostname
    else:
        return "[{}]:{}".format(hostname, port)


def key_is_encrypted(key):
    """
    .. versionadded:: 2015.8.7

    Function to determine whether or not a private key is encrypted with a
    passphrase.

    Checks key for a ``Proc-Type`` header with ``ENCRYPTED`` in the value. If
    found, returns ``True``, otherwise returns ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.key_is_encrypted /root/id_rsa
    """
    return __utils__["ssh.key_is_encrypted"](key)
