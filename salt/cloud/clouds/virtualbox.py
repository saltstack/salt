"""
A salt cloud provider that lets you use virtualbox on your machine
and act as a cloud.

For now this will only clone existing VMs. It's best to create a template
from which we will clone.

Followed
https://docs.saltstack.com/en/latest/topics/cloud/cloud.html#non-libcloud-based-modules
to create this.

Dicts provided by salt:
    __opts__ : contains the options used to run Salt Cloud,
        as well as a set of configuration and environment variables
"""

# Import python libs
import logging

# Import salt libs
from salt.exceptions import SaltCloudSystemExit
import salt.config as config
import salt.utils.cloud as cloud
from utils.virtualbox import vb_list_machines, vb_clone_vm, HAS_LIBS, vb_machine_exists, vb_destroy_machine, \
    vb_machinestate_to_str, vb_get_machine

log = logging.getLogger(__name__)

"""
The name salt will identify the lib by
"""
__virtualname__ = 'virtualbox'


def __virtual__():
    """
    This function determines whether or not
    to make this cloud module available upon execution.
    Most often, it uses get_configured_provider() to determine
     if the necessary configuration has been set up.
    It may also check for necessary imports decide whether to load the module.
    In most cases, it will return a True or False value.
    If the name of the driver used does not match the filename,
     then that name should be returned instead of True.

    @return True|False|str
    """

    if not HAS_LIBS:
        return False

    if get_configured_provider() is False:
        return False

    # If the name of the driver used does not match the filename,
    #  then that name should be returned instead of True.
    # return __virtualname__
    return True


def get_configured_provider():
    """
    Return the first configured instance.
    """
    configured = config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ()  # keys we need from the provider configuration
    )
    log.debug("First virtualbox configuration %s" % configured)
    return configured


def create(vm_info):
    """
    Creates a virtual machine from the given VM information.
    This is what is used to request a virtual machine to be created by the
    cloud provider, wait for it to become available,
    and then (optionally) log in and install Salt on it.

    Fires:
        "starting create" : This event is tagged salt/cloud/<vm name>/creating.
        The payload contains the names of the VM, profile and provider.

    @param vm_info {dict}
            {
                name: <str>
                profile: <dict>
                driver: <provider>:<profile>
                clonefrom: <vm_name>
            }
    @return dict of resulting vm. !!!Passwords can and should be included!!!
    """
    log.debug("Creating virtualbox with %s" % vm_info)
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_info['profile'] and config.is_profile_configured(
            __opts__,
                __active_provider_name__ or 'virtualbox',
            vm_info['profile']
        ) is False:
            return False
    except AttributeError:
        pass

    log.debug("Going to fire event: starting create")
    cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_info['name']),
        {
            'name': vm_info['name'],
            'profile': vm_info['profile'],
            'driver': vm_info['driver'],
        },
        transport=__opts__['transport']
    )

    # TODO Calculate kwargs with parameters required by virtualbox
    # to create the virtual machine.
    request_kwargs = {
        'name': vm_info['name'],
        'clone_from': vm_info['clonefrom']
    }

    cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_info['name']),
        request_kwargs,
        transport=__opts__['transport']
    )
    vm_result = vb_clone_vm(**request_kwargs)

    # TODO Prepare deployment of salt on the vm
    # Any private data, including passwords and keys (including public keys)
    # should be stripped from the deploy kwargs before the event is fired.
    deploy_kwargs = {
    }

    cloud.fire_event(
        'event',
        'deploying salt',
        'salt/cloud/{0}/deploying'.format(vm_info['name']),
        deploy_kwargs,
        transport=__opts__['transport']
    )

    deploy_kwargs.update({
        # TODO Add private data
    })

    # TODO wait for target machine to become available
    # TODO deploy!
    # Do we have to call this?
    # cloud.deploy_script(None, **deploy_kwargs)

    cloud.fire_event(
        'event',
        'created machine',
        'salt/cloud/{0}/created'.format(vm_info['name']),
        vm_result,
        transport=__opts__['transport']
    )

    # Passwords should be included in this object!!
    return vm_result


def list_nodes_full(kwargs=None, call=None):
    """
    All information available about all nodes should be returned in this function.
    The fields in the list_nodes() function should also be returned,
    even if they would not normally be provided by the cloud provider.

    This is because some functions both within Salt and 3rd party will break if an expected field is not present.
    This function is normally called with the -F option:

    .. code-block:: bash
        salt-cloud -F


    @param kwargs:
    @type kwargs:
    @param call:
    @type call:
    @return:
    @rtype:
    """
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called '
            'with -f or --function.'
        )

    machines = {}

    # TODO ask for the correct attributes e.g state and private_ips
    for machine in vb_list_machines():
        name = machine.get("name")
        if name:
            machines[name] = machine
            machine.update({
                "id": machine.get("id", ""),
                "image": machine.get("image", ""),
                "size": "%s MB" % machine.get("memorySize", 0),
                "state": vb_machinestate_to_str(machine.get("state", -1))[0],
                "private_ips": [],
                "public_ips": [],
            })
            del machine["name"]

    return machines


def list_nodes(kwargs=None, call=None):
    """
    This function returns a list of nodes available on this cloud provider, using the following fields:

    id (str)
    image (str)
    size (str)
    state (str)
    private_ips (list)
    public_ips (list)

    No other fields should be returned in this function, and all of these fields should be returned, even if empty.
    The private_ips and public_ips fields should always be of a list type, even if empty,
    and the other fields should always be of a str type.
    This function is normally called with the -Q option:

    .. code-block:: bash
        salt-cloud -Q


    @param kwargs:
    @type kwargs:
    @param call:
    @type call:
    @return:
    @rtype:
    """
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called '
            'with -f or --function.'
        )

    attributes = [
        "id",
        "image",
        "size",
        "state",
        "private_ips",
        "public_ips",
    ]
    machines_full_info = list_nodes_full()
    return dict([
                    (key, dict([
                                   (attribute, value[attribute])
                                   for attribute in attributes
                                   ])
                     )
                    for key, value in machines_full_info.iteritems()
                    ])


def list_nodes_select(call=None):
    """
    Return a list of the VMs that are on the provider, with select fields
    """
    log.info(__opts__)
    return cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def destroy(name, call=None):
    """
    This function irreversibly destroys a virtual machine on the cloud provider.
    Before doing so, it should fire an event on the Salt event bus.

    The tag for this event is `salt/cloud/<vm name>/destroying`.
    Once the virtual machine has been destroyed, another event is fired.
    The tag for that event is `salt/cloud/<vm name>/destroyed`.

    Dependencies:
        list_nodes

    @param name:
    @type name: str
    @param call:
    @type call:
    @return: True if all went well, otherwise an error message
    @rtype: bool|str
    """
    print "==========================================="
    log.info("Attempting to delete instance %s" % name)
    if not vb_machine_exists(name):
        return "%s doesn't exist and can't be deleted" % name

    cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    vb_destroy_machine(name)

    cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )


# TODO implement actions e.g start, stop, restart, etc.

# TODO implement functions

def show_image(kwargs, call=None):
    """
    Show the details of an image
    """
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_image action must be called with -f or --function.'
        )

    name = kwargs['image']
    log.info("Showing image %s" % name)
    machine = vb_get_machine(name)

    ret = {
        machine["name"]: machine
    }
    del machine["name"]
    return ret
