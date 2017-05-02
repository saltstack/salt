# -*- coding: utf-8 -*-
'''
Connection library for VMware

.. versionadded:: 2015.8.2

This is a base library used by a number of VMware services such as VMware
ESX, ESXi, and vCenter servers.

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>
:codeauthor: Alexandru Bleotu <alexandru.bleotu@morganstaley.com>

Dependencies
~~~~~~~~~~~~

- pyVmomi Python Module
- ESXCLI: This dependency is only needed to use the ``esxcli`` function. No other
  functions in this module rely on ESXCLI.

pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original VMware utils file
was developed against.

ESXCLI
------

This dependency is only needed to use the ``esxcli`` function. At the time of this
writing, no other functions in this module rely on ESXCLI.

The ESXCLI package is also referred to as the VMware vSphere CLI, or vCLI. VMware
provides vCLI package installation instructions for `vSphere 5.5`_ and
`vSphere 6.0`_.

.. _vSphere 5.5: http://pubs.vmware.com/vsphere-55/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html
.. _vSphere 6.0: http://pubs.vmware.com/vsphere-60/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html

Once all of the required dependencies are in place and the vCLI package is
installed, you can check to see if you can connect to your ESXi host or vCenter
server by running the following command:

.. code-block:: bash

    esxcli -s <host-location> -u <username> -p <password> system syslog config get

If the connection was successful, ESXCLI was successfully installed on your system.
You should see output related to the ESXi host's syslog configuration.

'''

# Import Python Libs
from __future__ import absolute_import
import atexit
import errno
import logging
import time

# Import Salt Libs
import salt.exceptions
import salt.modules.cmdmod
import salt.utils


# Import Third Party Libs
import salt.ext.six as six
from salt.ext.six.moves.http_client import BadStatusLine  # pylint: disable=E0611
try:
    from pyVim.connect import GetSi, SmartConnect, Disconnect, GetStub
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

try:
    import gssapi
    import base64
    HAS_GSSAPI = True
except ImportError:
    HAS_GSSAPI = False

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if PyVmomi is installed.
    '''
    if HAS_PYVMOMI:
        return True
    else:
        return False, 'Missing dependency: The salt.utils.vmware module requires pyVmomi.'


def esxcli(host, user, pwd, cmd, protocol=None, port=None, esxi_host=None, credstore=None):
    '''
    Shell out and call the specified esxcli commmand, parse the result
    and return something sane.

    :param host: ESXi or vCenter host to connect to
    :param user: User to connect as, usually root
    :param pwd: Password to connect with
    :param port: TCP port
    :param cmd: esxcli command and arguments
    :param esxi_host: If `host` is a vCenter host, then esxi_host is the
                      ESXi machine on which to execute this command
    :param credstore: Optional path to the credential store file

    :return: Dictionary
    '''

    esx_cmd = salt.utils.which('esxcli')
    if not esx_cmd:
        log.error('Missing dependency: The salt.utils.vmware.esxcli function requires ESXCLI.')
        return False

    # Set default port and protocol if none are provided.
    if port is None:
        port = 443
    if protocol is None:
        protocol = 'https'

    if credstore:
        esx_cmd += ' --credstore \'{0}\''.format(credstore)

    if not esxi_host:
        # Then we are connecting directly to an ESXi server,
        # 'host' points at that server, and esxi_host is a reference to the
        # ESXi instance we are manipulating
        esx_cmd += ' -s {0} -u {1} -p \'{2}\' ' \
                   '--protocol={3} --portnumber={4} {5}'.format(host,
                                                                user,
                                                                pwd,
                                                                protocol,
                                                                port,
                                                                cmd)
    else:
        esx_cmd += ' -s {0} -h {1} -u {2} -p \'{3}\' ' \
                   '--protocol={4} --portnumber={5} {6}'.format(host,
                                                                esxi_host,
                                                                user,
                                                                pwd,
                                                                protocol,
                                                                port,
                                                                cmd)

    ret = salt.modules.cmdmod.run_all(esx_cmd, output_loglevel='quiet')

    return ret


def _get_service_instance(host, username, password, protocol,
                          port, mechanism, principal, domain):
    '''
    Internal method to authenticate with a vCenter server or ESX/ESXi host
    and return the service instance object.
    '''
    log.trace('Retrieving new service instance')
    token = None
    if mechanism == 'userpass':
        if username is None:
            raise salt.exceptions.CommandExecutionError(
                'Login mechanism userpass was specified but the mandatory '
                'parameter \'username\' is missing')
        if password is None:
            raise salt.exceptions.CommandExecutionError(
                'Login mechanism userpass was specified but the mandatory '
                'parameter \'password\' is missing')
    elif mechanism == 'sspi':
        if principal is not None and domain is not None:
            try:
                token = get_gssapi_token(principal, host, domain)
            except Exception as exc:
                raise salt.exceptions.VMwareConnectionError(str(exc))
        else:
            err_msg = 'Login mechanism \'{0}\' was specified but the' \
                      ' mandatory parameters are missing'.format(mechanism)
            raise salt.exceptions.CommandExecutionError(err_msg)
    else:
        raise salt.exceptions.CommandExecutionError(
            'Unsupported mechanism: \'{0}\''.format(mechanism))
    try:
        log.trace('Connecting using the \'{0}\' mechanism, with username '
                  '\'{1}\''.format(mechanism, username))
        service_instance = SmartConnect(
            host=host,
            user=username,
            pwd=password,
            protocol=protocol,
            port=port,
            b64token=token,
            mechanism=mechanism)
    except TypeError as exc:
        if 'unexpected keyword argument' in exc.message:
            log.error('Initial connect to the VMware endpoint failed with {0}'.format(exc.message))
            log.error('This may mean that a version of PyVmomi EARLIER than 6.0.0.2016.6 is installed.')
            log.error('We recommend updating to that version or later.')
            raise
    except Exception as exc:

        default_msg = 'Could not connect to host \'{0}\'. ' \
                      'Please check the debug log for more information.'.format(host)

        try:
            if (isinstance(exc, vim.fault.HostConnectFault) and
                '[SSL: CERTIFICATE_VERIFY_FAILED]' in exc.msg) or \
               '[SSL: CERTIFICATE_VERIFY_FAILED]' in str(exc):

                import ssl
                service_instance = SmartConnect(
                    host=host,
                    user=username,
                    pwd=password,
                    protocol=protocol,
                    port=port,
                    sslContext=ssl._create_unverified_context(),
                    b64token=token,
                    mechanism=mechanism)
            else:
                err_msg = exc.msg if hasattr(exc, 'msg') else default_msg
                log.trace(exc)
                raise salt.exceptions.VMwareConnectionError(err_msg)
        except Exception as exc:
            if 'certificate verify failed' in str(exc):
                import ssl
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                context.verify_mode = ssl.CERT_NONE
                try:
                    service_instance = SmartConnect(
                        host=host,
                        user=username,
                        pwd=password,
                        protocol=protocol,
                        port=port,
                        sslContext=context,
                        b64token=token,
                        mechanism=mechanism
                    )
                except Exception as exc:
                    err_msg = exc.msg if hasattr(exc, 'msg') else str(exc)
                    log.trace(err_msg)
                    raise salt.exceptions.VMwareConnectionError(
                        'Could not connect to host \'{0}\': '
                        '{1}'.format(host, err_msg))
            else:
                err_msg = exc.msg if hasattr(exc, 'msg') else default_msg
                log.trace(exc)
                raise salt.exceptions.VMwareConnectionError(err_msg)
    atexit.register(Disconnect, service_instance)
    return service_instance


def get_customizationspec_ref(si, customization_spec_name):
    '''
    Get a reference to a VMware customization spec for the purposes of customizing a clone

    si
        ServiceInstance for the vSphere or ESXi server (see get_service_instance)

    customization_spec_name
        Name of the customization spec

    '''
    customization_spec_name = si.content.customizationSpecManager.GetCustomizationSpec(name=customization_spec_name)
    return customization_spec_name


def get_datastore_ref(si, datastore_name):
    '''
    Get a reference to a VMware datastore for the purposes of adding/removing disks

    si
        ServiceInstance for the vSphere or ESXi server (see get_service_instance)

    datastore_name
        Name of the datastore

    '''
    inventory = get_inventory(si)
    container = inventory.viewManager.CreateContainerView(inventory.rootFolder, [vim.Datastore], True)
    for item in container.view:
        if item.name == datastore_name:
            return item
    return None


def get_service_instance(host, username=None, password=None, protocol=None,
                         port=None, mechanism='userpass', principal=None,
                         domain=None):
    '''
    Authenticate with a vCenter server or ESX/ESXi host and return the service instance object.

    host
        The location of the vCenter server or ESX/ESXi host.

    username
        The username used to login to the vCenter server or ESX/ESXi host.
        Required if mechanism is ``userpass``

    password
        The password used to login to the vCenter server or ESX/ESXi host.
        Required if mechanism is ``userpass``

    protocol
        Optionally set to alternate protocol if the vCenter server or ESX/ESXi host is not
        using the default protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the vCenter server or ESX/ESXi host is not
        using the default port. Default port is ``443``.

    mechanism
        pyVmomi connection mechanism. Can either be ``userpass`` or ``sspi``.
        Default mechanism is ``userpass``.

    principal
        Kerberos service principal. Required if mechanism is ``sspi``

    domain
        Kerberos user domain. Required if mechanism is ``sspi``
    '''

    if protocol is None:
        protocol = 'https'
    if port is None:
        port = 443

    service_instance = GetSi()
    if service_instance:
        stub = GetStub()
        if salt.utils.is_proxy() or (hasattr(stub, 'host') and stub.host != ':'.join([host, str(port)])):
            # Proxies will fork and mess up the cached service instance.
            # If this is a proxy or we are connecting to a different host
            # invalidate the service instance to avoid a potential memory leak
            # and reconnect
            Disconnect(service_instance)
            service_instance = None
        else:
            return service_instance

    if not service_instance:
        service_instance = _get_service_instance(host,
                                                 username,
                                                 password,
                                                 protocol,
                                                 port,
                                                 mechanism,
                                                 principal,
                                                 domain)

    # Test if data can actually be retrieved or connection has gone stale
    log.trace('Checking connection is still authenticated')
    try:
        service_instance.CurrentTime()
    except vim.fault.NotAuthenticated:
        log.trace('Session no longer authenticating. Reconnecting')
        Disconnect(service_instance)
        service_instance = _get_service_instance(host,
                                                 username,
                                                 password,
                                                 protocol,
                                                 port,
                                                 mechanism,
                                                 principal,
                                                 domain)
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)

    return service_instance


def get_service_instance_from_managed_object(mo_ref, name='<unnamed>'):
    '''
    Retrieves the service instance from a managed object.

    me_ref
        Reference to a managed object (of type vim.ManagedEntity).

    name
        Name of managed object. This field is optional.
    '''
    if not name:
        name = mo_ref.name
    log.trace('[{0}] Retrieving service instance from managed object'
              ''.format(name))
    si = vim.ServiceInstance('ServiceInstance')
    si._stub = mo_ref._stub
    return si


def disconnect(service_instance):
    '''
    Function that disconnects from the vCenter server or ESXi host

    service_instance
        The Service Instance from which to obtain managed object references.
    '''
    log.trace('Disconnecting')
    try:
        Disconnect(service_instance)
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def is_connection_to_a_vcenter(service_instance):
    '''
    Function that returns True if the connection is made to a vCenter Server and
    False if the connection is made to an ESXi host

    service_instance
        The Service Instance from which to obtain managed object references.
    '''
    try:
        api_type = service_instance.content.about.apiType
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    log.trace('api_type = {0}'.format(api_type))
    if api_type == 'VirtualCenter':
        return True
    elif api_type == 'HostAgent':
        return False
    else:
        raise salt.exceptions.VMwareApiError(
            'Unexpected api type \'{0}\' . Supported types: '
            '\'VirtualCenter/HostAgent\''.format(api_type))


def _get_dvs(service_instance, dvs_name):
    '''
    Return a reference to a Distributed Virtual Switch object.

    :param service_instance: PyVmomi service instance
    :param dvs_name: Name of DVS to return
    :return: A PyVmomi DVS object
    '''
    switches = list_dvs(service_instance)
    if dvs_name in switches:
        inventory = get_inventory(service_instance)
        container = inventory.viewManager.CreateContainerView(inventory.rootFolder, [vim.DistributedVirtualSwitch], True)
        for item in container.view:
            if item.name == dvs_name:
                return item

    return None


def _get_pnics(host_reference):
    '''
    Helper function that returns a list of PhysicalNics and their information.
    '''
    return host_reference.config.network.pnic


def _get_vnics(host_reference):
    '''
    Helper function that returns a list of VirtualNics and their information.
    '''
    return host_reference.config.network.vnic


def _get_vnic_manager(host_reference):
    '''
    Helper function that returns a list of Virtual NicManagers
    and their information.
    '''
    return host_reference.configManager.virtualNicManager


def _get_dvs_portgroup(dvs, portgroup_name):
    '''
    Return a portgroup object corresponding to the portgroup name on the dvs

    :param dvs: DVS object
    :param portgroup_name: Name of portgroup to return
    :return: Portgroup object
    '''
    for portgroup in dvs.portgroup:
        if portgroup.name == portgroup_name:
            return portgroup

    return None


def _get_dvs_uplink_portgroup(dvs, portgroup_name):
    '''
    Return a portgroup object corresponding to the portgroup name on the dvs

    :param dvs: DVS object
    :param portgroup_name: Name of portgroup to return
    :return: Portgroup object
    '''
    for portgroup in dvs.portgroup:
        if portgroup.name == portgroup_name:
            return portgroup

    return None


def get_gssapi_token(principal, host, domain):
    '''
    Get the gssapi token for Kerberos connection

    principal
       The service principal
    host
       Host url where we would like to authenticate
    domain
       Kerberos user domain
    '''

    if not HAS_GSSAPI:
        raise ImportError('The gssapi library is not imported.')

    service = '{0}/{1}@{2}'.format(principal, host, domain)
    log.debug('Retrieving gsspi token for service {0}'.format(service))
    service_name = gssapi.Name(service, gssapi.C_NT_USER_NAME)
    ctx = gssapi.InitContext(service_name)
    in_token = None
    while not ctx.established:
        out_token = ctx.step(in_token)
        if out_token:
            if six.PY2:
                return base64.b64encode(out_token)
            return base64.b64encode(salt.utils.to_bytes(out_token))
        if ctx.established:
            break
        if not in_token:
            raise salt.exceptions.CommandExecutionError(
                'Can\'t receive token, no response from server')
    raise salt.exceptions.CommandExecutionError(
        'Context established, but didn\'t receive token')


def get_hardware_grains(service_instance):
    '''
    Return hardware info for standard minion grains if the service_instance is a HostAgent type

    service_instance
        The service instance object to get hardware info for

    .. versionadded:: 2016.11.0
    '''
    hw_grain_data = {}
    if get_inventory(service_instance).about.apiType == 'HostAgent':
        view = service_instance.content.viewManager.CreateContainerView(service_instance.RetrieveContent().rootFolder,
                                                                        [vim.HostSystem], True)
        if view:
            if view.view:
                if len(view.view) > 0:
                    hw_grain_data['manufacturer'] = view.view[0].hardware.systemInfo.vendor
                    hw_grain_data['productname'] = view.view[0].hardware.systemInfo.model

                    for _data in view.view[0].hardware.systemInfo.otherIdentifyingInfo:
                        if _data.identifierType.key == 'ServiceTag':
                            hw_grain_data['serialnumber'] = _data.identifierValue

                    hw_grain_data['osfullname'] = view.view[0].summary.config.product.fullName
                    hw_grain_data['osmanufacturer'] = view.view[0].summary.config.product.vendor
                    hw_grain_data['osrelease'] = view.view[0].summary.config.product.version
                    hw_grain_data['osbuild'] = view.view[0].summary.config.product.build
                    hw_grain_data['os_family'] = view.view[0].summary.config.product.name
                    hw_grain_data['os'] = view.view[0].summary.config.product.name
                    hw_grain_data['mem_total'] = view.view[0].hardware.memorySize /1024/1024
                    hw_grain_data['biosversion'] = view.view[0].hardware.biosInfo.biosVersion
                    hw_grain_data['biosreleasedate'] = view.view[0].hardware.biosInfo.releaseDate.date().strftime('%m/%d/%Y')
                    hw_grain_data['cpu_model'] = view.view[0].hardware.cpuPkg[0].description
                    hw_grain_data['kernel'] = view.view[0].summary.config.product.productLineId
                    hw_grain_data['num_cpu_sockets'] = view.view[0].hardware.cpuInfo.numCpuPackages
                    hw_grain_data['num_cpu_cores'] = view.view[0].hardware.cpuInfo.numCpuCores
                    hw_grain_data['num_cpus'] = hw_grain_data['num_cpu_sockets'] * hw_grain_data['num_cpu_cores']
                    hw_grain_data['ip_interfaces'] = {}
                    hw_grain_data['ip4_interfaces'] = {}
                    hw_grain_data['ip6_interfaces'] = {}
                    hw_grain_data['hwaddr_interfaces'] = {}
                    for _vnic in view.view[0].configManager.networkSystem.networkConfig.vnic:
                        hw_grain_data['ip_interfaces'][_vnic.device] = []
                        hw_grain_data['ip4_interfaces'][_vnic.device] = []
                        hw_grain_data['ip6_interfaces'][_vnic.device] = []

                        hw_grain_data['ip_interfaces'][_vnic.device].append(_vnic.spec.ip.ipAddress)
                        hw_grain_data['ip4_interfaces'][_vnic.device].append(_vnic.spec.ip.ipAddress)
                        if _vnic.spec.ip.ipV6Config:
                            hw_grain_data['ip6_interfaces'][_vnic.device].append(_vnic.spec.ip.ipV6Config.ipV6Address)
                        hw_grain_data['hwaddr_interfaces'][_vnic.device] = _vnic.spec.mac
                    hw_grain_data['host'] = view.view[0].configManager.networkSystem.dnsConfig.hostName
                    hw_grain_data['domain'] = view.view[0].configManager.networkSystem.dnsConfig.domainName
                    hw_grain_data['fqdn'] = '{0}{1}{2}'.format(
                            view.view[0].configManager.networkSystem.dnsConfig.hostName,
                            ('.' if view.view[0].configManager.networkSystem.dnsConfig.domainName else ''),
                            view.view[0].configManager.networkSystem.dnsConfig.domainName)

                    for _pnic in view.view[0].configManager.networkSystem.networkInfo.pnic:
                        hw_grain_data['hwaddr_interfaces'][_pnic.device] = _pnic.mac

                    hw_grain_data['timezone'] = view.view[0].configManager.dateTimeSystem.dateTimeInfo.timeZone.name
                view = None
    return hw_grain_data


def get_inventory(service_instance):
    '''
    Return the inventory of a Service Instance Object.

    service_instance
        The Service Instance Object for which to obtain inventory.
    '''
    return service_instance.RetrieveContent()


def get_root_folder(service_instance):
    '''
    Returns the root folder of a vCenter.

    service_instance
        The Service Instance Object for which to obtain the root folder.
    '''
    try:
        log.trace('Retrieving root folder')
        return service_instance.RetrieveContent().rootFolder
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def get_content(service_instance, obj_type, property_list=None,
                container_ref=None, traversal_spec=None,
                local_properties=False):
    '''
    Returns the content of the specified type of object for a Service Instance.

    For more information, please see:
    http://pubs.vmware.com/vsphere-50/index.jsp?topic=%2Fcom.vmware.wssdk.pg.doc_50%2FPG_Ch5_PropertyCollector.7.6.html

    service_instance
        The Service Instance from which to obtain content.

    obj_type
        The type of content to obtain.

    property_list
        An optional list of object properties to used to return even more filtered content results.

    container_ref
        An optional reference to the managed object to search under. Can either be an object of type Folder, Datacenter,
        ComputeResource, Resource Pool or HostSystem. If not specified, default behaviour is to search under the inventory
        rootFolder.

    traversal_spec
        An optional TraversalSpec to be used instead of the standard
        ``Traverse All`` spec.

    local_properties
        Flag specifying whether the properties to be retrieved are local to the
        container. If that is the case, the traversal spec needs to be None.
    '''
    # Start at the rootFolder if container starting point not specified
    if not container_ref:
        container_ref = get_root_folder(service_instance)

    # By default, the object reference used as the starting poing for the filter
    # is the container_ref passed in the function
    obj_ref = container_ref
    local_traversal_spec = False
    if not traversal_spec and not local_properties:
        local_traversal_spec = True
        # We don't have a specific traversal spec override so we are going to
        # get everything using a container view
        try:
            obj_ref = service_instance.content.viewManager.CreateContainerView(
                container_ref, [obj_type], True)
        except vim.fault.VimFault as exc:
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            raise salt.exceptions.VMwareRuntimeError(exc.msg)

        # Create 'Traverse All' traversal spec to determine the path for
        # collection
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name='traverseEntities',
            path='view',
            skip=False,
            type=vim.view.ContainerView
        )

    # Create property spec to determine properties to be retrieved
    property_spec = vmodl.query.PropertyCollector.PropertySpec(
        type=obj_type,
        all=True if not property_list else False,
        pathSet=property_list
    )

    # Create object spec to navigate content
    obj_spec = vmodl.query.PropertyCollector.ObjectSpec(
        obj=obj_ref,
        skip=True if not local_properties else False,
        selectSet=[traversal_spec] if not local_properties else None
    )

    # Create a filter spec and specify object, property spec in it
    filter_spec = vmodl.query.PropertyCollector.FilterSpec(
        objectSet=[obj_spec],
        propSet=[property_spec],
        reportMissingObjectsInResults=False
    )

    # Retrieve the contents
    try:
        content = service_instance.content.propertyCollector.RetrieveContents([filter_spec])
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)

    # Destroy the object view
    if local_traversal_spec:
        try:
            obj_ref.Destroy()
        except vim.fault.VimFault as exc:
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            raise salt.exceptions.VMwareRuntimeError(exc.msg)

    return content


def get_mor_by_property(service_instance, object_type, property_value, property_name='name', container_ref=None):
    '''
    Returns the first managed object reference having the specified property value.

    service_instance
        The Service Instance from which to obtain managed object references.

    object_type
        The type of content for which to obtain managed object references.

    property_value
        The name of the property for which to obtain the managed object reference.

    property_name
        An object property used to return the specified object reference results. Defaults to ``name``.

    container_ref
        An optional reference to the managed object to search under. Can either be an object of type Folder, Datacenter,
        ComputeResource, Resource Pool or HostSystem. If not specified, default behaviour is to search under the inventory
        rootFolder.
    '''
    # Get list of all managed object references with specified property
    object_list = get_mors_with_properties(service_instance, object_type, property_list=[property_name], container_ref=container_ref)

    for obj in object_list:
        obj_id = str(obj.get('object', '')).strip('\'"')
        if obj[property_name] == property_value or property_value == obj_id:
            return obj['object']

    return None


def get_mors_with_properties(service_instance, object_type, property_list=None,
                             container_ref=None, traversal_spec=None,
                             local_properties=False):
    '''
    Returns a list containing properties and managed object references for the managed object.

    service_instance
        The Service Instance from which to obtain managed object references.

    object_type
        The type of content for which to obtain managed object references.

    property_list
        An optional list of object properties used to return even more filtered managed object reference results.

    container_ref
        An optional reference to the managed object to search under. Can either be an object of type Folder, Datacenter,
        ComputeResource, Resource Pool or HostSystem. If not specified, default behaviour is to search under the inventory
        rootFolder.

    traversal_spec
        An optional TraversalSpec to be used instead of the standard
        ``Traverse All`` spec

    local_properties
        Flag specigying whether the properties to be retrieved are local to the
        container. If that is the case, the traversal spec needs to be None.
    '''
    # Get all the content
    content_args = [service_instance, object_type]
    content_kwargs = {'property_list': property_list,
                      'container_ref': container_ref,
                      'traversal_spec': traversal_spec,
                      'local_properties': local_properties}
    try:
        content = get_content(*content_args, **content_kwargs)
    except BadStatusLine:
        content = get_content(*content_args, **content_kwargs)
    except IOError as e:
        if e.errno != errno.EPIPE:
            raise e
        content = get_content(*content_args, **content_kwargs)

    object_list = []
    for obj in content:
        properties = {}
        for prop in obj.propSet:
            properties[prop.name] = prop.val
        properties['object'] = obj.obj
        object_list.append(properties)
    log.trace('Retrieved {0} objects'.format(len(object_list)))
    return object_list


def get_properties_of_managed_object(mo_ref, properties):
    '''
    Returns specific properties of a managed object, retrieved in an
    optimally.

    mo_ref
        The managed object reference.

    properties
        List of properties of the managed object to retrieve.
    '''
    service_instance = get_service_instance_from_managed_object(mo_ref)
    log.trace('Retrieving name of {0}'''.format(type(mo_ref).__name__))
    try:
        items = get_mors_with_properties(service_instance,
                                         type(mo_ref),
                                         container_ref=mo_ref,
                                         property_list=['name'],
                                         local_properties=True)
        mo_name = items[0]['name']
    except vmodl.query.InvalidProperty:
        mo_name = '<unnamed>'
    log.trace('Retrieving properties \'{0}\' of {1} \'{2}\''
              ''.format(properties, type(mo_ref).__name__, mo_name))
    items = get_mors_with_properties(service_instance,
                                     type(mo_ref),
                                     container_ref=mo_ref,
                                     property_list=properties,
                                     local_properties=True)
    if not items:
        raise salt.exceptions.VMwareApiError(
            'Properties of managed object \'{0}\' weren\'t '
            'retrieved'.format(mo_name))
    return items[0]


def get_managed_object_name(mo_ref):
    '''
    Returns the name of a managed object.
    If the name wasn't found, it returns None.

    mo_ref
        The managed object reference.
    '''
    props = get_properties_of_managed_object(mo_ref, ['name'])
    return props.get('name')


def get_network_adapter_type(adapter_type):
    '''
    Return the network adapter type.

    adpater_type
        The adapter type from which to obtain the network adapter type.
    '''
    if adapter_type == "vmxnet":
        return vim.vm.device.VirtualVmxnet()
    elif adapter_type == "vmxnet2":
        return vim.vm.device.VirtualVmxnet2()
    elif adapter_type == "vmxnet3":
        return vim.vm.device.VirtualVmxnet3()
    elif adapter_type == "e1000":
        return vim.vm.device.VirtualE1000()
    elif adapter_type == "e1000e":
        return vim.vm.device.VirtualE1000e()


def list_objects(service_instance, vim_object, properties=None):
    '''
    Returns a simple list of objects from a given service instance.

    service_instance
        The Service Instance for which to obtain a list of objects.

    object_type
        The type of content for which to obtain information.

    properties
        An optional list of object properties used to return reference results.
        If not provided, defaults to ``name``.
    '''
    if properties is None:
        properties = ['name']

    items = []
    item_list = get_mors_with_properties(service_instance, vim_object, properties)
    for item in item_list:
        items.append(item['name'])
    return items


def list_datacenters(service_instance):
    '''
    Returns a list of datacenters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datacenters.
    '''
    return list_objects(service_instance, vim.Datacenter)


def get_datacenters(service_instance, datacenter_names=None,
                    get_all_datacenters=False):
    '''
    Returns all datacenters in a vCenter.

    service_instance
        The Service Instance Object from which to obtain cluster.

    datacenter_names
        List of datacenter names to filter by. Default value is None.

    get_all_datacenters
        Flag specifying whether to retrieve all datacenters.
        Default value is None.
    '''
    items = [i['object'] for i in
             get_mors_with_properties(service_instance,
                                      vim.Datacenter,
                                      property_list=['name'])
             if get_all_datacenters or
             (datacenter_names and i['name'] in datacenter_names)]
    return items


def get_datacenter(service_instance, datacenter_name):
    '''
    Returns a vim.Datacenter managed object.

    service_instance
        The Service Instance Object from which to obtain datacenter.

    datacenter_name
        The datacenter name
    '''
    items = get_datacenters(service_instance,
                            datacenter_names=[datacenter_name])
    if not items:
        raise salt.exceptions.VMwareObjectRetrievalError(
            'Datacenter \'{0}\' was not found'.format(datacenter_name))
    return items[0]


def create_datacenter(service_instance, datacenter_name):
    '''
    Creates a datacenter.

    .. versionadded:: Nitrogen

    service_instance
        The Service Instance Object

    datacenter_name
        The datacenter name
    '''
    root_folder = get_root_folder(service_instance)
    log.trace('Creating datacenter \'{0}\''.format(datacenter_name))
    try:
        dc_obj = root_folder.CreateDatacenter(datacenter_name)
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    return dc_obj


def get_cluster(dc_ref, cluster):
    '''
    Returns a cluster in a datacenter.

    dc_ref
        The datacenter reference

    cluster
        The cluster to be retrieved
    '''
    dc_name = get_managed_object_name(dc_ref)
    log.trace('Retrieving cluster \'{0}\' from datacenter \'{1}\''
              ''.format(cluster, dc_name))
    si = get_service_instance_from_managed_object(dc_ref, name=dc_name)
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path='hostFolder',
        skip=True,
        type=vim.Datacenter,
        selectSet=[vmodl.query.PropertyCollector.TraversalSpec(
            path='childEntity',
            skip=False,
            type=vim.Folder)])
    items = [i['object'] for i in
             get_mors_with_properties(si,
                                      vim.ClusterComputeResource,
                                      container_ref=dc_ref,
                                      property_list=['name'],
                                      traversal_spec=traversal_spec)
            if i['name'] == cluster]
    if not items:
        raise salt.exceptions.VMwareObjectRetrievalError(
            'Cluster \'{0}\' was not found in datacenter '
            '\'{1}\''. format(cluster, dc_name))
    return items[0]


def create_cluster(dc_ref, cluster_name, cluster_spec):
    '''
    Creates a cluster in a datacenter.

    dc_ref
        The parent datacenter reference.

    cluster_name
        The cluster name.

    cluster_spec
        The cluster spec (vim.ClusterConfigSpecEx).
        Defaults to None.
    '''
    dc_name = get_managed_object_name(dc_ref)
    log.trace('Creating cluster \'{0}\' in datacenter \'{1}\''
              ''.format(cluster_name, dc_name))
    try:
        dc_ref.hostFolder.CreateClusterEx(cluster_name, cluster_spec)
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def update_cluster(cluster_ref, cluster_spec):
    '''
    Updates a cluster in a datacenter.

    cluster_ref
        The cluster reference.

    cluster_spec
        The cluster spec (vim.ClusterConfigSpecEx).
        Defaults to None.
    '''
    cluster_name = get_managed_object_name(cluster_ref)
    log.trace('Updating cluster \'{0}\''.format(cluster_name))
    try:
        task = cluster_ref.ReconfigureComputeResource_Task(cluster_spec,
                                                           modify=True)
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, cluster_name, 'ClusterUpdateTask')


def list_clusters(service_instance):
    '''
    Returns a list of clusters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain clusters.
    '''
    return list_objects(service_instance, vim.ClusterComputeResource)


def list_datastore_clusters(service_instance):
    '''
    Returns a list of datastore clusters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datastore clusters.
    '''
    return list_objects(service_instance, vim.StoragePod)


def list_datastores(service_instance):
    '''
    Returns a list of datastores associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datastores.
    '''
    return list_objects(service_instance, vim.Datastore)


def get_hosts(service_instance, datacenter_name=None, host_names=None,
              cluster_name=None, get_all_hosts=False):
    '''
    Returns a list of vim.HostSystem objects representing ESXi hosts
    in a vcenter filtered by their names and/or datacenter, cluster membership.

    service_instance
        The Service Instance Object from which to obtain the hosts.

    datacenter_name
        The datacenter name. Default is None.

    host_names
        The host_names to be retrieved. Default is None.

    cluster_name
        The cluster name - used to restrict the hosts retrieved. Only used if
        the datacenter is set.  This argument is optional.

    get_all_hosts
        Specifies whether to retrieve all hosts in the container.
        Default value is False.
    '''
    properties = ['name']
    if not host_names:
        host_names = []
    if cluster_name:
        properties.append('parent')
    if datacenter_name:
        start_point = get_datacenter(service_instance, datacenter_name)
        if cluster_name:
            # Retrieval to test if cluster exists. Cluster existence only makes
            # sense if the cluster has been specified
            cluster = get_cluster(start_point, cluster_name)
    else:
        # Assume the root folder is the starting point
        start_point = get_root_folder(service_instance)

    # Search for the objects
    hosts = get_mors_with_properties(service_instance,
                                     vim.HostSystem,
                                     container_ref=start_point,
                                     property_list=properties)
    filtered_hosts = []
    for h in hosts:
        # Complex conditions checking if a host should be added to the
        # filtered list (either due to its name and/or cluster membership)
        name_condition = get_all_hosts or (h['name'] in host_names)
        # the datacenter_name needs to be set in order for the cluster
        # condition membership to be checked, otherwise the condition is
        # ignored
        cluster_condition = \
                (not datacenter_name or not cluster_name or
                 (isinstance(h['parent'], vim.ClusterComputeResource) and
                  h['parent'].name == cluster_name))

        if name_condition and cluster_condition:
            filtered_hosts.append(h['object'])

    return filtered_hosts


def list_hosts(service_instance):
    '''
    Returns a list of hosts associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain hosts.
    '''
    return list_objects(service_instance, vim.HostSystem)


def list_resourcepools(service_instance):
    '''
    Returns a list of resource pools associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain resource pools.
    '''
    return list_objects(service_instance, vim.ResourcePool)


def list_networks(service_instance):
    '''
    Returns a list of networks associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain networks.
    '''
    return list_objects(service_instance, vim.Network)


def list_vms(service_instance):
    '''
    Returns a list of VMs associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain VMs.
    '''
    return list_objects(service_instance, vim.VirtualMachine)


def list_folders(service_instance):
    '''
    Returns a list of folders associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain folders.
    '''
    return list_objects(service_instance, vim.Folder)


def list_dvs(service_instance):
    '''
    Returns a list of distributed virtual switches associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain distributed virtual switches.
    '''
    return list_objects(service_instance, vim.DistributedVirtualSwitch)


def list_vapps(service_instance):
    '''
    Returns a list of vApps associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain vApps.
    '''
    return list_objects(service_instance, vim.VirtualApp)


def list_portgroups(service_instance):
    '''
    Returns a list of distributed virtual portgroups associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain distributed virtual switches.
    '''
    return list_objects(service_instance, vim.dvs.DistributedVirtualPortgroup)


def wait_for_task(task, instance_name, task_type, sleep_seconds=1, log_level='debug'):
    '''
    Waits for a task to be completed.

    task
        The task to wait for.

    instance_name
        The name of the ESXi host, vCenter Server, or Virtual Machine that
        the task is being run on.

    task_type
        The type of task being performed. Useful information for debugging purposes.

    sleep_seconds
        The number of seconds to wait before querying the task again.
        Defaults to ``1`` second.

    log_level
        The level at which to log task information. Default is ``debug``,
        but ``info`` is also supported.
    '''
    time_counter = 0
    start_time = time.time()
    log.trace('task = {0}, task_type = {1}'.format(task,
                                                   task.__class__.__name__))
    try:
        task_info = task.info
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    while task_info.state == 'running' or task_info.state == 'queued':
        if time_counter % sleep_seconds == 0:
            msg = '[ {0} ] Waiting for {1} task to finish [{2} s]'.format(
                instance_name, task_type, time_counter)
            if log_level == 'info':
                log.info(msg)
            else:
                log.debug(msg)
        time.sleep(1.0 - ((time.time() - start_time) % 1.0))
        time_counter += 1
        try:
            task_info = task.info
        except vim.fault.VimFault as exc:
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            raise salt.exceptions.VMwareRuntimeError(exc.msg)
    if task_info.state == 'success':
        msg = '[ {0} ] Successfully completed {1} task in {2} seconds'.format(
            instance_name, task_type, time_counter)
        if log_level == 'info':
            log.info(msg)
        else:
            log.debug(msg)
        # task is in a successful state
        return task_info.result
    else:
        # task is in an error state
        try:
            raise task_info.error
        except vim.fault.VimFault as exc:
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.fault.SystemError as exc:
            raise salt.exceptions.VMwareSystemError(exc.msg)
        except vmodl.fault.InvalidArgument as exc:
            exc_message = exc.msg
            if exc.faultMessage:
                exc_message = '{0} ({1})'.format(exc_message,
                                                 exc.faultMessage[0].message)
            raise salt.exceptions.VMwareApiError(exc_message)
