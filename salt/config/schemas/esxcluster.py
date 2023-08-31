"""
    :codeauthor: :email:`Alexandru Bleotu (alexandru.bleotu@morganstanley.com)`


    salt.config.schemas.esxcluster
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ESX Cluster configuration schemas
"""


from salt.utils.schema import (
    AnyOfItem,
    ArrayItem,
    BooleanItem,
    ComplexSchemaItem,
    DefinitionsSchema,
    DictItem,
    IntegerItem,
    Schema,
    StringItem,
)


class OptionValueItem(ComplexSchemaItem):
    """Sechma item of the OptionValue"""

    title = "OptionValue"
    key = StringItem(title="Key", required=True)
    value = AnyOfItem(items=[StringItem(), BooleanItem(), IntegerItem()])


class AdmissionControlPolicyItem(ComplexSchemaItem):
    """
    Schema item of the HA admission control policy
    """

    title = "Admission Control Policy"

    cpu_failover_percent = IntegerItem(
        title="CPU Failover Percent", minimum=0, maximum=100
    )
    memory_failover_percent = IntegerItem(
        title="Memory Failover Percent", minimum=0, maximum=100
    )


class DefaultVmSettingsItem(ComplexSchemaItem):
    """
    Schema item of the HA default vm settings
    """

    title = "Default VM Settings"

    isolation_response = StringItem(
        title="Isolation Response",
        enum=["clusterIsolationResponse", "none", "powerOff", "shutdown"],
    )
    restart_priority = StringItem(
        title="Restart Priority",
        enum=["clusterRestartPriority", "disabled", "high", "low", "medium"],
    )


class HAConfigItem(ComplexSchemaItem):
    """
    Schema item of ESX cluster high availability
    """

    title = "HA Configuration"
    description = "ESX cluster HA configuration json schema item"

    enabled = BooleanItem(
        title="Enabled", description="Specifies if HA should be enabled"
    )
    admission_control_enabled = BooleanItem(title="Admission Control Enabled")
    admission_control_policy = AdmissionControlPolicyItem()
    default_vm_settings = DefaultVmSettingsItem()
    hb_ds_candidate_policy = StringItem(
        title="Heartbeat Datastore Candidate Policy",
        enum=["allFeasibleDs", "allFeasibleDsWithUserPreference", "userSelectedDs"],
    )
    host_monitoring = StringItem(
        title="Host Monitoring", choices=["enabled", "disabled"]
    )
    options = ArrayItem(min_items=1, items=OptionValueItem())
    vm_monitoring = StringItem(
        title="Vm Monitoring",
        choices=["vmMonitoringDisabled", "vmAndAppMonitoring", "vmMonitoringOnly"],
    )


class vSANClusterConfigItem(ComplexSchemaItem):
    """
    Schema item of the ESX cluster vSAN configuration
    """

    title = "vSAN Configuration"
    description = "ESX cluster vSAN configurationi item"

    enabled = BooleanItem(
        title="Enabled", description="Specifies if vSAN should be enabled"
    )
    auto_claim_storage = BooleanItem(
        title="Auto Claim Storage",
        description=(
            "Specifies whether the storage of member ESXi hosts should "
            "be automatically claimed for vSAN"
        ),
    )
    dedup_enabled = BooleanItem(
        title="Enabled", description="Specifies dedup should be enabled"
    )
    compression_enabled = BooleanItem(
        title="Enabled", description="Specifies if compression should be enabled"
    )


class DRSConfigItem(ComplexSchemaItem):
    """
    Schema item of the ESX cluster DRS configuration
    """

    title = "DRS Configuration"
    description = "ESX cluster DRS configuration item"

    enabled = BooleanItem(
        title="Enabled", description="Specifies if DRS should be enabled"
    )
    vmotion_rate = IntegerItem(
        title="vMotion rate",
        description=(
            "Aggressiveness to do automatic vMotions: "
            "1 (least aggressive) - 5 (most aggressive)"
        ),
        minimum=1,
        maximum=5,
    )
    default_vm_behavior = StringItem(
        title="Default VM DRS Behavior",
        description="Specifies the default VM DRS behavior",
        enum=["fullyAutomated", "partiallyAutomated", "manual"],
    )


class ESXClusterConfigSchema(DefinitionsSchema):
    """
    Schema of the ESX cluster config
    """

    title = "ESX Cluster Configuration Schema"
    description = "ESX cluster configuration schema"

    ha = HAConfigItem()
    vsan = vSANClusterConfigItem()
    drs = DRSConfigItem()
    vm_swap_placement = StringItem(title="VM Swap Placement")


class ESXClusterEntitySchema(Schema):
    """Schema of the ESX cluster entity"""

    title = "ESX Cluster Entity Schema"
    description = "ESX cluster entity schema"

    type = StringItem(
        title="Type",
        description="Specifies the entity type",
        required=True,
        enum=["cluster"],
    )

    datacenter = StringItem(
        title="Datacenter",
        description="Specifies the cluster datacenter",
        required=True,
        pattern=r"\w+",
    )

    cluster = StringItem(
        title="Cluster",
        description="Specifies the cluster name",
        required=True,
        pattern=r"\w+",
    )


class LicenseSchema(Schema):
    """
    Schema item of the ESX cluster vSAN configuration
    """

    title = "Licenses schema"
    description = "License configuration schema"

    licenses = DictItem(
        title="Licenses",
        description="Dictionary containing the license name to key mapping",
        required=True,
        additional_properties=StringItem(
            title="License Key",
            description="Specifies the license key",
            pattern=r"^(\w{5}-\w{5}-\w{5}-\w{5}-\w{5})$",
        ),
    )


class EsxclusterProxySchema(Schema):
    """
    Schema of the esxcluster proxy input
    """

    title = "Esxcluster Proxy Schema"
    description = "Esxcluster proxy schema"
    additional_properties = False
    proxytype = StringItem(required=True, enum=["esxcluster"])
    vcenter = StringItem(required=True, pattern=r"[^\s]+")
    datacenter = StringItem(required=True)
    cluster = StringItem(required=True)
    mechanism = StringItem(required=True, enum=["userpass", "sspi"])
    username = StringItem()
    passwords = ArrayItem(min_items=1, items=StringItem(), unique_items=True)
    # TODO Should be changed when anyOf is supported for schemas
    domain = StringItem()
    principal = StringItem()
    protocol = StringItem()
    port = IntegerItem(minimum=1)
