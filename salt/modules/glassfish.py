"""
Module for working with the Glassfish/Payara 4.x management API
.. versionadded:: 2016.11.0
:depends: requests
"""

import urllib.parse

import salt.defaults.exitcodes
import salt.utils.json
from salt.exceptions import CommandExecutionError

try:
    import requests

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

__virtualname__ = "glassfish"

# Default server
DEFAULT_SERVER = {
    "ssl": False,
    "url": "localhost",
    "port": 4848,
    "user": None,
    "password": None,
}


def __virtual__():
    """
    Only load if requests is installed
    """
    if HAS_LIBS:
        return __virtualname__
    else:
        return (
            False,
            'The "{}" module could not be loaded: "requests" is not installed.'.format(
                __virtualname__
            ),
        )


def _get_headers():
    """
    Return fixed dict with headers (JSON data + mandatory "Requested by" header)
    """
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-By": "GlassFish REST HTML interface",
    }


def _get_auth(username, password):
    """
    Returns the HTTP auth header
    """
    if username and password:
        return requests.auth.HTTPBasicAuth(username, password)
    else:
        return None


def _get_url(ssl, url, port, path):
    """
    Returns the URL of the endpoint
    """
    if ssl:
        return f"https://{url}:{port}/management/domain/{path}"
    else:
        return f"http://{url}:{port}/management/domain/{path}"


def _get_server(server):
    """
    Returns the server information if provided, or the defaults
    """
    return server if server else DEFAULT_SERVER


def _clean_data(data):
    """
    Removes SaltStack params from **kwargs
    """
    for key in list(data):
        if key.startswith("__pub"):
            del data[key]
    return data


def _api_response(response):
    """
    Check response status code + success_code returned by glassfish
    """
    if response.status_code == 404:
        __context__["retcode"] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        raise CommandExecutionError("Element doesn't exists")
    if response.status_code == 401:
        __context__["retcode"] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        raise CommandExecutionError("Bad username or password")
    elif response.status_code == 200 or response.status_code == 500:
        try:
            data = salt.utils.json.loads(response.content)
            if data["exit_code"] != "SUCCESS":
                __context__["retcode"] = salt.defaults.exitcodes.SALT_BUILD_FAIL
                raise CommandExecutionError(data["message"])
            return data
        except ValueError:
            __context__["retcode"] = salt.defaults.exitcodes.SALT_BUILD_FAIL
            raise CommandExecutionError("The server returned no data")
    else:
        response.raise_for_status()


def _api_get(path, server=None):
    """
    Do a GET request to the API
    """
    server = _get_server(server)
    response = requests.get(
        url=_get_url(server["ssl"], server["url"], server["port"], path),
        auth=_get_auth(server["user"], server["password"]),
        headers=_get_headers(),
        verify=True,
        timeout=120,
    )
    return _api_response(response)


def _api_post(path, data, server=None):
    """
    Do a POST request to the API
    """
    server = _get_server(server)
    response = requests.post(
        url=_get_url(server["ssl"], server["url"], server["port"], path),
        auth=_get_auth(server["user"], server["password"]),
        headers=_get_headers(),
        data=salt.utils.json.dumps(data),
        verify=True,
        timeout=120,
    )
    return _api_response(response)


def _api_delete(path, data, server=None):
    """
    Do a DELETE request to the API
    """
    server = _get_server(server)
    response = requests.delete(
        url=_get_url(server["ssl"], server["url"], server["port"], path),
        auth=_get_auth(server["user"], server["password"]),
        headers=_get_headers(),
        params=data,
        verify=True,
        timeout=120,
    )
    return _api_response(response)


# "Middle layer": uses _api_* functions to enum/get/create/update/delete elements
def _enum_elements(name, server=None):
    """
    Enum elements
    """
    elements = []
    data = _api_get(name, server)

    if any(data["extraProperties"]["childResources"]):
        for element in data["extraProperties"]["childResources"]:
            elements.append(element)
        return elements
    return None


def _get_element_properties(name, element_type, server=None):
    """
    Get an element's properties
    """
    properties = {}
    data = _api_get(f"{element_type}/{name}/property", server)

    # Get properties into a dict
    if any(data["extraProperties"]["properties"]):
        for element in data["extraProperties"]["properties"]:
            properties[element["name"]] = element["value"]
        return properties
    return {}


def _get_element(name, element_type, server=None, with_properties=True):
    """
    Get an element with or without properties
    """
    element = {}
    name = urllib.parse.quote(name, safe="")
    data = _api_get(f"{element_type}/{name}", server)

    # Format data, get properties if asked, and return the whole thing
    if any(data["extraProperties"]["entity"]):
        for key, value in data["extraProperties"]["entity"].items():
            element[key] = value
        if with_properties:
            element["properties"] = _get_element_properties(name, element_type)
        return element
    return None


def _create_element(name, element_type, data, server=None):
    """
    Create a new element
    """
    # Define property and id from name and properties + remove SaltStack parameters
    if "properties" in data:
        data["property"] = ""
        for key, value in data["properties"].items():
            if not data["property"]:
                data["property"] += "{}={}".format(key, value.replace(":", "\\:"))
            else:
                data["property"] += ":{}={}".format(key, value.replace(":", "\\:"))
        del data["properties"]

    # Send request
    _api_post(element_type, _clean_data(data), server)
    return urllib.parse.unquote(name)


def _update_element(name, element_type, data, server=None):
    """
    Update an element, including its properties
    """
    # Urlencode the name (names may have slashes)
    name = urllib.parse.quote(name, safe="")

    # Update properties first
    if "properties" in data:
        properties = []
        for key, value in data["properties"].items():
            properties.append({"name": key, "value": value})
        _api_post(f"{element_type}/{name}/property", properties, server)
        del data["properties"]

        # If the element only contained properties
        if not data:
            return urllib.parse.unquote(name)

    # Get the current data then merge updated data into it
    update_data = _get_element(name, element_type, server, with_properties=False)
    if update_data:
        update_data.update(data)
    else:
        __context__["retcode"] = salt.defaults.exitcodes.SALT_BUILD_FAIL
        raise CommandExecutionError(f"Cannot update {name}")

    # Finally, update the element
    _api_post(f"{element_type}/{name}", _clean_data(update_data), server)
    return urllib.parse.unquote(name)


def _delete_element(name, element_type, data, server=None):
    """
    Delete an element
    """
    _api_delete(
        "{}/{}".format(element_type, urllib.parse.quote(name, safe="")), data, server
    )
    return name


# Connector connection pools
def enum_connector_c_pool(server=None):
    """
    Enum connection pools
    """
    return _enum_elements("resources/connector-connection-pool", server)


def get_connector_c_pool(name, server=None):
    """
    Get a specific connection pool
    """
    return _get_element(name, "resources/connector-connection-pool", server)


def create_connector_c_pool(name, server=None, **kwargs):
    """
    Create a connection pool
    """
    defaults = {
        "connectionDefinitionName": "javax.jms.ConnectionFactory",
        "resourceAdapterName": "jmsra",
        "associateWithThread": False,
        "connectionCreationRetryAttempts": 0,
        "connectionCreationRetryIntervalInSeconds": 0,
        "connectionLeakReclaim": False,
        "connectionLeakTimeoutInSeconds": 0,
        "description": "",
        "failAllConnections": False,
        "id": name,
        "idleTimeoutInSeconds": 300,
        "isConnectionValidationRequired": False,
        "lazyConnectionAssociation": False,
        "lazyConnectionEnlistment": False,
        "matchConnections": True,
        "maxConnectionUsageCount": 0,
        "maxPoolSize": 32,
        "maxWaitTimeInMillis": 60000,
        "ping": False,
        "poolResizeQuantity": 2,
        "pooling": True,
        "steadyPoolSize": 8,
        "target": "server",
        "transactionSupport": "",
        "validateAtmostOncePeriodInSeconds": 0,
    }

    # Data = defaults + merge kwargs + remove salt
    data = defaults
    data.update(kwargs)

    # Check TransactionSupport against acceptable values
    if data["transactionSupport"] and data["transactionSupport"] not in (
        "XATransaction",
        "LocalTransaction",
        "NoTransaction",
    ):
        raise CommandExecutionError("Invalid transaction support")

    return _create_element(name, "resources/connector-connection-pool", data, server)


def update_connector_c_pool(name, server=None, **kwargs):
    """
    Update a connection pool
    """
    if "transactionSupport" in kwargs and kwargs["transactionSupport"] not in (
        "XATransaction",
        "LocalTransaction",
        "NoTransaction",
    ):
        raise CommandExecutionError("Invalid transaction support")
    return _update_element(name, "resources/connector-connection-pool", kwargs, server)


def delete_connector_c_pool(name, target="server", cascade=True, server=None):
    """
    Delete a connection pool
    """
    data = {"target": target, "cascade": cascade}
    return _delete_element(name, "resources/connector-connection-pool", data, server)


# Connector resources
def enum_connector_resource(server=None):
    """
    Enum connection resources
    """
    return _enum_elements("resources/connector-resource", server)


def get_connector_resource(name, server=None):
    """
    Get a specific connection resource
    """
    return _get_element(name, "resources/connector-resource", server)


def create_connector_resource(name, server=None, **kwargs):
    """
    Create a connection resource
    """
    defaults = {
        "description": "",
        "enabled": True,
        "id": name,
        "poolName": "",
        "objectType": "user",
        "target": "server",
    }

    # Data = defaults + merge kwargs + poolname
    data = defaults
    data.update(kwargs)

    if not data["poolName"]:
        raise CommandExecutionError("No pool name!")

    # Fix for lowercase vs camelCase naming differences
    for key, value in list(data.items()):
        del data[key]
        data[key.lower()] = value

    return _create_element(name, "resources/connector-resource", data, server)


def update_connector_resource(name, server=None, **kwargs):
    """
    Update a connection resource
    """
    # You're not supposed to update jndiName, if you do so, it will crash, silently
    if "jndiName" in kwargs:
        del kwargs["jndiName"]
    return _update_element(name, "resources/connector-resource", kwargs, server)


def delete_connector_resource(name, target="server", server=None):
    """
    Delete a connection resource
    """
    return _delete_element(
        name, "resources/connector-resource", {"target": target}, server
    )


# JMS Destinations
def enum_admin_object_resource(server=None):
    """
    Enum JMS destinations
    """
    return _enum_elements("resources/admin-object-resource", server)


def get_admin_object_resource(name, server=None):
    """
    Get a specific JMS destination
    """
    return _get_element(name, "resources/admin-object-resource", server)


def create_admin_object_resource(name, server=None, **kwargs):
    """
    Create a JMS destination
    """
    defaults = {
        "description": "",
        "className": "com.sun.messaging.Queue",
        "enabled": True,
        "id": name,
        "resAdapter": "jmsra",
        "resType": "javax.jms.Queue",
        "target": "server",
    }

    # Data = defaults + merge kwargs + poolname
    data = defaults
    data.update(kwargs)

    # ClassName isn't optional, even if the API says so
    if data["resType"] == "javax.jms.Queue":
        data["className"] = "com.sun.messaging.Queue"
    elif data["resType"] == "javax.jms.Topic":
        data["className"] = "com.sun.messaging.Topic"
    else:
        raise CommandExecutionError(
            'resType should be "javax.jms.Queue" or "javax.jms.Topic"!'
        )

    if data["resAdapter"] != "jmsra":
        raise CommandExecutionError('resAdapter should be "jmsra"!')

    # Fix for lowercase vs camelCase naming differences
    if "resType" in data:
        data["restype"] = data["resType"]
        del data["resType"]
    if "className" in data:
        data["classname"] = data["className"]
        del data["className"]

    return _create_element(name, "resources/admin-object-resource", data, server)


def update_admin_object_resource(name, server=None, **kwargs):
    """
    Update a JMS destination
    """
    if "jndiName" in kwargs:
        del kwargs["jndiName"]
    return _update_element(name, "resources/admin-object-resource", kwargs, server)


def delete_admin_object_resource(name, target="server", server=None):
    """
    Delete a JMS destination
    """
    return _delete_element(
        name, "resources/admin-object-resource", {"target": target}, server
    )


# JDBC Pools
def enum_jdbc_connection_pool(server=None):
    """
    Enum JDBC pools
    """
    return _enum_elements("resources/jdbc-connection-pool", server)


def get_jdbc_connection_pool(name, server=None):
    """
    Get a specific JDBC pool
    """
    return _get_element(name, "resources/jdbc-connection-pool", server)


def create_jdbc_connection_pool(name, server=None, **kwargs):
    """
    Create a connection resource
    """
    defaults = {
        "allowNonComponentCallers": False,
        "associateWithThread": False,
        "connectionCreationRetryAttempts": "0",
        "connectionCreationRetryIntervalInSeconds": "10",
        "connectionLeakReclaim": False,
        "connectionLeakTimeoutInSeconds": "0",
        "connectionValidationMethod": "table",
        "datasourceClassname": "",
        "description": "",
        "driverClassname": "",
        "failAllConnections": False,
        "idleTimeoutInSeconds": "300",
        "initSql": "",
        "isConnectionValidationRequired": False,
        "isIsolationLevelGuaranteed": True,
        "lazyConnectionAssociation": False,
        "lazyConnectionEnlistment": False,
        "matchConnections": False,
        "maxConnectionUsageCount": "0",
        "maxPoolSize": "32",
        "maxWaitTimeInMillis": 60000,
        "name": name,
        "nonTransactionalConnections": False,
        "ping": False,
        "poolResizeQuantity": "2",
        "pooling": True,
        "resType": "",
        "sqlTraceListeners": "",
        "statementCacheSize": "0",
        "statementLeakReclaim": False,
        "statementLeakTimeoutInSeconds": "0",
        "statementTimeoutInSeconds": "-1",
        "steadyPoolSize": "8",
        "target": "server",
        "transactionIsolationLevel": "",
        "validateAtmostOncePeriodInSeconds": "0",
        "validationClassname": "",
        "validationTableName": "",
        "wrapJdbcObjects": True,
    }

    # Data = defaults + merge kwargs + poolname
    data = defaults
    data.update(kwargs)

    # Check resType against acceptable values
    if data["resType"] not in (
        "javax.sql.DataSource",
        "javax.sql.XADataSource",
        "javax.sql.ConnectionPoolDataSource",
        "java.sql.Driver",
    ):
        raise CommandExecutionError("Invalid resource type")

    # Check connectionValidationMethod against acceptable velues
    if data["connectionValidationMethod"] not in (
        "auto-commit",
        "meta-data",
        "table",
        "custom-validation",
    ):
        raise CommandExecutionError("Invalid connection validation method")

    if data["transactionIsolationLevel"] and data["transactionIsolationLevel"] not in (
        "read-uncommitted",
        "read-committed",
        "repeatable-read",
        "serializable",
    ):
        raise CommandExecutionError("Invalid transaction isolation level")

    if not data["datasourceClassname"] and data["resType"] in (
        "javax.sql.DataSource",
        "javax.sql.ConnectionPoolDataSource",
        "javax.sql.XADataSource",
    ):
        raise CommandExecutionError(
            "No datasource class name while using datasource resType"
        )
    if not data["driverClassname"] and data["resType"] == "java.sql.Driver":
        raise CommandExecutionError("No driver class nime while using driver resType")

    return _create_element(name, "resources/jdbc-connection-pool", data, server)


def update_jdbc_connection_pool(name, server=None, **kwargs):
    """
    Update a JDBC pool
    """
    return _update_element(name, "resources/jdbc-connection-pool", kwargs, server)


def delete_jdbc_connection_pool(name, target="server", cascade=False, server=None):
    """
    Delete a JDBC pool
    """
    data = {"target": target, "cascade": cascade}
    return _delete_element(name, "resources/jdbc-connection-pool", data, server)


# JDBC resources
def enum_jdbc_resource(server=None):
    """
    Enum JDBC resources
    """
    return _enum_elements("resources/jdbc-resource", server)


def get_jdbc_resource(name, server=None):
    """
    Get a specific JDBC resource
    """
    return _get_element(name, "resources/jdbc-resource", server)


def create_jdbc_resource(name, server=None, **kwargs):
    """
    Create a JDBC resource
    """
    defaults = {
        "description": "",
        "enabled": True,
        "id": name,
        "poolName": "",
        "target": "server",
    }

    # Data = defaults + merge kwargs + poolname
    data = defaults
    data.update(kwargs)

    if not data["poolName"]:
        raise CommandExecutionError("No pool name!")

    return _create_element(name, "resources/jdbc-resource", data, server)


def update_jdbc_resource(name, server=None, **kwargs):
    """
    Update a JDBC resource
    """
    # You're not supposed to update jndiName, if you do so, it will crash, silently
    if "jndiName" in kwargs:
        del kwargs["jndiName"]
    return _update_element(name, "resources/jdbc-resource", kwargs, server)


def delete_jdbc_resource(name, target="server", server=None):
    """
    Delete a JDBC resource
    """
    return _delete_element(name, "resources/jdbc-resource", {"target": target}, server)


# System properties
def get_system_properties(server=None):
    """
    Get system properties
    """
    properties = {}
    data = _api_get("system-properties", server)

    # Get properties into a dict
    if any(data["extraProperties"]["systemProperties"]):
        for element in data["extraProperties"]["systemProperties"]:
            properties[element["name"]] = element["value"]
        return properties
    return {}


def update_system_properties(data, server=None):
    """
    Update system properties
    """
    _api_post("system-properties", _clean_data(data), server)
    return data


def delete_system_properties(name, server=None):
    """
    Delete a system property
    """
    _api_delete(f"system-properties/{name}", None, server)
