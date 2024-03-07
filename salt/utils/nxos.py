# Copyright (c) 2018 Cisco and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Util functions for the NXOS modules.
"""

import collections
import http.client
import json
import logging
import os
import re
import socket
from collections.abc import Iterable

import salt.utils.http
from salt.exceptions import (
    CommandExecutionError,
    NxosClientError,
    NxosError,
    NxosRequestNotSupported,
)
from salt.utils.args import clean_kwargs

log = logging.getLogger(__name__)


class UHTTPConnection(http.client.HTTPConnection):
    """
    Subclass of Python library HTTPConnection that uses a unix-domain socket.
    """

    def __init__(self, path):
        http.client.HTTPConnection.__init__(self, "localhost")
        self.path = path

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.path)
        self.sock = sock


class NxapiClient:
    """
    Class representing an NX-API client that connects over http(s) or
    unix domain socket (UDS).
    """

    # Location of unix domain socket for NX-API localhost
    NXAPI_UDS = "/tmp/nginx_local/nginx_1_be_nxapi.sock"
    # NXAPI listens for remote connections to "http(s)://<switch IP>/ins"
    # NXAPI listens for local connections to "http(s)://<UDS>/ins_local"
    NXAPI_REMOTE_URI_PATH = "/ins"
    NXAPI_UDS_URI_PATH = "/ins_local"
    NXAPI_VERSION = "1.0"

    def __init__(self, **nxos_kwargs):
        """
        Initialize NxapiClient() connection object.  By default this connects
        to the local unix domain socket (UDS).  If http(s) is required to
        connect to a remote device then
            nxos_kwargs['host'],
            nxos_kwargs['username'],
            nxos_kwargs['password'],
            nxos_kwargs['transport'],
            nxos_kwargs['port'],
        parameters must be provided.
        """
        self.nxargs = self._prepare_conn_args(clean_kwargs(**nxos_kwargs))
        # Default: Connect to unix domain socket on localhost.
        if self.nxargs["connect_over_uds"]:
            if not os.path.exists(self.NXAPI_UDS):
                raise NxosClientError(
                    f"No host specified and no UDS found at {self.NXAPI_UDS}\n"
                )

            # Create UHTTPConnection object for NX-API communication over UDS.
            log.info("Nxapi connection arguments: %s", self.nxargs)
            log.info("Connecting over unix domain socket")
            self.connection = UHTTPConnection(self.NXAPI_UDS)
        else:
            # Remote connection - Proxy Minion, connect over http(s)
            log.info("Nxapi connection arguments: %s", self.nxargs)
            log.info("Connecting over %s", self.nxargs["transport"])
            self.connection = salt.utils.http.query

    def _use_remote_connection(self, kwargs):
        """
        Determine if connection is local or remote
        """
        kwargs["host"] = kwargs.get("host")
        kwargs["username"] = kwargs.get("username")
        kwargs["password"] = kwargs.get("password")
        if (
            kwargs["host"] is None
            or kwargs["username"] is None
            or kwargs["password"] is None
        ):
            return False
        else:
            return True

    def _prepare_conn_args(self, kwargs):
        """
        Set connection arguments for remote or local connection.
        """
        kwargs["connect_over_uds"] = True
        kwargs["timeout"] = kwargs.get("timeout", 60)
        kwargs["cookie"] = kwargs.get("cookie", "admin")
        if self._use_remote_connection(kwargs):
            kwargs["transport"] = kwargs.get("transport", "https")
            if kwargs["transport"] == "https":
                kwargs["port"] = kwargs.get("port", 443)
            else:
                kwargs["port"] = kwargs.get("port", 80)
            kwargs["verify"] = kwargs.get("verify", True)
            if isinstance(kwargs["verify"], bool):
                kwargs["verify_ssl"] = kwargs["verify"]
            else:
                kwargs["ca_bundle"] = kwargs["verify"]
            kwargs["connect_over_uds"] = False
        return kwargs

    def _build_request(self, type, commands):
        """
        Build NX-API JSON request.
        """
        request = {}
        headers = {
            "content-type": "application/json",
        }
        if self.nxargs["connect_over_uds"]:
            user = self.nxargs["cookie"]
            headers["cookie"] = "nxapi_auth=" + user + ":local"
            request["url"] = self.NXAPI_UDS_URI_PATH
        else:
            request["url"] = "{transport}://{host}:{port}{uri}".format(
                transport=self.nxargs["transport"],
                host=self.nxargs["host"],
                port=self.nxargs["port"],
                uri=self.NXAPI_REMOTE_URI_PATH,
            )

        if isinstance(commands, (list, set, tuple)):
            commands = " ; ".join(commands)
        payload = {}
        # Some versions of NX-OS fail to process the payload properly if
        # 'input' gets serialized before 'type' and the payload of 'input'
        # contains the string 'type'.  Use an ordered dict to enforce ordering.
        payload["ins_api"] = collections.OrderedDict()
        payload["ins_api"]["version"] = self.NXAPI_VERSION
        payload["ins_api"]["type"] = type
        payload["ins_api"]["chunk"] = "0"
        payload["ins_api"]["sid"] = "1"
        payload["ins_api"]["input"] = commands
        payload["ins_api"]["output_format"] = "json"

        request["headers"] = headers
        request["payload"] = json.dumps(payload)
        request["opts"] = {"http_request_timeout": self.nxargs["timeout"]}
        log.info("request: %s", request)
        return request

    def request(self, type, command_list):
        """
        Send NX-API JSON request to the NX-OS device.
        """
        req = self._build_request(type, command_list)
        if self.nxargs["connect_over_uds"]:
            self.connection.request("POST", req["url"], req["payload"], req["headers"])
            response = self.connection.getresponse()
        else:
            response = self.connection(
                req["url"],
                method="POST",
                opts=req["opts"],
                data=req["payload"],
                header_dict=req["headers"],
                decode=True,
                decode_type="json",
                **self.nxargs,
            )

        return self.parse_response(response, command_list)

    def parse_response(self, response, command_list):
        """
        Parse NX-API JSON response from the NX-OS device.
        """
        # Check for 500 level NX-API Server Errors
        if isinstance(response, Iterable) and "status" in response:
            if int(response["status"]) >= 500:
                raise NxosError(f"{response}")
            else:
                raise NxosError(f"NX-API Request Not Supported: {response}")

        if isinstance(response, Iterable):
            body = response["dict"]
        else:
            body = response

        if self.nxargs["connect_over_uds"]:
            body = json.loads(response.read().decode("utf-8"))

        # Proceed with caution.  The JSON may not be complete.
        # Don't just return body['ins_api']['outputs']['output'] directly.
        output = body.get("ins_api")
        if output is None:
            raise NxosClientError(f"Unexpected JSON output\n{body}")
        if output.get("outputs"):
            output = output["outputs"]
        if output.get("output"):
            output = output["output"]

        # The result list stores results for each command that was sent to
        # nxapi.
        result = []
        # Keep track of successful commands using previous_commands list so
        # they can be displayed if a specific command fails in a chain of
        # commands.
        previous_commands = []

        # Make sure output and command_list lists to be processed in the
        # subesequent loop.
        if not isinstance(output, list):
            output = [output]
        if not isinstance(command_list, list):
            command_list = [command_list]
        if len(command_list) == 1 and ";" in command_list[0]:
            command_list = [cmd.strip() for cmd in command_list[0].split(";")]

        for cmd_result, cmd in zip(output, command_list):
            code = cmd_result.get("code")
            msg = cmd_result.get("msg")
            log.info("command %s:", cmd)
            log.info("PARSE_RESPONSE: %s %s", code, msg)
            if code == "400":
                raise CommandExecutionError(
                    {
                        "rejected_input": cmd,
                        "code": code,
                        "message": msg,
                        "cli_error": cmd_result.get("clierror"),
                        "previous_commands": previous_commands,
                    }
                )
            elif code == "413":
                raise NxosRequestNotSupported(f"Error 413: {msg}")
            elif code != "200":
                raise NxosError(f"Unknown Error: {msg}, Code: {code}")
            else:
                previous_commands.append(cmd)
                result.append(cmd_result["body"])

        return result


def nxapi_request(commands, method="cli_show", **kwargs):
    """
    Send exec and config commands to the NX-OS device over NX-API.

    commands
        The exec or config commands to be sent.

    method:
        ``cli_show_ascii``: Return raw test or unstructured output.
        ``cli_show``: Return structured output.
        ``cli_conf``: Send configuration commands to the device.
        Defaults to ``cli_show``.

    transport: ``https``
        Specifies the type of connection transport to use. Valid values for the
        connection are ``http``, and  ``https``.

    host: ``localhost``
        The IP address or DNS host name of the device.

    username: ``admin``
        The username to pass to the device to authenticate the NX-API connection.

    password
        The password to pass to the device to authenticate the NX-API connection.

    port
        The TCP port of the endpoint for the NX-API connection. If this keyword is
        not specified, the default value is automatically determined by the
        transport type (``80`` for ``http``, or ``443`` for ``https``).

    timeout: ``60``
        Time in seconds to wait for the device to respond. Default: 60 seconds.

    verify: ``True``
        Either a boolean, in which case it controls whether we verify the NX-API
        TLS certificate, or a string, in which case it must be a path to a CA bundle
        to use. Defaults to ``True``.
    """
    client = NxapiClient(**kwargs)
    return client.request(method, commands)


def ping(**kwargs):
    """
    Verify connection to the NX-OS device over UDS.
    """
    return NxapiClient(**kwargs).nxargs["connect_over_uds"]


# Grains Functions


def _parser(block):
    return re.compile(f"^{block}\n(?:^[ \n].*$\n?)+", re.MULTILINE)


def _parse_software(data):
    """
    Internal helper function to parse sotware grain information.
    """
    ret = {"software": {}}
    software = _parser("Software").search(data).group(0)
    matcher = re.compile("^  ([^:]+): *([^\n]+)", re.MULTILINE)
    for line in matcher.finditer(software):
        key, val = line.groups()
        ret["software"][key] = val
    return ret["software"]


def _parse_hardware(data):
    """
    Internal helper function to parse hardware grain information.
    """
    ret = {"hardware": {}}
    hardware = _parser("Hardware").search(data).group(0)
    matcher = re.compile("^  ([^:\n]+): *([^\n]+)", re.MULTILINE)
    for line in matcher.finditer(hardware):
        key, val = line.groups()
        ret["hardware"][key] = val
    return ret["hardware"]


def _parse_plugins(data):
    """
    Internal helper function to parse plugin grain information.
    """
    ret = {"plugins": []}
    plugins = _parser("plugin").search(data).group(0)
    matcher = re.compile("^  (?:([^,]+), )+([^\n]+)", re.MULTILINE)
    for line in matcher.finditer(plugins):
        ret["plugins"].extend(line.groups())
    return ret["plugins"]


def version_info():
    client = NxapiClient()
    return client.request("cli_show_ascii", "show version")[0]


def system_info(data):
    """
    Helper method to return parsed system_info
    from the 'show version' command.
    """
    if not data:
        return {}
    info = {
        "software": _parse_software(data),
        "hardware": _parse_hardware(data),
        "plugins": _parse_plugins(data),
    }
    return {"nxos": info}
