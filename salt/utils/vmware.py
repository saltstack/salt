"""
Connection library for VMware

.. versionadded:: 2015.8.2

This is a base library used by a number of VMware services such as VMware
ESX, ESXi, and vCenter servers.

:codeauthor: Nitin Madhok <nmadhok@g.clemson.edu>
:codeauthor: Alexandru Bleotu <alexandru.bleotu@morganstanley.com>

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

"""

import atexit
import errno
import logging
import ssl
import time
from http.client import BadStatusLine

import salt.exceptions
import salt.modules.cmdmod
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

# pylint: disable=no-name-in-module
try:
    from pyVim.connect import Disconnect, GetSi, GetStub, SmartConnect, SoapStubAdapter
    from pyVmomi import VmomiSupport, vim, vmodl

    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

try:
    from com.vmware.vapi.std.errors_client import Unauthenticated
    from vmware.vapi.vsphere.client import create_vsphere_client

    HAS_VSPHERE_SDK = True

except ImportError:
    HAS_VSPHERE_SDK = False
# pylint: enable=no-name-in-module
try:
    import base64

    import gssapi

    HAS_GSSAPI = True
except ImportError:
    HAS_GSSAPI = False


log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if PyVmomi is installed.
    """
    if HAS_PYVMOMI:
        return True

    return False, "Missing dependency: The salt.utils.vmware module requires pyVmomi."


def esxcli(
    host, user, pwd, cmd, protocol=None, port=None, esxi_host=None, credstore=None
):
    """
    Shell out and call the specified esxcli command, parse the result
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
    """

    esx_cmd = salt.utils.path.which("esxcli")
    if not esx_cmd:
        log.error(
            "Missing dependency: The salt.utils.vmware.esxcli function requires ESXCLI."
        )
        return False

    # Set default port and protocol if none are provided.
    if port is None:
        port = 443
    if protocol is None:
        protocol = "https"

    if credstore:
        esx_cmd += " --credstore '{}'".format(credstore)

    if not esxi_host:
        # Then we are connecting directly to an ESXi server,
        # 'host' points at that server, and esxi_host is a reference to the
        # ESXi instance we are manipulating
        esx_cmd += " -s {} -u {} -p '{}' --protocol={} --portnumber={} {}".format(
            host, user, pwd, protocol, port, cmd
        )
    else:
        esx_cmd += " -s {} -h {} -u {} -p '{}' --protocol={} --portnumber={} {}".format(
            host, esxi_host, user, pwd, protocol, port, cmd
        )

    ret = salt.modules.cmdmod.run_all(esx_cmd, output_loglevel="quiet")

    return ret


def get_vsphere_client(
    server, username, password, session=None, verify_ssl=True, ca_bundle=None
):
    """
    Internal helper method to create an instance of the vSphere API client.
    Please provide username and password to authenticate.

    :param basestring server:
        vCenter host name or IP address
    :param basestring username:
        Name of the user
    :param basestring password:
        Password of the user
    :param Session session:
        Request HTTP session instance. If not specified, one
        is automatically created and used
    :param boolean verify_ssl:
        Verify the SSL certificate. Default: True
    :param basestring ca_bundle:
        Path to the ca bundle to use when verifying SSL certificates.

    :returns:
        Vsphere Client instance
    :rtype:
        :class:`vmware.vapi.vmc.client.VsphereClient`
    """
    if not session:
        # Create an https session to be used for a vSphere client
        session = salt.utils.http.session(verify_ssl=verify_ssl, ca_bundle=ca_bundle)
    client = None
    try:
        client = create_vsphere_client(
            server=server, username=username, password=password, session=session
        )
    except Unauthenticated as err:
        log.trace(err)
    return client


def _get_service_instance(
    host,
    username,
    password,
    protocol,
    port,
    mechanism,
    principal,
    domain,
    verify_ssl=True,
):
    """
    Internal method to authenticate with a vCenter server or ESX/ESXi host
    and return the service instance object.
    """
    log.trace("Retrieving new service instance")
    token = None
    if mechanism == "userpass":
        if username is None:
            raise salt.exceptions.CommandExecutionError(
                "Login mechanism userpass was specified but the mandatory "
                "parameter 'username' is missing"
            )
        if password is None:
            raise salt.exceptions.CommandExecutionError(
                "Login mechanism userpass was specified but the mandatory "
                "parameter 'password' is missing"
            )
    elif mechanism == "sspi":
        if principal is not None and domain is not None:
            try:
                token = get_gssapi_token(principal, host, domain)
            except Exception as exc:  # pylint: disable=broad-except
                raise salt.exceptions.VMwareConnectionError(str(exc))
        else:
            err_msg = (
                "Login mechanism '{}' was specified but the"
                " mandatory parameters are missing".format(mechanism)
            )
            raise salt.exceptions.CommandExecutionError(err_msg)
    else:
        raise salt.exceptions.CommandExecutionError(
            "Unsupported mechanism: '{}'".format(mechanism)
        )

    log.trace(
        "Connecting using the '%s' mechanism, with username '%s'",
        mechanism,
        username,
    )
    default_msg = (
        "Could not connect to host '{}'. "
        "Please check the debug log for more information.".format(host)
    )

    try:
        if verify_ssl:
            service_instance = SmartConnect(
                host=host,
                user=username,
                pwd=password,
                protocol=protocol,
                port=port,
                b64token=token,
                mechanism=mechanism,
            )
    except TypeError as exc:
        if "unexpected keyword argument" in exc.message:
            log.error(
                "Initial connect to the VMware endpoint failed with %s", exc.message
            )
            log.error(
                "This may mean that a version of PyVmomi EARLIER than 6.0.0.2016.6 is"
                " installed."
            )
            log.error("We recommend updating to that version or later.")
            raise
    except Exception as exc:  # pylint: disable=broad-except
        # pyVmomi's SmartConnect() actually raises Exception in some cases.
        if (
            isinstance(exc, vim.fault.HostConnectFault)
            and "[SSL: CERTIFICATE_VERIFY_FAILED]" in exc.msg
        ) or "[SSL: CERTIFICATE_VERIFY_FAILED]" in str(exc):
            err_msg = (
                "Could not verify the SSL certificate. You can use "
                "verify_ssl: False if you do not want to verify the "
                "SSL certificate. This is not recommended as it is "
                "considered insecure."
            )
        else:
            log.exception(exc)
            err_msg = exc.msg if hasattr(exc, "msg") else default_msg
        raise salt.exceptions.VMwareConnectionError(err_msg)

    if not verify_ssl:
        try:
            service_instance = SmartConnect(
                host=host,
                user=username,
                pwd=password,
                protocol=protocol,
                port=port,
                sslContext=ssl._create_unverified_context(),
                b64token=token,
                mechanism=mechanism,
            )
        except Exception as exc:  # pylint: disable=broad-except
            # pyVmomi's SmartConnect() actually raises Exception in some cases.
            if "certificate verify failed" in str(exc):
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
                        mechanism=mechanism,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    log.exception(exc)
                    err_msg = exc.msg if hasattr(exc, "msg") else str(exc)
                    raise salt.exceptions.VMwareConnectionError(
                        "Could not connect to host '{}': {}".format(host, err_msg)
                    )
            else:
                err_msg = exc.msg if hasattr(exc, "msg") else default_msg
                log.trace(exc)
                raise salt.exceptions.VMwareConnectionError(err_msg)

    atexit.register(Disconnect, service_instance)
    return service_instance


def get_customizationspec_ref(si, customization_spec_name):
    """
    Get a reference to a VMware customization spec for the purposes of customizing a clone

    si
        ServiceInstance for the vSphere or ESXi server (see get_service_instance)

    customization_spec_name
        Name of the customization spec

    """
    customization_spec_name = si.content.customizationSpecManager.GetCustomizationSpec(
        name=customization_spec_name
    )
    return customization_spec_name


def get_mor_using_container_view(si, obj_type, obj_name):
    """
    Get reference to an object of specified object type and name

    si
        ServiceInstance for the vSphere or ESXi server (see get_service_instance)

    obj_type
        Type of the object (vim.StoragePod, vim.Datastore, etc)

    obj_name
        Name of the object

    """
    inventory = get_inventory(si)
    container = inventory.viewManager.CreateContainerView(
        inventory.rootFolder, [obj_type], True
    )
    for item in container.view:
        if item.name == obj_name:
            return item
    return None


def get_service_instance(
    host,
    username=None,
    password=None,
    protocol=None,
    port=None,
    mechanism="userpass",
    principal=None,
    domain=None,
    verify_ssl=True,
):
    """
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

    verify_ssl
        Verify the SSL certificate. Default: True
    """

    if protocol is None:
        protocol = "https"
    if port is None:
        port = 443

    service_instance = GetSi()
    if service_instance:
        stub = GetStub()
        if salt.utils.platform.is_proxy() or (
            hasattr(stub, "host") and stub.host != ":".join([host, str(port)])
        ):
            # Proxies will fork and mess up the cached service instance.
            # If this is a proxy or we are connecting to a different host
            # invalidate the service instance to avoid a potential memory leak
            # and reconnect
            Disconnect(service_instance)
            service_instance = None

    if not service_instance:
        service_instance = _get_service_instance(
            host,
            username,
            password,
            protocol,
            port,
            mechanism,
            principal,
            domain,
            verify_ssl=verify_ssl,
        )

    # Test if data can actually be retrieved or connection has gone stale
    log.trace("Checking connection is still authenticated")
    try:
        service_instance.CurrentTime()
    except vim.fault.NotAuthenticated:
        log.trace("Session no longer authenticating. Reconnecting")
        Disconnect(service_instance)
        service_instance = _get_service_instance(
            host,
            username,
            password,
            protocol,
            port,
            mechanism,
            principal,
            domain,
            verify_ssl=verify_ssl,
        )
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)

    return service_instance


def get_new_service_instance_stub(service_instance, path, ns=None, version=None):
    """
    Returns a stub that points to a different path,
    created from an existing connection.

    service_instance
        The Service Instance.

    path
        Path of the new stub.

    ns
        Namespace of the new stub.
        Default value is None

    version
        Version of the new stub.
        Default value is None.
    """
    # For python 2.7.9 and later, the default SSL context has more strict
    # connection handshaking rule. We may need turn off the hostname checking
    # and the client side cert verification.
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    stub = service_instance._stub
    hostname = stub.host.split(":")[0]
    session_cookie = stub.cookie.split('"')[1]
    VmomiSupport.GetRequestContext()["vcSessionCookie"] = session_cookie
    new_stub = SoapStubAdapter(
        host=hostname, ns=ns, path=path, version=version, poolSize=0, sslContext=context
    )
    new_stub.cookie = stub.cookie
    return new_stub


def get_service_instance_from_managed_object(mo_ref, name="<unnamed>"):
    """
    Retrieves the service instance from a managed object.

    me_ref
        Reference to a managed object (of type vim.ManagedEntity).

    name
        Name of managed object. This field is optional.
    """
    if not name:
        name = mo_ref.name
    log.trace("[%s] Retrieving service instance from managed object", name)
    si = vim.ServiceInstance("ServiceInstance")
    si._stub = mo_ref._stub
    return si


def disconnect(service_instance):
    """
    Function that disconnects from the vCenter server or ESXi host

    service_instance
        The Service Instance from which to obtain managed object references.
    """
    log.trace("Disconnecting")
    try:
        Disconnect(service_instance)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def is_connection_to_a_vcenter(service_instance):
    """
    Function that returns True if the connection is made to a vCenter Server and
    False if the connection is made to an ESXi host

    service_instance
        The Service Instance from which to obtain managed object references.
    """
    try:
        api_type = service_instance.content.about.apiType
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    log.trace("api_type = %s", api_type)
    if api_type == "VirtualCenter":
        return True
    elif api_type == "HostAgent":
        return False
    else:
        raise salt.exceptions.VMwareApiError(
            "Unexpected api type '{}' . Supported types: "
            "'VirtualCenter/HostAgent'".format(api_type)
        )


def get_service_info(service_instance):
    """
    Returns information of the vCenter or ESXi host

    service_instance
        The Service Instance from which to obtain managed object references.
    """
    try:
        return service_instance.content.about
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def _get_dvs(service_instance, dvs_name):
    """
    Return a reference to a Distributed Virtual Switch object.

    :param service_instance: PyVmomi service instance
    :param dvs_name: Name of DVS to return
    :return: A PyVmomi DVS object
    """
    switches = list_dvs(service_instance)
    if dvs_name in switches:
        inventory = get_inventory(service_instance)
        container = inventory.viewManager.CreateContainerView(
            inventory.rootFolder, [vim.DistributedVirtualSwitch], True
        )
        for item in container.view:
            if item.name == dvs_name:
                return item

    return None


def _get_pnics(host_reference):
    """
    Helper function that returns a list of PhysicalNics and their information.
    """
    return host_reference.config.network.pnic


def _get_vnics(host_reference):
    """
    Helper function that returns a list of VirtualNics and their information.
    """
    return host_reference.config.network.vnic


def _get_vnic_manager(host_reference):
    """
    Helper function that returns a list of Virtual NicManagers
    and their information.
    """
    return host_reference.configManager.virtualNicManager


def _get_dvs_portgroup(dvs, portgroup_name):
    """
    Return a portgroup object corresponding to the portgroup name on the dvs

    :param dvs: DVS object
    :param portgroup_name: Name of portgroup to return
    :return: Portgroup object
    """
    for portgroup in dvs.portgroup:
        if portgroup.name == portgroup_name:
            return portgroup

    return None


def _get_dvs_uplink_portgroup(dvs, portgroup_name):
    """
    Return a portgroup object corresponding to the portgroup name on the dvs

    :param dvs: DVS object
    :param portgroup_name: Name of portgroup to return
    :return: Portgroup object
    """
    for portgroup in dvs.portgroup:
        if portgroup.name == portgroup_name:
            return portgroup

    return None


def get_gssapi_token(principal, host, domain):
    """
    Get the gssapi token for Kerberos connection

    principal
       The service principal
    host
       Host url where we would like to authenticate
    domain
       Kerberos user domain
    """

    if not HAS_GSSAPI:
        raise ImportError("The gssapi library is not imported.")

    service = "{}/{}@{}".format(principal, host, domain)
    log.debug("Retrieving gsspi token for service %s", service)
    service_name = gssapi.Name(service, gssapi.C_NT_USER_NAME)
    ctx = gssapi.InitContext(service_name)
    in_token = None
    while not ctx.established:
        out_token = ctx.step(in_token)
        if out_token:
            return base64.b64encode(salt.utils.stringutils.to_bytes(out_token))
        if ctx.established:
            break
        if not in_token:
            raise salt.exceptions.CommandExecutionError(
                "Can't receive token, no response from server"
            )
    raise salt.exceptions.CommandExecutionError(
        "Context established, but didn't receive token"
    )


def get_hardware_grains(service_instance):
    """
    Return hardware info for standard minion grains if the service_instance is a HostAgent type

    service_instance
        The service instance object to get hardware info for

    .. versionadded:: 2016.11.0
    """
    hw_grain_data = {}
    if get_inventory(service_instance).about.apiType == "HostAgent":
        view = service_instance.content.viewManager.CreateContainerView(
            service_instance.RetrieveContent().rootFolder, [vim.HostSystem], True
        )
        if view and view.view:
            hw_grain_data["manufacturer"] = view.view[0].hardware.systemInfo.vendor
            hw_grain_data["productname"] = view.view[0].hardware.systemInfo.model

            for _data in view.view[0].hardware.systemInfo.otherIdentifyingInfo:
                if _data.identifierType.key == "ServiceTag":
                    hw_grain_data["serialnumber"] = _data.identifierValue

            hw_grain_data["osfullname"] = view.view[0].summary.config.product.fullName
            hw_grain_data["osmanufacturer"] = view.view[0].summary.config.product.vendor
            hw_grain_data["osrelease"] = view.view[0].summary.config.product.version
            hw_grain_data["osbuild"] = view.view[0].summary.config.product.build
            hw_grain_data["os_family"] = view.view[0].summary.config.product.name
            hw_grain_data["os"] = view.view[0].summary.config.product.name
            hw_grain_data["mem_total"] = view.view[0].hardware.memorySize / 1024 / 1024
            hw_grain_data["biosversion"] = view.view[0].hardware.biosInfo.biosVersion
            hw_grain_data["biosreleasedate"] = (
                view.view[0].hardware.biosInfo.releaseDate.date().strftime("%m/%d/%Y")
            )
            hw_grain_data["cpu_model"] = view.view[0].hardware.cpuPkg[0].description
            hw_grain_data["kernel"] = view.view[0].summary.config.product.productLineId
            hw_grain_data["num_cpu_sockets"] = view.view[
                0
            ].hardware.cpuInfo.numCpuPackages
            hw_grain_data["num_cpu_cores"] = view.view[0].hardware.cpuInfo.numCpuCores
            hw_grain_data["num_cpus"] = (
                hw_grain_data["num_cpu_sockets"] * hw_grain_data["num_cpu_cores"]
            )
            hw_grain_data["ip_interfaces"] = {}
            hw_grain_data["ip4_interfaces"] = {}
            hw_grain_data["ip6_interfaces"] = {}
            hw_grain_data["hwaddr_interfaces"] = {}
            for _vnic in view.view[0].configManager.networkSystem.networkConfig.vnic:
                hw_grain_data["ip_interfaces"][_vnic.device] = []
                hw_grain_data["ip4_interfaces"][_vnic.device] = []
                hw_grain_data["ip6_interfaces"][_vnic.device] = []

                hw_grain_data["ip_interfaces"][_vnic.device].append(
                    _vnic.spec.ip.ipAddress
                )
                hw_grain_data["ip4_interfaces"][_vnic.device].append(
                    _vnic.spec.ip.ipAddress
                )
                if _vnic.spec.ip.ipV6Config:
                    hw_grain_data["ip6_interfaces"][_vnic.device].append(
                        _vnic.spec.ip.ipV6Config.ipV6Address
                    )
                hw_grain_data["hwaddr_interfaces"][_vnic.device] = _vnic.spec.mac
            hw_grain_data["host"] = view.view[
                0
            ].configManager.networkSystem.dnsConfig.hostName
            hw_grain_data["domain"] = view.view[
                0
            ].configManager.networkSystem.dnsConfig.domainName
            hw_grain_data["fqdn"] = "{}{}{}".format(
                view.view[0].configManager.networkSystem.dnsConfig.hostName,
                (
                    "."
                    if view.view[0].configManager.networkSystem.dnsConfig.domainName
                    else ""
                ),
                view.view[0].configManager.networkSystem.dnsConfig.domainName,
            )

            for _pnic in view.view[0].configManager.networkSystem.networkInfo.pnic:
                hw_grain_data["hwaddr_interfaces"][_pnic.device] = _pnic.mac

            hw_grain_data["timezone"] = view.view[
                0
            ].configManager.dateTimeSystem.dateTimeInfo.timeZone.name
        view = None
    return hw_grain_data


def get_inventory(service_instance):
    """
    Return the inventory of a Service Instance Object.

    service_instance
        The Service Instance Object for which to obtain inventory.
    """
    return service_instance.RetrieveContent()


def get_root_folder(service_instance):
    """
    Returns the root folder of a vCenter.

    service_instance
        The Service Instance Object for which to obtain the root folder.
    """
    try:
        log.trace("Retrieving root folder")
        return service_instance.RetrieveContent().rootFolder
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def get_content(
    service_instance,
    obj_type,
    property_list=None,
    container_ref=None,
    traversal_spec=None,
    local_properties=False,
):
    """
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
    """
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
                container_ref, [obj_type], True
            )
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.VimFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareRuntimeError(exc.msg)

        # Create 'Traverse All' traversal spec to determine the path for
        # collection
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name="traverseEntities",
            path="view",
            skip=False,
            type=vim.view.ContainerView,
        )

    # Create property spec to determine properties to be retrieved
    property_spec = vmodl.query.PropertyCollector.PropertySpec(
        type=obj_type, all=True if not property_list else False, pathSet=property_list
    )

    # Create object spec to navigate content
    obj_spec = vmodl.query.PropertyCollector.ObjectSpec(
        obj=obj_ref,
        skip=True if not local_properties else False,
        selectSet=[traversal_spec] if not local_properties else None,
    )

    # Create a filter spec and specify object, property spec in it
    filter_spec = vmodl.query.PropertyCollector.FilterSpec(
        objectSet=[obj_spec],
        propSet=[property_spec],
        reportMissingObjectsInResults=False,
    )

    # Retrieve the contents
    try:
        content = service_instance.content.propertyCollector.RetrieveContents(
            [filter_spec]
        )
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)

    # Destroy the object view
    if local_traversal_spec:
        try:
            obj_ref.Destroy()
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.VimFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareRuntimeError(exc.msg)

    return content


def get_mor_by_property(
    service_instance,
    object_type,
    property_value,
    property_name="name",
    container_ref=None,
):
    """
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
    """
    # Get list of all managed object references with specified property
    object_list = get_mors_with_properties(
        service_instance,
        object_type,
        property_list=[property_name],
        container_ref=container_ref,
    )

    for obj in object_list:
        obj_id = str(obj.get("object", "")).strip("'\"")
        if obj[property_name] == property_value or property_value == obj_id:
            return obj["object"]

    return None


def get_mors_with_properties(
    service_instance,
    object_type,
    property_list=None,
    container_ref=None,
    traversal_spec=None,
    local_properties=False,
):
    """
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
    """
    # Get all the content
    content_args = [service_instance, object_type]
    content_kwargs = {
        "property_list": property_list,
        "container_ref": container_ref,
        "traversal_spec": traversal_spec,
        "local_properties": local_properties,
    }
    try:
        content = get_content(*content_args, **content_kwargs)
    except BadStatusLine:
        content = get_content(*content_args, **content_kwargs)
    except OSError as exc:
        if exc.errno != errno.EPIPE:
            raise
        content = get_content(*content_args, **content_kwargs)

    object_list = []
    for obj in content:
        properties = {}
        for prop in obj.propSet:
            properties[prop.name] = prop.val
        properties["object"] = obj.obj
        object_list.append(properties)
    log.trace("Retrieved %s objects", len(object_list))
    return object_list


def get_properties_of_managed_object(mo_ref, properties):
    """
    Returns specific properties of a managed object, retrieved in an
    optimally.

    mo_ref
        The managed object reference.

    properties
        List of properties of the managed object to retrieve.
    """
    service_instance = get_service_instance_from_managed_object(mo_ref)
    log.trace("Retrieving name of %s", type(mo_ref).__name__)
    try:
        items = get_mors_with_properties(
            service_instance,
            type(mo_ref),
            container_ref=mo_ref,
            property_list=["name"],
            local_properties=True,
        )
        mo_name = items[0]["name"]
    except vmodl.query.InvalidProperty:
        mo_name = "<unnamed>"
    log.trace(
        "Retrieving properties '%s' of %s '%s'",
        properties,
        type(mo_ref).__name__,
        mo_name,
    )
    items = get_mors_with_properties(
        service_instance,
        type(mo_ref),
        container_ref=mo_ref,
        property_list=properties,
        local_properties=True,
    )
    if not items:
        raise salt.exceptions.VMwareApiError(
            "Properties of managed object '{}' weren't retrieved".format(mo_name)
        )
    return items[0]


def get_managed_object_name(mo_ref):
    """
    Returns the name of a managed object.
    If the name wasn't found, it returns None.

    mo_ref
        The managed object reference.
    """
    props = get_properties_of_managed_object(mo_ref, ["name"])
    return props.get("name")


def get_network_adapter_type(adapter_type):
    """
    Return the network adapter type.

    adpater_type
        The adapter type from which to obtain the network adapter type.
    """
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

    raise ValueError("An unknown network adapter object type name.")


def get_network_adapter_object_type(adapter_object):
    """
    Returns the network adapter type.

    adapter_object
        The adapter object from which to obtain the network adapter type.
    """
    if isinstance(adapter_object, vim.vm.device.VirtualVmxnet2):
        return "vmxnet2"
    if isinstance(adapter_object, vim.vm.device.VirtualVmxnet3):
        return "vmxnet3"
    if isinstance(adapter_object, vim.vm.device.VirtualVmxnet):
        return "vmxnet"
    if isinstance(adapter_object, vim.vm.device.VirtualE1000e):
        return "e1000e"
    if isinstance(adapter_object, vim.vm.device.VirtualE1000):
        return "e1000"

    raise ValueError("An unknown network adapter object type.")


def get_dvss(dc_ref, dvs_names=None, get_all_dvss=False):
    """
    Returns distributed virtual switches (DVSs) in a datacenter.

    dc_ref
        The parent datacenter reference.

    dvs_names
        The names of the DVSs to return. Default is None.

    get_all_dvss
        Return all DVSs in the datacenter. Default is False.
    """
    dc_name = get_managed_object_name(dc_ref)
    log.trace(
        "Retrieving DVSs in datacenter '%s', dvs_names='%s', get_all_dvss=%s",
        dc_name,
        ",".join(dvs_names) if dvs_names else None,
        get_all_dvss,
    )
    properties = ["name"]
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path="networkFolder",
        skip=True,
        type=vim.Datacenter,
        selectSet=[
            vmodl.query.PropertyCollector.TraversalSpec(
                path="childEntity", skip=False, type=vim.Folder
            )
        ],
    )
    service_instance = get_service_instance_from_managed_object(dc_ref)
    items = [
        i["object"]
        for i in get_mors_with_properties(
            service_instance,
            vim.DistributedVirtualSwitch,
            container_ref=dc_ref,
            property_list=properties,
            traversal_spec=traversal_spec,
        )
        if get_all_dvss or (dvs_names and i["name"] in dvs_names)
    ]
    return items


def get_network_folder(dc_ref):
    """
    Retrieves the network folder of a datacenter
    """
    dc_name = get_managed_object_name(dc_ref)
    log.trace("Retrieving network folder in datacenter '%s'", dc_name)
    service_instance = get_service_instance_from_managed_object(dc_ref)
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path="networkFolder", skip=False, type=vim.Datacenter
    )
    entries = get_mors_with_properties(
        service_instance,
        vim.Folder,
        container_ref=dc_ref,
        property_list=["name"],
        traversal_spec=traversal_spec,
    )
    if not entries:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Network folder in datacenter '{}' wasn't retrieved".format(dc_name)
        )
    return entries[0]["object"]


def create_dvs(dc_ref, dvs_name, dvs_create_spec=None):
    """
    Creates a distributed virtual switches (DVS) in a datacenter.
    Returns the reference to the newly created distributed virtual switch.

    dc_ref
        The parent datacenter reference.

    dvs_name
        The name of the DVS to create.

    dvs_create_spec
        The DVS spec (vim.DVSCreateSpec) to use when creating the DVS.
        Default is None.
    """
    dc_name = get_managed_object_name(dc_ref)
    log.trace("Creating DVS '%s' in datacenter '%s'", dvs_name, dc_name)
    if not dvs_create_spec:
        dvs_create_spec = vim.DVSCreateSpec()
    if not dvs_create_spec.configSpec:
        dvs_create_spec.configSpec = vim.VMwareDVSConfigSpec()
        dvs_create_spec.configSpec.name = dvs_name
    netw_folder_ref = get_network_folder(dc_ref)
    try:
        task = netw_folder_ref.CreateDVS_Task(dvs_create_spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, dvs_name, str(task.__class__))


def update_dvs(dvs_ref, dvs_config_spec):
    """
    Updates a distributed virtual switch with the config_spec.

    dvs_ref
        The DVS reference.

    dvs_config_spec
        The updated config spec (vim.VMwareDVSConfigSpec) to be applied to
        the DVS.
    """
    dvs_name = get_managed_object_name(dvs_ref)
    log.trace("Updating dvs '%s'", dvs_name)
    try:
        task = dvs_ref.ReconfigureDvs_Task(dvs_config_spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, dvs_name, str(task.__class__))


def set_dvs_network_resource_management_enabled(dvs_ref, enabled):
    """
    Sets whether NIOC is enabled on a DVS.

    dvs_ref
        The DVS reference.

    enabled
        Flag specifying whether NIOC is enabled.
    """
    dvs_name = get_managed_object_name(dvs_ref)
    log.trace(
        "Setting network resource management enable to %s on dvs '%s'",
        enabled,
        dvs_name,
    )
    try:
        dvs_ref.EnableNetworkResourceManagement(enable=enabled)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def get_dvportgroups(parent_ref, portgroup_names=None, get_all_portgroups=False):
    """
    Returns distributed virtual porgroups (dvportgroups).
    The parent object can be either a datacenter or a dvs.

    parent_ref
        The parent object reference. Can be either a datacenter or a dvs.

    portgroup_names
        The names of the dvss to return. Default is None.

    get_all_portgroups
        Return all portgroups in the parent. Default is False.
    """
    if not isinstance(parent_ref, (vim.Datacenter, vim.DistributedVirtualSwitch)):
        raise salt.exceptions.ArgumentValueError(
            "Parent has to be either a datacenter, or a distributed virtual switch"
        )
    parent_name = get_managed_object_name(parent_ref)
    log.trace(
        "Retrieving portgroup in %s '%s', portgroups_names='%s', get_all_portgroups=%s",
        type(parent_ref).__name__,
        parent_name,
        ",".join(portgroup_names) if portgroup_names else None,
        get_all_portgroups,
    )
    properties = ["name"]
    if isinstance(parent_ref, vim.Datacenter):
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            path="networkFolder",
            skip=True,
            type=vim.Datacenter,
            selectSet=[
                vmodl.query.PropertyCollector.TraversalSpec(
                    path="childEntity", skip=False, type=vim.Folder
                )
            ],
        )
    else:  # parent is distributed virtual switch
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            path="portgroup", skip=False, type=vim.DistributedVirtualSwitch
        )

    service_instance = get_service_instance_from_managed_object(parent_ref)
    items = [
        i["object"]
        for i in get_mors_with_properties(
            service_instance,
            vim.DistributedVirtualPortgroup,
            container_ref=parent_ref,
            property_list=properties,
            traversal_spec=traversal_spec,
        )
        if get_all_portgroups or (portgroup_names and i["name"] in portgroup_names)
    ]
    return items


def get_uplink_dvportgroup(dvs_ref):
    """
    Returns the uplink distributed virtual portgroup of a distributed virtual
    switch (dvs)

    dvs_ref
        The dvs reference
    """
    dvs_name = get_managed_object_name(dvs_ref)
    log.trace("Retrieving uplink portgroup of dvs '%s'", dvs_name)
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path="portgroup", skip=False, type=vim.DistributedVirtualSwitch
    )
    service_instance = get_service_instance_from_managed_object(dvs_ref)
    items = [
        entry["object"]
        for entry in get_mors_with_properties(
            service_instance,
            vim.DistributedVirtualPortgroup,
            container_ref=dvs_ref,
            property_list=["tag"],
            traversal_spec=traversal_spec,
        )
        if entry["tag"] and [t for t in entry["tag"] if t.key == "SYSTEM/DVS.UPLINKPG"]
    ]
    if not items:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Uplink portgroup of DVS '{}' wasn't found".format(dvs_name)
        )
    return items[0]


def create_dvportgroup(dvs_ref, spec):
    """
    Creates a distributed virtual portgroup on a distributed virtual switch
    (dvs)

    dvs_ref
        The dvs reference

    spec
        Portgroup spec (vim.DVPortgroupConfigSpec)
    """
    dvs_name = get_managed_object_name(dvs_ref)
    log.trace("Adding portgroup %s to dvs '%s'", spec.name, dvs_name)
    log.trace("spec = %s", spec)
    try:
        task = dvs_ref.CreateDVPortgroup_Task(spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, dvs_name, str(task.__class__))


def update_dvportgroup(portgroup_ref, spec):
    """
    Updates a distributed virtual portgroup

    portgroup_ref
        The portgroup reference

    spec
        Portgroup spec (vim.DVPortgroupConfigSpec)
    """
    pg_name = get_managed_object_name(portgroup_ref)
    log.trace("Updating portgrouo %s", pg_name)
    try:
        task = portgroup_ref.ReconfigureDVPortgroup_Task(spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, pg_name, str(task.__class__))


def remove_dvportgroup(portgroup_ref):
    """
    Removes a distributed virtual portgroup

    portgroup_ref
        The portgroup reference
    """
    pg_name = get_managed_object_name(portgroup_ref)
    log.trace("Removing portgroup %s", pg_name)
    try:
        task = portgroup_ref.Destroy_Task()
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, pg_name, str(task.__class__))


def get_networks(parent_ref, network_names=None, get_all_networks=False):
    """
    Returns networks of standard switches.
    The parent object can be a datacenter.

    parent_ref
        The parent object reference. A datacenter object.

    network_names
        The name of the standard switch networks. Default is None.

    get_all_networks
        Boolean indicates whether to return all networks in the parent.
        Default is False.
    """

    if not isinstance(parent_ref, vim.Datacenter):
        raise salt.exceptions.ArgumentValueError("Parent has to be a datacenter.")
    parent_name = get_managed_object_name(parent_ref)
    log.trace(
        "Retrieving network from %s '%s', network_names='%s', get_all_networks=%s",
        type(parent_ref).__name__,
        parent_name,
        ",".join(network_names) if network_names else None,
        get_all_networks,
    )
    properties = ["name"]
    service_instance = get_service_instance_from_managed_object(parent_ref)
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path="networkFolder",
        skip=True,
        type=vim.Datacenter,
        selectSet=[
            vmodl.query.PropertyCollector.TraversalSpec(
                path="childEntity", skip=False, type=vim.Folder
            )
        ],
    )
    items = [
        i["object"]
        for i in get_mors_with_properties(
            service_instance,
            vim.Network,
            container_ref=parent_ref,
            property_list=properties,
            traversal_spec=traversal_spec,
        )
        if get_all_networks or (network_names and i["name"] in network_names)
    ]
    return items


def list_objects(service_instance, vim_object, properties=None):
    """
    Returns a simple list of objects from a given service instance.

    service_instance
        The Service Instance for which to obtain a list of objects.

    object_type
        The type of content for which to obtain information.

    properties
        An optional list of object properties used to return reference results.
        If not provided, defaults to ``name``.
    """
    if properties is None:
        properties = ["name"]

    items = []
    item_list = get_mors_with_properties(service_instance, vim_object, properties)
    for item in item_list:
        items.append(item["name"])
    return items


def get_license_manager(service_instance):
    """
    Returns the license manager.

    service_instance
        The Service Instance Object from which to obrain the license manager.
    """

    log.debug("Retrieving license manager")
    try:
        lic_manager = service_instance.content.licenseManager
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    return lic_manager


def get_license_assignment_manager(service_instance):
    """
    Returns the license assignment manager.

    service_instance
        The Service Instance Object from which to obrain the license manager.
    """

    log.debug("Retrieving license assignment manager")
    try:
        lic_assignment_manager = (
            service_instance.content.licenseManager.licenseAssignmentManager
        )
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    if not lic_assignment_manager:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "License assignment manager was not retrieved"
        )
    return lic_assignment_manager


def get_licenses(service_instance, license_manager=None):
    """
    Returns the licenses on a specific instance.

    service_instance
        The Service Instance Object from which to obrain the licenses.

    license_manager
        The License Manager object of the service instance. If not provided it
        will be retrieved.
    """

    if not license_manager:
        license_manager = get_license_manager(service_instance)
    log.debug("Retrieving licenses")
    try:
        return license_manager.licenses
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def add_license(service_instance, key, description, license_manager=None):
    """
    Adds a license.

    service_instance
        The Service Instance Object.

    key
        The key of the license to add.

    description
        The description of the license to add.

    license_manager
        The License Manager object of the service instance. If not provided it
        will be retrieved.
    """
    if not license_manager:
        license_manager = get_license_manager(service_instance)
    label = vim.KeyValue()
    label.key = "VpxClientLicenseLabel"
    label.value = description
    log.debug("Adding license '%s'", description)
    try:
        vmware_license = license_manager.AddLicense(key, [label])
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    return vmware_license


def get_assigned_licenses(
    service_instance, entity_ref=None, entity_name=None, license_assignment_manager=None
):
    """
    Returns the licenses assigned to an entity. If entity ref is not provided,
    then entity_name is assumed to be the vcenter. This is later checked if
    the entity name is provided.

    service_instance
        The Service Instance Object from which to obtain the licenses.

    entity_ref
        VMware entity to get the assigned licenses for.
        If None, the entity is the vCenter itself.
        Default is None.

    entity_name
        Entity name used in logging.
        Default is None.

    license_assignment_manager
        The LicenseAssignmentManager object of the service instance.
        If not provided it will be retrieved.
        Default is None.
    """
    if not license_assignment_manager:
        license_assignment_manager = get_license_assignment_manager(service_instance)
    if not entity_name:
        raise salt.exceptions.ArgumentValueError("No entity_name passed")
    # If entity_ref is not defined, then interested in the vcenter
    entity_id = None
    entity_type = "moid"
    check_name = False
    if not entity_ref:
        if entity_name:
            check_name = True
        entity_type = "uuid"
        try:
            entity_id = service_instance.content.about.instanceUuid
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.VimFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareRuntimeError(exc.msg)
    else:
        entity_id = entity_ref._moId

    log.trace("Retrieving licenses assigned to '%s'", entity_name)
    try:
        assignments = license_assignment_manager.QueryAssignedLicenses(entity_id)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)

    if entity_type == "uuid" and len(assignments) > 1:
        log.trace("Unexpectectedly retrieved more than one VCenter license assignment.")
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Unexpected return. Expect only a single assignment"
        )

    if check_name:
        if entity_name != assignments[0].entityDisplayName:
            log.trace(
                "Getting license info for wrong vcenter: %s != %s",
                entity_name,
                assignments[0].entityDisplayName,
            )
            raise salt.exceptions.VMwareObjectRetrievalError(
                "Got license assignment info for a different vcenter"
            )

    return [a.assignedLicense for a in assignments]


def assign_license(
    service_instance,
    license_key,
    license_name,
    entity_ref=None,
    entity_name=None,
    license_assignment_manager=None,
):
    """
    Assigns a license to an entity.

    service_instance
        The Service Instance Object from which to obrain the licenses.

    license_key
        The key of the license to add.

    license_name
        The description of the license to add.

    entity_ref
        VMware entity to assign the license to.
        If None, the entity is the vCenter itself.
        Default is None.

    entity_name
        Entity name used in logging.
        Default is None.

    license_assignment_manager
        The LicenseAssignmentManager object of the service instance.
        If not provided it will be retrieved
        Default is None.
    """
    if not license_assignment_manager:
        license_assignment_manager = get_license_assignment_manager(service_instance)
    entity_id = None

    if not entity_ref:
        # vcenter
        try:
            entity_id = service_instance.content.about.instanceUuid
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.VimFault as exc:
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            raise salt.exceptions.VMwareRuntimeError(exc.msg)
        if not entity_name:
            entity_name = "vCenter"
    else:
        # e.g. vsan cluster or host
        entity_id = entity_ref._moId

    log.trace("Assigning license to '%s'", entity_name)
    try:
        vmware_license = license_assignment_manager.UpdateAssignedLicense(
            entity_id, license_key, license_name
        )
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    return vmware_license


def list_datacenters(service_instance):
    """
    Returns a list of datacenters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datacenters.
    """
    return list_objects(service_instance, vim.Datacenter)


def get_datacenters(service_instance, datacenter_names=None, get_all_datacenters=False):
    """
    Returns all datacenters in a vCenter.

    service_instance
        The Service Instance Object from which to obtain cluster.

    datacenter_names
        List of datacenter names to filter by. Default value is None.

    get_all_datacenters
        Flag specifying whether to retrieve all datacenters.
        Default value is None.
    """
    items = [
        i["object"]
        for i in get_mors_with_properties(
            service_instance, vim.Datacenter, property_list=["name"]
        )
        if get_all_datacenters or (datacenter_names and i["name"] in datacenter_names)
    ]
    return items


def get_datacenter(service_instance, datacenter_name):
    """
    Returns a vim.Datacenter managed object.

    service_instance
        The Service Instance Object from which to obtain datacenter.

    datacenter_name
        The datacenter name
    """
    items = get_datacenters(service_instance, datacenter_names=[datacenter_name])
    if not items:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Datacenter '{}' was not found".format(datacenter_name)
        )
    return items[0]


def create_datacenter(service_instance, datacenter_name):
    """
    Creates a datacenter.

    .. versionadded:: 2017.7.0

    service_instance
        The Service Instance Object

    datacenter_name
        The datacenter name
    """
    root_folder = get_root_folder(service_instance)
    log.trace("Creating datacenter '%s'", datacenter_name)
    try:
        dc_obj = root_folder.CreateDatacenter(datacenter_name)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    return dc_obj


def get_cluster(dc_ref, cluster):
    """
    Returns a cluster in a datacenter.

    dc_ref
        The datacenter reference

    cluster
        The cluster to be retrieved
    """
    dc_name = get_managed_object_name(dc_ref)
    log.trace("Retrieving cluster '%s' from datacenter '%s'", cluster, dc_name)
    si = get_service_instance_from_managed_object(dc_ref, name=dc_name)
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path="hostFolder",
        skip=True,
        type=vim.Datacenter,
        selectSet=[
            vmodl.query.PropertyCollector.TraversalSpec(
                path="childEntity", skip=False, type=vim.Folder
            )
        ],
    )
    items = [
        i["object"]
        for i in get_mors_with_properties(
            si,
            vim.ClusterComputeResource,
            container_ref=dc_ref,
            property_list=["name"],
            traversal_spec=traversal_spec,
        )
        if i["name"] == cluster
    ]
    if not items:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Cluster '{}' was not found in datacenter '{}'".format(cluster, dc_name)
        )
    return items[0]


def create_cluster(dc_ref, cluster_name, cluster_spec):
    """
    Creates a cluster in a datacenter.

    dc_ref
        The parent datacenter reference.

    cluster_name
        The cluster name.

    cluster_spec
        The cluster spec (vim.ClusterConfigSpecEx).
        Defaults to None.
    """
    dc_name = get_managed_object_name(dc_ref)
    log.trace("Creating cluster '%s' in datacenter '%s'", cluster_name, dc_name)
    try:
        dc_ref.hostFolder.CreateClusterEx(cluster_name, cluster_spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def update_cluster(cluster_ref, cluster_spec):
    """
    Updates a cluster in a datacenter.

    cluster_ref
        The cluster reference.

    cluster_spec
        The cluster spec (vim.ClusterConfigSpecEx).
        Defaults to None.
    """
    cluster_name = get_managed_object_name(cluster_ref)
    log.trace("Updating cluster '%s'", cluster_name)
    try:
        task = cluster_ref.ReconfigureComputeResource_Task(cluster_spec, modify=True)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, cluster_name, "ClusterUpdateTask")


def list_clusters(service_instance):
    """
    Returns a list of clusters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain clusters.
    """
    return list_objects(service_instance, vim.ClusterComputeResource)


def list_datastore_clusters(service_instance):
    """
    Returns a list of datastore clusters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datastore clusters.
    """
    return list_objects(service_instance, vim.StoragePod)


def list_datastores(service_instance):
    """
    Returns a list of datastores associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datastores.
    """
    return list_objects(service_instance, vim.Datastore)


def get_datastore_files(
    service_instance, directory, datastores, container_object, browser_spec
):
    """
    Get the files with a given browser specification from the datastore.

    service_instance
        The Service Instance Object from which to obtain datastores.

    directory
        The name of the directory where we would like to search

    datastores
        Name of the datastores

    container_object
        The base object for searches

    browser_spec
        BrowserSpec object which defines the search criteria

    return
        list of vim.host.DatastoreBrowser.SearchResults objects
    """

    files = []
    datastore_objects = get_datastores(
        service_instance, container_object, datastore_names=datastores
    )
    for datobj in datastore_objects:
        try:
            task = datobj.browser.SearchDatastore_Task(
                datastorePath="[{}] {}".format(datobj.name, directory),
                searchSpec=browser_spec,
            )
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.VimFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareRuntimeError(exc.msg)
        try:
            files.append(
                salt.utils.vmware.wait_for_task(
                    task, directory, "query virtual machine files"
                )
            )
        except salt.exceptions.VMwareFileNotFoundError:
            pass
    return files


def get_datastores(
    service_instance,
    reference,
    datastore_names=None,
    backing_disk_ids=None,
    get_all_datastores=False,
):
    """
    Returns a list of vim.Datastore objects representing the datastores visible
    from a VMware object, filtered by their names, or the backing disk
    cannonical name or scsi_addresses

    service_instance
        The Service Instance Object from which to obtain datastores.

    reference
        The VMware object from which the datastores are visible.

    datastore_names
        The list of datastore names to be retrieved. Default value is None.

    backing_disk_ids
        The list of canonical names of the disks backing the datastores
        to be retrieved. Only supported if reference is a vim.HostSystem.
        Default value is None

    get_all_datastores
        Specifies whether to retrieve all disks in the host.
        Default value is False.
    """
    obj_name = get_managed_object_name(reference)
    if get_all_datastores:
        log.trace("Retrieving all datastores visible to '%s'", obj_name)
    else:
        log.trace(
            "Retrieving datastores visible to '%s': names = (%s); "
            "backing disk ids = (%s)",
            obj_name,
            datastore_names,
            backing_disk_ids,
        )
        if backing_disk_ids and not isinstance(reference, vim.HostSystem):

            raise salt.exceptions.ArgumentValueError(
                "Unsupported reference type '{}' when backing disk filter "
                "is set".format(reference.__class__.__name__)
            )
    if (not get_all_datastores) and backing_disk_ids:
        # At this point we know the reference is a vim.HostSystem
        log.trace("Filtering datastores with backing disk ids: %s", backing_disk_ids)
        storage_system = get_storage_system(service_instance, reference, obj_name)
        props = salt.utils.vmware.get_properties_of_managed_object(
            storage_system, ["fileSystemVolumeInfo.mountInfo"]
        )
        mount_infos = props.get("fileSystemVolumeInfo.mountInfo", [])
        disk_datastores = []
        # Non vmfs volumes aren't backed by a disk
        for vol in [
            i.volume for i in mount_infos if isinstance(i.volume, vim.HostVmfsVolume)
        ]:

            if not [e for e in vol.extent if e.diskName in backing_disk_ids]:
                # Skip volume if it doesn't contain an extent with a
                # canonical name of interest
                continue
            log.trace(
                "Found datastore '%s' for disk id(s) '%s'",
                vol.name,
                [e.diskName for e in vol.extent],
            )
            disk_datastores.append(vol.name)
        log.trace("Datastore found for disk filter: %s", disk_datastores)
        if datastore_names:
            datastore_names.extend(disk_datastores)
        else:
            datastore_names = disk_datastores

    if (not get_all_datastores) and (not datastore_names):
        log.trace(
            "No datastore to be filtered after retrieving the datastores "
            "backed by the disk id(s) '%s'",
            backing_disk_ids,
        )
        return []

    log.trace("datastore_names = %s", datastore_names)

    # Use the default traversal spec
    if isinstance(reference, vim.HostSystem):
        # Create a different traversal spec for hosts because it looks like the
        # default doesn't retrieve the datastores
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name="host_datastore_traversal",
            path="datastore",
            skip=False,
            type=vim.HostSystem,
        )
    elif isinstance(reference, vim.ClusterComputeResource):
        # Traversal spec for clusters
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name="cluster_datastore_traversal",
            path="datastore",
            skip=False,
            type=vim.ClusterComputeResource,
        )
    elif isinstance(reference, vim.Datacenter):
        # Traversal spec for datacenter
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name="datacenter_datastore_traversal",
            path="datastore",
            skip=False,
            type=vim.Datacenter,
        )
    elif isinstance(reference, vim.StoragePod):
        # Traversal spec for datastore clusters
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name="datastore_cluster_traversal",
            path="childEntity",
            skip=False,
            type=vim.StoragePod,
        )
    elif (
        isinstance(reference, vim.Folder)
        and get_managed_object_name(reference) == "Datacenters"
    ):
        # Traversal of root folder (doesn't support multiple levels of Folders)
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            path="childEntity",
            selectSet=[
                vmodl.query.PropertyCollector.TraversalSpec(
                    path="datastore", skip=False, type=vim.Datacenter
                )
            ],
            skip=False,
            type=vim.Folder,
        )
    else:
        raise salt.exceptions.ArgumentValueError(
            "Unsupported reference type '{}'".format(reference.__class__.__name__)
        )

    items = get_mors_with_properties(
        service_instance,
        object_type=vim.Datastore,
        property_list=["name"],
        container_ref=reference,
        traversal_spec=traversal_spec,
    )
    log.trace("Retrieved %s datastores", len(items))
    items = [i for i in items if get_all_datastores or i["name"] in datastore_names]
    log.trace("Filtered datastores: %s", [i["name"] for i in items])
    return [i["object"] for i in items]


def rename_datastore(datastore_ref, new_datastore_name):
    """
    Renames a datastore

    datastore_ref
        vim.Datastore reference to the datastore object to be changed

    new_datastore_name
        New datastore name
    """
    ds_name = get_managed_object_name(datastore_ref)
    log.trace("Renaming datastore '%s' to '%s'", ds_name, new_datastore_name)
    try:
        datastore_ref.RenameDatastore(new_datastore_name)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)


def get_storage_system(service_instance, host_ref, hostname=None):
    """
    Returns a host's storage system
    """

    if not hostname:
        hostname = get_managed_object_name(host_ref)

    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path="configManager.storageSystem", type=vim.HostSystem, skip=False
    )
    objs = get_mors_with_properties(
        service_instance,
        vim.HostStorageSystem,
        property_list=["systemFile"],
        container_ref=host_ref,
        traversal_spec=traversal_spec,
    )
    if not objs:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Host's '{}' storage system was not retrieved".format(hostname)
        )
    log.trace("[%s] Retrieved storage system", hostname)
    return objs[0]["object"]


def _get_partition_info(storage_system, device_path):
    """
    Returns partition information for a device path, of type
    vim.HostDiskPartitionInfo
    """
    try:
        partition_infos = storage_system.RetrieveDiskPartitionInfo(
            devicePath=[device_path]
        )
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    log.trace("partition_info = %s", partition_infos[0])
    return partition_infos[0]


def _get_new_computed_partition_spec(storage_system, device_path, partition_info):
    """
    Computes the new disk partition info when adding a new vmfs partition that
    uses up the remainder of the disk; returns a tuple
    (new_partition_number, vim.HostDiskPartitionSpec
    """
    log.trace(
        "Adding a partition at the end of the disk and getting the new "
        "computed partition spec"
    )
    # TODO implement support for multiple partitions
    # We support adding a partition add the end of the disk with partitions
    free_partitions = [p for p in partition_info.layout.partition if p.type == "none"]
    if not free_partitions:
        raise salt.exceptions.VMwareObjectNotFoundError(
            "Free partition was not found on device '{}'".format(
                partition_info.deviceName
            )
        )
    free_partition = free_partitions[0]

    # Create a layout object that copies the existing one
    layout = vim.HostDiskPartitionLayout(
        total=partition_info.layout.total, partition=partition_info.layout.partition
    )
    # Create a partition with the free space on the disk
    # Change the free partition type to vmfs
    free_partition.type = "vmfs"
    try:
        computed_partition_info = storage_system.ComputeDiskPartitionInfo(
            devicePath=device_path,
            partitionFormat=vim.HostDiskPartitionInfoPartitionFormat.gpt,
            layout=layout,
        )
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    log.trace("computed partition info = {0}", computed_partition_info)
    log.trace("Retrieving new partition number")
    partition_numbers = [
        p.partition
        for p in computed_partition_info.layout.partition
        if (
            p.start.block == free_partition.start.block
            or
            # XXX If the entire disk is free (i.e. the free
            # disk partition starts at block 0) the newily
            # created partition is created from block 1
            (free_partition.start.block == 0 and p.start.block == 1)
        )
        and p.end.block == free_partition.end.block
        and p.type == "vmfs"
    ]
    if not partition_numbers:
        raise salt.exceptions.VMwareNotFoundError(
            "New partition was not found in computed partitions of device '{}'".format(
                partition_info.deviceName
            )
        )
    log.trace("new partition number = %s", partition_numbers[0])
    return (partition_numbers[0], computed_partition_info.spec)


def create_vmfs_datastore(
    host_ref, datastore_name, disk_ref, vmfs_major_version, storage_system=None
):
    """
    Creates a VMFS datastore from a disk_id

    host_ref
        vim.HostSystem object referencing a host to create the datastore on

    datastore_name
        Name of the datastore

    disk_ref
        vim.HostScsiDislk on which the datastore is created

    vmfs_major_version
        VMFS major version to use
    """
    # TODO Support variable sized partitions
    hostname = get_managed_object_name(host_ref)
    disk_id = disk_ref.canonicalName
    log.debug(
        "Creating datastore '%s' on host '%s', scsi disk '%s', vmfs v%s",
        datastore_name,
        hostname,
        disk_id,
        vmfs_major_version,
    )
    if not storage_system:
        si = get_service_instance_from_managed_object(host_ref, name=hostname)
        storage_system = get_storage_system(si, host_ref, hostname)

    target_disk = disk_ref
    partition_info = _get_partition_info(storage_system, target_disk.devicePath)
    log.trace("partition_info = %s", partition_info)
    new_partition_number, partition_spec = _get_new_computed_partition_spec(
        storage_system, target_disk.devicePath, partition_info
    )
    spec = vim.VmfsDatastoreCreateSpec(
        vmfs=vim.HostVmfsSpec(
            majorVersion=vmfs_major_version,
            volumeName=datastore_name,
            extent=vim.HostScsiDiskPartition(
                diskName=disk_id, partition=new_partition_number
            ),
        ),
        diskUuid=target_disk.uuid,
        partition=partition_spec,
    )
    try:
        ds_ref = host_ref.configManager.datastoreSystem.CreateVmfsDatastore(spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    log.debug("Created datastore '%s' on host '%s'", datastore_name, hostname)
    return ds_ref


def get_host_datastore_system(host_ref, hostname=None):
    """
    Returns a host's datastore system

    host_ref
        Reference to the ESXi host

    hostname
        Name of the host. This argument is optional.
    """

    if not hostname:
        hostname = get_managed_object_name(host_ref)
    service_instance = get_service_instance_from_managed_object(host_ref)
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path="configManager.datastoreSystem", type=vim.HostSystem, skip=False
    )
    objs = get_mors_with_properties(
        service_instance,
        vim.HostDatastoreSystem,
        property_list=["datastore"],
        container_ref=host_ref,
        traversal_spec=traversal_spec,
    )
    if not objs:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Host's '{}' datastore system was not retrieved".format(hostname)
        )
    log.trace("[%s] Retrieved datastore system", hostname)
    return objs[0]["object"]


def remove_datastore(service_instance, datastore_ref):
    """
    Creates a VMFS datastore from a disk_id

    service_instance
        The Service Instance Object containing the datastore

    datastore_ref
        The reference to the datastore to remove
    """
    ds_props = get_properties_of_managed_object(datastore_ref, ["host", "info", "name"])
    ds_name = ds_props["name"]
    log.debug("Removing datastore '%s'", ds_name)
    ds_hosts = ds_props.get("host")
    if not ds_hosts:
        raise salt.exceptions.VMwareApiError(
            "Datastore '{}' can't be removed. No attached hosts found".format(ds_name)
        )
    hostname = get_managed_object_name(ds_hosts[0].key)
    host_ds_system = get_host_datastore_system(ds_hosts[0].key, hostname=hostname)
    try:
        host_ds_system.RemoveDatastore(datastore_ref)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    log.trace("[%s] Removed datastore '%s'", hostname, ds_name)


def get_hosts(
    service_instance,
    datacenter_name=None,
    host_names=None,
    cluster_name=None,
    get_all_hosts=False,
):
    """
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
    """
    properties = ["name"]
    if cluster_name and not datacenter_name:
        raise salt.exceptions.ArgumentValueError(
            "Must specify the datacenter when specifying the cluster"
        )
    if not host_names:
        host_names = []
    if not datacenter_name:
        # Assume the root folder is the starting point
        start_point = get_root_folder(service_instance)
    else:
        start_point = get_datacenter(service_instance, datacenter_name)
        if cluster_name:
            # Retrieval to test if cluster exists. Cluster existence only makes
            # sense if the datacenter has been specified
            properties.append("parent")

    # Search for the objects
    hosts = get_mors_with_properties(
        service_instance,
        vim.HostSystem,
        container_ref=start_point,
        property_list=properties,
    )
    log.trace("Retrieved hosts: %s", [h["name"] for h in hosts])
    filtered_hosts = []
    for h in hosts:
        # Complex conditions checking if a host should be added to the
        # filtered list (either due to its name and/or cluster membership)

        if cluster_name:
            if not isinstance(h["parent"], vim.ClusterComputeResource):
                continue
            parent_name = get_managed_object_name(h["parent"])
            if parent_name != cluster_name:
                continue

        if get_all_hosts:
            filtered_hosts.append(h["object"])
            continue

        if h["name"] in host_names:
            filtered_hosts.append(h["object"])
    return filtered_hosts


def _get_scsi_address_to_lun_key_map(
    service_instance, host_ref, storage_system=None, hostname=None
):
    """
    Returns a map between the scsi addresses and the keys of all luns on an ESXi
    host.
        map[<scsi_address>] = <lun key>

    service_instance
        The Service Instance Object from which to obtain the hosts

    host_ref
        The vim.HostSystem object representing the host that contains the
        requested disks.

    storage_system
        The host's storage system. Default is None.

    hostname
        Name of the host. Default is None.
    """
    if not hostname:
        hostname = get_managed_object_name(host_ref)
    if not storage_system:
        storage_system = get_storage_system(service_instance, host_ref, hostname)
    try:
        device_info = storage_system.storageDeviceInfo
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    if not device_info:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Host's '{}' storage device info was not retrieved".format(hostname)
        )
    multipath_info = device_info.multipathInfo
    if not multipath_info:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Host's '{}' multipath info was not retrieved".format(hostname)
        )
    if multipath_info.lun is None:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "No luns were retrieved from host '{}'".format(hostname)
        )
    lun_key_by_scsi_addr = {}
    for l in multipath_info.lun:
        # The vmware scsi_address may have multiple comma separated values
        # The first one is the actual scsi address
        lun_key_by_scsi_addr.update({p.name.split(",")[0]: l.lun for p in l.path})
    log.trace(
        "Scsi address to lun id map on host '%s': %s", hostname, lun_key_by_scsi_addr
    )
    return lun_key_by_scsi_addr


def get_all_luns(host_ref, storage_system=None, hostname=None):
    """
    Returns a list of all vim.HostScsiDisk objects in a disk

    host_ref
        The vim.HostSystem object representing the host that contains the
        requested disks.

    storage_system
        The host's storage system. Default is None.

    hostname
        Name of the host. This argument is optional.
    """
    if not hostname:
        hostname = get_managed_object_name(host_ref)
    if not storage_system:
        si = get_service_instance_from_managed_object(host_ref, name=hostname)
        storage_system = get_storage_system(si, host_ref, hostname)
        if not storage_system:
            raise salt.exceptions.VMwareObjectRetrievalError(
                "Host's '{}' storage system was not retrieved".format(hostname)
            )
    try:
        device_info = storage_system.storageDeviceInfo
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    if not device_info:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Host's '{}' storage device info was not retrieved".format(hostname)
        )

    scsi_luns = device_info.scsiLun
    if scsi_luns:
        log.trace(
            "Retrieved scsi luns in host '%s': %s",
            hostname,
            [l.canonicalName for l in scsi_luns],
        )
        return scsi_luns
    log.trace("Retrieved no scsi_luns in host '%s'", hostname)
    return []


def get_scsi_address_to_lun_map(host_ref, storage_system=None, hostname=None):
    """
    Returns a map of all vim.ScsiLun objects on a ESXi host keyed by their
    scsi address

    host_ref
        The vim.HostSystem object representing the host that contains the
        requested disks.

    storage_system
        The host's storage system. Default is None.

    hostname
        Name of the host. This argument is optional.
    """
    if not hostname:
        hostname = get_managed_object_name(host_ref)
    si = get_service_instance_from_managed_object(host_ref, name=hostname)
    if not storage_system:
        storage_system = get_storage_system(si, host_ref, hostname)
    lun_ids_to_scsi_addr_map = _get_scsi_address_to_lun_key_map(
        si, host_ref, storage_system, hostname
    )
    luns_to_key_map = {
        d.key: d for d in get_all_luns(host_ref, storage_system, hostname)
    }
    return {
        scsi_addr: luns_to_key_map[lun_key]
        for scsi_addr, lun_key in lun_ids_to_scsi_addr_map.items()
    }


def get_disks(host_ref, disk_ids=None, scsi_addresses=None, get_all_disks=False):
    """
    Returns a list of vim.HostScsiDisk objects representing disks
    in a ESXi host, filtered by their cannonical names and scsi_addresses

    host_ref
        The vim.HostSystem object representing the host that contains the
        requested disks.

    disk_ids
        The list of canonical names of the disks to be retrieved. Default value
        is None

    scsi_addresses
        The list of scsi addresses of the disks to be retrieved. Default value
        is None

    get_all_disks
        Specifies whether to retrieve all disks in the host.
        Default value is False.
    """
    hostname = get_managed_object_name(host_ref)
    if get_all_disks:
        log.trace("Retrieving all disks in host '%s'", hostname)
    else:
        log.trace(
            "Retrieving disks in host '%s': ids = (%s); scsi addresses = (%s)",
            hostname,
            disk_ids,
            scsi_addresses,
        )
        if not (disk_ids or scsi_addresses):
            return []
    si = get_service_instance_from_managed_object(host_ref, name=hostname)
    storage_system = get_storage_system(si, host_ref, hostname)
    disk_keys = []
    if scsi_addresses:
        # convert the scsi addresses to disk keys
        lun_key_by_scsi_addr = _get_scsi_address_to_lun_key_map(
            si, host_ref, storage_system, hostname
        )
        disk_keys = [
            key
            for scsi_addr, key in lun_key_by_scsi_addr.items()
            if scsi_addr in scsi_addresses
        ]
        log.trace("disk_keys based on scsi_addresses = %s", disk_keys)

    scsi_luns = get_all_luns(host_ref, storage_system)
    scsi_disks = [
        disk
        for disk in scsi_luns
        if isinstance(disk, vim.HostScsiDisk)
        and (
            get_all_disks
            or
            # Filter by canonical name
            (disk_ids and (disk.canonicalName in disk_ids))
            or
            # Filter by disk keys from scsi addresses
            (disk.key in disk_keys)
        )
    ]
    log.trace(
        "Retrieved disks in host '%s': %s",
        hostname,
        [d.canonicalName for d in scsi_disks],
    )
    return scsi_disks


def get_disk_partition_info(host_ref, disk_id, storage_system=None):
    """
    Returns all partitions on a disk

    host_ref
        The reference of the ESXi host containing the disk

    disk_id
        The canonical name of the disk whose partitions are to be removed

    storage_system
        The ESXi host's storage system. Default is None.
    """
    hostname = get_managed_object_name(host_ref)
    service_instance = get_service_instance_from_managed_object(host_ref)
    if not storage_system:
        storage_system = get_storage_system(service_instance, host_ref, hostname)

    props = get_properties_of_managed_object(
        storage_system, ["storageDeviceInfo.scsiLun"]
    )
    if not props.get("storageDeviceInfo.scsiLun"):
        raise salt.exceptions.VMwareObjectRetrievalError(
            "No devices were retrieved in host '{}'".format(hostname)
        )
    log.trace(
        "[%s] Retrieved %s devices: %s",
        hostname,
        len(props["storageDeviceInfo.scsiLun"]),
        ", ".join([l.canonicalName for l in props["storageDeviceInfo.scsiLun"]]),
    )
    disks = [
        l
        for l in props["storageDeviceInfo.scsiLun"]
        if isinstance(l, vim.HostScsiDisk) and l.canonicalName == disk_id
    ]
    if not disks:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Disk '{}' was not found in host '{}'".format(disk_id, hostname)
        )
    log.trace("[%s] device_path = %s", hostname, disks[0].devicePath)
    partition_info = _get_partition_info(storage_system, disks[0].devicePath)
    log.trace(
        "[%s] Retrieved %s partition(s) on disk '%s'",
        hostname,
        len(partition_info.spec.partition),
        disk_id,
    )
    return partition_info


def erase_disk_partitions(
    service_instance, host_ref, disk_id, hostname=None, storage_system=None
):
    """
    Erases all partitions on a disk

    in a vcenter filtered by their names and/or datacenter, cluster membership

    service_instance
        The Service Instance Object from which to obtain all information

    host_ref
        The reference of the ESXi host containing the disk

    disk_id
        The canonical name of the disk whose partitions are to be removed

    hostname
        The ESXi hostname. Default is None.

    storage_system
        The ESXi host's storage system. Default is None.
    """

    if not hostname:
        hostname = get_managed_object_name(host_ref)
    if not storage_system:
        storage_system = get_storage_system(service_instance, host_ref, hostname)

    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path="configManager.storageSystem", type=vim.HostSystem, skip=False
    )
    results = get_mors_with_properties(
        service_instance,
        vim.HostStorageSystem,
        ["storageDeviceInfo.scsiLun"],
        container_ref=host_ref,
        traversal_spec=traversal_spec,
    )
    if not results:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Host's '{}' devices were not retrieved".format(hostname)
        )
    log.trace(
        "[%s] Retrieved %s devices: %s",
        hostname,
        len(results[0].get("storageDeviceInfo.scsiLun", [])),
        ", ".join(
            [l.canonicalName for l in results[0].get("storageDeviceInfo.scsiLun", [])]
        ),
    )
    disks = [
        l
        for l in results[0].get("storageDeviceInfo.scsiLun", [])
        if isinstance(l, vim.HostScsiDisk) and l.canonicalName == disk_id
    ]
    if not disks:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "Disk '{}' was not found in host '{}'".format(disk_id, hostname)
        )
    log.trace("[%s] device_path = %s", hostname, disks[0].devicePath)
    # Erase the partitions by setting an empty partition spec
    try:
        storage_system.UpdateDiskPartitions(
            disks[0].devicePath, vim.HostDiskPartitionSpec()
        )
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    log.trace("[%s] Erased partitions on disk '%s'", hostname, disk_id)


def get_diskgroups(host_ref, cache_disk_ids=None, get_all_disk_groups=False):
    """
    Returns a list of vim.VsanHostDiskMapping objects representing disks
    in a ESXi host, filtered by their cannonical names.

    host_ref
        The vim.HostSystem object representing the host that contains the
        requested disks.

    cache_disk_ids
        The list of cannonical names of the cache disks to be retrieved. The
        canonical name of the cache disk is enough to identify the disk group
        because it is guaranteed to have one and only one cache disk.
        Default is None.

    get_all_disk_groups
        Specifies whether to retrieve all disks groups in the host.
        Default value is False.
    """
    hostname = get_managed_object_name(host_ref)
    if get_all_disk_groups:
        log.trace("Retrieving all disk groups on host '%s'", hostname)
    else:
        log.trace(
            "Retrieving disk groups from host '%s', with cache disk ids : (%s)",
            hostname,
            cache_disk_ids,
        )
        if not cache_disk_ids:
            return []
    try:
        vsan_host_config = host_ref.config.vsanHostConfig
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    if not vsan_host_config:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "No host config found on host '{}'".format(hostname)
        )
    vsan_storage_info = vsan_host_config.storageInfo
    if not vsan_storage_info:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "No vsan storage info found on host '{}'".format(hostname)
        )
    vsan_disk_mappings = vsan_storage_info.diskMapping
    if not vsan_disk_mappings:
        return []
    disk_groups = [
        dm
        for dm in vsan_disk_mappings
        if (get_all_disk_groups or (dm.ssd.canonicalName in cache_disk_ids))
    ]
    log.trace(
        "Retrieved disk groups on host '%s', with cache disk ids : %s",
        hostname,
        [d.ssd.canonicalName for d in disk_groups],
    )
    return disk_groups


def _check_disks_in_diskgroup(disk_group, cache_disk_id, capacity_disk_ids):
    """
    Checks that the disks in a disk group are as expected and raises
    CheckError exceptions if the check fails
    """
    if not disk_group.ssd.canonicalName == cache_disk_id:
        raise salt.exceptions.ArgumentValueError(
            "Incorrect diskgroup cache disk; got id: '{}'; expected id: '{}'".format(
                disk_group.ssd.canonicalName, cache_disk_id
            )
        )
    non_ssd_disks = [d.canonicalName for d in disk_group.nonSsd]
    if sorted(non_ssd_disks) != sorted(capacity_disk_ids):
        raise salt.exceptions.ArgumentValueError(
            "Incorrect capacity disks; got ids: '{}'; expected ids: '{}'".format(
                sorted(non_ssd_disks), sorted(capacity_disk_ids)
            )
        )
    log.trace("Checked disks in diskgroup with cache disk id '%s'", cache_disk_id)
    return True


# TODO Support host caches on multiple datastores
def get_host_cache(host_ref, host_cache_manager=None):
    """
    Returns a vim.HostScsiDisk if the host cache is configured on the specified
    host, other wise returns None

    host_ref
        The vim.HostSystem object representing the host that contains the
        requested disks.

    host_cache_manager
        The vim.HostCacheConfigurationManager object representing the cache
        configuration manager on the specified host. Default is None. If None,
        it will be retrieved in the method
    """
    hostname = get_managed_object_name(host_ref)
    service_instance = get_service_instance_from_managed_object(host_ref)
    log.trace("Retrieving the host cache on host '%s'", hostname)
    if not host_cache_manager:
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            path="configManager.cacheConfigurationManager",
            type=vim.HostSystem,
            skip=False,
        )
        results = get_mors_with_properties(
            service_instance,
            vim.HostCacheConfigurationManager,
            ["cacheConfigurationInfo"],
            container_ref=host_ref,
            traversal_spec=traversal_spec,
        )
        if not results or not results[0].get("cacheConfigurationInfo"):
            log.trace("Host '%s' has no host cache", hostname)
            return None
        return results[0]["cacheConfigurationInfo"][0]
    else:
        results = get_properties_of_managed_object(
            host_cache_manager, ["cacheConfigurationInfo"]
        )
        if not results:
            log.trace("Host '%s' has no host cache", hostname)
            return None
        return results["cacheConfigurationInfo"][0]


# TODO Support host caches on multiple datastores
def configure_host_cache(
    host_ref, datastore_ref, swap_size_MiB, host_cache_manager=None
):
    """
    Configures the host cahe of the specified host

    host_ref
        The vim.HostSystem object representing the host that contains the
        requested disks.

    datastore_ref
        The vim.Datastore opject representing the datastore the host cache will
        be configured on.

    swap_size_MiB
        The size in Mibibytes of the swap.

    host_cache_manager
        The vim.HostCacheConfigurationManager object representing the cache
        configuration manager on the specified host. Default is None. If None,
        it will be retrieved in the method
    """
    hostname = get_managed_object_name(host_ref)
    if not host_cache_manager:
        props = get_properties_of_managed_object(
            host_ref, ["configManager.cacheConfigurationManager"]
        )
        if not props.get("configManager.cacheConfigurationManager"):
            raise salt.exceptions.VMwareObjectRetrievalError(
                "Host '{}' has no host cache".format(hostname)
            )
        host_cache_manager = props["configManager.cacheConfigurationManager"]
    log.trace(
        "Configuring the host cache on host '%s', datastore '%s', swap size=%s MiB",
        hostname,
        datastore_ref.name,
        swap_size_MiB,
    )

    spec = vim.HostCacheConfigurationSpec(
        datastore=datastore_ref, swapSize=swap_size_MiB
    )
    log.trace("host_cache_spec=%s", spec)
    try:
        task = host_cache_manager.ConfigureHostCache_Task(spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, hostname, "HostCacheConfigurationTask")
    log.trace("Configured host cache on host '%s'", hostname)
    return True


def list_hosts(service_instance):
    """
    Returns a list of hosts associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain hosts.
    """
    return list_objects(service_instance, vim.HostSystem)


def get_resource_pools(
    service_instance,
    resource_pool_names,
    datacenter_name=None,
    get_all_resource_pools=False,
):
    """
    Retrieves resource pool objects

    service_instance
        The service instance object to query the vCenter

    resource_pool_names
        Resource pool names

    datacenter_name
        Name of the datacenter where the resource pool is available

    get_all_resource_pools
        Boolean

    return
        Resourcepool managed object reference
    """

    properties = ["name"]
    if not resource_pool_names:
        resource_pool_names = []
    if datacenter_name:
        container_ref = get_datacenter(service_instance, datacenter_name)
    else:
        container_ref = get_root_folder(service_instance)

    resource_pools = get_mors_with_properties(
        service_instance,
        vim.ResourcePool,
        container_ref=container_ref,
        property_list=properties,
    )

    selected_pools = []
    for pool in resource_pools:
        if get_all_resource_pools or (pool["name"] in resource_pool_names):
            selected_pools.append(pool["object"])
    if not selected_pools:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "The resource pools with properties "
            "names={} get_all={} could not be found".format(
                selected_pools, get_all_resource_pools
            )
        )

    return selected_pools


def list_resourcepools(service_instance):
    """
    Returns a list of resource pools associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain resource pools.
    """
    return list_objects(service_instance, vim.ResourcePool)


def list_networks(service_instance):
    """
    Returns a list of networks associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain networks.
    """
    return list_objects(service_instance, vim.Network)


def list_vms(service_instance):
    """
    Returns a list of VMs associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain VMs.
    """
    return list_objects(service_instance, vim.VirtualMachine)


def list_folders(service_instance):
    """
    Returns a list of folders associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain folders.
    """
    return list_objects(service_instance, vim.Folder)


def list_dvs(service_instance):
    """
    Returns a list of distributed virtual switches associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain distributed virtual switches.
    """
    return list_objects(service_instance, vim.DistributedVirtualSwitch)


def list_vapps(service_instance):
    """
    Returns a list of vApps associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain vApps.
    """
    return list_objects(service_instance, vim.VirtualApp)


def list_portgroups(service_instance):
    """
    Returns a list of distributed virtual portgroups associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain distributed virtual switches.
    """
    return list_objects(service_instance, vim.dvs.DistributedVirtualPortgroup)


def wait_for_task(task, instance_name, task_type, sleep_seconds=1, log_level="debug"):
    """
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
    """
    time_counter = 0
    start_time = time.time()
    log.trace("task = %s, task_type = %s", task, task.__class__.__name__)
    try:
        task_info = task.info
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.FileNotFound as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareFileNotFoundError(exc.msg)
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    while task_info.state == "running" or task_info.state == "queued":
        if time_counter % sleep_seconds == 0:
            msg = "[ {} ] Waiting for {} task to finish [{} s]".format(
                instance_name, task_type, time_counter
            )
            if log_level == "info":
                log.info(msg)
            else:
                log.debug(msg)
        time.sleep(1.0 - ((time.time() - start_time) % 1.0))
        time_counter += 1
        try:
            task_info = task.info
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.FileNotFound as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareFileNotFoundError(exc.msg)
        except vim.fault.VimFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareRuntimeError(exc.msg)
    if task_info.state == "success":
        msg = "[ {} ] Successfully completed {} task in {} seconds".format(
            instance_name, task_type, time_counter
        )
        if log_level == "info":
            log.info(msg)
        else:
            log.debug(msg)
        # task is in a successful state
        return task_info.result
    else:
        # task is in an error state
        try:
            raise task_info.error
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.FileNotFound as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareFileNotFoundError(exc.msg)
        except vim.fault.VimFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.fault.SystemError as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareSystemError(exc.msg)
        except vmodl.fault.InvalidArgument as exc:
            log.exception(exc)
            exc_message = exc.msg
            if exc.faultMessage:
                exc_message = "{} ({})".format(exc_message, exc.faultMessage[0].message)
            raise salt.exceptions.VMwareApiError(exc_message)


def get_vm_by_property(
    service_instance,
    name,
    datacenter=None,
    vm_properties=None,
    traversal_spec=None,
    parent_ref=None,
):
    """
    Get virtual machine properties based on the traversal specs and properties list,
    returns Virtual Machine object with properties.

    service_instance
        Service instance object to access vCenter

    name
        Name of the virtual machine.

    datacenter
        Datacenter name

    vm_properties
        List of vm properties.

    traversal_spec
        Traversal Spec object(s) for searching.

    parent_ref
        Container Reference object for searching under a given object.
    """
    if datacenter and not parent_ref:
        parent_ref = salt.utils.vmware.get_datacenter(service_instance, datacenter)
    if not vm_properties:
        vm_properties = [
            "name",
            "config.hardware.device",
            "summary.storage.committed",
            "summary.storage.uncommitted",
            "summary.storage.unshared",
            "layoutEx.file",
            "config.guestFullName",
            "config.guestId",
            "guest.net",
            "config.hardware.memoryMB",
            "config.hardware.numCPU",
            "config.files.vmPathName",
            "summary.runtime.powerState",
            "guest.toolsStatus",
        ]
    vm_list = salt.utils.vmware.get_mors_with_properties(
        service_instance,
        vim.VirtualMachine,
        vm_properties,
        container_ref=parent_ref,
        traversal_spec=traversal_spec,
    )
    vm_formatted = [vm for vm in vm_list if vm["name"] == name]
    if not vm_formatted:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "The virtual machine was not found."
        )
    elif len(vm_formatted) > 1:
        raise salt.exceptions.VMwareMultipleObjectsError(
            " ".join(
                [
                    "Multiple virtual machines were found with the"
                    "same name, please specify a container."
                ]
            )
        )
    return vm_formatted[0]


def get_folder(service_instance, datacenter, placement, base_vm_name=None):
    """
    Returns a Folder Object

    service_instance
        Service instance object

    datacenter
        Name of the datacenter

    placement
        Placement dictionary

    base_vm_name
        Existing virtual machine name (for cloning)
    """
    log.trace("Retrieving folder information")
    if base_vm_name:
        vm_object = get_vm_by_property(
            service_instance, base_vm_name, vm_properties=["name"]
        )
        vm_props = salt.utils.vmware.get_properties_of_managed_object(
            vm_object, properties=["parent"]
        )
        if "parent" in vm_props:
            folder_object = vm_props["parent"]
        else:
            raise salt.exceptions.VMwareObjectRetrievalError(
                " ".join(["The virtual machine parent", "object is not defined"])
            )
    elif "folder" in placement:
        folder_objects = salt.utils.vmware.get_folders(
            service_instance, [placement["folder"]], datacenter
        )
        if len(folder_objects) > 1:
            raise salt.exceptions.VMwareMultipleObjectsError(
                " ".join(
                    [
                        "Multiple instances are available of the",
                        "specified folder {}".format(placement["folder"]),
                    ]
                )
            )
        folder_object = folder_objects[0]
    elif datacenter:
        datacenter_object = salt.utils.vmware.get_datacenter(
            service_instance, datacenter
        )
        dc_props = salt.utils.vmware.get_properties_of_managed_object(
            datacenter_object, properties=["vmFolder"]
        )
        if "vmFolder" in dc_props:
            folder_object = dc_props["vmFolder"]
        else:
            raise salt.exceptions.VMwareObjectRetrievalError(
                "The datacenter vm folder object is not defined"
            )
    return folder_object


def get_placement(service_instance, datacenter, placement=None):
    """
    To create a virtual machine a resource pool needs to be supplied, we would like to use the strictest as possible.

    datacenter
        Name of the datacenter

    placement
        Dictionary with the placement info, cluster, host resource pool name

    return
        Resource pool, cluster and host object if any applies
    """
    log.trace("Retrieving placement information")
    resourcepool_object, placement_object = None, None
    if "host" in placement:
        host_objects = get_hosts(
            service_instance, datacenter_name=datacenter, host_names=[placement["host"]]
        )
        if not host_objects:
            raise salt.exceptions.VMwareObjectRetrievalError(
                " ".join(
                    [
                        "The specified host",
                        "{} cannot be found.".format(placement["host"]),
                    ]
                )
            )
        try:
            host_props = get_properties_of_managed_object(
                host_objects[0], properties=["resourcePool"]
            )
            resourcepool_object = host_props["resourcePool"]
        except vmodl.query.InvalidProperty:
            traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
                path="parent",
                skip=True,
                type=vim.HostSystem,
                selectSet=[
                    vmodl.query.PropertyCollector.TraversalSpec(
                        path="resourcePool", skip=False, type=vim.ClusterComputeResource
                    )
                ],
            )
            resourcepools = get_mors_with_properties(
                service_instance,
                vim.ResourcePool,
                container_ref=host_objects[0],
                property_list=["name"],
                traversal_spec=traversal_spec,
            )
            if resourcepools:
                resourcepool_object = resourcepools[0]["object"]
            else:
                raise salt.exceptions.VMwareObjectRetrievalError(
                    "The resource pool of host {} cannot be found.".format(
                        placement["host"]
                    )
                )
        placement_object = host_objects[0]
    elif "resourcepool" in placement:
        resourcepool_objects = get_resource_pools(
            service_instance, [placement["resourcepool"]], datacenter_name=datacenter
        )
        if len(resourcepool_objects) > 1:
            raise salt.exceptions.VMwareMultipleObjectsError(
                " ".join(
                    [
                        "Multiple instances are available of the",
                        "specified host {}.".format(placement["host"]),
                    ]
                )
            )
        resourcepool_object = resourcepool_objects[0]
        res_props = get_properties_of_managed_object(
            resourcepool_object, properties=["parent"]
        )
        if "parent" in res_props:
            placement_object = res_props["parent"]
        else:
            raise salt.exceptions.VMwareObjectRetrievalError(
                " ".join(["The resource pool's parent", "object is not defined"])
            )
    elif "cluster" in placement:
        datacenter_object = get_datacenter(service_instance, datacenter)
        cluster_object = get_cluster(datacenter_object, placement["cluster"])
        clus_props = get_properties_of_managed_object(
            cluster_object, properties=["resourcePool"]
        )
        if "resourcePool" in clus_props:
            resourcepool_object = clus_props["resourcePool"]
        else:
            raise salt.exceptions.VMwareObjectRetrievalError(
                " ".join(["The cluster's resource pool", "object is not defined"])
            )
        placement_object = cluster_object
    else:
        # We are checking the schema for this object, this exception should never be raised
        raise salt.exceptions.VMwareObjectRetrievalError(
            " ".join(["Placement is not defined."])
        )
    return (resourcepool_object, placement_object)


def convert_to_kb(unit, size):
    """
    Converts the given size to KB based on the unit, returns a long integer.

    unit
        Unit of the size eg. GB; Note: to VMware a GB is the same as GiB = 1024MiB
    size
        Number which represents the size
    """
    if unit.lower() == "gb":
        # vCenter needs long value
        target_size = int(size * 1024 * 1024)
    elif unit.lower() == "mb":
        target_size = int(size * 1024)
    elif unit.lower() == "kb":
        target_size = int(size)
    else:
        raise salt.exceptions.ArgumentValueError("The unit is not specified")
    return {"size": target_size, "unit": "KB"}


def power_cycle_vm(virtual_machine, action="on"):
    """
    Powers on/off a virtual machine specified by its name.

    virtual_machine
        vim.VirtualMachine object to power on/off virtual machine

    action
        Operation option to power on/off the machine
    """
    if action == "on":
        try:
            task = virtual_machine.PowerOn()
            task_name = "power on"
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.VimFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareRuntimeError(exc.msg)
    elif action == "off":
        try:
            task = virtual_machine.PowerOff()
            task_name = "power off"
        except vim.fault.NoPermission as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(
                "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
            )
        except vim.fault.VimFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareApiError(exc.msg)
        except vmodl.RuntimeFault as exc:
            log.exception(exc)
            raise salt.exceptions.VMwareRuntimeError(exc.msg)
    else:
        raise salt.exceptions.ArgumentValueError("The given action is not supported")
    try:
        wait_for_task(task, get_managed_object_name(virtual_machine), task_name)
    except salt.exceptions.VMwareFileNotFoundError as exc:
        raise salt.exceptions.VMwarePowerOnError(
            " ".join(
                [
                    "An error occurred during power",
                    "operation, a file was not found: {}".format(exc),
                ]
            )
        )
    return virtual_machine


def create_vm(
    vm_name, vm_config_spec, folder_object, resourcepool_object, host_object=None
):
    """
    Creates virtual machine from config spec

    vm_name
        Virtual machine name to be created

    vm_config_spec
        Virtual Machine Config Spec object

    folder_object
        vm Folder managed object reference

    resourcepool_object
        Resource pool object where the machine will be created

    host_object
        Host object where the machine will ne placed (optional)

    return
        Virtual Machine managed object reference
    """
    try:
        if host_object and isinstance(host_object, vim.HostSystem):
            task = folder_object.CreateVM_Task(
                vm_config_spec, pool=resourcepool_object, host=host_object
            )
        else:
            task = folder_object.CreateVM_Task(vm_config_spec, pool=resourcepool_object)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    vm_object = wait_for_task(task, vm_name, "CreateVM Task", 10, "info")
    return vm_object


def register_vm(datacenter, name, vmx_path, resourcepool_object, host_object=None):
    """
    Registers a virtual machine to the inventory with the given vmx file, on success
    it returns the vim.VirtualMachine managed object reference

    datacenter
        Datacenter object of the virtual machine, vim.Datacenter object

    name
        Name of the virtual machine

    vmx_path:
        Full path to the vmx file, datastore name should be included

    resourcepool
        Placement resource pool of the virtual machine, vim.ResourcePool object

    host
        Placement host of the virtual machine, vim.HostSystem object
    """
    try:
        if host_object:
            task = datacenter.vmFolder.RegisterVM_Task(
                path=vmx_path,
                name=name,
                asTemplate=False,
                host=host_object,
                pool=resourcepool_object,
            )
        else:
            task = datacenter.vmFolder.RegisterVM_Task(
                path=vmx_path, name=name, asTemplate=False, pool=resourcepool_object
            )
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    try:
        vm_ref = wait_for_task(task, name, "RegisterVM Task")
    except salt.exceptions.VMwareFileNotFoundError as exc:
        raise salt.exceptions.VMwareVmRegisterError(
            "An error occurred during registration operation, the "
            "configuration file was not found: {}".format(exc)
        )
    return vm_ref


def update_vm(vm_ref, vm_config_spec):
    """
    Updates the virtual machine configuration with the given object

    vm_ref
        Virtual machine managed object reference

    vm_config_spec
        Virtual machine config spec object to update
    """
    vm_name = get_managed_object_name(vm_ref)
    log.trace("Updating vm '%s'", vm_name)
    try:
        task = vm_ref.ReconfigVM_Task(vm_config_spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    vm_ref = wait_for_task(task, vm_name, "ReconfigureVM Task")
    return vm_ref


def delete_vm(vm_ref):
    """
    Destroys the virtual machine

    vm_ref
        Managed object reference of a virtual machine object
    """
    vm_name = get_managed_object_name(vm_ref)
    log.trace("Destroying vm '%s'", vm_name)
    try:
        task = vm_ref.Destroy_Task()
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
    wait_for_task(task, vm_name, "Destroy Task")


def unregister_vm(vm_ref):
    """
    Destroys the virtual machine

    vm_ref
        Managed object reference of a virtual machine object
    """
    vm_name = get_managed_object_name(vm_ref)
    log.trace("Destroying vm '%s'", vm_name)
    try:
        vm_ref.UnregisterVM()
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise salt.exceptions.VMwareApiError(
            "Not enough permissions. Required privilege: {}".format(exc.privilegeId)
        )
    except vim.fault.VimFault as exc:
        raise salt.exceptions.VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        raise salt.exceptions.VMwareRuntimeError(exc.msg)
