"""
Runner to provide F5 Load Balancer functionality

:depends:   - pycontrol Python module

:configuration: In order to connect to a F5 Load Balancer, you must specify
    in the Salt master configuration the currently available load balancers

    .. code-block:: yaml

        load_balancers:
          bigip1.example.com:
            username: admin
            password: secret
          bigip2.example.com:
            username: admin
            password: secret
"""

from salt.exceptions import CommandExecutionError

try:
    import pycontrol.pycontrol as f5

    HAS_PYCONTROL = True
except ImportError:
    HAS_PYCONTROL = False


def __virtual__():
    if not HAS_PYCONTROL:
        return False
    return True


class F5Mgmt:
    def __init__(self, lb, username, password):
        self.lb = lb
        self.username = username
        self.password = password
        self._connect()

    def _connect(self):
        """
        Connect to F5
        """
        try:
            self.bigIP = f5.BIGIP(
                hostname=self.lb,
                username=self.username,
                password=self.password,
                fromurl=True,
                wsdls=["LocalLB.VirtualServer", "LocalLB.Pool"],
            )
        except Exception:  # pylint: disable=broad-except
            raise Exception("Unable to connect to {}".format(self.lb))

        return True

    def create_vs(self, name, ip, port, protocol, profile, pool_name):
        """
        Create a virtual server
        """
        vs = self.bigIP.LocalLB.VirtualServer
        vs_def = vs.typefactory.create("Common.VirtualServerDefinition")

        vs_def.name = name
        vs_def.address = ip
        vs_def.port = port

        common_protocols = vs.typefactory.create("Common.ProtocolType")

        p = [i[0] for i in common_protocols if i[0].split("_")[1] == protocol.upper()]

        if p:
            vs_def.protocol = p
        else:
            raise CommandExecutionError("Unknown protocol")

        vs_def_seq = vs.typefactory.create("Common.VirtualServerSequence")
        vs_def_seq.item = [vs_def]

        vs_type = vs.typefactory.create("LocalLB.VirtualServer.VirtualServerType")
        vs_resource = vs.typefactory.create(
            "LocalLB.VirtualServer.VirtualServerResource"
        )

        vs_resource.type = vs_type.RESOURCE_TYPE_POOL
        vs_resource.default_pool_name = pool_name

        resource_seq = vs.typefactory.create(
            "LocalLB.VirtualServer.VirtualServerResourceSequence"
        )

        resource_seq.item = [vs_resource]

        vs_context = vs.typefactory.create("LocalLB.ProfileContextType")
        vs_profile = vs.typefactory.create("LocalLB.VirtualServer.VirtualServerProfile")

        vs_profile.profile_context = vs_context.PROFILE_CONTEXT_TYPE_ALL
        vs_profile.profile_name = protocol

        vs_profile_http = vs.typefactory.create(
            "LocalLB.VirtualServer.VirtualServerProfile"
        )
        vs_profile_http.profile_name = profile

        vs_profile_conn = vs.typefactory.create(
            "LocalLB.VirtualServer.VirtualServerProfile"
        )
        vs_profile_conn.profile_name = "oneconnect"

        vs_profile_seq = vs.typefactory.create(
            "LocalLB.VirtualServer.VirtualServerProfileSequence"
        )
        vs_profile_seq.item = [vs_profile, vs_profile_http, vs_profile_conn]

        try:
            vs.create(
                definitions=vs_def_seq,
                wildmasks=["255.255.255.255"],
                resources=resource_seq,
                profiles=[vs_profile_seq],
            )
        except Exception as e:  # pylint: disable=broad-except
            raise Exception(
                "Unable to create `{}` virtual server\n\n{}".format(name, e)
            )
        return True

    def create_pool(self, name, method="ROUND_ROBIN"):
        """
        Create a pool on the F5 load balancer
        """
        lbmethods = self.bigIP.LocalLB.Pool.typefactory.create("LocalLB.LBMethod")

        supported_method = [
            i[0] for i in lbmethods if (i[0].split("_", 2)[-1] == method.upper())
        ]

        if supported_method and not self.check_pool(name):
            try:
                self.bigIP.LocalLB.Pool.create(
                    pool_names=[name], lb_methods=[supported_method], members=[[]]
                )
            except Exception as e:  # pylint: disable=broad-except
                raise Exception("Unable to create `{}` pool\n\n{}".format(name, e))
        else:
            raise Exception("Unsupported method")
        return True

    def add_pool_member(self, name, port, pool_name):
        """
        Add a node to a pool
        """
        if not self.check_pool(pool_name):
            raise CommandExecutionError("{} pool does not exists".format(pool_name))

        members_seq = self.bigIP.LocalLB.Pool.typefactory.create(
            "Common.IPPortDefinitionSequence"
        )
        members_seq.items = []

        member = self.bigIP.LocalLB.Pool.typefactory.create("Common.IPPortDefinition")

        member.address = name
        member.port = port

        members_seq.items.append(member)

        try:
            self.bigIP.LocalLB.Pool.add_member(
                pool_names=[pool_name], members=[members_seq]
            )
        except Exception as e:  # pylint: disable=broad-except
            raise Exception(
                "Unable to add `{}` to `{}`\n\n{}".format(name, pool_name, e)
            )
        return True

    def check_pool(self, name):
        """
        Check to see if a pool exists
        """
        pools = self.bigIP.LocalLB.Pool
        for pool in pools.get_list():
            if pool.split("/")[-1] == name:
                return True
        return False

    def check_virtualserver(self, name):
        """
        Check to see if a virtual server exists
        """
        vs = self.bigIP.LocalLB.VirtualServer
        for v in vs.get_list():
            if v.split("/")[-1] == name:
                return True
        return False

    def check_member_pool(self, member, pool_name):
        """
        Check a pool member exists in a specific pool
        """
        members = self.bigIP.LocalLB.Pool.get_member(pool_names=[pool_name])[0]
        for mem in members:
            if member == mem.address:
                return True
        return False

    def lbmethods(self):
        """
        List all the load balancer methods
        """
        methods = self.bigIP.LocalLB.Pool.typefactory.create("LocalLB.LBMethod")
        return [method[0].split("_", 2)[-1] for method in methods]


def create_vs(lb, name, ip, port, protocol, profile, pool_name):
    """
    Create a virtual server

    CLI Examples:

    .. code-block:: bash

        salt-run f5.create_vs lbalancer vs_name 10.0.0.1 80 tcp http poolname
    """
    if __opts__["load_balancers"].get(lb, None):
        (username, password) = list(__opts__["load_balancers"][lb].values())
    else:
        raise Exception("Unable to find `{}` load balancer".format(lb))

    F5 = F5Mgmt(lb, username, password)
    F5.create_vs(name, ip, port, protocol, profile, pool_name)
    return True


def create_pool(lb, name, method="ROUND_ROBIN"):
    """
    Create a pool on the F5 load balancer

    CLI Examples:

    .. code-block:: bash

        salt-run f5.create_pool load_balancer pool_name loadbalance_method
        salt-run f5.create_pool load_balancer my_pool ROUND_ROBIN
    """
    if __opts__["load_balancers"].get(lb, None):
        (username, password) = list(__opts__["load_balancers"][lb].values())
    else:
        raise Exception("Unable to find `{}` load balancer".format(lb))
    F5 = F5Mgmt(lb, username, password)
    F5.create_pool(name, method)
    return True


def add_pool_member(lb, name, port, pool_name):
    """
    Add a node to a pool

    CLI Examples:

    .. code-block:: bash

        salt-run f5.add_pool_member load_balancer 10.0.0.1 80 my_pool
    """
    if __opts__["load_balancers"].get(lb, None):
        (username, password) = list(__opts__["load_balancers"][lb].values())
    else:
        raise Exception("Unable to find `{}` load balancer".format(lb))
    F5 = F5Mgmt(lb, username, password)
    F5.add_pool_member(name, port, pool_name)
    return True


def check_pool(lb, name):
    """
    Check to see if a pool exists

    CLI Examples:

    .. code-block:: bash

        salt-run f5.check_pool load_balancer pool_name
    """
    if __opts__["load_balancers"].get(lb, None):
        (username, password) = list(__opts__["load_balancers"][lb].values())
    else:
        raise Exception("Unable to find `{}` load balancer".format(lb))
    F5 = F5Mgmt(lb, username, password)
    return F5.check_pool(name)


def check_virtualserver(lb, name):
    """
    Check to see if a virtual server exists

    CLI Examples:

    .. code-block:: bash

        salt-run f5.check_virtualserver load_balancer virtual_server
    """
    if __opts__["load_balancers"].get(lb, None):
        (username, password) = list(__opts__["load_balancers"][lb].values())
    else:
        raise Exception("Unable to find `{}` load balancer".format(lb))
    F5 = F5Mgmt(lb, username, password)
    return F5.check_virtualserver(name)


def check_member_pool(lb, member, pool_name):
    """
    Check a pool member exists in a specific pool

    CLI Examples:

    .. code-block:: bash

        salt-run f5.check_member_pool load_balancer 10.0.0.1 my_pool
    """
    if __opts__["load_balancers"].get(lb, None):
        (username, password) = list(__opts__["load_balancers"][lb].values())
    else:
        raise Exception("Unable to find `{}` load balancer".format(lb))
    F5 = F5Mgmt(lb, username, password)
    return F5.check_member_pool(member, pool_name)
