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


def domain_update_call(
    name,
    cpu=None,
    mem=None,
    disk_profile=None,
    disks=None,
    nic_profile=None,
    interfaces=None,
    graphics=None,
    connection=None,
    username=None,
    password=None,
    boot=None,
    numatune=None,
    boot_dev=None,
    hypervisor_features=None,
    clock=None,
    serials=None,
    consoles=None,
    stop_on_reboot=False,
    live=True,
    host_devices=None,
    test=False,
):
    """
    Create a call object with the missing default parameters from virt.update()
    """
    return call(
        name,
        cpu=cpu,
        mem=mem,
        disk_profile=disk_profile,
        disks=disks,
        nic_profile=nic_profile,
        interfaces=interfaces,
        graphics=graphics,
        live=live,
        connection=connection,
        username=username,
        password=password,
        boot=boot,
        numatune=numatune,
        serials=serials,
        consoles=consoles,
        test=test,
        boot_dev=boot_dev,
        hypervisor_features=hypervisor_features,
        clock=clock,
        stop_on_reboot=stop_on_reboot,
        host_devices=host_devices,
    )
