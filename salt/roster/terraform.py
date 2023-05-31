"""
Dynamic roster from terraform current state
===========================================

This roster module allows you dynamically generate the roster from the terraform
resources defined with the `Terraform Salt`_ provider.

It exposes all salt_host resources with the same attributes to the salt-ssh
roster, making it completely independent of the type of terraform resource, and
providing the integration using terraform constructs with interpolation.

Basic Example
-------------

Given a simple salt-ssh tree with a Saltfile:

.. code-block:: yaml

    salt-ssh:
      config_dir: etc/salt
      max_procs: 30
      wipe_ssh: True

and ``etc/salt/master``:

.. code-block:: yaml

    root_dir: .
      file_roots:
        base:
          - srv/salt
      pillar_roots:
        base:
          - srv/pillar
      roster: terraform

In the same folder as your ``Saltfile``, create terraform file with resources
like cloud instances, virtual machines, etc. For every single one of those that
you want to manage with Salt, create a ``salt_host`` resource:

.. code-block:: text

    resource "salt_host" "dbminion" {
      salt_id = "dbserver"
      host = "${libvirt_domain.vm-db.network_interface.0.addresses.0}"
      user = "root"
      passwd = "linux"
    }

You can use the count attribute to create multiple roster entries with a single
definition. Please refer to the `Terraform Salt`_ provider for more detailed
examples.

.. _Terraform Salt: https://github.com/dmacvicar/terraform-provider-salt
"""

import logging
import os.path

import salt.utils.files
import salt.utils.json

log = logging.getLogger(__name__)

TF_OUTPUT_PREFIX = "salt.roster."
TF_ROSTER_ATTRS = {
    "host": "s",
    "user": "s",
    "passwd": "s",
    "port": "i",
    "sudo": "b",
    "sudo_user": "s",
    "tty": "b",
    "priv": "s",
    "timeout": "i",
    "minion_opts": "m",
    "thin_dir": "s",
    "cmd_umask": "i",
}
MINION_ID = "salt_id"


def _handle_old_salt_host_resource(resource):
    """
    Handles salt_host resources.
    See https://github.com/dmacvicar/terraform-provider-salt

    Returns roster attributes for the resource or None
    """
    ret = {}
    attrs = resource.get("primary", {}).get("attributes", {})
    ret[MINION_ID] = attrs.get(MINION_ID)
    valid_attrs = set(attrs.keys()).intersection(TF_ROSTER_ATTRS.keys())
    for attr in valid_attrs:
        ret[attr] = _cast_output_to_type(
            attr, attrs.get(attr), TF_ROSTER_ATTRS.get(attr)
        )
    return ret


def _handle_new_salt_host_resource(resource):
    """
    Handles salt_host resources.
    See https://github.com/dmacvicar/terraform-provider-salt
    Returns roster attributes for the resource or None
    """
    rets = []
    instances = resource.get("instances", [])
    for instance in instances:
        ret = {}
        attrs = instance.get("attributes", {})
        ret[MINION_ID] = attrs.get(MINION_ID)
        valid_attrs = set(attrs.keys()).intersection(TF_ROSTER_ATTRS.keys())
        for attr in valid_attrs:
            ret[attr] = _cast_output_to_type(
                attr, attrs.get(attr), TF_ROSTER_ATTRS.get(attr)
            )
        log.info(ret)
        rets.append(ret)
    return rets


def _add_ssh_key(ret):
    """
    Setups the salt-ssh minion to be accessed with salt-ssh default key
    """
    priv = None
    if __opts__.get("ssh_use_home_key") and os.path.isfile(
        os.path.expanduser("~/.ssh/id_rsa")
    ):
        priv = os.path.expanduser("~/.ssh/id_rsa")
    else:
        priv = __opts__.get(
            "ssh_priv",
            os.path.abspath(os.path.join(__opts__["pki_dir"], "ssh", "salt-ssh.rsa")),
        )
    if priv and os.path.isfile(priv):
        ret["priv"] = priv


def _cast_output_to_type(attr, value, typ):
    """cast the value depending on the terraform type"""
    if value is None:
        # Timeout needs to default to 0 if the value is None
        # The ssh command that is run cannot handle `-o ConnectTimeout=None`
        if attr == "timeout":
            return 0
        else:
            return value

    if value is None:
        return value
    if typ == "b":
        return bool(value)
    if typ == "i":
        return int(value)
    return value


def _parse_state_file(state_file_path="terraform.tfstate"):
    """
    Parses the terraform state file passing different resource types to the right handler
    """
    with salt.utils.files.fopen(state_file_path, "r") as fh_:
        tfstate = salt.utils.json.load(fh_)
    if "resources" in tfstate:
        return _do_parse_new_state_file(tfstate)
    elif "modules" in tfstate:
        return _do__parse_old_state_file(tfstate)
    else:
        log.error("Malformed tfstate file.")
        return {}


def _do_parse_new_state_file(tfstate):
    """
    Parses the terraform state file passing different resource types to the right handler  terraform version >= v0.13.0
    """
    ret = {}
    resources = tfstate.get("resources")
    if not resources:
        log.error("Malformed tfstate file. No resources found")
        return ret
    for resource in resources:
        if resource["type"] == "salt_host":
            roster_entrys = _handle_new_salt_host_resource(resource)

            if not roster_entrys or len(roster_entrys) < 1:
                continue
            for roster_entry in roster_entrys:
                if not roster_entry:
                    continue

                minion_id = roster_entry.get(MINION_ID, resource.get("id"))
                if not minion_id:
                    continue

                if MINION_ID in roster_entry:
                    del roster_entry[MINION_ID]
                _add_ssh_key(roster_entry)
                ret[minion_id] = roster_entry
    return ret


def _do__parse_old_state_file(tfstate):
    """
    Parses the terraform state file passing different resource types to the right handler  terraform version < v0.13.0
    """
    ret = {}
    modules = tfstate.get("modules")
    if not modules:
        log.error("Malformed tfstate file. No modules found")
        return ret

    for module in modules:
        resources = module.get("resources", [])
        for resource_name, resource in resources.items():
            roster_entry = None
            if resource["type"] == "salt_host":
                roster_entry = _handle_old_salt_host_resource(resource)

            if not roster_entry:
                continue

            minion_id = roster_entry.get(MINION_ID, resource.get("id"))
            if not minion_id:
                continue

            if MINION_ID in roster_entry:
                del roster_entry[MINION_ID]
            _add_ssh_key(roster_entry)
            ret[minion_id] = roster_entry
    return ret


def targets(tgt, tgt_type="glob", **kwargs):  # pylint: disable=W0613
    """
    Returns the roster from the terraform state file, checks opts for location, but defaults to terraform.tfstate
    """
    roster_file = os.path.abspath("terraform.tfstate")
    if __opts__.get("roster_file"):
        roster_file = os.path.abspath(__opts__["roster_file"])

    if not os.path.isfile(roster_file):
        log.error("Can't find terraform state file '%s'", roster_file)
        return {}

    log.debug("terraform roster: using %s state file", roster_file)

    if not roster_file.endswith(".tfstate"):
        log.error("Terraform roster can only be used with terraform state files")
        return {}

    raw = _parse_state_file(roster_file)
    log.debug("%s hosts in terraform state file", len(raw))
    return __utils__["roster_matcher.targets"](raw, tgt, tgt_type, "ipv4")
