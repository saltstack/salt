"""
Microsoft IIS site management

This module provides the ability to add/remove websites and application pools
from Microsoft IIS.

.. versionadded:: 2016.3.0

"""

# Define the module's virtual name
__virtualname__ = "win_iis"


def __virtual__():
    """
    Load only on minions that have the win_iis module.
    """
    if "win_iis.create_site" in __salt__:
        return __virtualname__
    return (False, "win_iis module could not be loaded")


def _get_binding_info(hostheader="", ipaddress="*", port=80):
    """
    Combine the host header, IP address, and TCP port into bindingInformation format.
    """
    ret = r"{}:{}:{}".format(ipaddress, port, hostheader.replace(" ", ""))

    return ret


def deployed(
    name, sourcepath, apppool="", hostheader="", ipaddress="*", port=80, protocol="http"
):
    """
    Ensure the website has been deployed.

    .. note:

        This function only validates against the site name, and will return True even
        if the site already exists with a different configuration. It will not modify
        the configuration of an existing site.

    :param str name: The IIS site name.
    :param str sourcepath: The physical path of the IIS site.
    :param str apppool: The name of the IIS application pool.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str protocol: The application protocol of the binding.

    .. note:

        If an application pool is specified, and that application pool does not already exist,
        it will be created.

    Example of usage with only the required arguments. This will default to using the default application pool
    assigned by IIS:

    .. code-block:: yaml

        site0-deployed:
            win_iis.deployed:
                - name: site0
                - sourcepath: C:\\inetpub\\site0

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-deployed:
            win_iis.deployed:
                - name: site0
                - sourcepath: C:\\inetpub\\site0
                - apppool: site0
                - hostheader: site0.local
                - ipaddress: '*'
                - port: 443
                - protocol: https
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    current_sites = __salt__["win_iis.list_sites"]()

    if name in current_sites:
        ret["comment"] = f"Site already present: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Site will be created: {name}"
        ret["changes"] = {"old": None, "new": name}
    else:
        ret["comment"] = f"Created site: {name}"
        ret["changes"] = {"old": None, "new": name}
        ret["result"] = __salt__["win_iis.create_site"](
            name, sourcepath, apppool, hostheader, ipaddress, port, protocol
        )
    return ret


def remove_site(name):
    """
    Delete a website from IIS.

    :param str name: The IIS site name.

    Usage:

    .. code-block:: yaml

        defaultwebsite-remove:
            win_iis.remove_site:
                - name: Default Web Site
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    current_sites = __salt__["win_iis.list_sites"]()

    if name not in current_sites:
        ret["comment"] = f"Site has already been removed: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Site will be removed: {name}"
        ret["changes"] = {"old": name, "new": None}
    else:
        ret["comment"] = f"Removed site: {name}"
        ret["changes"] = {"old": name, "new": None}
        ret["result"] = __salt__["win_iis.remove_site"](name)
    return ret


def create_binding(
    name, site, hostheader="", ipaddress="*", port=80, protocol="http", sslflags=0
):
    """
    Create an IIS binding.

    .. note:

        This function only validates against the binding ipaddress:port:hostheader combination,
        and will return True even if the binding already exists with a different configuration.
        It will not modify the configuration of an existing binding.

    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str protocol: The application protocol of the binding.
    :param str sslflags: The flags representing certificate type and storage of the binding.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-https-binding:
            win_iis.create_binding:
                - site: site0

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-https-binding:
            win_iis.create_binding:
                - site: site0
                - hostheader: site0.local
                - ipaddress: '*'
                - port: 443
                - protocol: https
                - sslflags: 0
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_bindings = __salt__["win_iis.list_bindings"](site)

    if binding_info in current_bindings:
        ret["comment"] = f"Binding already present: {binding_info}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Binding will be created: {binding_info}"
        ret["changes"] = {"old": None, "new": binding_info}
    else:
        ret["comment"] = f"Created binding: {binding_info}"
        ret["changes"] = {"old": None, "new": binding_info}
        ret["result"] = __salt__["win_iis.create_binding"](
            site, hostheader, ipaddress, port, protocol, sslflags
        )
    return ret


def remove_binding(name, site, hostheader="", ipaddress="*", port=80):
    """
    Remove an IIS binding.

    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-https-binding-remove:
            win_iis.remove_binding:
                - site: site0

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-https-binding-remove:
            win_iis.remove_binding:
                - site: site0
                - hostheader: site0.local
                - ipaddress: '*'
                - port: 443
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_bindings = __salt__["win_iis.list_bindings"](site)

    if binding_info not in current_bindings:
        ret["comment"] = f"Binding has already been removed: {binding_info}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Binding will be removed: {binding_info}"
        ret["changes"] = {"old": binding_info, "new": None}
    else:
        ret["comment"] = f"Removed binding: {binding_info}"
        ret["changes"] = {"old": binding_info, "new": None}
        ret["result"] = __salt__["win_iis.remove_binding"](
            site, hostheader, ipaddress, port
        )
    return ret


def create_cert_binding(name, site, hostheader="", ipaddress="*", port=443, sslflags=0):
    """
    Assign a certificate to an IIS binding.

    .. note:

        The web binding that the certificate is being assigned to must already exist.

    :param str name: The thumbprint of the certificate.
    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.
    :param str sslflags: Flags representing certificate type and certificate storage of the binding.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-cert-binding:
            win_iis.create_cert_binding:
                - name: 9988776655443322111000AAABBBCCCDDDEEEFFF
                - site: site0

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-cert-binding:
            win_iis.create_cert_binding:
                - name: 9988776655443322111000AAABBBCCCDDDEEEFFF
                - site: site0
                - hostheader: site0.local
                - ipaddress: 192.168.1.199
                - port: 443
                - sslflags: 1

    .. versionadded:: 2016.11.0
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_cert_bindings = __salt__["win_iis.list_cert_bindings"](site)

    if binding_info in current_cert_bindings:
        current_name = current_cert_bindings[binding_info]["certificatehash"]

        if name == current_name:
            ret["comment"] = f"Certificate binding already present: {name}"
            ret["result"] = True
            return ret
        ret["comment"] = (
            "Certificate binding already present with a different"
            " thumbprint: {}".format(current_name)
        )
        ret["result"] = False
    elif __opts__["test"]:
        ret["comment"] = f"Certificate binding will be created: {name}"
        ret["changes"] = {"old": None, "new": name}
    else:
        ret["comment"] = f"Created certificate binding: {name}"
        ret["changes"] = {"old": None, "new": name}
        ret["result"] = __salt__["win_iis.create_cert_binding"](
            name, site, hostheader, ipaddress, port, sslflags
        )
    return ret


def remove_cert_binding(name, site, hostheader="", ipaddress="*", port=443):
    """
    Remove a certificate from an IIS binding.

    .. note:

        This function only removes the certificate from the web binding. It does
        not remove the web binding itself.

    :param str name: The thumbprint of the certificate.
    :param str site: The IIS site name.
    :param str hostheader: The host header of the binding.
    :param str ipaddress: The IP address of the binding.
    :param str port: The TCP port of the binding.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-cert-binding-remove:
            win_iis.remove_cert_binding:
                - name: 9988776655443322111000AAABBBCCCDDDEEEFFF
                - site: site0

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-cert-binding-remove:
            win_iis.remove_cert_binding:
                - name: 9988776655443322111000AAABBBCCCDDDEEEFFF
                - site: site0
                - hostheader: site0.local
                - ipaddress: 192.168.1.199
                - port: 443

    .. versionadded:: 2016.11.0
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    binding_info = _get_binding_info(hostheader, ipaddress, port)
    current_cert_bindings = __salt__["win_iis.list_cert_bindings"](site)

    if binding_info not in current_cert_bindings:
        ret["comment"] = f"Certificate binding has already been removed: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Certificate binding will be removed: {name}"
        ret["changes"] = {"old": name, "new": None}
    else:
        current_name = current_cert_bindings[binding_info]["certificatehash"]

        if name == current_name:
            ret["comment"] = f"Removed certificate binding: {name}"
            ret["changes"] = {"old": name, "new": None}
            ret["result"] = __salt__["win_iis.remove_cert_binding"](
                name, site, hostheader, ipaddress, port
            )
    return ret


def create_apppool(name):
    """
    Create an IIS application pool.

    .. note:

        This function only validates against the application pool name, and will return
        True even if the application pool already exists with a different configuration.
        It will not modify the configuration of an existing application pool.

    :param str name: The name of the IIS application pool.

    Usage:

    .. code-block:: yaml

        site0-apppool:
            win_iis.create_apppool:
                - name: site0
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    current_apppools = __salt__["win_iis.list_apppools"]()

    if name in current_apppools:
        ret["comment"] = f"Application pool already present: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Application pool will be created: {name}"
        ret["changes"] = {"old": None, "new": name}
    else:
        ret["comment"] = f"Created application pool: {name}"
        ret["changes"] = {"old": None, "new": name}
        ret["result"] = __salt__["win_iis.create_apppool"](name)
    return ret


def remove_apppool(name):
    # Remove IIS AppPool
    """
    Remove an IIS application pool.

    :param str name: The name of the IIS application pool.

    Usage:

    .. code-block:: yaml

        defaultapppool-remove:
            win_iis.remove_apppool:
                - name: DefaultAppPool
    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    current_apppools = __salt__["win_iis.list_apppools"]()

    if name not in current_apppools:
        ret["comment"] = f"Application pool has already been removed: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Application pool will be removed: {name}"
        ret["changes"] = {"old": name, "new": None}
    else:
        ret["comment"] = f"Removed application pool: {name}"
        ret["changes"] = {"old": name, "new": None}
        ret["result"] = __salt__["win_iis.remove_apppool"](name)
    return ret


def container_setting(name, container, settings=None):
    """
    Set the value of the setting for an IIS container.

    :param str name: The name of the IIS container.
    :param str container: The type of IIS container. The container types are:
        AppPools, Sites, SslBindings
    :param str settings: A dictionary of the setting names and their values.
        Example of usage for the ``AppPools`` container:

    .. code-block:: yaml

        site0-apppool-setting:
            win_iis.container_setting:
                - name: site0
                - container: AppPools
                - settings:
                    managedPipelineMode: Integrated
                    processModel.maxProcesses: 1
                    processModel.userName: TestUser
                    processModel.password: TestPassword
                    processModel.identityType: SpecificUser

    Example of usage for the ``Sites`` container:

    .. code-block:: yaml

        site0-site-setting:
            win_iis.container_setting:
                - name: site0
                - container: Sites
                - settings:
                    logFile.logFormat: W3C
                    logFile.period: Daily
                    limits.maxUrlSegments: 32
    """

    identityType_map2string = {
        0: "LocalSystem",
        1: "LocalService",
        2: "NetworkService",
        3: "SpecificUser",
        4: "ApplicationPoolIdentity",
    }
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    if not settings:
        ret["comment"] = "No settings to change provided."
        ret["result"] = True
        return ret

    ret_settings = {
        "changes": {},
        "failures": {},
    }

    current_settings = __salt__["win_iis.get_container_setting"](
        name=name, container=container, settings=settings.keys()
    )
    for setting in settings:
        # map identity type from numeric to string for comparing
        if (
            setting == "processModel.identityType"
            and settings[setting] in identityType_map2string
        ):
            settings[setting] = identityType_map2string[settings[setting]]

        if str(settings[setting]) != str(current_settings[setting]):
            if setting == "processModel.password":
                ret_settings["changes"][setting] = {
                    "old": "XXX-REDACTED-XXX",
                    "new": "XXX-REDACTED-XXX",
                }
            else:
                ret_settings["changes"][setting] = {
                    "old": current_settings[setting],
                    "new": settings[setting],
                }
    if not ret_settings["changes"]:
        ret["comment"] = "Settings already contain the provided values."
        ret["result"] = True
        return ret
    elif __opts__["test"]:
        ret["comment"] = "Settings will be changed."
        ret["changes"] = ret_settings["changes"]
        return ret

    __salt__["win_iis.set_container_setting"](
        name=name, container=container, settings=settings
    )

    new_settings = __salt__["win_iis.get_container_setting"](
        name=name, container=container, settings=settings.keys()
    )
    for setting in settings:
        if str(settings[setting]) != str(new_settings[setting]):
            if setting == "processModel.password":
                ret_settings["failures"][setting] = {
                    "old": "XXX-REDACTED-XXX",
                    "new": "XXX-REDACTED-XXX",
                }
            else:
                ret_settings["failures"][setting] = {
                    "old": current_settings[setting],
                    "new": new_settings[setting],
                }
            ret_settings["changes"].pop(setting, None)
        else:
            if setting == "processModel.password":
                ret_settings["changes"][setting] = {
                    "old": "XXX-REDACTED-XXX",
                    "new": "XXX-REDACTED-XXX",
                }

    if ret_settings["failures"]:
        ret["comment"] = "Some settings failed to change."
        ret["changes"] = ret_settings
        ret["result"] = False
    else:
        ret["comment"] = "Set settings to contain the provided values."
        ret["changes"] = ret_settings["changes"]
        ret["result"] = True

    return ret


def create_app(name, site, sourcepath, apppool=None):
    """
    Create an IIS application.

    .. note:

        This function only validates against the application name, and will return True
        even if the application already exists with a different configuration. It will not
        modify the configuration of an existing application.

    :param str name: The IIS application.
    :param str site: The IIS site name.
    :param str sourcepath: The physical path.
    :param str apppool: The name of the IIS application pool.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-v1-app:
            win_iis.create_app:
                - name: v1
                - site: site0
                - sourcepath: C:\\inetpub\\site0\\v1

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-v1-app:
            win_iis.create_app:
                - name: v1
                - site: site0
                - sourcepath: C:\\inetpub\\site0\\v1
                - apppool: site0
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    current_apps = __salt__["win_iis.list_apps"](site)

    if name in current_apps:
        ret["comment"] = f"Application already present: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Application will be created: {name}"
        ret["changes"] = {"old": None, "new": name}
    else:
        ret["comment"] = f"Created application: {name}"
        ret["changes"] = {"old": None, "new": name}
        ret["result"] = __salt__["win_iis.create_app"](name, site, sourcepath, apppool)
    return ret


def remove_app(name, site):
    """
    Remove an IIS application.

    :param str name: The application name.
    :param str site: The IIS site name.

    Usage:

    .. code-block:: yaml

        site0-v1-app-remove:
            win_iis.remove_app:
                - name: v1
                - site: site0
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    current_apps = __salt__["win_iis.list_apps"](site)

    if name not in current_apps:
        ret["comment"] = f"Application has already been removed: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Application will be removed: {name}"
        ret["changes"] = {"old": name, "new": None}
    else:
        ret["comment"] = f"Removed application: {name}"
        ret["changes"] = {"old": name, "new": None}
        ret["result"] = __salt__["win_iis.remove_app"](name, site)
    return ret


def create_vdir(name, site, sourcepath, app="/"):
    """
    Create an IIS virtual directory.

    .. note:

        This function only validates against the virtual directory name, and will return
        True even if the virtual directory already exists with a different configuration.
        It will not modify the configuration of an existing virtual directory.

    :param str name: The virtual directory name.
    :param str site: The IIS site name.
    :param str sourcepath: The physical path.
    :param str app: The IIS application.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-foo-vdir:
            win_iis.create_vdir:
                - name: foo
                - site: site0
                - sourcepath: C:\\inetpub\\vdirs\\foo

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-foo-vdir:
            win_iis.create_vdir:
                - name: foo
                - site: site0
                - sourcepath: C:\\inetpub\\vdirs\\foo
                - app: v1
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    current_vdirs = __salt__["win_iis.list_vdirs"](site, app)

    if name in current_vdirs:
        ret["comment"] = f"Virtual directory already present: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Virtual directory will be created: {name}"
        ret["changes"] = {"old": None, "new": name}
    else:
        ret["comment"] = f"Created virtual directory: {name}"
        ret["changes"] = {"old": None, "new": name}
        ret["result"] = __salt__["win_iis.create_vdir"](name, site, sourcepath, app)

    return ret


def remove_vdir(name, site, app="/"):
    """
    Remove an IIS virtual directory.

    :param str name: The virtual directory name.
    :param str site: The IIS site name.
    :param str app: The IIS application.

    Example of usage with only the required arguments:

    .. code-block:: yaml

        site0-foo-vdir-remove:
            win_iis.remove_vdir:
                - name: foo
                - site: site0

    Example of usage specifying all available arguments:

    .. code-block:: yaml

        site0-foo-vdir-remove:
            win_iis.remove_vdir:
                - name: foo
                - site: site0
                - app: v1
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    current_vdirs = __salt__["win_iis.list_vdirs"](site, app)

    if name not in current_vdirs:
        ret["comment"] = f"Virtual directory has already been removed: {name}"
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = f"Virtual directory will be removed: {name}"
        ret["changes"] = {"old": name, "new": None}
    else:
        ret["comment"] = f"Removed virtual directory: {name}"
        ret["changes"] = {"old": name, "new": None}
        ret["result"] = __salt__["win_iis.remove_vdir"](name, site, app)

    return ret


def set_app(name, site, settings=None):
    # pylint: disable=anomalous-backslash-in-string
    r"""
    .. versionadded:: 2017.7.0

    Set the value of the setting for an IIS web application.

    .. note::
        This function only configures existing app. Params are case sensitive.

    :param str name: The IIS application.
    :param str site: The IIS site name.
    :param str settings: A dictionary of the setting names and their values.

    Available settings:

    - ``physicalPath`` - The physical path of the webapp
    - ``applicationPool`` - The application pool for the webapp
    - ``userName`` "connectAs" user
    - ``password`` "connectAs" password for user

    :rtype: bool

    Example of usage:

    .. code-block:: yaml

        site0-webapp-setting:
            win_iis.set_app:
                - name: app0
                - site: Default Web Site
                - settings:
                    userName: domain\\user
                    password: pass
                    physicalPath: c:\inetpub\wwwroot
                    applicationPool: appPool0
    """
    # pylint: enable=anomalous-backslash-in-string
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    if not settings:
        ret["comment"] = "No settings to change provided."
        ret["result"] = True
        return ret

    ret_settings = {
        "changes": {},
        "failures": {},
    }

    current_settings = __salt__["win_iis.get_webapp_settings"](
        name=name, site=site, settings=settings.keys()
    )
    for setting in settings:
        if str(settings[setting]) != str(current_settings[setting]):
            ret_settings["changes"][setting] = {
                "old": current_settings[setting],
                "new": settings[setting],
            }
    if not ret_settings["changes"]:
        ret["comment"] = "Settings already contain the provided values."
        ret["result"] = True
        return ret
    elif __opts__["test"]:
        ret["comment"] = "Settings will be changed."
        ret["changes"] = ret_settings
        return ret

    __salt__["win_iis.set_webapp_settings"](name=name, site=site, settings=settings)
    new_settings = __salt__["win_iis.get_webapp_settings"](
        name=name, site=site, settings=settings.keys()
    )

    for setting in settings:
        if str(settings[setting]) != str(new_settings[setting]):
            ret_settings["failures"][setting] = {
                "old": current_settings[setting],
                "new": new_settings[setting],
            }
            ret_settings["changes"].pop(setting, None)

    if ret_settings["failures"]:
        ret["comment"] = "Some settings failed to change."
        ret["changes"] = ret_settings
        ret["result"] = False
    else:
        ret["comment"] = "Set settings to contain the provided values."
        ret["changes"] = ret_settings["changes"]
        ret["result"] = True

    return ret


def webconfiguration_settings(name, settings=None):
    r"""
    Set the value of webconfiguration settings.

    :param str name: The name of the IIS PSPath containing the settings.
        Possible PSPaths are :
        MACHINE, MACHINE/WEBROOT, IIS:\, IIS:\Sites\sitename, ...
    :param dict settings: Dictionaries of dictionaries.
        You can match a specific item in a collection with this syntax inside a key:
        'Collection[{name: site0}].logFile.directory'

    Example of usage for the ``MACHINE/WEBROOT`` PSPath:

    .. code-block:: yaml

        MACHINE-WEBROOT-level-security:
          win_iis.webconfiguration_settings:
            - name: 'MACHINE/WEBROOT'
            - settings:
                system.web/authentication/forms:
                  requireSSL: True
                  protection: "All"
                  credentials.passwordFormat: "SHA1"
                system.web/httpCookies:
                  httpOnlyCookies: True

    Example of usage for the ``IIS:\Sites\site0`` PSPath:

    .. code-block:: yaml

        site0-IIS-Sites-level-security:
          win_iis.webconfiguration_settings:
            - name: 'IIS:\Sites\site0'
            - settings:
                system.webServer/httpErrors:
                  errorMode: "DetailedLocalOnly"
                system.webServer/security/requestFiltering:
                  allowDoubleEscaping: False
                  verbs.Collection:
                    - verb: TRACE
                      allowed: False
                  fileExtensions.allowUnlisted: False

    Example of usage for the ``IIS:\`` PSPath with a collection matching:

    .. code-block:: yaml

        site0-IIS-level-security:
          win_iis.webconfiguration_settings:
            - name: 'IIS:\'
            - settings:
                system.applicationHost/sites:
                  'Collection[{name: site0}].logFile.directory': 'C:\logs\iis\site0'

    """

    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    if not settings:
        ret["comment"] = "No settings to change provided."
        ret["result"] = True
        return ret

    ret_settings = {
        "changes": {},
        "failures": {},
    }

    settings_list = list()

    for filter, filter_settings in settings.items():
        for setting_name, value in filter_settings.items():
            settings_list.append(
                {"filter": filter, "name": setting_name, "value": value}
            )

    current_settings_list = __salt__["win_iis.get_webconfiguration_settings"](
        name=name, settings=settings_list
    )
    for idx, setting in enumerate(settings_list):

        is_collection = setting["name"].split(".")[-1] == "Collection"
        # If this is a new setting and not an update to an existing setting
        if len(current_settings_list) <= idx:
            ret_settings["changes"][setting["filter"] + "." + setting["name"]] = {
                "old": {},
                "new": settings_list[idx]["value"],
            }
        elif (
            is_collection
            and list(map(dict, setting["value"]))
            != list(map(dict, current_settings_list[idx]["value"]))
        ) or (
            not is_collection
            and str(setting["value"]) != str(current_settings_list[idx]["value"])
        ):
            ret_settings["changes"][setting["filter"] + "." + setting["name"]] = {
                "old": current_settings_list[idx]["value"],
                "new": settings_list[idx]["value"],
            }
    if not ret_settings["changes"]:
        ret["comment"] = "Settings already contain the provided values."
        ret["result"] = True
        return ret
    elif __opts__["test"]:
        ret["comment"] = "Settings will be changed."
        ret["changes"] = ret_settings
        return ret

    success = __salt__["win_iis.set_webconfiguration_settings"](
        name=name, settings=settings_list
    )

    new_settings_list = __salt__["win_iis.get_webconfiguration_settings"](
        name=name, settings=settings_list
    )
    for idx, setting in enumerate(settings_list):

        is_collection = setting["name"].split(".")[-1] == "Collection"
        if (is_collection and setting["value"] != new_settings_list[idx]["value"]) or (
            not is_collection
            and str(setting["value"]) != str(new_settings_list[idx]["value"])
        ):
            ret_settings["failures"][setting["filter"] + "." + setting["name"]] = {
                "old": current_settings_list[idx]["value"],
                "new": new_settings_list[idx]["value"],
            }
            ret_settings["changes"].get(setting["filter"] + "." + setting["name"], None)

    if ret_settings["failures"]:
        ret["comment"] = "Some settings failed to change."
        ret["changes"] = ret_settings
        ret["result"] = False
    else:
        ret["comment"] = "Set settings to contain the provided values."
        ret["changes"] = ret_settings["changes"]
        ret["result"] = success

    return ret
