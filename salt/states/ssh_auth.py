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
        # check if this is of form {options} {enc} {key} {comment}
        sshre = re.compile(r"^(.*?)\s?((?:ssh\-|ecds)[\w-]+\s.+)$")
        fullkey = sshre.search(name)
        # if it is {key} [comment]
        if not fullkey:
            key_and_comment = name.split()
            name = key_and_comment[0]
            if len(key_and_comment) == 2:
                comment = key_and_comment[1]
        else:
            # if there are options, set them
            if fullkey.group(1):
                options = fullkey.group(1).split(",")
            # key is of format: {enc} {key} [comment]
            comps = fullkey.group(2).split()
            enc = comps[0]
            name = comps[1]
            if len(comps) == 3:
                comment = comps[2]

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
        # check if this is of form {options} {enc} {key} {comment}
        sshre = re.compile(r"^(.*?)\s?((?:ssh\-|ecds)[\w-]+\s.+)$")
        fullkey = sshre.search(name)
        # if it is {key} [comment]
        if not fullkey:
            key_and_comment = name.split()
            name = key_and_comment[0]
            if len(key_and_comment) == 2:
                comment = key_and_comment[1]
        else:
            # if there are options, set them
            if fullkey.group(1):
                options = fullkey.group(1).split(",")
            # key is of format: {enc} {key} [comment]
            comps = fullkey.group(2).split()
            enc = comps[0]
            name = comps[1]
            if len(comps) == 3:
                comment = comps[2]

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
        Defines what type of key is being used; can be ed25519, ecdsa, ssh-rsa
        or ssh-dss

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
        # check if this is of form {options} {enc} {key} {comment}
        sshre = re.compile(r"^(.*?)\s?((?:ssh\-|ecds)[\w-]+\s.+)$")
        fullkey = sshre.search(name)
        # if it is {key} [comment]
        if not fullkey:
            key_and_comment = name.split(None, 1)
            name = key_and_comment[0]
            if len(key_and_comment) == 2:
                comment = key_and_comment[1]
        else:
            # if there are options, set them
            if fullkey.group(1):
                options = fullkey.group(1).split(",")
            # key is of format: {enc} {key} [comment]
            comps = fullkey.group(2).split(None, 2)
            enc = comps[0]
            name = comps[1]
            if len(comps) == 3:
                comment = comps[2]

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
        key = __salt__["cp.get_file_str"](source, saltenv=__env__)
        filehasoptions = False
        # check if this is of form {options} {enc} {key} {comment}
        sshre = re.compile(r"^(ssh\-|ecds).*")
        key = key.rstrip().split("\n")
        for keyline in key:
            filehasoptions = sshre.match(keyline)
            if not filehasoptions:
                data = __salt__["ssh.set_auth_key_from_file"](
                    user,
                    source,
                    config=config,
                    saltenv=__env__,
                    fingerprint_hash_type=fingerprint_hash_type,
                )
            else:
                # Split keyline to get key and comment
                keyline = keyline.split(" ")
                key_type = keyline[0]
                key_value = keyline[1]
                key_comment = keyline[2] if len(keyline) > 2 else ""
                data = __salt__["ssh.set_auth_key"](
                    user,
                    key_value,
                    enc=key_type,
                    comment=key_comment,
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
        Defines what type of key is being used; can be ed25519, ecdsa, ssh-rsa
        or ssh-dss

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
        key = __salt__["cp.get_file_str"](source, saltenv=__env__)
        filehasoptions = False
        # check if this is of form {options} {enc} {key} {comment}
        sshre = re.compile(r"^(ssh\-|ecds).*")
        key = key.rstrip().split("\n")
        for keyline in key:
            filehasoptions = sshre.match(keyline)
            if not filehasoptions:
                ret["comment"] = __salt__["ssh.rm_auth_key_from_file"](
                    user,
                    source,
                    config,
                    saltenv=__env__,
                    fingerprint_hash_type=fingerprint_hash_type,
                )
            else:
                # Split keyline to get key
                keyline = keyline.split(" ")
                ret["comment"] = __salt__["ssh.rm_auth_key"](
                    user,
                    keyline[1],
                    config=config,
                    fingerprint_hash_type=fingerprint_hash_type,
                )
    else:
        # Get just the key
        sshre = re.compile(r"^(.*?)\s?((?:ssh\-|ecds)[\w-]+\s.+)$")
        fullkey = sshre.search(name)
        # if it is {key} [comment]
        if not fullkey:
            key_and_comment = name.split(None, 1)
            name = key_and_comment[0]
            if len(key_and_comment) == 2:
                comment = key_and_comment[1]
        else:
            # if there are options, set them
            if fullkey.group(1):
                options = fullkey.group(1).split(",")
            # key is of format: {enc} {key} [comment]
            comps = fullkey.group(2).split()
            enc = comps[0]
            name = comps[1]
            if len(comps) == 3:
                comment = comps[2]
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
        Defines what type of key is being used; can be ed25519, ecdsa, ssh-rsa
        or ssh-dss

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
