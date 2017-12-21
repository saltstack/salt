# -*- coding: utf-8 -*-
'''
Dynamic roster from terraform current state
===========================================

Currently supports libvirt and AWS resources.
(For libvirt support in terraform, see https://github.com/dmacvicar/terraform-provider-libvirt)

Roster values
-------------

Unless you override any of the values, the following values are used::

Minion ID
  The name is used (`name` attribute for libvirt, `Name` tag on AWS).
  If not available, the resource id is used.

`host`
  For libvirt resources, first address of the first interface is used.
  For AWS resources, the public_dns or the public_ip attributes are used.

`priv`
  If `ssh_use_home_key` config option is enabled and `~/.ssh/id_rsa'` exists, it will be used.
  Otherwise `ssh/salt-ssh.rsa` in `pki_dir` configuration option will be used.

Overriding values
-----------------

An output variable named `salt.roster.VARNAME` in a module would override the `VARNAME` roster
attribute for all resources of that module.

.. code-block:: hcl

    output "salt.roster.priv" {
      value = "/path/to/id_rsa"
    }

An output variable named `salt.roster.VARNAME.RESOURCENAME` in a module would override the `VARNAME` roster
attribute for resource `RESOURCENAME` of that module.

.. code-block:: hcl

    output "salt.roster.priv.libvirt_domain.domain.1" {
      value = "/path/to/id_rsa"
    }

Basic Example
-------------

Given a simple salt-ssh tree with a Saltfile

.. code-block:: yaml

    salt-ssh:
      config_dir: etc/salt
      max_procs: 30
      wipe_ssh: True

and etc/salt/master

.. code-block:: yaml

    root_dir: .
      file_roots:
        base:
          - srv/salt
      pillar_roots:
        base:
          - srv/pillar
      roster: terraform

We setup a terraform file that creates N virtual machines (libvirt_domain resources) setup
with cloud-init and the salt-ssh ssh key. In this case we set N to 2.

.. code-block:: hcl

    provider "libvirt" {
      uri = "qemu:///system"
    }

    resource "libvirt_cloudinit" "init" {
      name = "test-init.iso"
      ssh_authorized_key = "${file("etc/salt/pki/master/ssh/salt-ssh.rsa.pub")}"
    }

    resource "libvirt_volume" "opensuse_leap" {
      name = "opensuse_leap"
      source = "http://r.opensu.se/Cloud:Images:Leap_42.3/images/openSUSE-Leap-42.3-OpenStack.x86_64.qcow2"
    }

    resource "libvirt_volume" "volume" {
      name = "volume-${count.index}"
      base_volume_id = "${libvirt_volume.opensuse_leap.id}"
      count = 2
    }

    resource "libvirt_domain" "domain" {
      name = "domain-${count.index}"
      memory = 1024
      disk {
           volume_id = "${element(libvirt_volume.volume.*.id, count.index)}"
      }

      network_interface {
        network_name = "default"
        hostname = "minion${count.index}"
        wait_for_lease = 1
      }
      cloudinit = "${libvirt_cloudinit.init.id}"
      count = 2
    }

.. code-block:: bash

    $ terraform apply
    libvirt_cloudinit.init: Creating...
    ...
    libvirt_volume.opensuse_leap: Creating...
    ...
    libvirt_domain.domain.1: Creating...
    libvirt_domain.domain.0: Creating...
    ...
    libvirt_domain.domain.0: Creation complete
    ...
    libvirt_domain.domain.1: Creation complete

    Apply complete! Resources: 5 added, 0 changed, 0 destroyed.

    The state of your infrastructure has been saved to the path
    below. This state is required to modify and destroy your
    infrastructure, so keep it safe. To inspect the complete state
    use the `terraform show` command.

    State path: terraform.tfstate

You can start now using salt-ssh without any configuration.

.. code-block:: bash

   $ salt-ssh '*' test.ping
   domain-0:
       True
   domain-1:
       True

By default, the minion id

'''
from __future__ import absolute_import
import logging
import json
import os.path
import salt.utils
from salt.roster.flat import RosterMatcher
# pylint: disable=import-error
# pylint: disable=redefined-builtin
from salt.ext.six.moves import range
# pylint: enable=import-error,redefined-builtin

log = logging.getLogger(__name__)

TF_OUTPUT_PREFIX = 'salt.roster.'
TF_ROSTER_ATTRS = {'host': 's',
                   'user': 's',
                   'passwd': 's',
                   'port': 'i',
                   'sudo': 'b',
                   'sudo_user': 's',
                   'tty': 'b', 'priv': 's',
                   'timeout': 'i',
                   'minion_opts': 'm',
                   'thin_dir': 's',
                   'cmd_umask': 'i'}
MINION_ID = '_ID'


def _handle_libvirt_resource(resource):
    '''
    Handles libvirt resources.
    See https://github.com/dmacvicar/terraform-provider-libvirt

    Returns roster attributes for the resource or None
    '''
    ret = {}
    attrs = resource.get('primary', {}).get('attributes', {})
    name = attrs.get('name')
    if name:
        ret[MINION_ID] = name
    num_ifaces = int(attrs.get('network_interface.#', 0))
    for if_k in range(num_ifaces):
        num_addrs = int(attrs.get('network_interface.{0}.addresses.#'.format(if_k), 0))
        for addr_k in range(num_addrs):
            addr = attrs['network_interface.{0}.addresses.{1}'.format(if_k, addr_k)]
            if addr:
                ret['host'] = addr
                return ret
        log.warning("terraform: No adress for resource '%s' in state", name)
    return None


def _handle_aws_resource(resource):
    '''
    Reads public_dns or public_ip attributes from AWS resources.

    Returns roster attributes for the resource or None
    '''
    ret = {}
    attrs = resource.get('primary', {}).get('attributes', {})
    addr = attrs.get('public_dns', attrs.get('public_ip'))
    name = attrs.get('tags.Name')
    if name:
        ret[MINION_ID] = name

    if addr:
        ret['host'] = addr
        return ret
    else:
        log.warning("terraform: No adress for resource '%s' in state", name)
    return None


def _add_ssh_key(ret):
    '''
    Setups the salt-ssh minion to be accessed with salt-ssh default key
    '''
    priv = None
    if __opts__.get('ssh_use_home_key') and os.path.isfile(os.path.expanduser('~/.ssh/id_rsa')):
        priv = os.path.expanduser('~/.ssh/id_rsa')
    else:
        priv = __opts__.get(
            'ssh_priv',
            os.path.abspath(os.path.join(
                __opts__['pki_dir'],
                'ssh',
                'salt-ssh.rsa'
            ))
        )
    if priv and os.path.isfile(priv):
        ret['priv'] = priv


def _cast_output_to_type(value, typ):
    '''cast the value depending on the terraform type'''
    if typ == 'b':
        return bool(value)
    if typ == 'i':
        return int(value)
    return value


def _parse_roster_output_vars(global_settings, resource_settings, module):
    '''Parse the output vars from terraform'''
    outputs = module.get('outputs', [])
    for output_name, output in salt.ext.six.iteritems(outputs):
        if not output_name.startswith(TF_OUTPUT_PREFIX):
            continue
        target_part = output_name[len(TF_OUTPUT_PREFIX):]
        if target_part in TF_ROSTER_ATTRS.keys():
            global_settings[target_part] = _cast_output_to_type(output.get('value'), TF_ROSTER_ATTRS[target_part])
        else:
            complex_target_part = target_part.split('.', 1)
            if len(complex_target_part) != 2:
                continue
            attr = complex_target_part[0]
            resource_name = complex_target_part[1]
            if attr in TF_ROSTER_ATTRS.keys():
                if resource_name not in resource_settings:
                    resource_settings[resource_name] = {}
                resource_settings[resource_name][attr] = _cast_output_to_type(output.get('value'),
                                                                              TF_ROSTER_ATTRS[attr])


def _parse_state_file(state_file_path='terraform.tfstate'):
    '''
    Parses the terraform state file passing different resource types to the right handler
    '''
    ret = {}
    with salt.utils.files.fopen(state_file_path, 'r') as fh_:
        tfstate = json.load(fh_)

    modules = tfstate.get('modules')
    if not modules:
        log.error('Malformed tfstate file. No modules found')
        return ret

    for module in modules:
        global_settings = {}
        resource_settings = {}
        _parse_roster_output_vars(global_settings, resource_settings, module)

        resources = module.get('resources', [])
        for resource_name, resource in salt.ext.six.iteritems(resources):
            roster_entry = None
            if resource['type'] == 'libvirt_domain':
                roster_entry = _handle_libvirt_resource(resource)
            if resource['type'] == 'aws_instance':
                roster_entry = _handle_aws_resource(resource)

            if not roster_entry:
                continue

            minion_id = roster_entry.get(MINION_ID, resource.get('id'))
            if not minion_id:
                continue

            if MINION_ID in roster_entry:
                del roster_entry[MINION_ID]
            _add_ssh_key(roster_entry)
            # override values for this resource (salt.roster.VAR.RESOURCE)
            if resource_name in resource_settings:
                log.error(roster_entry)
                roster_entry.update(resource_settings[resource_name])
            # override global values (salt.roster.VAR)
            roster_entry.update(global_settings)
            ret[minion_id] = roster_entry
    return ret


def targets(tgt, tgt_type='glob', **kwargs):  # pylint: disable=W0613
    '''
    Returns the roster from the terraform state file, checks opts for location, but defaults to terraform.tfstate
    '''
    roster_file = os.path.abspath('terraform.tfstate')
    if __opts__.get('roster_file'):
        roster_file = os.path.abspath(__opts__['roster_file'])

    if not os.path.isfile(roster_file):
        log.error("Can't find terraform state file '%s'", roster_file)
        return {}

    log.debug('terraform roster: using %s state file', roster_file)

    if not roster_file.endswith('.tfstate'):
        log.error("Terraform roster can only be used with terraform state files")
        return {}

    raw = _parse_state_file(roster_file)
    log.debug('%s hosts in terraform state file', len(raw))
    rmatcher = RosterMatcher(raw, tgt, tgt_type, 'ipv4', opts=__opts__)
    return rmatcher.targets()
