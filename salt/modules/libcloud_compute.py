"""
Apache Libcloud Compute Management
==================================

Connection module for Apache Libcloud Compute management for a full list
of supported clouds, see http://libcloud.readthedocs.io/en/latest/compute/supported_providers.html

Clouds include Amazon EC2, Azure, Google GCE, VMware, OpenStack Nova

.. versionadded:: 2018.3.0

:configuration:
    This module uses a configuration profile for one or multiple cloud providers

    .. code-block:: yaml

        libcloud_compute:
            profile_test1:
              driver: google
              key: service-account@googlecloud.net
              secret: /path/to.key.json
            profile_test2:
              driver: arm
              key: 12345
              secret: mysecret

:depends: apache-libcloud
"""
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602


import logging
import os.path

import salt.utils.args
import salt.utils.compat
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

REQUIRED_LIBCLOUD_VERSION = "2.0.0"
try:
    # pylint: disable=unused-import
    import libcloud
    from libcloud.compute.providers import get_driver
    from libcloud.compute.base import Node

    # pylint: enable=unused-import
    if hasattr(libcloud, "__version__") and _LooseVersion(
        libcloud.__version__
    ) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
        raise ImportError()
    logging.getLogger("libcloud").setLevel(logging.CRITICAL)
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


def __virtual__():
    """
    Only load if libcloud libraries exist.
    """
    if not HAS_LIBCLOUD:
        return (
            False,
            "A apache-libcloud library with version at least {} was not found".format(
                REQUIRED_LIBCLOUD_VERSION
            ),
        )
    return True


def _get_driver(profile):
    config = __salt__["config.option"]("libcloud_compute")[profile]
    cls = get_driver(config["driver"])
    args = config.copy()
    del args["driver"]
    args["key"] = config.get("key")
    args["secret"] = config.get("secret", None)
    if args["secret"] is None:
        del args["secret"]
    args["secure"] = config.get("secure", True)
    args["host"] = config.get("host", None)
    args["port"] = config.get("port", None)
    return cls(**args)


def list_nodes(profile, **libcloud_kwargs):
    """
    Return a list of nodes

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_nodes method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_nodes profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    nodes = conn.list_nodes(**libcloud_kwargs)
    ret = []
    for node in nodes:
        ret.append(_simple_node(node))
    return ret


def list_sizes(profile, location_id=None, **libcloud_kwargs):
    """
    Return a list of node sizes

    :param profile: The profile key
    :type  profile: ``str``

    :param location_id: The location key, from list_locations
    :type  location_id: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_sizes method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_sizes profile1
        salt myminion libcloud_compute.list_sizes profile1 us-east1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    if location_id is not None:
        locations = [loc for loc in conn.list_locations() if loc.id == location_id]
        if not locations:
            raise ValueError("Location not found")
        else:
            sizes = conn.list_sizes(location=locations[0], **libcloud_kwargs)
    else:
        sizes = conn.list_sizes(**libcloud_kwargs)

    ret = []
    for size in sizes:
        ret.append(_simple_size(size))
    return ret


def list_locations(profile, **libcloud_kwargs):
    """
    Return a list of locations for this cloud

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_locations method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_locations profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    locations = conn.list_locations(**libcloud_kwargs)

    ret = []
    for loc in locations:
        ret.append(_simple_location(loc))
    return ret


def reboot_node(node_id, profile, **libcloud_kwargs):
    """
    Reboot a node in the cloud

    :param node_id: Unique ID of the node to reboot
    :type  node_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's reboot_node method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.reboot_node as-2346 profile1
    """
    conn = _get_driver(profile=profile)
    node = _get_by_id(conn.list_nodes(**libcloud_kwargs), node_id)
    return conn.reboot_node(node, **libcloud_kwargs)


def destroy_node(node_id, profile, **libcloud_kwargs):
    """
    Destroy a node in the cloud

    :param node_id: Unique ID of the node to destroy
    :type  node_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's destroy_node method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.destry_node as-2346 profile1
    """
    conn = _get_driver(profile=profile)
    node = _get_by_id(conn.list_nodes(**libcloud_kwargs), node_id)
    return conn.destroy_node(node, **libcloud_kwargs)


def list_volumes(profile, **libcloud_kwargs):
    """
    Return a list of storage volumes for this cloud

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_volumes method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_volumes profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    volumes = conn.list_volumes(**libcloud_kwargs)

    ret = []
    for volume in volumes:
        ret.append(_simple_volume(volume))
    return ret


def list_volume_snapshots(volume_id, profile, **libcloud_kwargs):
    """
    Return a list of storage volumes snapshots for this cloud

    :param volume_id: The volume identifier
    :type  volume_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_volume_snapshots method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_volume_snapshots vol1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    volume = _get_by_id(conn.list_volumes(), volume_id)
    snapshots = conn.list_volume_snapshots(volume, **libcloud_kwargs)

    ret = []
    for snapshot in snapshots:
        ret.append(_simple_volume_snapshot(snapshot))
    return ret


def create_volume(size, name, profile, location_id=None, **libcloud_kwargs):
    """
    Create a storage volume

    :param size: Size of volume in gigabytes (required)
    :type size: ``int``

    :param name: Name of the volume to be created
    :type name: ``str``

    :param location_id: Which data center to create a volume in. If
                            empty, undefined behavior will be selected.
                            (optional)
    :type location_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_volumes method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.create_volume 1000 vol1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    if location_id is not None:
        location = _get_by_id(conn.list_locations(), location_id)
    else:
        location = None
    # TODO : Support creating from volume snapshot

    volume = conn.create_volume(size, name, location, snapshot=None, **libcloud_kwargs)
    return _simple_volume(volume)


def create_volume_snapshot(volume_id, profile, name=None, **libcloud_kwargs):
    """
    Create a storage volume snapshot

    :param volume_id:  Volume ID from which to create the new
                        snapshot.
    :type  volume_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param name: Name of the snapshot to be created (optional)
    :type name: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's create_volume_snapshot method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.create_volume_snapshot vol1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    volume = _get_by_id(conn.list_volumes(), volume_id)

    snapshot = conn.create_volume_snapshot(volume, name=name, **libcloud_kwargs)
    return _simple_volume_snapshot(snapshot)


def attach_volume(node_id, volume_id, profile, device=None, **libcloud_kwargs):
    """
    Attaches volume to node.

    :param node_id:  Node ID to target
    :type  node_id: ``str``

    :param volume_id:  Volume ID from which to attach
    :type  volume_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param device: Where the device is exposed, e.g. '/dev/sdb'
    :type device: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's attach_volume method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.detach_volume vol1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    volume = _get_by_id(conn.list_volumes(), volume_id)
    node = _get_by_id(conn.list_nodes(), node_id)
    return conn.attach_volume(node, volume, device=device, **libcloud_kwargs)


def detach_volume(volume_id, profile, **libcloud_kwargs):
    """
    Detaches a volume from a node.

    :param volume_id:  Volume ID from which to detach
    :type  volume_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's detach_volume method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.detach_volume vol1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    volume = _get_by_id(conn.list_volumes(), volume_id)
    return conn.detach_volume(volume, **libcloud_kwargs)


def destroy_volume(volume_id, profile, **libcloud_kwargs):
    """
    Destroy a volume.

    :param volume_id:  Volume ID from which to destroy
    :type  volume_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's destroy_volume method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.destroy_volume vol1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    volume = _get_by_id(conn.list_volumes(), volume_id)
    return conn.destroy_volume(volume, **libcloud_kwargs)


def destroy_volume_snapshot(volume_id, snapshot_id, profile, **libcloud_kwargs):
    """
    Destroy a volume snapshot.

    :param volume_id:  Volume ID from which the snapshot belongs
    :type  volume_id: ``str``

    :param snapshot_id:  Volume Snapshot ID from which to destroy
    :type  snapshot_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's destroy_volume_snapshot method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.destroy_volume_snapshot snap1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    volume = _get_by_id(conn.list_volumes(), volume_id)
    snapshot = _get_by_id(conn.list_volume_snapshots(volume), snapshot_id)
    return conn.destroy_volume_snapshot(snapshot, **libcloud_kwargs)


def list_images(profile, location_id=None, **libcloud_kwargs):
    """
    Return a list of images for this cloud

    :param profile: The profile key
    :type  profile: ``str``

    :param location_id: The location key, from list_locations
    :type  location_id: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_images method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_images profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    if location_id is not None:
        location = _get_by_id(conn.list_locations(), location_id)
    else:
        location = None
    images = conn.list_images(location=location, **libcloud_kwargs)

    ret = []
    for image in images:
        ret.append(_simple_image(image))
    return ret


def create_image(node_id, name, profile, description=None, **libcloud_kwargs):
    """
    Create an image from a node

    :param node_id: Node to run the task on.
    :type node_id: ``str``

    :param name: name for new image.
    :type name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param description: description for new image.
    :type description: ``description``

    :param libcloud_kwargs: Extra arguments for the driver's create_image method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.create_image server1 my_image profile1
        salt myminion libcloud_compute.create_image server1 my_image profile1 description='test image'
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    node = _get_by_id(conn.list_nodes(), node_id)
    return _simple_image(
        conn.create_image(node, name, description=description, **libcloud_kwargs)
    )


def delete_image(image_id, profile, **libcloud_kwargs):
    """
    Delete an image of a node

    :param image_id: Image to delete
    :type image_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's delete_image method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.delete_image image1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    image = _get_by_id(conn.list_images(), image_id)
    return conn.delete_image(image, **libcloud_kwargs)


def get_image(image_id, profile, **libcloud_kwargs):
    """
    Get an image of a node

    :param image_id: Image to fetch
    :type image_id: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's delete_image method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.get_image image1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    image = conn.get_image(image_id, **libcloud_kwargs)
    return _simple_image(image)


def copy_image(
    source_region, image_id, name, profile, description=None, **libcloud_kwargs
):
    """
    Copies an image from a source region to the current region.

    :param source_region: Region to copy the node from.
    :type source_region: ``str``

    :param image_id: Image to copy.
    :type image_id: ``str``

    :param name: name for new image.
    :type name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param description: description for new image.
    :type name: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's copy_image method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.copy_image us-east1 image1 'new image' profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    image = conn.get_image(image_id, **libcloud_kwargs)
    new_image = conn.copy_image(
        source_region, image, name, description=description, **libcloud_kwargs
    )
    return _simple_image(new_image)


def list_key_pairs(profile, **libcloud_kwargs):
    """
    List all the available key pair objects.

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's list_key_pairs method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.list_key_pairs profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    keys = conn.list_key_pairs(**libcloud_kwargs)

    ret = []
    for key in keys:
        ret.append(_simple_key_pair(key))
    return ret


def get_key_pair(name, profile, **libcloud_kwargs):
    """
    Get a single key pair by name

    :param name: Name of the key pair to retrieve.
    :type name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's get_key_pair method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.get_key_pair pair1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    return _simple_key_pair(conn.get_key_pair(name, **libcloud_kwargs))


def create_key_pair(name, profile, **libcloud_kwargs):
    """
    Create a single key pair by name

    :param name: Name of the key pair to create.
    :type name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's create_key_pair method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.create_key_pair pair1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    return _simple_key_pair(conn.create_key_pair(name, **libcloud_kwargs))


def import_key_pair(name, key, profile, key_type=None, **libcloud_kwargs):
    """
    Import a new public key from string or a file path

    :param name: Key pair name.
    :type name: ``str``

    :param key: Public key material, the string or a path to a file
    :type  key: ``str`` or path ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param key_type: The key pair type, either `FILE` or `STRING`. Will detect if not provided
        and assume that if the string is a path to an existing path it is a FILE, else STRING.
    :type  key_type: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's import_key_pair_from_xxx method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.import_key_pair pair1 key_value_data123 profile1
        salt myminion libcloud_compute.import_key_pair pair1 /path/to/key profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    if os.path.exists(key) or key_type == "FILE":
        return _simple_key_pair(
            conn.import_key_pair_from_file(name, key, **libcloud_kwargs)
        )
    else:
        return _simple_key_pair(
            conn.import_key_pair_from_string(name, key, **libcloud_kwargs)
        )


def delete_key_pair(name, profile, **libcloud_kwargs):
    """
    Delete a key pair

    :param name: Key pair name.
    :type  name: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's import_key_pair_from_xxx method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.delete_key_pair pair1 profile1
    """
    conn = _get_driver(profile=profile)
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    key = conn.get_key_pair(name)
    return conn.delete_key_pair(key, **libcloud_kwargs)


def extra(method, profile, **libcloud_kwargs):
    """
    Call an extended method on the driver

    :param method: Driver's method name
    :type  method: ``str``

    :param profile: The profile key
    :type  profile: ``str``

    :param libcloud_kwargs: Extra arguments for the driver's method
    :type  libcloud_kwargs: ``dict``

    CLI Example:

    .. code-block:: bash

        salt myminion libcloud_compute.extra ex_get_permissions google container_name=my_container object_name=me.jpg --out=yaml
    """
    libcloud_kwargs = salt.utils.args.clean_kwargs(**libcloud_kwargs)
    conn = _get_driver(profile=profile)
    connection_method = getattr(conn, method)
    return connection_method(**libcloud_kwargs)


def _get_by_id(collection, id):
    """
    Get item from a list by the id field
    """
    matches = [item for item in collection if item.id == id]
    if not matches:
        raise ValueError("Could not find a matching item")
    elif len(matches) > 1:
        raise ValueError("The id matched {} items, not 1".format(len(matches)))
    return matches[0]


def _simple_volume(volume):
    return {
        "id": volume.id,
        "name": volume.name,
        "size": volume.size,
        "state": volume.state,
        "extra": volume.extra,
    }


def _simple_location(location):
    return {"id": location.id, "name": location.name, "country": location.country}


def _simple_size(size):
    return {
        "id": size.id,
        "name": size.name,
        "ram": size.ram,
        "disk": size.disk,
        "bandwidth": size.bandwidth,
        "price": size.price,
        "extra": size.extra,
    }


def _simple_node(node):
    return {
        "id": node.id,
        "name": node.name,
        "state": str(node.state),
        "public_ips": node.public_ips,
        "private_ips": node.private_ips,
        "size": _simple_size(node.size) if node.size else {},
        "extra": node.extra,
    }


def _simple_volume_snapshot(snapshot):
    return {
        "id": snapshot.id,
        "name": snapshot.name if hasattr(snapshot, "name") else snapshot.id,
        "size": snapshot.size,
        "extra": snapshot.extra,
        "created": snapshot.created,
        "state": snapshot.state,
    }


def _simple_image(image):
    return {
        "id": image.id,
        "name": image.name,
        "extra": image.extra,
    }


def _simple_key_pair(key):
    return {
        "name": key.name,
        "fingerprint": key.fingerprint,
        "public_key": key.public_key,
        "private_key": key.private_key,
        "extra": key.extra,
    }
