from tests.support.mock import call


def network_update_call(
    name,
    bridge,
    forward,
    vport=None,
    tag=None,
    ipv4_config=None,
    ipv6_config=None,
    connection=None,
    username=None,
    password=None,
    mtu=None,
    domain=None,
    nat=None,
    interfaces=None,
    addresses=None,
    physical_function=None,
    dns=None,
    test=False,
):
    """
    Create a call object with the missing default parameters from virt.network_update()
    """
    return call(
        name,
        bridge,
        forward,
        vport=vport,
        tag=tag,
        ipv4_config=ipv4_config,
        ipv6_config=ipv6_config,
        mtu=mtu,
        domain=domain,
        nat=nat,
        interfaces=interfaces,
        addresses=addresses,
        physical_function=physical_function,
        dns=dns,
        test=test,
        connection=connection,
        username=username,
        password=password,
    )
