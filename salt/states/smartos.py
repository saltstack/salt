"""
Management of SmartOS Standalone Compute Nodes

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       vmadm, imgadm
:platform:      smartos

.. versionadded:: 2016.3.0

.. code-block:: yaml

    vmtest.example.org:
      smartos.vm_present:
        - config:
            reprovision: true
        - vmconfig:
            image_uuid: c02a2044-c1bd-11e4-bd8c-dfc1db8b0182
            brand: joyent
            alias: vmtest
            quota: 5
            max_physical_memory: 512
            tags:
              label: 'test vm'
              owner: 'sjorge'
            nics:
              "82:1b:8e:49:e9:12":
                nic_tag: trunk
                mtu: 1500
                ips:
                  - 172.16.1.123/16
                  - 192.168.2.123/24
                vlan_id: 10
              "82:1b:8e:49:e9:13":
                nic_tag: trunk
                mtu: 1500
                ips:
                  - dhcp
                vlan_id: 30
            filesystems:
              "/bigdata":
                source: "/bulk/data"
                type: lofs
                options:
                  - ro
                  - nodevices

    kvmtest.example.org:
      smartos.vm_present:
        - vmconfig:
            brand: kvm
            alias: kvmtest
            cpu_type: host
            ram: 512
            vnc_port: 9
            tags:
              label: 'test kvm'
              owner: 'sjorge'
            disks:
              disk0:
                size: 2048
                model: virtio
                compression: lz4
                boot: true
            nics:
              "82:1b:8e:49:e9:15":
                nic_tag: trunk
                mtu: 1500
                ips:
                  - dhcp
                vlan_id: 30

    docker.example.org:
      smartos.vm_present:
        - config:
            auto_import: true
            reprovision: true
        - vmconfig:
            image_uuid: emby/embyserver:latest
            brand: lx
            alias: mydockervm
            quota: 5
            max_physical_memory: 1024
            tags:
              label: 'my emby docker'
              owner: 'sjorge'
            resolvers:
              - 172.16.1.1
            nics:
              "82:1b:8e:49:e9:18":
                nic_tag: trunk
                mtu: 1500
                ips:
                  - 172.16.1.118/24
                vlan_id: 10
            filesystems:
              "/config:
                source: "/vmdata/emby_config"
                type: lofs
                options:
                  - nodevices

    cleanup_images:
      smartos.image_vacuum

.. note::

    Keep in mind that when removing properties from vmconfig they will not get
    removed from the vm's current configuration, except for nics, disk, tags, ...
    they get removed via add_*, set_*, update_*, and remove_*. Properties must
    be manually reset to their default value.
    The same behavior as when using 'vmadm update'.

.. warning::

    For HVM (bhyve and KVM) brands the `image_uuid` field should go on the boot disks,
    this disk should NOT have a size specified. (See man vmadm)

"""

import json
import logging
import os

import salt.utils.atomicfile
import salt.utils.data
import salt.utils.files

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = "smartos"


def __virtual__():
    """
    Provides smartos state provided for SmartOS
    """
    if "vmadm.create" in __salt__ and "imgadm.list" in __salt__:
        return True
    else:
        return (
            False,
            "{} state module can only be loaded on SmartOS compute nodes".format(
                __virtualname__
            ),
        )


def _split_docker_uuid(uuid):
    """
    Split a smartos docker uuid into repo and tag
    """
    if uuid:
        uuid = uuid.split(":")
        if len(uuid) == 2:
            tag = uuid[1]
            repo = uuid[0]
            return repo, tag
    return None, None


def _is_uuid(uuid):
    """
    Check if uuid is a valid smartos uuid

    Example: e69a0918-055d-11e5-8912-e3ceb6df4cf8
    """
    if uuid and list(len(x) for x in uuid.split("-")) == [8, 4, 4, 4, 12]:
        return True
    return False


def _is_docker_uuid(uuid):
    """
    Check if uuid is a valid smartos docker uuid

    Example plexinc/pms-docker:plexpass
    """
    repo, tag = _split_docker_uuid(uuid)
    return not (not repo and not tag)


def _load_config():
    """
    Loads and parses /usbkey/config
    """
    config = {}

    if os.path.isfile("/usbkey/config"):
        with salt.utils.files.fopen("/usbkey/config", "r") as config_file:
            for optval in config_file:
                optval = salt.utils.stringutils.to_unicode(optval)
                if optval[0] == "#":
                    continue
                if "=" not in optval:
                    continue
                optval = optval.split("=")
                config[optval[0].lower()] = optval[1].strip().strip('"')
    log.debug("smartos.config - read /usbkey/config: %s", config)
    return config


def _write_config(config):
    """
    writes /usbkey/config
    """
    try:
        with salt.utils.atomicfile.atomic_open("/usbkey/config", "w") as config_file:
            config_file.write("#\n# This file was generated by salt\n#\n")
            for prop in salt.utils.odict.OrderedDict(sorted(config.items())):
                if " " in str(config[prop]):
                    if not config[prop].startswith('"') or not config[prop].endswith(
                        '"'
                    ):
                        config[prop] = '"{}"'.format(config[prop])
                config_file.write(
                    salt.utils.stringutils.to_str("{}={}\n".format(prop, config[prop]))
                )
        log.debug("smartos.config - wrote /usbkey/config: %s", config)
    except OSError:
        return False

    return True


def _parse_vmconfig(config, instances):
    """
    Parse vm_present vm config
    """
    vmconfig = None

    if isinstance(config, (salt.utils.odict.OrderedDict)):
        vmconfig = salt.utils.odict.OrderedDict()
        for prop in config:
            if prop not in instances:
                vmconfig[prop] = config[prop]
            else:
                if not isinstance(config[prop], (salt.utils.odict.OrderedDict)):
                    continue
                vmconfig[prop] = []
                for instance in config[prop]:
                    instance_config = config[prop][instance]
                    instance_config[instances[prop]] = instance
                    ## some property are lowercase
                    if "mac" in instance_config:
                        instance_config["mac"] = instance_config["mac"].lower()
                    ## calculate mac from vrrp_vrid
                    if "vrrp_vrid" in instance_config:
                        instance_config["mac"] = "00:00:5e:00:01:{}".format(
                            hex(int(instance_config["vrrp_vrid"]))
                            .split("x")[-1]
                            .zfill(2),
                        )
                    vmconfig[prop].append(instance_config)
    else:
        log.error("smartos.vm_present::parse_vmconfig - failed to parse")

    return vmconfig


def _get_instance_changes(current, state):
    """
    get modified properties
    """
    # get keys
    current_keys = set(current.keys())
    state_keys = set(state.keys())

    # compare configs
    changed = salt.utils.data.compare_dicts(current, state)
    for change in salt.utils.data.compare_dicts(current, state):
        if change in changed and changed[change]["old"] == "":
            del changed[change]
        if change in changed and changed[change]["new"] == "":
            del changed[change]

    return changed


def _copy_lx_vars(vmconfig):
    # NOTE: documentation on dockerinit: https://github.com/joyent/smartos-live/blob/master/src/dockerinit/README.md
    if "image_uuid" in vmconfig:
        # NOTE: retrieve tags and type from image
        imgconfig = __salt__["imgadm.get"](vmconfig["image_uuid"]).get("manifest", {})
        imgtype = imgconfig.get("type", "zone-dataset")
        imgtags = imgconfig.get("tags", {})

        # NOTE: copy kernel_version (if not specified in vmconfig)
        if "kernel_version" not in vmconfig and "kernel_version" in imgtags:
            vmconfig["kernel_version"] = imgtags["kernel_version"]

        # NOTE: copy docker vars
        if imgtype == "docker":
            vmconfig["docker"] = True
            vmconfig["kernel_version"] = vmconfig.get("kernel_version", "4.3.0")
            if "internal_metadata" not in vmconfig:
                vmconfig["internal_metadata"] = {}

            for var in imgtags.get("docker:config", {}):
                val = imgtags["docker:config"][var]
                var = "docker:{}".format(var.lower())

                # NOTE: skip empty values
                if not val:
                    continue

                # NOTE: skip or merge user values
                if var == "docker:env":
                    try:
                        val_config = json.loads(
                            vmconfig["internal_metadata"].get(var, "")
                        )
                    except ValueError as e:
                        val_config = []

                    for config_env_var in (
                        val_config
                        if isinstance(val_config, list)
                        else json.loads(val_config)
                    ):
                        config_env_var = config_env_var.split("=")
                        for img_env_var in val:
                            if img_env_var.startswith("{}=".format(config_env_var[0])):
                                val.remove(img_env_var)
                        val.append("=".join(config_env_var))
                elif var in vmconfig["internal_metadata"]:
                    continue

                if isinstance(val, list):
                    # NOTE: string-encoded JSON arrays
                    vmconfig["internal_metadata"][var] = json.dumps(val)
                else:
                    vmconfig["internal_metadata"][var] = val

    return vmconfig


def config_present(name, value):
    """
    Ensure configuration property is set to value in /usbkey/config

    name : string
        name of property
    value : string
        value of property

    """
    name = name.lower()
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    # load confiration
    config = _load_config()

    # handle bool and None value
    if isinstance(value, (bool)):
        value = "true" if value else "false"
    if not value:
        value = ""

    if name in config:
        if str(config[name]) == str(value):
            # we're good
            ret["result"] = True
            ret["comment"] = 'property {} already has value "{}"'.format(name, value)
        else:
            # update property
            ret["result"] = True
            ret["comment"] = 'updated property {} with value "{}"'.format(name, value)
            ret["changes"][name] = value
            config[name] = value
    else:
        # add property
        ret["result"] = True
        ret["comment"] = 'added property {} with value "{}"'.format(name, value)
        ret["changes"][name] = value
        config[name] = value

    # apply change if needed
    if not __opts__["test"] and ret["changes"]:
        ret["result"] = _write_config(config)

        if not ret["result"]:
            ret[
                "comment"
            ] = 'Could not add property {} with value "{}" to config'.format(
                name, value
            )

    return ret


def config_absent(name):
    """
    Ensure configuration property is absent in /usbkey/config

    name : string
        name of property

    """
    name = name.lower()
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    # load configuration
    config = _load_config()

    if name in config:
        # delete property
        ret["result"] = True
        ret["comment"] = "property {} deleted".format(name)
        ret["changes"][name] = None
        del config[name]
    else:
        # we're good
        ret["result"] = True
        ret["comment"] = "property {} is absent".format(name)

    # apply change if needed
    if not __opts__["test"] and ret["changes"]:
        ret["result"] = _write_config(config)

    return ret


def source_present(name, source_type="imgapi"):
    """
    Ensure an image source is present on the computenode

    name : string
        source url
    source_type : string
        source type (imgapi or docker)
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if name in __salt__["imgadm.sources"]():
        # source is present
        ret["result"] = True
        ret["comment"] = "image source {} is present".format(name)
    else:
        # add new source
        if __opts__["test"]:
            res = {}
            ret["result"] = True
        else:
            res = __salt__["imgadm.source_add"](name, source_type)
            ret["result"] = name in res

        if ret["result"]:
            ret["comment"] = "image source {} added".format(name)
            ret["changes"][name] = "added"
        else:
            ret["comment"] = "image source {} not added".format(name)
            if "Error" in res:
                ret["comment"] = "{}: {}".format(ret["comment"], res["Error"])

    return ret


def source_absent(name):
    """
    Ensure an image source is absent on the computenode

    name : string
        source url
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if name not in __salt__["imgadm.sources"]():
        # source is absent
        ret["result"] = True
        ret["comment"] = "image source {} is absent".format(name)
    else:
        # remove source
        if __opts__["test"]:
            res = {}
            ret["result"] = True
        else:
            res = __salt__["imgadm.source_delete"](name)
            ret["result"] = name not in res

        if ret["result"]:
            ret["comment"] = "image source {} deleted".format(name)
            ret["changes"][name] = "deleted"
        else:
            ret["comment"] = "image source {} not deleted".format(name)
            if "Error" in res:
                ret["comment"] = "{}: {}".format(ret["comment"], res["Error"])

    return ret


def image_present(name):
    """
    Ensure image is present on the computenode

    name : string
        uuid of image
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if _is_docker_uuid(name) and __salt__["imgadm.docker_to_uuid"](name):
        # docker image was imported
        ret["result"] = True
        ret["comment"] = "image {} ({}) is present".format(
            name,
            __salt__["imgadm.docker_to_uuid"](name),
        )
    elif name in __salt__["imgadm.list"]():
        # image was already imported
        ret["result"] = True
        ret["comment"] = "image {} is present".format(name)
    else:
        # add image
        if _is_docker_uuid(name):
            # NOTE: we cannot query available docker images
            available_images = [name]
        else:
            available_images = __salt__["imgadm.avail"]()

        if name in available_images:
            if __opts__["test"]:
                ret["result"] = True
                res = {}
                if _is_docker_uuid(name):
                    res["00000000-0000-0000-0000-000000000000"] = name
                else:
                    res[name] = available_images[name]
            else:
                res = __salt__["imgadm.import"](name)
                if _is_uuid(name):
                    ret["result"] = name in res
                elif _is_docker_uuid(name):
                    ret["result"] = __salt__["imgadm.docker_to_uuid"](name) is not None
            if ret["result"]:
                ret["comment"] = "image {} imported".format(name)
                ret["changes"] = res
            else:
                ret["comment"] = "image {} was unable to be imported".format(name)
        else:
            ret["result"] = False
            ret["comment"] = "image {} does not exists".format(name)

    return ret


def image_absent(name):
    """
    Ensure image is absent on the computenode

    name : string
        uuid of image

    .. note::

        computenode.image_absent will only remove the image if it is not used
        by a vm.
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    uuid = None
    if _is_uuid(name):
        uuid = name
    if _is_docker_uuid(name):
        uuid = __salt__["imgadm.docker_to_uuid"](name)

    if not uuid or uuid not in __salt__["imgadm.list"]():
        # image not imported
        ret["result"] = True
        ret["comment"] = "image {} is absent".format(name)
    else:
        # check if image in use by vm
        if uuid in __salt__["vmadm.list"](order="image_uuid"):
            ret["result"] = False
            ret["comment"] = "image {} currently in use by a vm".format(name)
        else:
            # delete image
            if __opts__["test"]:
                ret["result"] = True
            else:
                image = __salt__["imgadm.get"](uuid)
                image_count = 0
                if image["manifest"]["name"] == "docker-layer":
                    # NOTE: docker images are made of multiple layers, loop over them
                    while image:
                        image_count += 1
                        __salt__["imgadm.delete"](image["manifest"]["uuid"])
                        if "origin" in image["manifest"]:
                            image = __salt__["imgadm.get"](image["manifest"]["origin"])
                        else:
                            image = None
                else:
                    # NOTE: normal images can just be delete
                    __salt__["imgadm.delete"](uuid)

            ret["result"] = uuid not in __salt__["imgadm.list"]()
            if image_count:
                ret["comment"] = "image {} and {} children deleted".format(
                    name, image_count
                )
            else:
                ret["comment"] = "image {} deleted".format(name)
            ret["changes"][name] = None

    return ret


def image_vacuum(name):
    """
    Delete images not in use or installed via image_present

    .. warning::

        Only image_present states that are included via the
        top file will be detected.
    """
    name = name.lower()
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    # list of images to keep
    images = []

    # retrieve image_present state data for host
    for state in __salt__["state.show_lowstate"]():
        # don't throw exceptions when not highstate run
        if "state" not in state:
            continue

        # skip if not from this state module
        if state["state"] != __virtualname__:
            continue
        # skip if not image_present
        if state["fun"] not in ["image_present"]:
            continue
        # keep images installed via image_present
        if "name" in state:
            if _is_uuid(state["name"]):
                images.append(state["name"])
            elif _is_docker_uuid(state["name"]):
                state["name"] = __salt__["imgadm.docker_to_uuid"](state["name"])
                if not state["name"]:
                    continue
                images.append(state["name"])

    # retrieve images in use by vms
    for image_uuid in __salt__["vmadm.list"](order="image_uuid"):
        if image_uuid not in images:
            images.append(image_uuid)

    # purge unused images
    ret["result"] = True
    for image_uuid in __salt__["imgadm.list"]():
        if image_uuid in images:
            continue

        image = __salt__["imgadm.get"](image_uuid)
        if image["manifest"]["name"] == "docker-layer":
            # NOTE: docker images are made of multiple layers, loop over them
            while image:
                image_uuid = image["manifest"]["uuid"]
                if image_uuid in __salt__["imgadm.delete"](image_uuid):
                    ret["changes"][image_uuid] = None
                else:
                    ret["result"] = False
                    ret["comment"] = "failed to delete images"
                if "origin" in image["manifest"]:
                    image = __salt__["imgadm.get"](image["manifest"]["origin"])
                else:
                    image = None
        else:
            # NOTE: normal images can just be delete
            if image_uuid in __salt__["imgadm.delete"](image_uuid):
                ret["changes"][image_uuid] = None
            else:
                ret["result"] = False
                ret["comment"] = "failed to delete images"

    if ret["result"] and not ret["changes"]:
        ret["comment"] = "no images deleted"
    elif ret["result"] and ret["changes"]:
        ret["comment"] = "images deleted"

    return ret


def vm_present(name, vmconfig, config=None):
    """
    Ensure vm is present on the computenode

    name : string
        hostname of vm
    vmconfig : dict
        options to set for the vm
    config : dict
        fine grain control over vm_present

    .. note::

        The following configuration properties can be toggled in the config parameter.
          - kvm_reboot (true)                - reboots of kvm zones if needed for a config update
          - auto_import (false)              - automatic importing of missing images
          - auto_lx_vars (true)              - copy kernel_version and docker:* variables from image
          - reprovision (false)              - reprovision on image_uuid changes
          - enforce_tags (true)              - false = add tags only, true =  add, update, and remove tags
          - enforce_routes (true)            - false = add tags only, true =  add, update, and remove routes
          - enforce_internal_metadata (true) - false = add metadata only, true =  add, update, and remove metadata
          - enforce_customer_metadata (true) - false = add metadata only, true =  add, update, and remove metadata

    .. note::

        State ID is used as hostname. Hostnames must be unique.

    .. note::

        If hostname is provided in vmconfig this will take president over the State ID.
        This allows multiple states to be applied to the same vm.

    .. note::

        The following instances should have a unique ID.
          - nic : mac
          - filesystem: target
          - disk : path or diskN for zvols

        e.g. disk0 will be the first disk added, disk1 the 2nd,...

    .. versionchanged:: 2019.2.0

        Added support for docker image uuids, added auto_lx_vars configuration, documented some missing configuration options.

    """
    name = name.lower()
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    # config defaults
    state_config = config if config else {}
    config = {
        "kvm_reboot": True,
        "auto_import": False,
        "auto_lx_vars": True,
        "reprovision": False,
        "enforce_tags": True,
        "enforce_routes": True,
        "enforce_internal_metadata": True,
        "enforce_customer_metadata": True,
    }
    config.update(state_config)
    log.debug("smartos.vm_present::%s::config - %s", name, config)

    # map special vmconfig parameters
    #  collections have set/remove handlers
    #  instances have add/update/remove handlers and a unique id
    vmconfig_type = {
        "collection": ["tags", "customer_metadata", "internal_metadata", "routes"],
        "instance": {
            "nics": "mac",
            "disks": "path",
            "filesystems": "target",
            "pci_devices": "path",
        },
        "create_only": ["filesystems"],
    }
    vmconfig_docker_keep = [
        "docker:id",
        "docker:restartcount",
    ]
    vmconfig_docker_array = [
        "docker:env",
        "docker:cmd",
        "docker:entrypoint",
    ]

    # parse vmconfig
    vmconfig = _parse_vmconfig(vmconfig, vmconfig_type["instance"])
    log.debug("smartos.vm_present::%s::vmconfig - %s", name, vmconfig)

    # set hostname if needed
    if "hostname" not in vmconfig:
        vmconfig["hostname"] = name

    # prepare image_uuid
    if "image_uuid" in vmconfig:
        # NOTE: lookup uuid from docker uuid (normal uuid's are passed throuhg unmodified)
        #       we must do this again if we end up importing a missing image later!
        docker_uuid = __salt__["imgadm.docker_to_uuid"](vmconfig["image_uuid"])
        vmconfig["image_uuid"] = docker_uuid if docker_uuid else vmconfig["image_uuid"]

        # NOTE: import image (if missing and allowed)
        if vmconfig["image_uuid"] not in __salt__["imgadm.list"]():
            if config["auto_import"]:
                if not __opts__["test"]:
                    res = __salt__["imgadm.import"](vmconfig["image_uuid"])
                    vmconfig["image_uuid"] = __salt__["imgadm.docker_to_uuid"](
                        vmconfig["image_uuid"]
                    )
                    if vmconfig["image_uuid"] not in res:
                        ret["result"] = False
                        ret["comment"] = "failed to import image {}".format(
                            vmconfig["image_uuid"]
                        )
            else:
                ret["result"] = False
                ret["comment"] = "image {} not installed".format(vmconfig["image_uuid"])

    # prepare disk.*.image_uuid
    for disk in vmconfig["disks"] if "disks" in vmconfig else []:
        if "image_uuid" in disk and disk["image_uuid"] not in __salt__["imgadm.list"]():
            if config["auto_import"]:
                if not __opts__["test"]:
                    res = __salt__["imgadm.import"](disk["image_uuid"])
                    if disk["image_uuid"] not in res:
                        ret["result"] = False
                        ret["comment"] = "failed to import image {}".format(
                            disk["image_uuid"]
                        )
            else:
                ret["result"] = False
                ret["comment"] = "image {} not installed".format(disk["image_uuid"])

    # docker json-array handling
    if "internal_metadata" in vmconfig:
        for var in vmconfig_docker_array:
            if var not in vmconfig["internal_metadata"]:
                continue
            if isinstance(vmconfig["internal_metadata"][var], list):
                vmconfig["internal_metadata"][var] = json.dumps(
                    vmconfig["internal_metadata"][var]
                )

    # copy lx variables
    if vmconfig["brand"] == "lx" and config["auto_lx_vars"]:
        # NOTE: we can only copy the lx vars after the image has bene imported
        vmconfig = _copy_lx_vars(vmconfig)

    # quick abort if things look wrong
    # NOTE: use explicit check for false, otherwise None also matches!
    if ret["result"] is False:
        return ret

    # check if vm exists
    if vmconfig["hostname"] in __salt__["vmadm.list"](order="hostname"):
        # update vm
        ret["result"] = True

        # expand vmconfig
        vmconfig = {
            "state": vmconfig,
            "current": __salt__["vmadm.get"](vmconfig["hostname"], key="hostname"),
            "changed": {},
            "reprovision_uuid": None,
        }

        # prepare reprovision
        if "image_uuid" in vmconfig["state"]:
            vmconfig["reprovision_uuid"] = vmconfig["state"]["image_uuid"]
            vmconfig["state"]["image_uuid"] = vmconfig["current"]["image_uuid"]

        # disks need some special care
        if "disks" in vmconfig["state"]:
            new_disks = []
            for disk in vmconfig["state"]["disks"]:
                path = False
                if "disks" in vmconfig["current"]:
                    for cdisk in vmconfig["current"]["disks"]:
                        if cdisk["path"].endswith(disk["path"]):
                            path = cdisk["path"]
                            break
                if not path:
                    del disk["path"]
                else:
                    disk["path"] = path
                new_disks.append(disk)
            vmconfig["state"]["disks"] = new_disks

        # process properties
        for prop in vmconfig["state"]:
            # skip special vmconfig_types
            if (
                prop in vmconfig_type["instance"]
                or prop in vmconfig_type["collection"]
                or prop in vmconfig_type["create_only"]
            ):
                continue

            # skip unchanged properties
            if prop in vmconfig["current"]:
                if isinstance(vmconfig["current"][prop], (list)) or isinstance(
                    vmconfig["current"][prop], (dict)
                ):
                    if vmconfig["current"][prop] == vmconfig["state"][prop]:
                        continue
                else:
                    if "{}".format(vmconfig["current"][prop]) == "{}".format(
                        vmconfig["state"][prop]
                    ):
                        continue

            # add property to changeset
            vmconfig["changed"][prop] = vmconfig["state"][prop]

        # process collections
        for collection in vmconfig_type["collection"]:
            # skip create only collections
            if collection in vmconfig_type["create_only"]:
                continue

            # enforcement
            enforce = config["enforce_{}".format(collection)]
            log.debug("smartos.vm_present::enforce_%s = %s", collection, enforce)

            # dockerinit handling
            if collection == "internal_metadata" and vmconfig["state"].get(
                "docker", False
            ):
                if "internal_metadata" not in vmconfig["state"]:
                    vmconfig["state"]["internal_metadata"] = {}

                # preserve some docker specific metadata (added and needed by dockerinit)
                for var in vmconfig_docker_keep:
                    val = vmconfig["current"].get(collection, {}).get(var, None)
                    if val is not None:
                        vmconfig["state"]["internal_metadata"][var] = val

            # process add and update for collection
            if (
                collection in vmconfig["state"]
                and vmconfig["state"][collection] is not None
            ):
                for prop in vmconfig["state"][collection]:
                    # skip unchanged properties
                    if (
                        prop in vmconfig["current"][collection]
                        and vmconfig["current"][collection][prop]
                        == vmconfig["state"][collection][prop]
                    ):
                        continue

                    # skip update if not enforcing
                    if not enforce and prop in vmconfig["current"][collection]:
                        continue

                    # create set_ dict
                    if "set_{}".format(collection) not in vmconfig["changed"]:
                        vmconfig["changed"]["set_{}".format(collection)] = {}

                    # add property to changeset
                    vmconfig["changed"]["set_{}".format(collection)][prop] = vmconfig[
                        "state"
                    ][collection][prop]

            # process remove for collection
            if (
                enforce
                and collection in vmconfig["current"]
                and vmconfig["current"][collection] is not None
            ):
                for prop in vmconfig["current"][collection]:
                    # skip if exists in state
                    if (
                        collection in vmconfig["state"]
                        and vmconfig["state"][collection] is not None
                    ):
                        if prop in vmconfig["state"][collection]:
                            continue

                    # create remove_ array
                    if "remove_{}".format(collection) not in vmconfig["changed"]:
                        vmconfig["changed"]["remove_{}".format(collection)] = []

                    # remove property
                    vmconfig["changed"]["remove_{}".format(collection)].append(prop)

        # process instances
        for instance in vmconfig_type["instance"]:
            # skip create only instances
            if instance in vmconfig_type["create_only"]:
                continue

            # add or update instances
            if (
                instance in vmconfig["state"]
                and vmconfig["state"][instance] is not None
            ):
                for state_cfg in vmconfig["state"][instance]:
                    add_instance = True

                    # find instance with matching ids
                    for current_cfg in vmconfig["current"][instance]:
                        if vmconfig_type["instance"][instance] not in state_cfg:
                            continue

                        if (
                            state_cfg[vmconfig_type["instance"][instance]]
                            == current_cfg[vmconfig_type["instance"][instance]]
                        ):
                            # ids have matched, disable add instance
                            add_instance = False

                            changed = _get_instance_changes(current_cfg, state_cfg)
                            update_cfg = {}

                            # handle changes
                            for prop in changed:
                                update_cfg[prop] = state_cfg[prop]

                            # handle new properties
                            for prop in state_cfg:
                                # skip empty props like ips, options,..
                                if (
                                    isinstance(state_cfg[prop], (list))
                                    and not state_cfg[prop]
                                ):
                                    continue

                                if prop not in current_cfg:
                                    update_cfg[prop] = state_cfg[prop]

                            # update instance
                            if update_cfg:
                                # create update_ array
                                if (
                                    "update_{}".format(instance)
                                    not in vmconfig["changed"]
                                ):
                                    vmconfig["changed"][
                                        "update_{}".format(instance)
                                    ] = []

                                update_cfg[
                                    vmconfig_type["instance"][instance]
                                ] = state_cfg[vmconfig_type["instance"][instance]]
                                vmconfig["changed"][
                                    "update_{}".format(instance)
                                ].append(update_cfg)

                    if add_instance:
                        # create add_ array
                        if "add_{}".format(instance) not in vmconfig["changed"]:
                            vmconfig["changed"]["add_{}".format(instance)] = []

                        # add instance
                        vmconfig["changed"]["add_{}".format(instance)].append(state_cfg)

            # remove instances
            if (
                instance in vmconfig["current"]
                and vmconfig["current"][instance] is not None
            ):
                for current_cfg in vmconfig["current"][instance]:
                    remove_instance = True

                    # find instance with matching ids
                    if (
                        instance in vmconfig["state"]
                        and vmconfig["state"][instance] is not None
                    ):
                        for state_cfg in vmconfig["state"][instance]:
                            if vmconfig_type["instance"][instance] not in state_cfg:
                                continue

                            if (
                                state_cfg[vmconfig_type["instance"][instance]]
                                == current_cfg[vmconfig_type["instance"][instance]]
                            ):
                                # keep instance if matched
                                remove_instance = False

                    if remove_instance:
                        # create remove_ array
                        if "remove_{}".format(instance) not in vmconfig["changed"]:
                            vmconfig["changed"]["remove_{}".format(instance)] = []

                        # remove instance
                        vmconfig["changed"]["remove_{}".format(instance)].append(
                            current_cfg[vmconfig_type["instance"][instance]]
                        )

        # update vm if we have pending changes
        kvm_needs_start = False
        if not __opts__["test"] and vmconfig["changed"]:
            # stop kvm if disk updates and kvm_reboot
            if vmconfig["current"]["brand"] == "kvm" and config["kvm_reboot"]:
                if (
                    "add_disks" in vmconfig["changed"]
                    or "update_disks" in vmconfig["changed"]
                    or "remove_disks" in vmconfig["changed"]
                ):
                    if vmconfig["state"]["hostname"] in __salt__["vmadm.list"](
                        order="hostname", search="state=running"
                    ):
                        kvm_needs_start = True
                        __salt__["vmadm.stop"](
                            vm=vmconfig["state"]["hostname"], key="hostname"
                        )

            # do update
            rret = __salt__["vmadm.update"](
                vm=vmconfig["state"]["hostname"], key="hostname", **vmconfig["changed"]
            )
            if not isinstance(rret, (bool)) and "Error" in rret:
                ret["result"] = False
                ret["comment"] = "{}".format(rret["Error"])
            else:
                ret["result"] = True
                ret["changes"][vmconfig["state"]["hostname"]] = vmconfig["changed"]

        if ret["result"]:
            if __opts__["test"]:
                ret["changes"][vmconfig["state"]["hostname"]] = vmconfig["changed"]

            if (
                vmconfig["state"]["hostname"] in ret["changes"]
                and ret["changes"][vmconfig["state"]["hostname"]]
            ):
                ret["comment"] = "vm {} updated".format(vmconfig["state"]["hostname"])
                if (
                    config["kvm_reboot"]
                    and vmconfig["current"]["brand"] == "kvm"
                    and not __opts__["test"]
                ):
                    if vmconfig["state"]["hostname"] in __salt__["vmadm.list"](
                        order="hostname", search="state=running"
                    ):
                        __salt__["vmadm.reboot"](
                            vm=vmconfig["state"]["hostname"], key="hostname"
                        )
                    if kvm_needs_start:
                        __salt__["vmadm.start"](
                            vm=vmconfig["state"]["hostname"], key="hostname"
                        )
            else:
                ret["changes"] = {}
                ret["comment"] = "vm {} is up to date".format(
                    vmconfig["state"]["hostname"]
                )

            # reprovision (if required and allowed)
            if (
                "image_uuid" in vmconfig["current"]
                and vmconfig["reprovision_uuid"] != vmconfig["current"]["image_uuid"]
            ):
                if config["reprovision"]:
                    rret = __salt__["vmadm.reprovision"](
                        vm=vmconfig["state"]["hostname"],
                        key="hostname",
                        image=vmconfig["reprovision_uuid"],
                    )
                    if not isinstance(rret, (bool)) and "Error" in rret:
                        ret["result"] = False
                        ret["comment"] = "vm {} updated, reprovision failed".format(
                            vmconfig["state"]["hostname"]
                        )
                    else:
                        ret["comment"] = "vm {} updated and reprovisioned".format(
                            vmconfig["state"]["hostname"]
                        )
                        if vmconfig["state"]["hostname"] not in ret["changes"]:
                            ret["changes"][vmconfig["state"]["hostname"]] = {}
                        ret["changes"][vmconfig["state"]["hostname"]][
                            "image_uuid"
                        ] = vmconfig["reprovision_uuid"]
                else:
                    log.warning(
                        "smartos.vm_present::%s::reprovision - "
                        "image_uuid in state does not match current, "
                        "reprovision not allowed",
                        name,
                    )
        else:
            ret["comment"] = "vm {} failed to be updated".format(
                vmconfig["state"]["hostname"]
            )
            if not isinstance(rret, (bool)) and "Error" in rret:
                ret["comment"] = "{}".format(rret["Error"])
    else:
        # check required image installed
        ret["result"] = True

        # disks need some special care
        if "disks" in vmconfig:
            new_disks = []
            for disk in vmconfig["disks"]:
                if "path" in disk:
                    del disk["path"]
                new_disks.append(disk)
            vmconfig["disks"] = new_disks

        # create vm
        if ret["result"]:
            uuid = (
                __salt__["vmadm.create"](**vmconfig) if not __opts__["test"] else True
            )
            if not isinstance(uuid, (bool)) and "Error" in uuid:
                ret["result"] = False
                ret["comment"] = "{}".format(uuid["Error"])
            else:
                ret["result"] = True
                ret["changes"][vmconfig["hostname"]] = vmconfig
                ret["comment"] = "vm {} created".format(vmconfig["hostname"])

    return ret


def vm_absent(name, archive=False):
    """
    Ensure vm is absent on the computenode

    name : string
        hostname of vm
    archive : boolean
        toggle archiving of vm on removal

    .. note::

        State ID is used as hostname. Hostnames must be unique.

    """
    name = name.lower()
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if name not in __salt__["vmadm.list"](order="hostname"):
        # we're good
        ret["result"] = True
        ret["comment"] = "vm {} is absent".format(name)
    else:
        # delete vm
        if not __opts__["test"]:
            # set archive to true if needed
            if archive:
                __salt__["vmadm.update"](
                    vm=name, key="hostname", archive_on_delete=True
                )

            ret["result"] = __salt__["vmadm.delete"](name, key="hostname")
        else:
            ret["result"] = True

        if not isinstance(ret["result"], bool) and ret["result"].get("Error"):
            ret["result"] = False
            ret["comment"] = "failed to delete vm {}".format(name)
        else:
            ret["comment"] = "vm {} deleted".format(name)
            ret["changes"][name] = None

    return ret


def vm_running(name):
    """
    Ensure vm is in the running state on the computenode

    name : string
        hostname of vm

    .. note::

        State ID is used as hostname. Hostnames must be unique.

    """
    name = name.lower()
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if name in __salt__["vmadm.list"](order="hostname", search="state=running"):
        # we're good
        ret["result"] = True
        ret["comment"] = "vm {} already running".format(name)
    else:
        # start the vm
        ret["result"] = (
            True if __opts__["test"] else __salt__["vmadm.start"](name, key="hostname")
        )
        if not isinstance(ret["result"], bool) and ret["result"].get("Error"):
            ret["result"] = False
            ret["comment"] = "failed to start {}".format(name)
        else:
            ret["changes"][name] = "running"
            ret["comment"] = "vm {} started".format(name)

    return ret


def vm_stopped(name):
    """
    Ensure vm is in the stopped state on the computenode

    name : string
        hostname of vm

    .. note::

        State ID is used as hostname. Hostnames must be unique.

    """
    name = name.lower()
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if name in __salt__["vmadm.list"](order="hostname", search="state=stopped"):
        # we're good
        ret["result"] = True
        ret["comment"] = "vm {} already stopped".format(name)
    else:
        # stop the vm
        ret["result"] = (
            True if __opts__["test"] else __salt__["vmadm.stop"](name, key="hostname")
        )
        if not isinstance(ret["result"], bool) and ret["result"].get("Error"):
            ret["result"] = False
            ret["comment"] = "failed to stop {}".format(name)
        else:
            ret["changes"][name] = "stopped"
            ret["comment"] = "vm {} stopped".format(name)

    return ret


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
