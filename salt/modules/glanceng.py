"""
Glance module for interacting with OpenStack Glance

.. versionadded:: 2018.3.0

:depends:shade

Example configuration

.. code-block:: yaml

    glance:
      cloud: default

.. code-block:: yaml

    glance:
      auth:
        username: admin
        password: password123
        user_domain_name: mydomain
        project_name: myproject
        project_domain_name: myproject
        auth_url: https://example.org:5000/v3
      identity_api_version: 3
"""

HAS_SHADE = False
try:
    import shade

    HAS_SHADE = True
except ImportError:
    pass

__virtualname__ = "glanceng"


def __virtual__():
    """
    Only load this module if shade python module is installed
    """
    if HAS_SHADE:
        return __virtualname__
    return (
        False,
        "The glanceng execution module failed to load: shade python module is not"
        " available",
    )


def compare_changes(obj, **kwargs):
    """
    Compare two dicts returning only keys that exist in the first dict and are
    different in the second one
    """
    changes = {}
    for k, v in obj.items():
        if k in kwargs:
            if v != kwargs[k]:
                changes[k] = kwargs[k]
    return changes


def _clean_kwargs(keep_name=False, **kwargs):
    """
    Sanatize the arguments for use with shade
    """
    if "name" in kwargs and not keep_name:
        kwargs["name_or_id"] = kwargs.pop("name")

    return __utils__["args.clean_kwargs"](**kwargs)


def setup_clouds(auth=None):
    """
    Call functions to create Shade cloud objects in __context__ to take
    advantage of Shade's in-memory caching across several states
    """
    get_operator_cloud(auth)
    get_openstack_cloud(auth)


def get_operator_cloud(auth=None):
    """
    Return an operator_cloud
    """
    if auth is None:
        auth = __salt__["config.option"]("glance", {})
    if "shade_opcloud" in __context__:
        if __context__["shade_opcloud"].auth == auth:
            return __context__["shade_opcloud"]
    __context__["shade_opcloud"] = shade.operator_cloud(**auth)
    return __context__["shade_opcloud"]


def get_openstack_cloud(auth=None):
    """
    Return an openstack_cloud
    """
    if auth is None:
        auth = __salt__["config.option"]("glance", {})
    if "shade_oscloud" in __context__:
        if __context__["shade_oscloud"].auth == auth:
            return __context__["shade_oscloud"]
    __context__["shade_oscloud"] = shade.openstack_cloud(**auth)
    return __context__["shade_oscloud"]


def image_create(auth=None, **kwargs):
    """
    Create an image

    CLI Example:

    .. code-block:: bash

        salt '*' glanceng.image_create name=cirros file=cirros.raw disk_format=raw
        salt '*' glanceng.image_create name=cirros file=cirros.raw disk_format=raw hw_scsi_model=virtio-scsi hw_disk_bus=scsi
    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_image(**kwargs)


def image_delete(auth=None, **kwargs):
    """
    Delete an image

    CLI Example:

    .. code-block:: bash

        salt '*' glanceng.image_delete name=image1
        salt '*' glanceng.image_delete name=0e4febc2a5ab4f2c8f374b054162506d
    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_image(**kwargs)


def image_list(auth=None, **kwargs):
    """
    List images

    CLI Example:

    .. code-block:: bash

        salt '*' glanceng.image_list
        salt '*' glanceng.image_list
    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_images(**kwargs)


def image_search(auth=None, **kwargs):
    """
    Search for images

    CLI Example:

    .. code-block:: bash

        salt '*' glanceng.image_search name=image1
        salt '*' glanceng.image_search
    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.search_images(**kwargs)


def image_get(auth=None, **kwargs):
    """
    Get a single image

    CLI Example:

    .. code-block:: bash

        salt '*' glanceng.image_get name=image1
        salt '*' glanceng.image_get name=0e4febc2a5ab4f2c8f374b054162506d
    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_image(**kwargs)


def update_image_properties(auth=None, **kwargs):
    """
    Update properties for an image

    CLI Example:

    .. code-block:: bash

        salt '*' glanceng.update_image_properties name=image1 hw_scsi_model=virtio-scsi hw_disk_bus=scsi
        salt '*' glanceng.update_image_properties name=0e4febc2a5ab4f2c8f374b054162506d min_ram=1024
    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_image_properties(**kwargs)
