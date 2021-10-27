"""
    :codeauthor: :email:`Agnes Tevesz (agnes.tevesz@morganstanley.com)`

    salt.config.schemas.esxvm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ESX Virtual Machine configuration schemas
"""


from salt.utils.schema import (
    AnyOfItem,
    ArrayItem,
    BooleanItem,
    ComplexSchemaItem,
    DefinitionsSchema,
    IntegerItem,
    IPv4Item,
    NullItem,
    NumberItem,
    StringItem,
)


class ESXVirtualMachineSerialBackingItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine Serial Port Backing
    """

    title = "ESX Virtual Machine Serial Port Backing"
    description = "ESX virtual machine serial port backing"
    required = True

    uri = StringItem()
    direction = StringItem(enum=("client", "server"))
    filename = StringItem()


class ESXVirtualMachineDeviceConnectionItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine Serial Port Connection
    """

    title = "ESX Virtual Machine Serial Port Connection"
    description = "ESX virtual machine serial port connection"
    required = True

    allow_guest_control = BooleanItem(default=True)
    start_connected = BooleanItem(default=True)


class ESXVirtualMachinePlacementSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine Placement
    """

    title = "ESX Virtual Machine Placement Information"
    description = "ESX virtual machine placement property"
    required = True

    cluster = StringItem(
        title="Virtual Machine Cluster",
        description="Cluster of the virtual machine if it is placed to a cluster",
    )
    host = StringItem(
        title="Virtual Machine Host",
        description="Host of the virtual machine if it is placed to a standalone host",
    )
    resourcepool = StringItem(
        title="Virtual Machine Resource Pool",
        description=(
            "Resource pool of the virtual machine if it is placed to a resource pool"
        ),
    )
    folder = StringItem(
        title="Virtual Machine Folder",
        description=(
            "Folder of the virtual machine where it should be deployed, default is the"
            " datacenter vmFolder"
        ),
    )


class ESXVirtualMachineCdDriveClientSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine CD Drive Client
    """

    title = "ESX Virtual Machine Serial CD Client"
    description = "ESX virtual machine CD/DVD drive client properties"

    mode = StringItem(required=True, enum=("passthrough", "atapi"))


class ESXVirtualMachineCdDriveIsoSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine CD Drive ISO
    """

    title = "ESX Virtual Machine Serial CD ISO"
    description = "ESX virtual machine CD/DVD drive ISO properties"

    path = StringItem(required=True)


class ESXVirtualMachineCdDriveSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine CD Drives
    """

    title = "ESX Virtual Machine Serial CD"
    description = "ESX virtual machine CD/DVD drive properties"

    adapter = StringItem(
        title="Virtual Machine CD/DVD Adapter",
        description="Unique adapter name for virtual machine cd/dvd drive",
        required=True,
    )
    controller = StringItem(required=True)
    device_type = StringItem(
        title="Virtual Machine Device Type",
        description="CD/DVD drive of the virtual machine if it is placed to a cluster",
        required=True,
        default="client_device",
        enum=("datastore_iso_file", "client_device"),
    )
    client_device = ESXVirtualMachineCdDriveClientSchemaItem()
    datastore_iso_file = ESXVirtualMachineCdDriveIsoSchemaItem()
    connectable = ESXVirtualMachineDeviceConnectionItem()


class ESXVirtualMachineSerialSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine Serial Port
    """

    title = "ESX Virtual Machine Serial Port Configuration"
    description = "ESX virtual machine serial port properties"

    type = StringItem(
        title="Virtual Machine Serial Port Type",
        required=True,
        enum=("network", "pipe", "file", "device"),
    )
    adapter = StringItem(
        title="Virtual Machine Serial Port Name",
        description=(
            "Unique adapter name for virtual machine serial port "
            "for creation an arbitrary value should be specified"
        ),
        required=True,
    )
    backing = ESXVirtualMachineSerialBackingItem()
    connectable = ESXVirtualMachineDeviceConnectionItem()
    yield_port = BooleanItem(
        title="Serial Port Yield", description="Serial port yield", default=False
    )


class ESXVirtualMachineScsiSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine SCSI Controller
    """

    title = "ESX Virtual Machine SCSI Controller Configuration"
    description = "ESX virtual machine scsi controller properties"
    required = True

    adapter = StringItem(
        title="Virtual Machine SCSI Controller Name",
        description=(
            "Unique SCSI controller name "
            "for creation an arbitrary value should be specified"
        ),
        required=True,
    )
    type = StringItem(
        title="Virtual Machine SCSI type",
        description="Type of the SCSI controller",
        required=True,
        enum=("lsilogic", "lsilogic_sas", "paravirtual", "buslogic"),
    )
    bus_sharing = StringItem(
        title="Virtual Machine SCSI bus sharing",
        description="Sharing type of the SCSI bus",
        required=True,
        enum=("virtual_sharing", "physical_sharing", "no_sharing"),
    )
    bus_number = NumberItem(
        title="Virtual Machine SCSI bus number",
        description="Unique bus number of the SCSI device",
        required=True,
    )


class ESXVirtualMachineSataSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine SATA Controller
    """

    title = "ESX Virtual Machine SATA Controller Configuration"
    description = "ESX virtual machine SATA controller properties"
    required = False
    adapter = StringItem(
        title="Virtual Machine SATA Controller Name",
        description=(
            "Unique SATA controller name "
            "for creation an arbitrary value should be specified"
        ),
        required=True,
    )
    bus_number = NumberItem(
        title="Virtual Machine SATA bus number",
        description="Unique bus number of the SATA device",
        required=True,
    )


class ESXVirtualMachineDiskSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine Disk
    """

    title = "ESX Virtual Machine Disk Configuration"
    description = "ESX virtual machine disk properties"
    required = True

    size = NumberItem(
        title="Disk size", description="Size of the disk in GB", required=True
    )
    unit = StringItem(
        title="Disk size unit",
        description=(
            "Unit of the disk size, to VMware a GB is the same as GiB = 1024MiB"
        ),
        required=False,
        default="GB",
        enum=("KB", "MB", "GB"),
    )
    adapter = StringItem(
        title="Virtual Machine Adapter Name",
        description=(
            "Unique adapter name for virtual machine "
            "for creation an arbitrary value should be specified"
        ),
        required=True,
    )
    filename = StringItem(
        title="Virtual Machine Disk File",
        description="File name of the virtual machine vmdk",
    )
    datastore = StringItem(
        title="Virtual Machine Disk Datastore",
        description="Disk datastore where the virtual machine files will be placed",
        required=True,
    )
    address = StringItem(
        title="Virtual Machine SCSI Address",
        description="Address of the SCSI adapter for the virtual machine",
        pattern=r"\d:\d",
    )
    thin_provision = BooleanItem(
        title="Virtual Machine Disk Provision Type",
        description="Provision type of the disk",
        default=True,
        required=False,
    )
    eagerly_scrub = AnyOfItem(required=False, items=[BooleanItem(), NullItem()])
    controller = StringItem(
        title="Virtual Machine SCSI Adapter",
        description="Name of the SCSI adapter where the disk will be connected",
        required=True,
    )


class ESXVirtualMachineNicMapSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine Nic Map
    """

    title = "ESX Virtual Machine Nic Configuration"
    description = "ESX Virtual Machine nic properties"
    required = False

    domain = StringItem()
    gateway = IPv4Item()
    ip_addr = IPv4Item()
    subnet_mask = IPv4Item()


class ESXVirtualMachineInterfaceSchemaItem(ComplexSchemaItem):
    """
    Configuration Schema Item for ESX Virtual Machine Network Interface
    """

    title = "ESX Virtual Machine Network Interface Configuration"
    description = "ESX Virtual Machine network adapter properties"
    required = True

    name = StringItem(
        title="Virtual Machine Port Group",
        description="Specifies the port group name for the virtual machine connection",
        required=True,
    )
    adapter = StringItem(
        title="Virtual Machine Network Adapter",
        description=(
            "Unique name of the network adapter, "
            "for creation an arbitrary value should be specified"
        ),
        required=True,
    )
    adapter_type = StringItem(
        title="Virtual Machine Adapter Type",
        description="Network adapter type of the virtual machine",
        required=True,
        enum=("vmxnet", "vmxnet2", "vmxnet3", "e1000", "e1000e"),
        default="vmxnet3",
    )
    switch_type = StringItem(
        title="Virtual Machine Switch Type",
        description=(
            "Specifies the type of the virtual switch for the virtual machine"
            " connection"
        ),
        required=True,
        default="standard",
        enum=("standard", "distributed"),
    )
    mac = StringItem(
        title="Virtual Machine MAC Address",
        description="Mac address of the virtual machine",
        required=False,
        pattern="^([0-9a-f]{1,2}[:]){5}([0-9a-f]{1,2})$",
    )
    mapping = ESXVirtualMachineNicMapSchemaItem()
    connectable = ESXVirtualMachineDeviceConnectionItem()


class ESXVirtualMachineMemorySchemaItem(ComplexSchemaItem):
    """
    Configurtation Schema Item for ESX Virtual Machine Memory
    """

    title = "ESX Virtual Machine Memory Configuration"
    description = "ESX Virtual Machine memory property"
    required = True

    size = IntegerItem(
        title="Memory size", description="Size of the memory", required=True
    )

    unit = StringItem(
        title="Memory unit",
        description="Unit of the memory, to VMware a GB is the same as GiB = 1024MiB",
        required=False,
        default="MB",
        enum=("MB", "GB"),
    )
    hotadd = BooleanItem(required=False, default=False)
    reservation_max = BooleanItem(required=False, default=False)


class ESXVirtualMachineCpuSchemaItem(ComplexSchemaItem):
    """
    Configurtation Schema Item for ESX Virtual Machine CPU
    """

    title = "ESX Virtual Machine Memory Configuration"
    description = "ESX Virtual Machine memory property"
    required = True

    count = IntegerItem(
        title="CPU core count", description="CPU core count", required=True
    )
    cores_per_socket = IntegerItem(
        title="CPU cores per socket",
        description="CPU cores per socket count",
        required=False,
    )
    nested = BooleanItem(
        title="Virtual Machine Nested Property",
        description="Nested virtualization support",
        default=False,
    )
    hotadd = BooleanItem(
        title="Virtual Machine CPU hot add", description="CPU hot add", default=False
    )
    hotremove = BooleanItem(
        title="Virtual Machine CPU hot remove",
        description="CPU hot remove",
        default=False,
    )


class ESXVirtualMachineConfigSchema(DefinitionsSchema):
    """
    Configuration Schema for ESX Virtual Machines
    """

    title = "ESX Virtual Machine Configuration Schema"
    description = "ESX Virtual Machine configuration schema"

    vm_name = StringItem(
        title="Virtual Machine name",
        description="Name of the virtual machine",
        required=True,
    )
    cpu = ESXVirtualMachineCpuSchemaItem()
    memory = ESXVirtualMachineMemorySchemaItem()
    image = StringItem(
        title="Virtual Machine guest OS", description="Guest OS type", required=True
    )
    version = StringItem(
        title="Virtual Machine hardware version",
        description="Container hardware version property",
        required=True,
    )
    interfaces = ArrayItem(
        items=ESXVirtualMachineInterfaceSchemaItem(),
        min_items=1,
        required=False,
        unique_items=True,
    )
    disks = ArrayItem(
        items=ESXVirtualMachineDiskSchemaItem(),
        min_items=1,
        required=False,
        unique_items=True,
    )
    scsi_devices = ArrayItem(
        items=ESXVirtualMachineScsiSchemaItem(),
        min_items=1,
        required=False,
        unique_items=True,
    )
    serial_ports = ArrayItem(
        items=ESXVirtualMachineSerialSchemaItem(),
        min_items=0,
        required=False,
        unique_items=True,
    )
    cd_dvd_drives = ArrayItem(
        items=ESXVirtualMachineCdDriveSchemaItem(),
        min_items=0,
        required=False,
        unique_items=True,
    )
    sata_controllers = ArrayItem(
        items=ESXVirtualMachineSataSchemaItem(),
        min_items=0,
        required=False,
        unique_items=True,
    )
    datacenter = StringItem(
        title="Virtual Machine Datacenter",
        description="Datacenter of the virtual machine",
        required=True,
    )
    datastore = StringItem(
        title="Virtual Machine Datastore",
        description="Datastore of the virtual machine",
        required=True,
    )
    placement = ESXVirtualMachinePlacementSchemaItem()
    template = BooleanItem(
        title="Virtual Machine Template",
        description="Template to create the virtual machine from",
        default=False,
    )
    tools = BooleanItem(
        title="Virtual Machine VMware Tools",
        description="Install VMware tools on the guest machine",
        default=False,
    )
    power_on = BooleanItem(
        title="Virtual Machine Power",
        description="Power on virtual machine afret creation",
        default=False,
    )
    deploy = BooleanItem(
        title="Virtual Machine Deploy Salt",
        description="Deploy salt after successful installation",
        default=False,
    )


class ESXVirtualMachineRemoveSchema(DefinitionsSchema):
    """
    Remove Schema for ESX Virtual Machines to delete or unregister virtual machines
    """

    name = StringItem(
        title="Virtual Machine name",
        description="Name of the virtual machine",
        required=True,
    )
    datacenter = StringItem(
        title="Virtual Machine Datacenter",
        description="Datacenter of the virtual machine",
        required=True,
    )
    placement = AnyOfItem(
        required=False, items=[ESXVirtualMachinePlacementSchemaItem(), NullItem()]
    )
    power_off = BooleanItem(
        title="Power off vm",
        description="Power off vm before delete operation",
        required=False,
    )


class ESXVirtualMachineDeleteSchema(ESXVirtualMachineRemoveSchema):
    """
    Deletion Schema for ESX Virtual Machines
    """


class ESXVirtualMachineUnregisterSchema(ESXVirtualMachineRemoveSchema):
    """
    Unregister Schema for ESX Virtual Machines
    """
