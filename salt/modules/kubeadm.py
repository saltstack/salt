"""
Module for kubeadm
:maintainer:    Alberto Planas <aplanas@suse.com>
:maturity:      new
:depends:       None
:platform:      Linux
"""

import json
import logging
import re

import salt.utils.files
from salt.exceptions import CommandExecutionError

ADMIN_CFG = "/etc/kubernetes/admin.conf"

log = logging.getLogger(__name__)

__virtualname__ = "kubeadm"

# Define not exported variables from Salt, so this can be imported as
# a normal module
try:
    __salt__
except NameError:
    __salt__ = {}


def _api_server_endpoint(config=None):
    """
    Return the API server endpoint
    """
    config = config if config else ADMIN_CFG
    endpoint = None
    try:
        with salt.utils.files.fopen(config, "r") as fp_:
            endpoint = re.search(
                r"^\s*server: https?://(.*)$", fp_.read(), re.MULTILINE
            ).group(1)
    # pylint:disable=broad-except
    except Exception:
        # Any error or exception is mapped to None
        pass
    return endpoint


def _token(create_if_needed=False):
    """
    Return a valid bootstrap token
    """
    tokens = token_list()
    if not tokens and create_if_needed:
        token_create(description="Token created by kubeadm salt module")
        tokens = token_list()
    # We expect that the token is valid for authentication and signing
    return tokens[0]["token"] if tokens else None


def _discovery_token_ca_cert_hash():
    cmd = [
        "openssl",
        "x509",
        "-pubkey",
        "-in",
        "/etc/kubernetes/pki/ca.crt",
        "|",
        "openssl",
        "rsa",
        "-pubin",
        "-outform",
        "der",
        "2>/dev/null",
        "|",
        "openssl",
        "dgst",
        "-sha256",
        "-hex",
        "|",
        "sed",
        "'s/^.* //'",
    ]
    result = __salt__["cmd.run_all"](" ".join(cmd), python_shell=True)
    if result["retcode"]:
        raise CommandExecutionError(result["stderr"])

    return "sha256:{}".format(result["stdout"])


def join_params(create_if_needed=False):
    """
    .. versionadded:: 3001

    Return the parameters required for joining into the cluster

    create_if_needed
       If the token bucket is empty and this parameter is True, a new
       token will be created.

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.join_params
       salt '*' kubeadm.join_params create_if_needed=True

    """

    params = {
        "api-server-endpoint": _api_server_endpoint(),
        "token": _token(create_if_needed),
        "discovery-token-ca-cert-hash": _discovery_token_ca_cert_hash(),
    }
    return params


def version(kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    Return the version of kubeadm

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.version

    """
    cmd = ["kubeadm", "version"]

    parameters = [("kubeconfig", kubeconfig), ("rootfs", rootfs)]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    cmd.extend(["--output", "json"])

    return json.loads(__salt__["cmd.run_stdout"](cmd))


def _cmd(cmd):
    """Utility function to run commands."""
    result = __salt__["cmd.run_all"](cmd)
    if result["retcode"]:
        raise CommandExecutionError(result["stderr"])
    return result["stdout"]


def token_create(
    token=None,
    config=None,
    description=None,
    groups=None,
    ttl=None,
    usages=None,
    kubeconfig=None,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Create bootstrap tokens on the server

    token
       Token to write, if None one will be generated. The token must
       match a regular expression, that by default is
       [a-z0-9]{6}.[a-z0-9]{16}

    config
       Path to kubeadm configuration file

    description
       A human friendly description of how this token is used

    groups
       List of extra groups that this token will authenticate, default
       to ['system:bootstrappers:kubeadm:default-node-token']

    ttl
       The duration defore the token is automatically deleted (1s, 2m,
       3h). If set to '0' the token will never expire. Default value
       is 24h0m0s

    usages
       Describes the ways in which this token can be used. The default
       value is ['signing', 'authentication']

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.token_create
       salt '*' kubeadm.token_create a1b2c.0123456789abcdef
       salt '*' kubeadm.token_create ttl='6h'
       salt '*' kubeadm.token_create usages="['signing']"

    """
    cmd = ["kubeadm", "token", "create"]
    if token:
        cmd.append(token)

    parameters = [
        ("config", config),
        ("description", description),
        ("groups", groups),
        ("ttl", ttl),
        ("usages", usages),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            if parameter in ("groups", "usages"):
                cmd.extend(["--{}".format(parameter), json.dumps(value)])
            else:
                cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def token_delete(token, kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    Delete bootstrap tokens on the server

    token
       Token to write, if None one will be generated. The token must
       match a regular expression, that by default is
       [a-z0-9]{6}.[a-z0-9]{16}

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.token_delete a1b2c
       salt '*' kubeadm.token_create a1b2c.0123456789abcdef

    """
    cmd = ["kubeadm", "token", "delete", token]

    parameters = [("kubeconfig", kubeconfig), ("rootfs", rootfs)]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return bool(_cmd(cmd))


def token_generate(kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    Generate and return a bootstrap token, but do not create it on the
    server

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.token_generate

    """
    cmd = ["kubeadm", "token", "generate"]

    parameters = [("kubeconfig", kubeconfig), ("rootfs", rootfs)]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def token_list(kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    List bootstrap tokens on the server

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.token_list

    """
    cmd = ["kubeadm", "token", "list"]

    parameters = [("kubeconfig", kubeconfig), ("rootfs", rootfs)]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    lines = _cmd(cmd).splitlines()

    tokens = []
    if lines:
        # Find the header and parse it.  We do not need to validate
        # the content, as the regex will take care of future changes.
        header = lines.pop(0)
        header = [i.lower() for i in re.findall(r"(\w+(?:\s\w+)*)", header)]

        for line in lines:
            # TODO(aplanas): descriptions with multiple spaces can
            # break the parser.
            values = re.findall(r"(\S+(?:\s\S+)*)", line)
            if len(header) != len(values):
                log.error("Error parsing line: '%s'", line)
                continue
            tokens.append({key: value for key, value in zip(header, values)})
    return tokens


def alpha_certs_renew(rootfs=None):
    """
    .. versionadded:: 3001

    Renews certificates for a Kubernetes cluster

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.alpha_certs_renew

    """
    cmd = ["kubeadm", "alpha", "certs", "renew"]

    parameters = [("rootfs", rootfs)]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def alpha_kubeconfig_user(
    client_name,
    apiserver_advertise_address=None,
    apiserver_bind_port=None,
    cert_dir=None,
    org=None,
    token=None,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Outputs a kubeconfig file for an additional user

    client_name
       The name of the user. It will be used as the CN if client
       certificates are created

    apiserver_advertise_address
       The IP address the API server is accessible on

    apiserver_bind_port
       The port the API server is accessible on (default 6443)

    cert_dir
       The path where certificates are stored (default
       "/etc/kubernetes/pki")

    org
       The organization of the client certificate

    token
       The token that show be used as the authentication mechanism for
       this kubeconfig, instead of client certificates

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.alpha_kubeconfig_user client_name=user

    """
    cmd = ["kubeadm", "alpha", "kubeconfig", "user", "--client-name", client_name]

    parameters = [
        ("apiserver-advertise-address", apiserver_advertise_address),
        ("apiserver-bind-port", apiserver_bind_port),
        ("cert-dir", cert_dir),
        ("org", org),
        ("token", token),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def alpha_kubelet_config_download(kubeconfig=None, kubelet_version=None, rootfs=None):
    """
    .. versionadded:: 3001

    Downloads the kubelet configuration from the cluster ConfigMap
    kubelet-config-1.X

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    kubelet_version
       The desired version for the kubelet

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.alpha_kubelet_config_download
       salt '*' kubeadm.alpha_kubelet_config_download kubelet_version='1.14.0'

    """
    cmd = ["kubeadm", "alpha", "kubelet", "config", "download"]

    parameters = [
        ("kubeconfig", kubeconfig),
        ("kubelet-version", kubelet_version),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def alpha_kubelet_config_enable_dynamic(
    node_name, kubeconfig=None, kubelet_version=None, rootfs=None
):
    """
    .. versionadded:: 3001

    Enables or updates dynamic kubelet configuration for a node

    node_name
       Name of the node that should enable the dynamic kubelet
       configuration

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    kubelet_version
       The desired version for the kubelet

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.alpha_kubelet_config_enable_dynamic node-1

    """
    cmd = [
        "kubeadm",
        "alpha",
        "kubelet",
        "config",
        "enable-dynamic",
        "--node-name",
        node_name,
    ]

    parameters = [
        ("kubeconfig", kubeconfig),
        ("kubelet-version", kubelet_version),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def alpha_selfhosting_pivot(
    cert_dir=None,
    config=None,
    kubeconfig=None,
    store_certs_in_secrets=False,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Converts a static Pod-hosted control plane into a selt-hosted one

    cert_dir
       The path where certificates are stored (default
       "/etc/kubernetes/pki")

    config
       Path to kubeadm configuration file

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    store_certs_in_secrets
       Enable storing certs in secrets

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.alpha_selfhost_pivot

    """
    cmd = ["kubeadm", "alpha", "selfhosting", "pivot", "--force"]

    if store_certs_in_secrets:
        cmd.append("--store-certs-in-secrets")

    parameters = [
        ("cert-dir", cert_dir),
        ("config", config),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def config_images_list(
    config=None,
    feature_gates=None,
    kubernetes_version=None,
    kubeconfig=None,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Print a list of images kubeadm will use

    config
       Path to kubeadm configuration file

    feature_gates
       A set of key=value pairs that describe feature gates for
       various features

    kubernetes_version
       Choose a specifig Kubernetes version for the control plane
       (default "stable-1")

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.config_images_list

    """
    cmd = ["kubeadm", "config", "images", "list"]

    parameters = [
        ("config", config),
        ("feature-gates", feature_gates),
        ("kubernetes-version", kubernetes_version),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd).splitlines()


def config_images_pull(
    config=None,
    cri_socket=None,
    feature_gates=None,
    kubernetes_version=None,
    kubeconfig=None,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Pull images used by kubeadm

    config
       Path to kubeadm configuration file

    cri_socket
       Path to the CRI socket to connect

    feature_gates
       A set of key=value pairs that describe feature gates for
       various features

    kubernetes_version
       Choose a specifig Kubernetes version for the control plane
       (default "stable-1")

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.config_images_pull

    """
    cmd = ["kubeadm", "config", "images", "pull"]

    parameters = [
        ("config", config),
        ("cri-socket", cri_socket),
        ("feature-gates", feature_gates),
        ("kubernetes-version", kubernetes_version),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    prefix = "[config/images] Pulled "
    return [(line.replace(prefix, "")) for line in _cmd(cmd).splitlines()]


def config_migrate(old_config, new_config=None, kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    Read an older version of the kubeadm configuration API types from
    a file, and output the similar config object for the newer version

    old_config
       Path to the kubeadm config file that is usin the old API
       version and should be converted

    new_config
       Path to the resulting equivalent kubeadm config file using the
       new API version. If not specified the output will be returned

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.config_migrate /oldconfig.cfg

    """
    cmd = ["kubeadm", "config", "migrate", "--old-config", old_config]

    parameters = [
        ("new-config", new_config),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def config_print_init_defaults(component_configs=None, kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    Return default init configuration, that can be used for 'kubeadm
    init'

    component_config
       A comma-separated list for component config API object to print
       the default values for (valid values: KubeProxyConfiguration,
       KubeletConfiguration)

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.config_print_init_defaults

    """
    cmd = ["kubeadm", "config", "print", "init-defaults"]

    parameters = [
        ("component-configs", component_configs),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def config_print_join_defaults(component_configs=None, kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    Return default join configuration, that can be used for 'kubeadm
    join'

    component_config
       A comma-separated list for component config API object to print
       the default values for (valid values: KubeProxyConfiguration,
       KubeletConfiguration)

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.config_print_join_defaults

    """
    cmd = ["kubeadm", "config", "print", "join-defaults"]

    parameters = [
        ("component-configs", component_configs),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def config_upload_from_file(config, kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    Upload a configuration file to the in-cluster ConfigMap for
    kubeadm configuration

    config
       Path to a kubeadm configuration file

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.config_upload_from_file /config.cfg

    """
    cmd = ["kubeadm", "config", "upload", "from-file", "--config", config]

    parameters = [("kubeconfig", kubeconfig), ("rootfs", rootfs)]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def config_upload_from_flags(
    apiserver_advertise_address=None,
    apiserver_bind_port=None,
    apiserver_cert_extra_sans=None,
    cert_dir=None,
    cri_socket=None,
    feature_gates=None,
    kubernetes_version=None,
    node_name=None,
    pod_network_cidr=None,
    service_cidr=None,
    service_dns_domain=None,
    kubeconfig=None,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Create the in-cluster configuration file for the first time using
    flags

    apiserver_advertise_address
       The IP address the API server will advertise it's listening on

    apiserver_bind_port
       The port the API server is accessible on (default 6443)

    apiserver_cert_extra_sans
       Optional extra Subject Alternative Names (SANs) to use for the
       API Server serving certificate

    cert_dir
       The path where to save and store the certificates (default
       "/etc/kubernetes/pki")

    cri_socket
       Path to the CRI socket to connect

    feature_gates
       A set of key=value pairs that describe feature gates for
       various features

    kubernetes_version
       Choose a specifig Kubernetes version for the control plane
       (default "stable-1")

    node_name
       Specify the node name

    pod_network_cidr
       Specify range of IP addresses for the pod network

    service_cidr
       Use alternative range of IP address for service VIPs (default
       "10.96.0.0/12")

    service_dns_domain
       Use alternative domain for services (default "cluster.local")

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.config_upload_from_flags

    """
    cmd = ["kubeadm", "config", "upload", "from-flags"]

    parameters = [
        ("apiserver-advertise-address", apiserver_advertise_address),
        ("apiserver-bind-port", apiserver_bind_port),
        ("apiserver-cert-extra-sans", apiserver_cert_extra_sans),
        ("cert-dir", cert_dir),
        ("cri-socket", cri_socket),
        ("feature-gates", feature_gates),
        ("kubernetes-version", kubernetes_version),
        ("node-name", node_name),
        ("pod-network-cidr", pod_network_cidr),
        ("service-cidr", service_cidr),
        ("service-dns-domain", service_dns_domain),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def config_view(kubeconfig=None, rootfs=None):
    """
    .. versionadded:: 3001

    View the kubeadm configuration stored inside the cluster

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.config_view

    """
    cmd = ["kubeadm", "config", "view"]

    parameters = [("kubeconfig", kubeconfig), ("rootfs", rootfs)]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


def init(
    apiserver_advertise_address=None,
    apiserver_bind_port=None,
    apiserver_cert_extra_sans=None,
    cert_dir=None,
    certificate_key=None,
    control_plane_endpoint=None,
    config=None,
    cri_socket=None,
    experimental_upload_certs=False,
    upload_certs=False,
    feature_gates=None,
    ignore_preflight_errors=None,
    image_repository=None,
    kubernetes_version=None,
    node_name=None,
    pod_network_cidr=None,
    service_cidr=None,
    service_dns_domain=None,
    skip_certificate_key_print=False,
    skip_phases=None,
    skip_token_print=False,
    token=None,
    token_ttl=None,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Command to set up the Kubernetes control plane

    apiserver_advertise_address
       The IP address the API server will advertise it's listening on

    apiserver_bind_port
       The port the API server is accessible on (default 6443)

    apiserver_cert_extra_sans
       Optional extra Subject Alternative Names (SANs) to use for the
       API Server serving certificate

    cert_dir
       The path where to save and store the certificates (default
       "/etc/kubernetes/pki")

    certificate_key
       Key used to encrypt the control-plane certificates in the
       kubeadm-certs Secret

    config
       Path to a kubeadm configuration file

    control_plane_endpoint
       Specify a stable IP address or DNS name for the control plane

    cri_socket
       Path to the CRI socket to connect

    experimental_upload_certs
       Upload control-plane certificate to the kubeadm-certs Secret. ( kubeadm version =< 1.16 )

    upload_certs
       Upload control-plane certificate to the kubeadm-certs Secret. ( kubeadm version > 1.16 )

    feature_gates
       A set of key=value pairs that describe feature gates for
       various features

    ignore_preflight_errors
       A list of checks whose errors will be shown as warnings

    image_repository
       Choose a container registry to pull control plane images from

    kubernetes_version
       Choose a specifig Kubernetes version for the control plane
       (default "stable-1")

    node_name
       Specify the node name

    pod_network_cidr
       Specify range of IP addresses for the pod network

    service_cidr
       Use alternative range of IP address for service VIPs (default
       "10.96.0.0/12")

    service_dns_domain
       Use alternative domain for services (default "cluster.local")

    skip_certificate_key_print
       Don't print the key used to encrypt the control-plane
       certificates

    skip_phases
       List of phases to be skipped

    skip_token_print
       Skip printing of the default bootstrap token generated by
       'kubeadm init'

    token
       The token to use for establishing bidirectional trust between
       nodes and control-plane nodes. The token must match a regular
       expression, that by default is [a-z0-9]{6}.[a-z0-9]{16}

    token_ttl
       The duration defore the token is automatically deleted (1s, 2m,
       3h). If set to '0' the token will never expire. Default value
       is 24h0m0s

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.init pod_network_cidr='10.244.0.0/16'

    """
    cmd = ["kubeadm", "init"]

    if experimental_upload_certs:
        cmd.append("--experimental-upload-certs")
    if upload_certs:
        cmd.append("--upload-certs")
    if skip_certificate_key_print:
        cmd.append("--skip-certificate-key-print")
    if skip_token_print:
        cmd.append("--skip-token-print")

    parameters = [
        ("apiserver-advertise-address", apiserver_advertise_address),
        ("apiserver-bind-port", apiserver_bind_port),
        ("apiserver-cert-extra-sans", apiserver_cert_extra_sans),
        ("cert-dir", cert_dir),
        ("certificate-key", certificate_key),
        ("config", config),
        ("control-plane-endpoint", control_plane_endpoint),
        ("cri-socket", cri_socket),
        ("feature-gates", feature_gates),
        ("ignore-preflight-errors", ignore_preflight_errors),
        ("image-repository", image_repository),
        ("kubernetes-version", kubernetes_version),
        ("node-name", node_name),
        ("pod-network-cidr", pod_network_cidr),
        ("service-cidr", service_cidr),
        ("service-dns-domain", service_dns_domain),
        ("skip-phases", skip_phases),
        ("token", token),
        ("token-ttl", token_ttl),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


# TODO(aplanas):
#   * init_phase_addon_all
#   * init_phase_addon_coredns
#   * init_phase_addon_kube_proxy
#   * init_phase_bootstrap_token
#   * init_phase_certs_all
#   * init_phase_certs_apiserver
#   * init_phase_certs_apiserver_etcd_client
#   * init_phase_certs_apiserver_kubelet_client
#   * init_phase_certs_ca
#   * init_phase_certs_etcd_ca
#   * init_phase_certs_etcd_healthcheck_client
#   * init_phase_certs_etcd_peer
#   * init_phase_certs_etcd_server
#   * init_phase_certs_front_proxy_ca
#   * init_phase_certs_front_proxy_client
#   * init_phase_certs_sa
#   * init_phase_control_plane_all
#   * init_phase_control_plane_apiserver
#   * init_phase_control_plane_controller_manager
#   * init_phase_control_plane_scheduler
#   * init_phase_etcd_local
#   * init_phase_kubeconfig_admin
#   * init_phase_kubeconfig_all
#   * init_phase_kubeconfig_controller_manager
#   * init_phase_kubeconfig_kubelet
#   * init_phase_kubeconfig_scheduler
#   * init_phase_kubelet_start
#   * init_phase_mark_control_plane
#   * init_phase_preflight
#   * init_phase_upload_certs
#   * init_phase_upload_config_all
#   * init_phase_upload_config_kuneadm
#   * init_phase_upload_config_kubelet


def join(
    api_server_endpoint=None,
    apiserver_advertise_address=None,
    apiserver_bind_port=None,
    certificate_key=None,
    config=None,
    cri_socket=None,
    discovery_file=None,
    discovery_token=None,
    discovery_token_ca_cert_hash=None,
    discovery_token_unsafe_skip_ca_verification=False,
    experimental_control_plane=False,
    control_plane=False,
    ignore_preflight_errors=None,
    node_name=None,
    skip_phases=None,
    tls_bootstrap_token=None,
    token=None,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Command to join to an existing cluster

    api_server_endpoint
       IP address or domain name and port of the API Server

    apiserver_advertise_address
       If the node should host a new control plane instance, the IP
       address the API Server will advertise it's listening on

    apiserver_bind_port
       If the node should host a new control plane instance, the port
       the API Server to bind to (default 6443)

    certificate_key
       Use this key to decrypt the certificate secrets uploaded by
       init

    config
       Path to a kubeadm configuration file

    cri_socket
       Path to the CRI socket to connect

    discovery_file
       For file-based discovery, a file or URL from which to load
       cluster information

    discovery_token
       For token-based discovery, the token used to validate cluster
       information fetched from the API Server

    discovery_token_ca_cert_hash
       For token-based discovery, validate that the root CA public key
       matches this hash (format: "<type>:<value>")

    discovery_token_unsafe_skip_ca_verification
       For token-based discovery, allow joining without
       'discovery-token-ca-cert-hash' pinning

    experimental_control_plane
       Create a new control plane instance on this node (kubeadm version =< 1.16)

    control_plane
       Create a new control plane instance on this node (kubeadm version > 1.16)

    ignore_preflight_errors
       A list of checks whose errors will be shown as warnings

    node_name
       Specify the node name

    skip_phases
       List of phases to be skipped

    tls_bootstrap_token
       Specify the token used to temporarily authenticate with the
       Kubernetes Control Plane while joining the node

    token
       Use this token for both discovery-token and tls-bootstrap-token
       when those values are not provided

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.join 10.160.65.165:6443 token='token'

    """
    cmd = ["kubeadm", "join"]

    if api_server_endpoint:
        cmd.append(api_server_endpoint)
    if discovery_token_unsafe_skip_ca_verification:
        cmd.append("--discovery-token-unsafe-skip-ca-verification")
    if experimental_control_plane:
        cmd.append("--experimental-control-plane")
    if control_plane:
        cmd.append("--control-plane")

    parameters = [
        ("apiserver-advertise-address", apiserver_advertise_address),
        ("apiserver-bind-port", apiserver_bind_port),
        ("certificate-key", certificate_key),
        ("config", config),
        ("cri-socket", cri_socket),
        ("discovery-file", discovery_file),
        ("discovery-token", discovery_token),
        ("discovery-token-ca-cert-hash", discovery_token_ca_cert_hash),
        ("ignore-preflight-errors", ignore_preflight_errors),
        ("node-name", node_name),
        ("skip-phases", skip_phases),
        ("tls-bootstrap-token", tls_bootstrap_token),
        ("token", token),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


# TODO(aplanas):
#   * join_phase_control_plane_join_all
#   * join_phase_control_plane_join_etcd
#   * join_phase_control_plane_join_mark_control_plane
#   * join_phase_control_plane_join_update_status
#   * join_phase_control_plane_prepare_all
#   * join_phase_control_plane_prepare_certs
#   * join_phase_control_plane_prepare_control_plane
#   * join_phase_control_plane_prepare_download_certs
#   * join_phase_control_plane_prepare_kubeconfig
#   * join_phase_kubelet_start
#   * join_phase_preflight


def reset(
    cert_dir=None,
    cri_socket=None,
    ignore_preflight_errors=None,
    kubeconfig=None,
    rootfs=None,
):
    """
    .. versionadded:: 3001

    Revert any changes made to this host by 'kubeadm init' or 'kubeadm
    join'

    cert_dir
       The path to the directory where the certificates are stored
       (default "/etc/kubernetes/pki")

    cri_socket
       Path to the CRI socket to connect

    ignore_preflight_errors
       A list of checks whose errors will be shown as warnings

    kubeconfig
       The kubeconfig file to use when talking to the cluster. The
       default values in /etc/kubernetes/admin.conf

    rootfs
       The path to the real host root filesystem

    CLI Example:

    .. code-block:: bash

       salt '*' kubeadm.join 10.160.65.165:6443 token='token'

    """
    cmd = ["kubeadm", "reset", "--force"]

    parameters = [
        ("cert-dir", cert_dir),
        ("cri-socket", cri_socket),
        ("ignore-preflight-errors", ignore_preflight_errors),
        ("kubeconfig", kubeconfig),
        ("rootfs", rootfs),
    ]
    for parameter, value in parameters:
        if value:
            cmd.extend(["--{}".format(parameter), str(value)])

    return _cmd(cmd)


# TODO(aplanas):
#   *  upgrade_apply
#   *  upgrade_diff
#   *  upgrade_node
#   *  upgrade_plan
