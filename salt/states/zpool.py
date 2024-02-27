"""
States for managing zpools

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs, salt.modules.zpool
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: 2016.3.0
.. versionchanged:: 2018.3.1
  Big refactor to remove duplicate code, better type conversions and improved
  consistency in output.

.. code-block:: yaml

    oldpool:
      zpool.absent:
        - export: true

    newpool:
      zpool.present:
        - config:
            import: false
            force: true
        - properties:
            comment: salty storage pool
        - layout:
            - mirror:
              - /dev/disk0
              - /dev/disk1
            - mirror:
              - /dev/disk2
              - /dev/disk3

    partitionpool:
      zpool.present:
        - config:
            import: false
            force: true
        - properties:
            comment: disk partition salty storage pool
            ashift: '12'
            feature@lz4_compress: enabled
        - filesystem_properties:
            compression: lz4
            atime: on
            relatime: on
        - layout:
            - /dev/disk/by-uuid/3e43ce94-77af-4f52-a91b-6cdbb0b0f41b

    simplepool:
      zpool.present:
        - config:
            import: false
            force: true
        - properties:
            comment: another salty storage pool
        - layout:
            - /dev/disk0
            - /dev/disk1

.. warning::

    The layout will never be updated, it will only be used at time of creation.
    It's a whole lot of work to figure out if a devices needs to be detached, removed,
    etc. This is best done by the sysadmin on a case per case basis.

    Filesystem properties are also not updated, this should be managed by the zfs state module.

"""

import logging
import os

from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = "zpool"


def __virtual__():
    """
    Provides zpool state
    """
    if not __grains__.get("zfs_support"):
        return False, "The zpool state cannot be loaded: zfs not supported"
    return __virtualname__


def _layout_to_vdev(layout, device_dir=None):
    """
    Turn the layout data into usable vdevs spedcification

    We need to support 2 ways of passing the layout:

    .. code::
        layout_new:
          - mirror:
            - disk0
            - disk1
          - mirror:
            - disk2
            - disk3

    .. code:
        layout_legacy:
          mirror-0:
            disk0
            disk1
          mirror-1:
            disk2
            disk3

    """
    vdevs = []

    # NOTE: check device_dir exists
    if device_dir and not os.path.exists(device_dir):
        device_dir = None

    # NOTE: handle list of OrderedDicts (new layout)
    if isinstance(layout, list):
        # NOTE: parse each vdev as a tiny layout and just append
        for vdev in layout:
            if isinstance(vdev, OrderedDict):
                vdevs.extend(_layout_to_vdev(vdev, device_dir))
            else:
                if device_dir and vdev[0] != "/":
                    vdev = os.path.join(device_dir, vdev)
                vdevs.append(vdev)

    # NOTE: handle nested OrderedDict (legacy layout)
    #       this is also used to parse the nested OrderedDicts
    #       from the new layout
    elif isinstance(layout, OrderedDict):
        for vdev in layout:
            # NOTE: extract the vdev type and disks in the vdev
            vdev_type = vdev.split("-")[0]
            vdev_disk = layout[vdev]

            # NOTE: skip appending the dummy type 'disk'
            if vdev_type != "disk":
                vdevs.append(vdev_type)

            # NOTE: ensure the disks are a list (legacy layout are not)
            if not isinstance(vdev_disk, list):
                vdev_disk = vdev_disk.split(" ")

            # NOTE: also append the actualy disks behind the type
            #       also prepend device_dir to disks if required
            for disk in vdev_disk:
                if device_dir and disk[0] != "/":
                    disk = os.path.join(device_dir, disk)
                vdevs.append(disk)

    # NOTE: we got invalid data for layout
    else:
        vdevs = None

    return vdevs


def present(
    name, properties=None, filesystem_properties=None, layout=None, config=None
):
    """
    ensure storage pool is present on the system

    name : string
        name of storage pool
    properties : dict
        optional set of properties to set for the storage pool
    filesystem_properties : dict
        optional set of filesystem properties to set for the storage pool (creation only)
    layout: dict
        disk layout to use if the pool does not exist (creation only)
    config : dict
        fine grain control over this state

    .. note::

        The following configuration properties can be toggled in the config parameter.
          - import (true) - try to import the pool before creating it if absent
          - import_dirs (None) - specify additional locations to scan for devices on import (comma-separated)
          - device_dir (None, SunOS=/dev/dsk, Linux=/dev) - specify device directory to prepend for none
            absolute device paths
          - force (false) - try to force the import or creation

    .. note::

        It is no longer needed to give a unique name to each top-level vdev, the old
        layout format is still supported but no longer recommended.

        .. code-block:: yaml

            - mirror:
              - /tmp/vdisk3
              - /tmp/vdisk2
            - mirror:
              - /tmp/vdisk0
              - /tmp/vdisk1

        The above yaml will always result in the following zpool create:

        .. code-block:: bash

            zpool create mypool mirror /tmp/vdisk3 /tmp/vdisk2 mirror /tmp/vdisk0 /tmp/vdisk1

    .. warning::

        The legacy format is also still supported but not recommended,
        because ID's inside the layout dict must be unique they need to have a suffix.

        .. code-block:: yaml

            mirror-0:
              /tmp/vdisk3
              /tmp/vdisk2
            mirror-1:
              /tmp/vdisk0
              /tmp/vdisk1

    .. warning::

        Pay attention to the order of your dict!

        .. code-block:: yaml

            - mirror:
              - /tmp/vdisk0
              - /tmp/vdisk1
            - /tmp/vdisk2

        The above will result in the following zpool create:

        .. code-block:: bash

            zpool create mypool mirror /tmp/vdisk0 /tmp/vdisk1 /tmp/vdisk2

        Creating a 3-way mirror! While you probably expect it to be mirror
        root vdev with 2 devices + a root vdev of 1 device!

    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    # config defaults
    default_config = {
        "import": True,
        "import_dirs": None,
        "device_dir": None,
        "force": False,
    }
    if __grains__["kernel"] == "SunOS":
        default_config["device_dir"] = "/dev/dsk"
    elif __grains__["kernel"] == "Linux":
        default_config["device_dir"] = "/dev"

    # merge state config
    if config:
        default_config.update(config)
    config = default_config

    # ensure properties are zfs values
    if properties:
        properties = __utils__["zfs.from_auto_dict"](properties)
    elif properties is None:
        properties = {}
    if filesystem_properties:
        filesystem_properties = __utils__["zfs.from_auto_dict"](filesystem_properties)
    elif filesystem_properties is None:
        filesystem_properties = {}

    # parse layout
    vdevs = _layout_to_vdev(layout, config["device_dir"])
    if vdevs:
        vdevs.insert(0, name)

    # log configuration
    log.debug("zpool.present::%s::config - %s", name, config)
    log.debug("zpool.present::%s::vdevs - %s", name, vdevs)
    log.debug("zpool.present::%s::properties -  %s", name, properties)
    log.debug(
        "zpool.present::%s::filesystem_properties -  %s", name, filesystem_properties
    )

    # ensure the pool is present
    ret["result"] = False

    # don't do anything because this is a test
    if __opts__["test"]:
        if __salt__["zpool.exists"](name):
            ret["result"] = True
            ret["comment"] = "storage pool {} is {}".format(name, "uptodate")
        else:
            ret["result"] = None
            ret["changes"][name] = "imported" if config["import"] else "created"
            ret["comment"] = "storage pool {} would have been {}".format(
                name, ret["changes"][name]
            )

    # update pool
    elif __salt__["zpool.exists"](name):
        ret["result"] = True

        # fetch current pool properties
        properties_current = __salt__["zpool.get"](name, parsable=True)

        # build list of properties to update
        properties_update = []
        if properties:
            for prop in properties:
                # skip unexisting properties
                if prop not in properties_current:
                    log.warning(
                        "zpool.present::%s::update - unknown property: %s", name, prop
                    )
                    continue

                # compare current and wanted value
                # Enabled "feature@" properties may report either "enabled" or
                # "active", depending on whether they're currently in-use.
                if prop.startswith("feature@") and properties_current[prop] == "active":
                    effective_property = "enabled"
                else:
                    effective_property = properties_current[prop]

                if effective_property != properties[prop]:
                    properties_update.append(prop)

        # update pool properties
        for prop in properties_update:
            res = __salt__["zpool.set"](name, prop, properties[prop])

            if res["set"]:
                if name not in ret["changes"]:
                    ret["changes"][name] = {}
                ret["changes"][name][prop] = properties[prop]
            else:
                ret["result"] = False
                if ret["comment"] == "":
                    ret["comment"] = "The following properties were not updated:"
                ret["comment"] = "{} {}".format(ret["comment"], prop)

        if ret["result"]:
            ret["comment"] = (
                "properties updated" if ret["changes"] else "no update needed"
            )

    # import or create the pool (at least try to anyway)
    else:
        # import pool
        if config["import"]:
            mod_res = __salt__["zpool.import"](
                name,
                force=config["force"],
                dir=config["import_dirs"],
            )

            ret["result"] = mod_res["imported"]
            if ret["result"]:
                ret["changes"][name] = "imported"
                ret["comment"] = f"storage pool {name} was imported"

        # create pool
        if not ret["result"] and vdevs:
            log.debug("zpool.present::%s::creating", name)

            # execute zpool.create
            mod_res = __salt__["zpool.create"](
                *vdevs,
                force=config["force"],
                properties=properties,
                filesystem_properties=filesystem_properties,
            )

            ret["result"] = mod_res["created"]
            if ret["result"]:
                ret["changes"][name] = "created"
                ret["comment"] = f"storage pool {name} was created"
            elif "error" in mod_res:
                ret["comment"] = mod_res["error"]
            else:
                ret["comment"] = f"could not create storage pool {name}"

        # give up, we cannot import the pool and we do not have a layout to create it
        if not ret["result"] and not vdevs:
            ret["comment"] = (
                "storage pool {} was not imported, no (valid) layout specified for"
                " creation".format(name)
            )

    return ret


def absent(name, export=False, force=False):
    """
    ensure storage pool is absent on the system

    name : string
        name of storage pool
    export : boolean
        export instead of destroy the zpool if present
    force : boolean
        force destroy or export

    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    # log configuration
    log.debug("zpool.absent::%s::config::force = %s", name, force)
    log.debug("zpool.absent::%s::config::export = %s", name, export)

    # ensure the pool is absent
    if __salt__["zpool.exists"](name):  # looks like we need to do some work
        mod_res = {}
        ret["result"] = False

        # NOTE: handle test
        if __opts__["test"]:
            ret["result"] = True

        # NOTE: try to export the pool
        elif export:
            mod_res = __salt__["zpool.export"](name, force=force)
            ret["result"] = mod_res["exported"]

        # NOTE: try to destroy the pool
        else:
            mod_res = __salt__["zpool.destroy"](name, force=force)
            ret["result"] = mod_res["destroyed"]

        if ret["result"]:  # update the changes and comment
            ret["changes"][name] = "exported" if export else "destroyed"
            ret["comment"] = "storage pool {} was {}".format(name, ret["changes"][name])
        elif "error" in mod_res:
            ret["comment"] = mod_res["error"]

    else:  # we are looking good
        ret["result"] = True
        ret["comment"] = f"storage pool {name} is absent"

    return ret
