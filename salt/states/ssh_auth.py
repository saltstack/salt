"""
Control of entries in SSH authorized_key files
==============================================

The information stored in a user's SSH authorized key file can be easily
controlled via the ssh_auth state. Defaults can be set by the enc, options,
and comment keys. These defaults can be overridden by including them in the
name.

Since the YAML specification limits the length of simple keys to 1024
characters, and since SSH keys are often longer than that, you may have
to use a YAML 'explicit key', as demonstrated in the second example below.

.. code-block:: yaml

    AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY==:
      ssh_auth.present:
        - user: root
        - enc: ssh-dss

    ? AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY==...
    :
      ssh_auth.present:
        - user: root
        - enc: ssh-dss

    thatch:
      ssh_auth.present:
        - user: root
        - source: salt://ssh_keys/thatch.id_rsa.pub
        - config: '%h/.ssh/authorized_keys'

    sshkeys:
      ssh_auth.present:
        - user: root
        - enc: ssh-rsa
        - options:
          - option1="value1"
          - option2="value2 flag2"
        - comment: myuser
        - names:
          - AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY==
          - ssh-dss AAAAB3NzaCL0sQ9fJ5bYTEyY== user@domain
          - option3="value3" ssh-dss AAAAB3NzaC1kcQ9J5bYTEyY== other@testdomain
          - AAAAB3NzaC1kcQ9fJFF435bYTEyY== newcomment

    sshkeys:
      ssh_auth.manage:
        - user: root
        - enc: ssh-rsa
        - options:
          - option1="value1"
          - option2="value2 flag2"
        - comment: myuser
        - ssh_keys:
          - AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY==
          - ssh-dss AAAAB3NzaCL0sQ9fJ5bYTEyY== user@domain
          - option3="value3" ssh-dss AAAAB3NzaC1kcQ9J5bYTEyY== other@testdomain
          - AAAAB3NzaC1kcQ9fJFF435bYTEyY== newcomment
"""


import re
import sys

sshre = re.compile(
    r"((?P<options>.*?)\s)?"
    r"(?P<keytype>\S+?-\S+?|ed25519|ecdsa)\s"
    r"(?P<key>[0-9A-Za-z/+]+={0,2})"
    r"(\s(?P<comment>.+))?"
)


def _present_test(
    user, name, enc, comment, options, source, config, fingerprint_hash_type
):
    """
    Run checks for "present"
    """
    result = None
    if source:
        keys = __salt__["ssh.check_key_file"](
            user,
            source,
            config,
            saltenv=__env__,
            fingerprint_hash_type=fingerprint_hash_type,
        )
        if keys:
            comment = ""
            for key, status in keys.items():
                if status == "exists":
                    continue
                comment += "Set to {}: {}\n".format(status, key)
            if comment:
                return result, comment
        err = sys.modules[__salt__["test.ping"].__module__].__context__.pop(
            "ssh_auth.error", None
        )
        if err:
            return False, err
        else:
            return (
                True,
                "All host keys in file {} are already present".format(source),
            )
    else:
        fullkey = _parse_line(name)
        name = fullkey.get("key", name)
        enc = fullkey.get("keytype", enc)
        comment = fullkey.get("comment", comment)
        options = fullkey.get("options", options)

    check = __salt__["ssh.check_key"](
        user,
        name,
        enc,
        comment,
        options,
        config=config,
        fingerprint_hash_type=fingerprint_hash_type,
    )
    if check == "update":
        comment = "Key {} for user {} is set to be updated".format(name, user)
    elif check == "add":
        comment = "Key {} for user {} is set to be added".format(name, user)
    elif check == "exists":
        result = True
        comment = "The authorized host key {} is already present for user {}".format(
            name, user
        )

    return result, comment


def _absent_test(
    user, name, enc, comment, options, source, config, fingerprint_hash_type
):
    """
    Run checks for "absent"
    """
    result = None
    if source:
        keys = __salt__["ssh.check_key_file"](
            user,
            source,
            config,
            saltenv=__env__,
            fingerprint_hash_type=fingerprint_hash_type,
        )
        if keys:
            comment = ""
            for key, status in list(keys.items()):
                if status == "add":
                    continue
                comment += "Set to remove: {}\n".format(key)
            if comment:
                return result, comment
        err = sys.modules[__salt__["test.ping"].__module__].__context__.pop(
            "ssh_auth.error", None
        )
        if err:
            return False, err
        else:
            return (True, "All host keys in file {} are already absent".format(source))
    else:
        fullkey = _parse_line(name)
        name = fullkey.get("key", name)
        enc = fullkey.get("keytype", enc)
        comment = fullkey.get("comment", comment)
        options = fullkey.get("options", options)

    check = __salt__["ssh.check_key"](
        user,
        name,
        enc,
        comment,
        options,
        config=config,
        fingerprint_hash_type=fingerprint_hash_type,
    )
    if check == "update" or check == "exists":
        comment = "Key {} for user {} is set for removal".format(name, user)
    else:
        comment = "Key is already absent"
        result = True

    return result, comment


def _parse_line(line):
    """
    Attempt to parse a protocol version 2 authorized_keys line.

    Allows non-standard keytype extensions like sk-ssh-ed25519@openssh.com.
    """
    if line is None or line == "" or line[0] == "#":
        return {}

    match = sshre.fullmatch(line)
    if not match:
        # the key is probably not valid, but try anyway
        key_and_comment = line.split(maxsplit=1)
        ret = {"key": key_and_comment[0], "comment": key_and_comment.get(1)}
    else:
        ret = match.groupdict()
        if ret["options"] is not None:
            ret["options"] = ret["options"].split(",")
    return {k: v for k, v in ret.items() if v is not None}


def present(
    name,
    user,
    enc="ssh-rsa",
    comment="",
    source="",
    options=None,
    config=".ssh/authorized_keys",
    fingerprint_hash_type=None,
    **kwargs
):
    """
    Verifies that the specified SSH key is present for the specified user

    name
        The SSH key to manage

    user
        The user who owns the SSH authorized keys file to modify

    enc
        Defines what type of key is being used, can be ed25519, ecdsa,
        ssh-rsa, ssh-dss or any other type as of openssh server version 8.7.

    comment
        The comment to be placed with the SSH public key

    source
        The source file for the key(s). Can contain any number of public keys,
        in standard "authorized_keys" format. If this is set, comment and enc
        will be ignored.

    .. note::
        The source file must contain keys in the format ``<enc> <key>
        <comment>``. If you have generated a keypair using PuTTYgen, then you
        will need to do the following to retrieve an OpenSSH-compatible public
        key.

        1. In PuTTYgen, click ``Load``, and select the *private* key file (not
           the public key), and click ``Open``.
        2. Copy the public key from the box labeled ``Public key for pasting
           into OpenSSH authorized_keys file``.
        3. Paste it into a new file.

    options
        The options passed to the key, pass a list object

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/authorized_keys". Token expansion %u and
        %h for username and home path supported.

    fingerprint_hash_type
        The public key fingerprint hash type that the public key fingerprint
        was originally hashed with. This defaults to ``sha256`` if not specified.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if source == "":
        fullkey = _parse_line(name)
        name = fullkey.get("key", name)
        enc = fullkey.get("keytype", enc)
        comment = fullkey.get("comment", comment)
        options = fullkey.get("options", options)

    if __opts__["test"]:
        ret["result"], ret["comment"] = _present_test(
            user,
            name,
            enc,
            comment,
            options or [],
            source,
            config,
            fingerprint_hash_type,
        )
        return ret

    # Get only the path to the file without env referrences to check if exists
    if source != "":
        source_path = __salt__["cp.get_url"](source, None, saltenv=__env__)

    if source != "" and not source_path:
        data = "no key"
    elif source != "" and source_path:
        keys = __salt__["cp.get_file_str"](source, saltenv=__env__).rstrip().split("\n")
        for key_line in keys:
            key_data = _parse_line(key_line)
            if "key" not in key_data:
                continue
            elif "options" not in key_data:
                data = __salt__["ssh.set_auth_key_from_file"](
                    user,
                    source,
                    config=config,
                    saltenv=__env__,
                    fingerprint_hash_type=fingerprint_hash_type,
                )
            else:
                data = __salt__["ssh.set_auth_key"](
                    user,
                    key_data["key"],
                    enc=key_data.get("keytype"),
                    comment=key_data.get("comment", ""),
                    options=options or [],
                    config=config,
                    fingerprint_hash_type=fingerprint_hash_type,
                )
    else:
        data = __salt__["ssh.set_auth_key"](
            user,
            name,
            enc=enc,
            comment=comment,
            options=options or [],
            config=config,
            fingerprint_hash_type=fingerprint_hash_type,
        )

    if data == "replace":
        ret["changes"][name] = "Updated"
        ret["comment"] = "The authorized host key {} for user {} was updated".format(
            name, user
        )
        return ret
    elif data == "no change":
        ret[
            "comment"
        ] = "The authorized host key {} is already present for user {}".format(
            name, user
        )
    elif data == "new":
        ret["changes"][name] = "New"
        ret["comment"] = "The authorized host key {} for user {} was added".format(
            name, user
        )
    elif data == "no key":
        ret["result"] = False
        ret["comment"] = "Failed to add the ssh key. Source file {} is missing".format(
            source
        )
    elif data == "fail":
        ret["result"] = False
        err = sys.modules[__salt__["test.ping"].__module__].__context__.pop(
            "ssh_auth.error", None
        )
        if err:
            ret["comment"] = err
        else:
            ret["comment"] = (
                "Failed to add the ssh key. Is the home "
                "directory available, and/or does the key file "
                "exist?"
            )
    elif data == "invalid" or data == "Invalid public key":
        ret["result"] = False
        ret[
            "comment"
        ] = "Invalid public ssh key, most likely has spaces or invalid syntax"

    return ret


def absent(
    name,
    user,
    enc="ssh-rsa",
    comment="",
    source="",
    options=None,
    config=".ssh/authorized_keys",
    fingerprint_hash_type=None,
):
    """
    Verifies that the specified SSH key is absent

    name
        The SSH key to manage

    user
        The user who owns the SSH authorized keys file to modify

    enc
        Defines what type of key is being used, can be ed25519, ecdsa,
        ssh-rsa, ssh-dss or any other type as of openssh server version 8.7.

    comment
        The comment to be placed with the SSH public key

    options
        The options passed to the key, pass a list object

    source
        The source file for the key(s). Can contain any number of public keys,
        in standard "authorized_keys" format. If this is set, comment, enc and
        options will be ignored.

        .. versionadded:: 2015.8.0

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/authorized_keys". Token expansion %u and
        %h for username and home path supported.

    fingerprint_hash_type
        The public key fingerprint hash type that the public key fingerprint
        was originally hashed with. This defaults to ``sha256`` if not specified.

        .. versionadded:: 2016.11.7
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if __opts__["test"]:
        ret["result"], ret["comment"] = _absent_test(
            user,
            name,
            enc,
            comment,
            options or [],
            source,
            config,
            fingerprint_hash_type,
        )
        return ret

    # Extract Key from file if source is present
    if source != "":
        keys = __salt__["cp.get_file_str"](source, saltenv=__env__).rstrip().split("\n")
        for key_line in keys:
            key_data = _parse_line(key_line)
            if "key" not in key_data:
                continue
            elif "options" not in key_data:
                ret["comment"] = __salt__["ssh.rm_auth_key_from_file"](
                    user,
                    source,
                    config,
                    saltenv=__env__,
                    fingerprint_hash_type=fingerprint_hash_type,
                )
            else:
                ret["comment"] = __salt__["ssh.rm_auth_key"](
                    user,
                    key_data["key"],
                    config=config,
                    fingerprint_hash_type=fingerprint_hash_type,
                )
    else:
        # Get just the key
        name = _parse_line(name).get("key", name)
        ret["comment"] = __salt__["ssh.rm_auth_key"](
            user, name, config=config, fingerprint_hash_type=fingerprint_hash_type
        )

    if ret["comment"] == "User authorized keys file not present":
        ret["result"] = False
        return ret
    elif ret["comment"] == "Key removed":
        ret["changes"][name] = "Removed"

    return ret


def manage(
    name,
    ssh_keys,
    user,
    enc="ssh-rsa",
    comment="",
    source="",
    options=None,
    config=".ssh/authorized_keys",
    fingerprint_hash_type=None,
    **kwargs
):
    """
    .. versionadded:: 3000

    Ensures that only the specified ssh_keys are present for the specified user

    ssh_keys
        The SSH key to manage

    user
        The user who owns the SSH authorized keys file to modify

    enc
        Defines what type of key is being used, can be ed25519, ecdsa,
        ssh-rsa, ssh-dss or any other type as of openssh server version 8.7.

    comment
        The comment to be placed with the SSH public key

    source
        The source file for the key(s). Can contain any number of public keys,
        in standard "authorized_keys" format. If this is set, comment and enc
        will be ignored.

    .. note::
        The source file must contain keys in the format ``<enc> <key>
        <comment>``. If you have generated a keypair using PuTTYgen, then you
        will need to do the following to retrieve an OpenSSH-compatible public
        key.

        1. In PuTTYgen, click ``Load``, and select the *private* key file (not
           the public key), and click ``Open``.
        2. Copy the public key from the box labeled ``Public key for pasting
           into OpenSSH authorized_keys file``.
        3. Paste it into a new file.

    options
        The options passed to the keys, pass a list object

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/authorized_keys". Token expansion %u and
        %h for username and home path supported.

    fingerprint_hash_type
        The public key fingerprint hash type that the public key fingerprint
        was originally hashed with. This defaults to ``sha256`` if not specified.
    """
    ret = {"name": "", "changes": {}, "result": True, "comment": ""}

    all_potential_keys = []
    for ssh_key in ssh_keys:
        # gather list potential ssh keys for removal comparison
        # options, enc, and comments could be in the mix
        all_potential_keys.extend(ssh_key.split(" "))
    existing_keys = __salt__["ssh.auth_keys"](user=user).keys()
    remove_keys = set(existing_keys).difference(all_potential_keys)
    for remove_key in remove_keys:
        if __opts__["test"]:
            remove_comment = "{} Key set for removal".format(remove_key)
            ret["comment"] = remove_comment
            ret["result"] = None
        else:
            remove_comment = absent(remove_key, user)["comment"]
            ret["changes"][remove_key] = remove_comment

    for ssh_key in ssh_keys:
        run_return = present(
            ssh_key,
            user,
            enc,
            comment,
            source,
            options,
            config,
            fingerprint_hash_type,
            **kwargs
        )
        if run_return["changes"]:
            ret["changes"].update(run_return["changes"])
        else:
            ret["comment"] += "\n" + run_return["comment"]
            ret["comment"] = ret["comment"].strip()

        if run_return["result"] is None:
            ret["result"] = None
        elif not run_return["result"]:
            ret["result"] = False

    return ret
