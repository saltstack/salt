"""
State management of a java keystore
"""


import logging
import os

__virtualname__ = "keystore"

# Init logger
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load this module if the keystore execution module is available
    """
    if "keystore.list" in __salt__:
        return __virtualname__
    return (
        False,
        "Cannot load the {} state module: keystore execution module not found".format(
            __virtualname__
        ),
    )


def managed(name, passphrase, entries, force_remove=False):
    """
    Create or manage a java keystore.

    name
        The path to the keystore file

    passphrase
        The password to the keystore

    entries
        A list containing an alias, certificate, and optional private_key.
        The certificate and private_key can be a file or a string

        .. code-block:: yaml

            - entries:
              - alias: hostname2
                certificate: /path/to/cert.crt
                private_key: /path/to/key.key
              - alias: stringhost
                certificate: |
                  -----BEGIN CERTIFICATE-----
                  MIICEjCCAXsCAg36MA0GCSqGSIb3DQEBBQUAMIGbMQswCQYDVQQGEwJKUDEOMAwG
                  ...
                  2VguKv4SWjRFoRkIfIlHX0qVviMhSlNy2ioFLy7JcPZb+v3ftDGywUqcBiVDoea0
                  -----END CERTIFICATE-----

    force_remove
        If True will cause the state to remove any entries found in the keystore which are not
        defined in the state. The default is False.

    Example

    .. code-block:: yaml

        define_keystore:
          keystore.managed:
            - name: /path/to/keystore
            - passphrase: changeit
            - force_remove: True
            - entries:
              - alias: hostname1
                certificate: /path/to/cert.crt
              - alias: remotehost
                certificate: /path/to/cert2.crt
                private_key: /path/to/key2.key
              - alias: pillarhost
                certificate: {{ salt.pillar.get('path:to:cert') }}
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    keep_list = []
    old_aliases = []

    if force_remove:
        if os.path.exists(name):
            existing_entries = __salt__["keystore.list"](name, passphrase)
            for entry in existing_entries:
                old_aliases.append(entry.get("alias"))
            log.debug("Existing aliases list: %s", old_aliases)

    for entry in entries:
        update_entry = True
        existing_entry = None
        if os.path.exists(name):
            if force_remove:
                keep_list.append(entry["alias"])

            existing_entry = __salt__["keystore.list"](name, passphrase, entry["alias"])
            if existing_entry:
                existing_sha1 = existing_entry[0]["sha1"]
                new_sha1 = __salt__["x509.read_certificate"](entry["certificate"])[
                    "SHA1 Finger Print"
                ]
                if existing_sha1 == new_sha1:
                    update_entry = False

        if update_entry:
            if __opts__["test"]:
                ret["result"] = None
                if existing_entry:
                    ret["comment"] += "Alias {} would have been updated\n".format(
                        entry["alias"]
                    )
                else:
                    ret["comment"] += "Alias {} would have been added\n".format(
                        entry["alias"]
                    )
            else:
                if existing_entry:
                    result = __salt__["keystore.remove"](
                        entry["alias"], name, passphrase
                    )
                    result = __salt__["keystore.add"](
                        entry["alias"],
                        name,
                        passphrase,
                        entry["certificate"],
                        private_key=entry.get("private_key", None),
                    )
                    if result:
                        ret["changes"][entry["alias"]] = "Updated"
                        ret["comment"] += "Alias {} updated.\n".format(entry["alias"])
                else:
                    result = __salt__["keystore.add"](
                        entry["alias"],
                        name,
                        passphrase,
                        entry["certificate"],
                        private_key=entry.get("private_key", None),
                    )
                    if result:
                        ret["changes"][entry["alias"]] = "Added"
                        ret["comment"] += "Alias {} added.\n".format(entry["alias"])

    if force_remove:
        # Determine which aliases need to be removed
        remove_list = list(set(old_aliases) - set(keep_list))
        log.debug("Will remove: %s", remove_list)
        for alias_name in remove_list:
            if __opts__["test"]:
                ret["comment"] += "Alias {} would have been removed".format(alias_name)
                ret["result"] = None
            else:
                __salt__["keystore.remove"](alias_name, name, passphrase)
                ret["changes"][alias_name] = "Removed"
                ret["comment"] += "Alias {} removed.\n".format(alias_name)

    if not ret["changes"] and not ret["comment"]:
        ret["comment"] = "No changes made.\n"
    return ret
