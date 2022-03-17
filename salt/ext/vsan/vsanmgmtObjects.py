# pylint: skip-file
from pyVmomi.VmomiSupport import (
    CreateDataType,
    CreateManagedType,
    CreateEnumType,
    AddVersion,
    AddVersionParent,
    F_LINK,
    F_LINKABLE,
    F_OPTIONAL,
)

CreateManagedType(
    "vim.cluster.VsanPerformanceManager",
    "VsanPerformanceManager",
    "vmodl.ManagedObject",
    "vim.version.version9",
    [],
    [
        (
            "setStatsObjectPolicy",
            "VsanPerfSetStatsObjectPolicy",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "profile",
                    "vim.vm.ProfileSpec",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "deleteStatsObject",
            "VsanPerfDeleteStatsObject",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "createStatsObjectTask",
            "VsanPerfCreateStatsObjectTask",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "profile",
                    "vim.vm.ProfileSpec",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "deleteStatsObjectTask",
            "VsanPerfDeleteStatsObjectTask",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "queryClusterHealth",
            "VsanPerfQueryClusterHealth",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (0, "vmodl.DynamicData[]", "vmodl.DynamicData[]"),
            "System.Read",
            None,
        ),
        (
            "queryStatsObjectInformation",
            "VsanPerfQueryStatsObjectInformation",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (
                0,
                "vim.cluster.VsanObjectInformation",
                "vim.cluster.VsanObjectInformation",
            ),
            "System.Read",
            None,
        ),
        (
            "queryNodeInformation",
            "VsanPerfQueryNodeInformation",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VsanPerfNodeInformation[]",
                "vim.cluster.VsanPerfNodeInformation[]",
            ),
            "System.Read",
            None,
        ),
        (
            "queryVsanPerf",
            "VsanPerfQueryPerf",
            "vim.version.version9",
            (
                (
                    "querySpecs",
                    "vim.cluster.VsanPerfQuerySpec[]",
                    "vim.version.version9",
                    0,
                    None,
                ),
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (
                0,
                "vim.cluster.VsanPerfEntityMetricCSV[]",
                "vim.cluster.VsanPerfEntityMetricCSV[]",
            ),
            "System.Read",
            None,
        ),
        (
            "getSupportedEntityTypes",
            "VsanPerfGetSupportedEntityTypes",
            "vim.version.version9",
            tuple(),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VsanPerfEntityType[]",
                "vim.cluster.VsanPerfEntityType[]",
            ),
            "System.Read",
            None,
        ),
        (
            "createStatsObject",
            "VsanPerfCreateStatsObject",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "profile",
                    "vim.vm.ProfileSpec",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "string", "string"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.cluster.VsanVcDiskManagementSystem",
    "VimClusterVsanVcDiskManagementSystem",
    "vmodl.ManagedObject",
    "vim.version.version10",
    [],
    [
        (
            "initializeDiskMappings",
            "InitializeDiskMappings",
            "vim.version.version10",
            (
                (
                    "spec",
                    "vim.vsan.host.DiskMappingCreationSpec",
                    "vim.version.version10",
                    0,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "retrieveAllFlashCapabilities",
            "RetrieveAllFlashCapabilities",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
            ),
            (
                0 | F_OPTIONAL,
                "vim.vsan.host.VsanHostCapability[]",
                "vim.vsan.host.VsanHostCapability[]",
            ),
            "System.Read",
            None,
        ),
        (
            "queryDiskMappings",
            "QueryDiskMappings",
            "vim.version.version10",
            (("host", "vim.HostSystem", "vim.version.version10", 0, None),),
            (
                0 | F_OPTIONAL,
                "vim.vsan.host.DiskMapInfoEx[]",
                "vim.vsan.host.DiskMapInfoEx[]",
            ),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.cluster.VsanObjectSystem",
    "VsanObjectSystem",
    "vmodl.ManagedObject",
    "vim.version.version9",
    [],
    [
        (
            "setVsanObjectPolicy",
            "VosSetVsanObjectPolicy",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                ("vsanObjectUuid", "string", "vim.version.version9", 0, None),
                (
                    "profile",
                    "vim.vm.ProfileSpec",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "queryObjectIdentities",
            "VsanQueryObjectIdentities",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                ("objUuids", "string[]", "vim.version.version9", 0 | F_OPTIONAL, None),
                (
                    "includeHealth",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "includeObjIdentity",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "includeSpaceSummary",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VsanObjectIdentityAndHealth",
                "vim.cluster.VsanObjectIdentityAndHealth",
            ),
            "System.Read",
            None,
        ),
        (
            "queryVsanObjectInformation",
            "VosQueryVsanObjectInformation",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ComputeResource",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "vsanObjectQuerySpecs",
                    "vim.cluster.VsanObjectQuerySpec[]",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (
                0,
                "vim.cluster.VsanObjectInformation[]",
                "vim.cluster.VsanObjectInformation[]",
            ),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.host.VsanStretchedClusterSystem",
    "VimHostVsanStretchedClusterSystem",
    "vmodl.ManagedObject",
    "vim.version.version10",
    [],
    [
        (
            "getStretchedClusterInfoFromCmmds",
            "VSANHostGetStretchedClusterInfoFromCmmds",
            "vim.version.version10",
            tuple(),
            (
                0 | F_OPTIONAL,
                "vim.host.VSANStretchedClusterHostInfo[]",
                "vim.host.VSANStretchedClusterHostInfo[]",
            ),
            "System.Read",
            None,
        ),
        (
            "witnessJoinVsanCluster",
            "VSANWitnessJoinVsanCluster",
            "vim.version.version10",
            (
                ("clusterUuid", "string", "vim.version.version10", 0, None),
                ("preferredFd", "string", "vim.version.version10", 0, None),
                (
                    "disableVsanAllowed",
                    "boolean",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "void", "void"),
            "System.Read",
            None,
        ),
        (
            "witnessSetPreferredFaultDomain",
            "VSANWitnessSetPreferredFaultDomain",
            "vim.version.version10",
            (("preferredFd", "string", "vim.version.version10", 0, None),),
            (0, "void", "void"),
            "System.Read",
            None,
        ),
        (
            "addUnicastAgent",
            "VSANHostAddUnicastAgent",
            "vim.version.version10",
            (
                ("witnessAddress", "string", "vim.version.version10", 0, None),
                ("witnessPort", "int", "vim.version.version10", 0 | F_OPTIONAL, None),
                ("overwrite", "boolean", "vim.version.version10", 0 | F_OPTIONAL, None),
            ),
            (0, "void", "void"),
            "System.Read",
            None,
        ),
        (
            "clusterGetPreferredFaultDomain",
            "VSANClusterGetPreferredFaultDomain",
            "vim.version.version10",
            tuple(),
            (
                0 | F_OPTIONAL,
                "vim.host.VSANCmmdsPreferredFaultDomainInfo",
                "vim.host.VSANCmmdsPreferredFaultDomainInfo",
            ),
            "System.Read",
            None,
        ),
        (
            "witnessLeaveVsanCluster",
            "VSANWitnessLeaveVsanCluster",
            "vim.version.version10",
            tuple(),
            (0, "void", "void"),
            "System.Read",
            None,
        ),
        (
            "getStretchedClusterCapability",
            "VSANHostGetStretchedClusterCapability",
            "vim.version.version10",
            tuple(),
            (
                0,
                "vim.host.VSANStretchedClusterHostCapability",
                "vim.host.VSANStretchedClusterHostCapability",
            ),
            "System.Read",
            None,
        ),
        (
            "removeUnicastAgent",
            "VSANHostRemoveUnicastAgent",
            "vim.version.version10",
            (
                ("witnessAddress", "string", "vim.version.version10", 0, None),
                (
                    "ignoreExistence",
                    "boolean",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "void", "void"),
            "System.Read",
            None,
        ),
        (
            "listUnicastAgent",
            "VSANHostListUnicastAgent",
            "vim.version.version10",
            tuple(),
            (0, "string", "string"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.VsanUpgradeSystemEx",
    "VsanUpgradeSystemEx",
    "vmodl.ManagedObject",
    "vim.version.version10",
    [],
    [
        (
            "performUpgrade",
            "PerformVsanUpgradeEx",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
                (
                    "performObjectUpgrade",
                    "boolean",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "downgradeFormat",
                    "boolean",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "allowReducedRedundancy",
                    "boolean",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "excludeHosts",
                    "vim.HostSystem[]",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "spec",
                    "vim.cluster.VsanDiskFormatConversionSpec",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "performUpgradePreflightCheck",
            "PerformVsanUpgradePreflightCheckEx",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
                (
                    "downgradeFormat",
                    "boolean",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "spec",
                    "vim.cluster.VsanDiskFormatConversionSpec",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (
                0,
                "vim.cluster.VsanDiskFormatConversionCheckResult",
                "vim.cluster.VsanDiskFormatConversionCheckResult",
            ),
            "System.Read",
            None,
        ),
        (
            "retrieveSupportedFormatVersion",
            "RetrieveSupportedVsanFormatVersion",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
            ),
            (0, "int", "int"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.cluster.VsanCapabilitySystem",
    "VsanCapabilitySystem",
    "vmodl.ManagedObject",
    "vim.version.version10",
    [],
    [
        (
            "getCapabilities",
            "VsanGetCapabilities",
            "vim.version.version10",
            (
                (
                    "targets",
                    "vmodl.ManagedObject[]",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.cluster.VsanCapability[]", "vim.cluster.VsanCapability[]"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.cluster.VsanSpaceReportSystem",
    "VsanSpaceReportSystem",
    "vmodl.ManagedObject",
    "vim.version.version9",
    [],
    [
        (
            "querySpaceUsage",
            "VsanQuerySpaceUsage",
            "vim.version.version9",
            (("cluster", "vim.ComputeResource", "vim.version.version9", 0, None),),
            (0, "vim.cluster.VsanSpaceUsage", "vim.cluster.VsanSpaceUsage"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.cluster.VsanVcClusterConfigSystem",
    "VsanVcClusterConfigSystem",
    "vmodl.ManagedObject",
    "vim.version.version10",
    [],
    [
        (
            "getConfigInfoEx",
            "VsanClusterGetConfig",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
            ),
            (0, "vim.vsan.ConfigInfoEx", "vim.vsan.ConfigInfoEx"),
            "System.Read",
            None,
        ),
        (
            "reconfigureEx",
            "VsanClusterReconfig",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
                (
                    "vsanReconfigSpec",
                    "vim.vsan.ReconfigSpec",
                    "vim.version.version10",
                    0,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.host.VsanHealthSystem",
    "HostVsanHealthSystem",
    "vmodl.ManagedObject",
    "vim.version.version9",
    [],
    [
        (
            "queryAdvCfg",
            "VsanHostQueryAdvCfg",
            "vim.version.version9",
            (("options", "string[]", "vim.version.version9", 0, None),),
            (0, "vim.option.OptionValue[]", "vim.option.OptionValue[]"),
            "System.Read",
            None,
        ),
        (
            "queryPhysicalDiskHealthSummary",
            "VsanHostQueryPhysicalDiskHealthSummary",
            "vim.version.version9",
            tuple(),
            (
                0,
                "vim.host.VsanPhysicalDiskHealthSummary",
                "vim.host.VsanPhysicalDiskHealthSummary",
            ),
            "System.Read",
            None,
        ),
        (
            "startProactiveRebalance",
            "VsanStartProactiveRebalance",
            "vim.version.version9",
            (
                ("timeSpan", "int", "vim.version.version9", 0 | F_OPTIONAL, None),
                (
                    "varianceThreshold",
                    "float",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                ("timeThreshold", "int", "vim.version.version9", 0 | F_OPTIONAL, None),
                ("rateThreshold", "int", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "queryHostInfoByUuids",
            "VsanHostQueryHostInfoByUuids",
            "vim.version.version9",
            (("uuids", "string[]", "vim.version.version9", 0, None),),
            (
                0,
                "vim.host.VsanQueryResultHostInfo[]",
                "vim.host.VsanQueryResultHostInfo[]",
            ),
            "System.Read",
            None,
        ),
        (
            "queryVersion",
            "VsanHostQueryHealthSystemVersion",
            "vim.version.version9",
            tuple(),
            (0, "string", "string"),
            "System.Read",
            None,
        ),
        (
            "queryVerifyNetworkSettings",
            "VsanHostQueryVerifyNetworkSettings",
            "vim.version.version9",
            (("peers", "string[]", "vim.version.version9", 0 | F_OPTIONAL, None),),
            (0, "vim.host.VsanNetworkHealthResult", "vim.host.VsanNetworkHealthResult"),
            "System.Read",
            None,
        ),
        (
            "queryRunIperfClient",
            "VsanHostQueryRunIperfClient",
            "vim.version.version9",
            (
                ("multicast", "boolean", "vim.version.version9", 0, None),
                ("serverIp", "string", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.host.VsanNetworkLoadTestResult",
                "vim.host.VsanNetworkLoadTestResult",
            ),
            "System.Read",
            None,
        ),
        (
            "runVmdkLoadTest",
            "VsanHostRunVmdkLoadTest",
            "vim.version.version9",
            (
                ("runname", "string", "vim.version.version9", 0, None),
                ("durationSec", "int", "vim.version.version9", 0, None),
                (
                    "specs",
                    "vim.host.VsanVmdkLoadTestSpec[]",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (
                0,
                "vim.host.VsanVmdkLoadTestResult[]",
                "vim.host.VsanVmdkLoadTestResult[]",
            ),
            "System.Read",
            None,
        ),
        (
            "queryObjectHealthSummary",
            "VsanHostQueryObjectHealthSummary",
            "vim.version.version9",
            (
                ("objUuids", "string[]", "vim.version.version9", 0 | F_OPTIONAL, None),
                (
                    "includeObjUuids",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "localHostOnly",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.host.VsanObjectOverallHealth", "vim.host.VsanObjectOverallHealth"),
            "System.Read",
            None,
        ),
        (
            "getHclInfo",
            "VsanGetHclInfo",
            "vim.version.version9",
            tuple(),
            (0, "vim.host.VsanHostHclInfo", "vim.host.VsanHostHclInfo"),
            "System.Read",
            None,
        ),
        (
            "cleanupVmdkLoadTest",
            "VsanHostCleanupVmdkLoadTest",
            "vim.version.version9",
            (
                ("runname", "string", "vim.version.version9", 0, None),
                (
                    "specs",
                    "vim.host.VsanVmdkLoadTestSpec[]",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "string", "string"),
            "System.Read",
            None,
        ),
        (
            "waitForVsanHealthGenerationIdChange",
            "VsanWaitForVsanHealthGenerationIdChange",
            "vim.version.version9",
            (("timeout", "int", "vim.version.version9", 0, None),),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "stopProactiveRebalance",
            "VsanStopProactiveRebalance",
            "vim.version.version9",
            tuple(),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "repairImmediateObjects",
            "VsanHostRepairImmediateObjects",
            "vim.version.version9",
            (
                ("uuids", "string[]", "vim.version.version9", 0 | F_OPTIONAL, None),
                ("repairType", "string", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (0, "vim.host.VsanRepairObjectsResult", "vim.host.VsanRepairObjectsResult"),
            "System.Read",
            None,
        ),
        (
            "prepareVmdkLoadTest",
            "VsanHostPrepareVmdkLoadTest",
            "vim.version.version9",
            (
                ("runname", "string", "vim.version.version9", 0, None),
                (
                    "specs",
                    "vim.host.VsanVmdkLoadTestSpec[]",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (0, "string", "string"),
            "System.Read",
            None,
        ),
        (
            "queryRunIperfServer",
            "VsanHostQueryRunIperfServer",
            "vim.version.version9",
            (
                ("multicast", "boolean", "vim.version.version9", 0, None),
                ("serverIp", "string", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (
                0,
                "vim.host.VsanNetworkLoadTestResult",
                "vim.host.VsanNetworkLoadTestResult",
            ),
            "System.Read",
            None,
        ),
        (
            "queryCheckLimits",
            "VsanHostQueryCheckLimits",
            "vim.version.version9",
            tuple(),
            (0, "vim.host.VsanLimitHealthResult", "vim.host.VsanLimitHealthResult"),
            "System.Read",
            None,
        ),
        (
            "getProactiveRebalanceInfo",
            "VsanGetProactiveRebalanceInfo",
            "vim.version.version9",
            tuple(),
            (
                0,
                "vim.host.VsanProactiveRebalanceInfoEx",
                "vim.host.VsanProactiveRebalanceInfoEx",
            ),
            "System.Read",
            None,
        ),
        (
            "checkClomdLiveness",
            "VsanHostClomdLiveness",
            "vim.version.version9",
            tuple(),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.cluster.VsanVcClusterHealthSystem",
    "VsanVcClusterHealthSystem",
    "vmodl.ManagedObject",
    "vim.version.version9",
    [],
    [
        (
            "queryClusterCreateVmHealthHistoryTest",
            "VsanQueryVcClusterCreateVmHealthHistoryTest",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("count", "int", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VsanClusterCreateVmHealthTestResult[]",
                "vim.cluster.VsanClusterCreateVmHealthTestResult[]",
            ),
            "System.Read",
            None,
        ),
        (
            "setLogLevel",
            "VsanHealthSetLogLevel",
            "vim.version.version9",
            (
                (
                    "level",
                    "vim.cluster.VsanHealthLogLevelEnum",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "void", "void"),
            "System.Read",
            None,
        ),
        (
            "testVsanClusterTelemetryProxy",
            "VsanHealthTestVsanClusterTelemetryProxy",
            "vim.version.version9",
            (
                (
                    "proxyConfig",
                    "vim.cluster.VsanClusterTelemetryProxyConfig",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "uploadHclDb",
            "VsanVcUploadHclDb",
            "vim.version.version9",
            (("db", "string", "vim.version.version9", 0, None),),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "updateHclDbFromWeb",
            "VsanVcUpdateHclDbFromWeb",
            "vim.version.version9",
            (("url", "string", "vim.version.version9", 0 | F_OPTIONAL, None),),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "repairClusterObjectsImmediate",
            "VsanHealthRepairClusterObjectsImmediate",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("uuids", "string[]", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "queryClusterNetworkPerfTest",
            "VsanQueryVcClusterNetworkPerfTest",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("multicast", "boolean", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterNetworkLoadTestResult",
                "vim.cluster.VsanClusterNetworkLoadTestResult",
            ),
            "System.Read",
            None,
        ),
        (
            "queryClusterVmdkLoadHistoryTest",
            "VsanQueryVcClusterVmdkLoadHistoryTest",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("count", "int", "vim.version.version9", 0 | F_OPTIONAL, None),
                ("taskId", "string", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VsanClusterVmdkLoadTestResult[]",
                "vim.cluster.VsanClusterVmdkLoadTestResult[]",
            ),
            "System.Read",
            None,
        ),
        (
            "queryVsanClusterHealthCheckInterval",
            "VsanHealthQueryVsanClusterHealthCheckInterval",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (0, "int", "int"),
            "System.Read",
            None,
        ),
        (
            "queryClusterCreateVmHealthTest",
            "VsanQueryVcClusterCreateVmHealthTest",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("timeout", "int", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterCreateVmHealthTestResult",
                "vim.cluster.VsanClusterCreateVmHealthTestResult",
            ),
            "System.Read",
            None,
        ),
        (
            "getClusterHclInfo",
            "VsanVcClusterGetHclInfo",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                (
                    "includeHostsResult",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.cluster.VsanClusterHclInfo", "vim.cluster.VsanClusterHclInfo"),
            "System.Read",
            None,
        ),
        (
            "queryAttachToSrHistory",
            "VsanQueryAttachToSrHistory",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("count", "int", "vim.version.version9", 0 | F_OPTIONAL, None),
                ("taskId", "string", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VsanAttachToSrOperation[]",
                "vim.cluster.VsanAttachToSrOperation[]",
            ),
            "System.Read",
            None,
        ),
        (
            "rebalanceCluster",
            "VsanRebalanceCluster",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                (
                    "targetHosts",
                    "vim.HostSystem[]",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "runVmdkLoadTest",
            "VsanVcClusterRunVmdkLoadTest",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("runname", "string", "vim.version.version9", 0, None),
                ("durationSec", "int", "vim.version.version9", 0 | F_OPTIONAL, None),
                (
                    "specs",
                    "vim.host.VsanVmdkLoadTestSpec[]",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                ("action", "string", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "sendVsanTelemetry",
            "VsanHealthSendVsanTelemetry",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (0, "void", "void"),
            "System.Read",
            None,
        ),
        (
            "queryClusterNetworkPerfHistoryTest",
            "VsanQueryVcClusterNetworkPerfHistoryTest",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("count", "int", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VsanClusterNetworkLoadTestResult[]",
                "vim.cluster.VsanClusterNetworkLoadTestResult[]",
            ),
            "System.Read",
            None,
        ),
        (
            "queryClusterHealthSummary",
            "VsanQueryVcClusterHealthSummary",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                (
                    "vmCreateTimeout",
                    "int",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                ("objUuids", "string[]", "vim.version.version9", 0 | F_OPTIONAL, None),
                (
                    "includeObjUuids",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                ("fields", "string[]", "vim.version.version9", 0 | F_OPTIONAL, None),
                (
                    "fetchFromCache",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (
                0,
                "vim.cluster.VsanClusterHealthSummary",
                "vim.cluster.VsanClusterHealthSummary",
            ),
            "System.Read",
            None,
        ),
        (
            "stopRebalanceCluster",
            "VsanStopRebalanceCluster",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                (
                    "targetHosts",
                    "vim.HostSystem[]",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "queryVsanClusterHealthConfig",
            "VsanHealthQueryVsanClusterHealthConfig",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (
                0,
                "vim.cluster.VsanClusterHealthConfigs",
                "vim.cluster.VsanClusterHealthConfigs",
            ),
            "System.Read",
            None,
        ),
        (
            "attachVsanSupportBundleToSr",
            "VsanAttachVsanSupportBundleToSr",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                ("srNumber", "string", "vim.version.version9", 0, None),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "queryClusterVmdkWorkloadTypes",
            "VsanQueryVcClusterVmdkWorkloadTypes",
            "vim.version.version9",
            tuple(),
            (
                0,
                "vim.cluster.VsanStorageWorkloadType[]",
                "vim.cluster.VsanStorageWorkloadType[]",
            ),
            "System.Read",
            None,
        ),
        (
            "queryVerifyClusterHealthSystemVersions",
            "VsanVcClusterQueryVerifyHealthSystemVersions",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (
                0,
                "vim.cluster.VsanClusterHealthSystemVersionResult",
                "vim.cluster.VsanClusterHealthSystemVersionResult",
            ),
            "System.Read",
            None,
        ),
        (
            "isRebalanceRunning",
            "VsanHealthIsRebalanceRunning",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                (
                    "targetHosts",
                    "vim.HostSystem[]",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "setVsanClusterHealthCheckInterval",
            "VsanHealthSetVsanClusterHealthCheckInterval",
            "vim.version.version9",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version9",
                    0,
                    None,
                ),
                (
                    "vsanClusterHealthCheckInterval",
                    "int",
                    "vim.version.version9",
                    0,
                    None,
                ),
            ),
            (0, "void", "void"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.cluster.VsanVcStretchedClusterSystem",
    "VimClusterVsanVcStretchedClusterSystem",
    "vmodl.ManagedObject",
    "vim.version.version10",
    [],
    [
        (
            "isWitnessHost",
            "VSANVcIsWitnessHost",
            "vim.version.version10",
            (("host", "vim.HostSystem", "vim.version.version10", 0, None),),
            (0, "boolean", "boolean"),
            "System.Read",
            None,
        ),
        (
            "setPreferredFaultDomain",
            "VSANVcSetPreferredFaultDomain",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
                ("preferredFd", "string", "vim.version.version10", 0, None),
                (
                    "witnessHost",
                    "vim.HostSystem",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "getPreferredFaultDomain",
            "VSANVcGetPreferredFaultDomain",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VSANPreferredFaultDomainInfo",
                "vim.cluster.VSANPreferredFaultDomainInfo",
            ),
            "System.Read",
            None,
        ),
        (
            "getWitnessHosts",
            "VSANVcGetWitnessHosts",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VSANWitnessHostInfo[]",
                "vim.cluster.VSANWitnessHostInfo[]",
            ),
            "System.Read",
            None,
        ),
        (
            "retrieveStretchedClusterVcCapability",
            "VSANVcRetrieveStretchedClusterVcCapability",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
                (
                    "verifyAllConnected",
                    "boolean",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (
                0 | F_OPTIONAL,
                "vim.cluster.VSANStretchedClusterCapability[]",
                "vim.cluster.VSANStretchedClusterCapability[]",
            ),
            "System.Read",
            None,
        ),
        (
            "convertToStretchedCluster",
            "VSANVcConvertToStretchedCluster",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
                (
                    "faultDomainConfig",
                    "vim.cluster.VSANStretchedClusterFaultDomainConfig",
                    "vim.version.version10",
                    0,
                    None,
                ),
                ("witnessHost", "vim.HostSystem", "vim.version.version10", 0, None),
                ("preferredFd", "string", "vim.version.version10", 0, None),
                (
                    "diskMapping",
                    "vim.vsan.host.DiskMapping",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
        (
            "removeWitnessHost",
            "VSANVcRemoveWitnessHost",
            "vim.version.version10",
            (
                (
                    "cluster",
                    "vim.ClusterComputeResource",
                    "vim.version.version10",
                    0,
                    None,
                ),
                (
                    "witnessHost",
                    "vim.HostSystem",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "witnessAddress",
                    "string",
                    "vim.version.version10",
                    0 | F_OPTIONAL,
                    None,
                ),
            ),
            (0, "vim.Task", "vim.Task"),
            "System.Read",
            None,
        ),
    ],
)
CreateManagedType(
    "vim.cluster.VsanClusterHealthSystem",
    "VsanClusterHealthSystem",
    "vmodl.ManagedObject",
    "vim.version.version9",
    [],
    [
        (
            "queryPhysicalDiskHealthSummary",
            "VsanQueryClusterPhysicalDiskHealthSummary",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.host.VsanPhysicalDiskHealthSummary[]",
                "vim.host.VsanPhysicalDiskHealthSummary[]",
            ),
            "System.Read",
            None,
        ),
        (
            "queryClusterNetworkPerfTest",
            "VsanQueryClusterNetworkPerfTest",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
                ("multicast", "boolean", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterNetworkLoadTestResult",
                "vim.cluster.VsanClusterNetworkLoadTestResult",
            ),
            "System.Read",
            None,
        ),
        (
            "queryAdvCfgSync",
            "VsanQueryClusterAdvCfgSync",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterAdvCfgSyncResult[]",
                "vim.cluster.VsanClusterAdvCfgSyncResult[]",
            ),
            "System.Read",
            None,
        ),
        (
            "repairClusterImmediateObjects",
            "VsanRepairClusterImmediateObjects",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
                ("uuids", "string[]", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterHealthSystemObjectsRepairResult",
                "vim.cluster.VsanClusterHealthSystemObjectsRepairResult",
            ),
            "System.Read",
            None,
        ),
        (
            "queryVerifyClusterNetworkSettings",
            "VsanQueryVerifyClusterNetworkSettings",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterNetworkHealthResult",
                "vim.cluster.VsanClusterNetworkHealthResult",
            ),
            "System.Read",
            None,
        ),
        (
            "queryClusterCreateVmHealthTest",
            "VsanQueryClusterCreateVmHealthTest",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
                ("timeout", "int", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterCreateVmHealthTestResult",
                "vim.cluster.VsanClusterCreateVmHealthTestResult",
            ),
            "System.Read",
            None,
        ),
        (
            "queryClusterHealthSystemVersions",
            "VsanQueryClusterHealthSystemVersions",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterHealthSystemVersionResult",
                "vim.cluster.VsanClusterHealthSystemVersionResult",
            ),
            "System.Read",
            None,
        ),
        (
            "getClusterHclInfo",
            "VsanClusterGetHclInfo",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
            ),
            (0, "vim.cluster.VsanClusterHclInfo", "vim.cluster.VsanClusterHclInfo"),
            "System.Read",
            None,
        ),
        (
            "queryCheckLimits",
            "VsanQueryClusterCheckLimits",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterLimitHealthResult",
                "vim.cluster.VsanClusterLimitHealthResult",
            ),
            "System.Read",
            None,
        ),
        (
            "queryCaptureVsanPcap",
            "VsanQueryClusterCaptureVsanPcap",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
                ("duration", "int", "vim.version.version9", 0, None),
                (
                    "vmknic",
                    "vim.cluster.VsanClusterHostVmknicMapping[]",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "includeRawPcap",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "includeIgmp",
                    "boolean",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                (
                    "cmmdsMsgTypeFilter",
                    "string[]",
                    "vim.version.version9",
                    0 | F_OPTIONAL,
                    None,
                ),
                ("cmmdsPorts", "int[]", "vim.version.version9", 0 | F_OPTIONAL, None),
                ("clusterUuid", "string", "vim.version.version9", 0 | F_OPTIONAL, None),
            ),
            (
                0,
                "vim.cluster.VsanVsanClusterPcapResult",
                "vim.cluster.VsanVsanClusterPcapResult",
            ),
            "System.Read",
            None,
        ),
        (
            "checkClusterClomdLiveness",
            "VsanCheckClusterClomdLiveness",
            "vim.version.version9",
            (
                ("hosts", "string[]", "vim.version.version9", 0, None),
                ("esxRootPassword", "string", "vim.version.version9", 0, None),
            ),
            (
                0,
                "vim.cluster.VsanClusterClomdLivenessResult",
                "vim.cluster.VsanClusterClomdLivenessResult",
            ),
            "System.Read",
            None,
        ),
    ],
)
CreateDataType(
    "vim.host.VSANCmmdsNodeInfo",
    "VimHostVSANCmmdsNodeInfo",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("nodeUuid", "string", "vim.version.version10", 0),
        ("isWitness", "boolean", "vim.version.version10", 0),
    ],
)
CreateDataType(
    "vim.host.VsanPhysicalDiskHealth",
    "VsanPhysicalDiskHealth",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("name", "string", "vim.version.version9", 0),
        ("uuid", "string", "vim.version.version9", 0),
        ("inCmmds", "boolean", "vim.version.version9", 0),
        ("inVsi", "boolean", "vim.version.version9", 0),
        ("dedupScope", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("formatVersion", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("isAllFlash", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("congestionValue", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("congestionArea", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("congestionHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("metadataHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "operationalHealthDescription",
            "string",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("operationalHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("dedupUsageHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("capacityHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("summaryHealth", "string", "vim.version.version9", 0),
        ("capacity", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("usedCapacity", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("reservedCapacity", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("totalBytes", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("freeBytes", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("hashedBytes", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("dedupedBytes", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("scsiDisk", "vim.host.ScsiDisk", "vim.version.version9", 0 | F_OPTIONAL),
        ("usedComponents", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("maxComponents", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("compLimitHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.vsan.DataEfficiencyConfig",
    "VsanDataEfficiencyConfig",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("dedupEnabled", "boolean", "vim.version.version10", 0),
        ("compressionEnabled", "boolean", "vim.version.version10", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.StorageComplianceResult",
    "VsanStorageComplianceResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("checkTime", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        ("profile", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("objectUUID", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "complianceStatus",
            "vim.cluster.StorageComplianceStatus",
            "vim.version.version9",
            0,
        ),
        ("mismatch", "boolean", "vim.version.version9", 0),
        (
            "violatedPolicies",
            "vim.cluster.StoragePolicyStatus[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "operationalStatus",
            "vim.cluster.StorageOperationalStatus",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthGroup",
    "VsanClusterHealthGroup",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("groupId", "string", "vim.version.version9", 0),
        ("groupName", "string", "vim.version.version9", 0),
        ("groupHealth", "string", "vim.version.version9", 0),
        (
            "groupTests",
            "vim.cluster.VsanClusterHealthTest[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "groupDetails",
            "vim.cluster.VsanClusterHealthResultBase[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanSpaceUsageDetailResult",
    "VsanSpaceUsageDetailResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "spaceUsageByObjectType",
            "vim.cluster.VsanObjectSpaceSummary[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        )
    ],
)
CreateDataType(
    "vim.cluster.VsanAttachToSrOperation",
    "VsanAttachToSrOperation",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("task", "vim.Task", "vim.version.version9", 0 | F_OPTIONAL),
        ("success", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("timestamp", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        ("srNumber", "string", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanObjectSpaceSummary",
    "VsanObjectSpaceSummary",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "objType",
            "vim.cluster.VsanObjectTypeEnum",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("overheadB", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("temporaryOverheadB", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("primaryCapacityB", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("provisionCapacityB", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("reservedCapacityB", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("overReservedB", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("physicalUsedB", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("usedB", "long", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHclInfo",
    "VsanClusterHclInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hclDbLastUpdate", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        ("hclDbAgeHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "hostResults",
            "vim.host.VsanHostHclInfo[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanPerfGraph",
    "VsanPerfGraph",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("id", "string", "vim.version.version9", 0),
        ("metrics", "vim.cluster.VsanPerfMetricId[]", "vim.version.version9", 0),
        ("unit", "vim.cluster.VsanPerfStatsUnitType", "vim.version.version9", 0),
        (
            "threshold",
            "vim.cluster.VsanPerfThreshold",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("name", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("description", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthResultBase",
    "VsanClusterHealthResultBase",
    "vmodl.DynamicData",
    "vim.version.version9",
    [("label", "string", "vim.version.version9", 0 | F_OPTIONAL)],
)
CreateDataType(
    "vim.cluster.VsanPerfTopEntity",
    "VsanPerfTopEntity",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("entityRefId", "string", "vim.version.version9", 0),
        ("value", "string", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterBalancePerDiskInfo",
    "VsanClusterBalancePerDiskInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("uuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("fullness", "long", "vim.version.version9", 0),
        ("variance", "long", "vim.version.version9", 0),
        ("fullnessAboveThreshold", "long", "vim.version.version9", 0),
        ("dataToMoveB", "long", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthTest",
    "VsanClusterHealthTest",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("testId", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("testName", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("testDescription", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("testShortDescription", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("testHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "testDetails",
            "vim.cluster.VsanClusterHealthResultBase[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "testActions",
            "vim.cluster.VsanClusterHealthAction[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.StoragePolicyStatus",
    "VsanStoragePolicyStatus",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("id", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("expectedValue", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("currentValue", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanPerfMemberInfo",
    "VsanPerfMemberInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [("thumbprint", "string", "vim.version.version9", 0)],
)
CreateDataType(
    "vim.cluster.VsanPerfMetricId",
    "VsanPerfMetricId",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("label", "string", "vim.version.version9", 0),
        ("group", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "rollupType",
            "vim.cluster.VsanPerfSummaryType",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "statsType",
            "vim.cluster.VsanPerfStatsType",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("name", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("description", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("metricsCollectInterval", "int", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VSANWitnessHostInfo",
    "VimClusterVSANWitnessHostInfo",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("nodeUuid", "string", "vim.version.version10", 0),
        ("faultDomainName", "string", "vim.version.version10", 0 | F_OPTIONAL),
        ("preferredFdName", "string", "vim.version.version10", 0 | F_OPTIONAL),
        ("preferredFdUuid", "string", "vim.version.version10", 0 | F_OPTIONAL),
        ("unicastAgentAddr", "string", "vim.version.version10", 0 | F_OPTIONAL),
        ("host", "vim.HostSystem", "vim.version.version10", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanHealthExtMgmtPreCheckResult",
    "VsanHealthExtMgmtPreCheckResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("overallResult", "boolean", "vim.version.version9", 0),
        ("esxVersionCheckPassed", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("drsCheckPassed", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("eamConnectionCheckPassed", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("installStateCheckPassed", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("results", "vim.cluster.VsanClusterHealthTest[]", "vim.version.version9", 0),
        ("vumRegistered", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.vsan.upgradesystem.HostWithHybridDiskgroupIssue",
    "VsanHostWithHybridDiskgroupIssue",
    "vim.VsanUpgradeSystem.PreflightCheckIssue",
    "vim.version.version10",
    [("hosts", "vim.HostSystem[]", "vim.version.version10", 0)],
)
CreateDataType(
    "vim.cluster.VsanPerfMetricSeriesCSV",
    "VsanPerfMetricSeriesCSV",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("metricId", "vim.cluster.VsanPerfMetricId", "vim.version.version9", 0),
        ("values", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanPerfQuerySpec",
    "VsanPerfQuerySpec",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("entityRefId", "string", "vim.version.version9", 0),
        ("startTime", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        ("endTime", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        ("group", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("labels", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("interval", "int", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanRepairObjectsResult",
    "VsanRepairObjectsResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("inQueueObjects", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "failedRepairObjects",
            "vim.host.VsanFailedRepairObjectResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("notInQueueObjects", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterNetworkPartitionInfo",
    "VsanClusterNetworkPartitionInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [("hosts", "string[]", "vim.version.version9", 0 | F_OPTIONAL)],
)
CreateDataType(
    "vim.vsan.upgradesystem.MixedEsxVersionIssue",
    "VsanMixedEsxVersionIssue",
    "vim.VsanUpgradeSystem.PreflightCheckIssue",
    "vim.version.version10",
    [],
)
CreateDataType(
    "vim.cluster.VsanClusterClomdLivenessResult",
    "VsanClusterClomdLivenessResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "clomdLivenessResult",
            "vim.cluster.VsanHostClomdLivenessResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("issueFound", "boolean", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanVsanClusterPcapResult",
    "VsanVsanClusterPcapResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("pkts", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "groups",
            "vim.cluster.VsanVsanClusterPcapGroup[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("issues", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "hostResults",
            "vim.host.VsanVsanPcapResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanPerfMasterInformation",
    "VsanPerfMasterInformation",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("secSinceLastStatsWrite", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("secSinceLastStatsCollect", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("statsIntervalSec", "long", "vim.version.version9", 0),
        (
            "collectionFailureHostUuids",
            "string[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("renamedStatsDirectories", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("statsDirectoryPercentFree", "long", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanHostCreateVmHealthTestResult",
    "VsanHostCreateVmHealthTestResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0),
        ("state", "string", "vim.version.version9", 0),
        ("fault", "vmodl.MethodFault", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanDiskFormatConversionCheckResult",
    "VsanDiskFormatConversionCheckResult",
    "vim.VsanUpgradeSystem.PreflightCheckResult",
    "vim.version.version10",
    [
        ("isSupported", "boolean", "vim.version.version10", 0),
        ("targetVersion", "int", "vim.version.version10", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthSystemObjectsRepairResult",
    "VsanClusterHealthSystemObjectsRepairResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("inRepairingQueueObjects", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "failedRepairObjects",
            "vim.host.VsanFailedRepairObjectResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("issueFound", "boolean", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.host.VsanHostHclInfo",
    "VsanHostHclInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0),
        ("hclChecked", "boolean", "vim.version.version9", 0),
        ("releaseName", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("error", "vmodl.MethodFault", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "controllers",
            "vim.host.VsanHclControllerInfo[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VSANStretchedClusterCapability",
    "VimClusterVSANStretchedClusterCapability",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("hostMoId", "string", "vim.version.version10", 0),
        ("connStatus", "string", "vim.version.version10", 0 | F_OPTIONAL),
        ("isSupported", "boolean", "vim.version.version10", 0 | F_OPTIONAL),
        (
            "hostCapability",
            "vim.host.VSANStretchedClusterHostCapability",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanDiskMappingsConfigSpec",
    "VimClusterVsanDiskMappingsConfigSpec",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        (
            "hostDiskMappings",
            "vim.cluster.VsanHostDiskMapping[]",
            "vim.version.version10",
            0,
        )
    ],
)
CreateDataType(
    "vim.host.VsanHostVmdkLoadTestResult",
    "VsanHostVmdkLoadTestResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0),
        ("issueFound", "boolean", "vim.version.version9", 0),
        ("faultMessage", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "vmdkResults",
            "vim.host.VsanVmdkLoadTestResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.vsan.ReconfigSpec",
    "VimVsanReconfigSpec",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        (
            "vsanClusterConfig",
            "vim.vsan.cluster.ConfigInfo",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
        (
            "dataEfficiencyConfig",
            "vim.vsan.DataEfficiencyConfig",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
        (
            "diskMappingSpec",
            "vim.cluster.VsanDiskMappingsConfigSpec",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
        (
            "faultDomainsSpec",
            "vim.cluster.VsanFaultDomainsConfigSpec",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
        ("modify", "boolean", "vim.version.version10", 0),
        ("allowReducedRedundancy", "boolean", "vim.version.version10", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanNetworkPeerHealthResult",
    "VsanNetworkPeerHealthResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("peer", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("peerHostname", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("peerVmknicName", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("smallPingTestSuccessPct", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("largePingTestSuccessPct", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("maxLatencyUs", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("onSameIpSubnet", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("sourceVmknicName", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanWitnessSpec",
    "VimClusterVsanWitnessSpec",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("host", "vim.HostSystem", "vim.version.version10", 0),
        ("preferredFaultDomainName", "string", "vim.version.version10", 0),
        (
            "diskMapping",
            "vim.vsan.host.DiskMapping",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.vsan.host.DiskMappingCreationSpec",
    "VimVsanHostDiskMappingCreationSpec",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("host", "vim.HostSystem", "vim.version.version10", 0),
        ("cacheDisks", "vim.host.ScsiDisk[]", "vim.version.version10", 0 | F_OPTIONAL),
        ("capacityDisks", "vim.host.ScsiDisk[]", "vim.version.version10", 0),
        (
            "creationType",
            "vim.vsan.host.DiskMappingCreationType",
            "vim.version.version10",
            0,
        ),
    ],
)
CreateDataType(
    "vim.host.VsanLimitHealthResult",
    "VsanLimitHealthResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("issueFound", "boolean", "vim.version.version9", 0),
        ("maxComponents", "int", "vim.version.version9", 0),
        ("freeComponents", "int", "vim.version.version9", 0),
        ("componentLimitHealth", "string", "vim.version.version9", 0),
        ("lowestFreeDiskSpacePct", "int", "vim.version.version9", 0),
        ("usedDiskSpaceB", "long", "vim.version.version9", 0),
        ("totalDiskSpaceB", "long", "vim.version.version9", 0),
        ("diskFreeSpaceHealth", "string", "vim.version.version9", 0),
        ("reservedRcSizeB", "long", "vim.version.version9", 0),
        ("totalRcSizeB", "long", "vim.version.version9", 0),
        ("rcFreeReservationHealth", "string", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VSANPreferredFaultDomainInfo",
    "VimClusterVSANPreferredFaultDomainInfo",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("preferredFaultDomainName", "string", "vim.version.version10", 0),
        ("preferredFaultDomainId", "string", "vim.version.version10", 0),
    ],
)
CreateDataType(
    "vim.host.VsanObjectOverallHealth",
    "VsanObjectOverallHealth",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "objectHealthDetail",
            "vim.host.VsanObjectHealth[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("objectVersionCompliance", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanVsanClusterPcapGroup",
    "VsanVsanClusterPcapGroup",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("master", "string", "vim.version.version9", 0),
        ("members", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthResultColumnInfo",
    "VsanClusterHealthResultColumnInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("label", "string", "vim.version.version9", 0),
        ("type", "string", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterNetworkHealthResult",
    "VsanClusterNetworkHealthResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "hostResults",
            "vim.host.VsanNetworkHealthResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("issueFound", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("vsanVmknicPresent", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("matchingMulticastConfig", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("matchingIpSubnets", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("pingTestSuccess", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("largePingTestSuccess", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("potentialMulticastIssue", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("otherHostsInVsanCluster", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "partitions",
            "vim.cluster.VsanClusterNetworkPartitionInfo[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("hostsWithVsanDisabled", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("hostsDisconnected", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("hostsCommFailure", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "hostsInEsxMaintenanceMode",
            "string[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "hostsInVsanMaintenanceMode",
            "string[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "infoAboutUnexpectedHosts",
            "vim.host.VsanQueryResultHostInfo[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanPerfNodeInformation",
    "VsanPerfNodeInformation",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("version", "string", "vim.version.version9", 0),
        ("hostname", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("error", "vmodl.MethodFault", "vim.version.version9", 0 | F_OPTIONAL),
        ("isCmmdsMaster", "boolean", "vim.version.version9", 0),
        ("isStatsMaster", "boolean", "vim.version.version9", 0),
        ("vsanMasterUuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("vsanNodeUuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "masterInfo",
            "vim.cluster.VsanPerfMasterInformation",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanPerfEntityMetricCSV",
    "VsanPerfEntityMetricCSV",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("entityRefId", "string", "vim.version.version9", 0),
        ("sampleInfo", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "value",
            "vim.cluster.VsanPerfMetricSeriesCSV[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.vsan.upgradesystem.DiskUnhealthIssue",
    "VsanDiskUnhealthIssue",
    "vim.VsanUpgradeSystem.PreflightCheckIssue",
    "vim.version.version10",
    [("uuids", "string[]", "vim.version.version10", 0)],
)
CreateDataType(
    "vim.cluster.VsanFaultDomainSpec",
    "VimClusterVsanFaultDomainSpec",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("hosts", "vim.HostSystem[]", "vim.version.version10", 0),
        ("name", "string", "vim.version.version10", 0),
    ],
)
CreateDataType(
    "vim.vsan.upgradesystem.ObjectInaccessibleIssue",
    "VsanObjectInaccessibleIssue",
    "vim.VsanUpgradeSystem.PreflightCheckIssue",
    "vim.version.version10",
    [("uuids", "string[]", "vim.version.version10", 0)],
)
CreateDataType(
    "vim.cluster.VsanDiskFormatConversionSpec",
    "VsanDiskFormatConversionSpec",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        (
            "dataEfficiencyConfig",
            "vim.vsan.DataEfficiencyConfig",
            "vim.version.version10",
            0 | F_OPTIONAL,
        )
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthAction",
    "VsanClusterHealthAction",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "actionId",
            "vim.cluster.VsanClusterHealthActionIdEnum",
            "vim.version.version9",
            0,
        ),
        ("actionLabel", "vmodl.LocalizableMessage", "vim.version.version9", 0),
        ("actionDescription", "vmodl.LocalizableMessage", "vim.version.version9", 0),
        ("enabled", "boolean", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthSystemVersionResult",
    "VsanClusterHealthSystemVersionResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "hostResults",
            "vim.cluster.VsanHostHealthSystemVersionResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("vcVersion", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("issueFound", "boolean", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthResultRow",
    "VsanClusterHealthResultRow",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("values", "string[]", "vim.version.version9", 0),
        (
            "nestedRows",
            "vim.cluster.VsanClusterHealthResultRow[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthSystemStatusResult",
    "VsanClusterHealthSystemStatusResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("status", "string", "vim.version.version9", 0),
        ("goalState", "string", "vim.version.version9", 0),
        ("untrackedHosts", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "trackedHostsStatus",
            "vim.host.VsanHostHealthSystemStatusResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanHostDiskMapping",
    "VimClusterVsanHostDiskMapping",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("host", "vim.HostSystem", "vim.version.version10", 0),
        ("cacheDisks", "vim.host.ScsiDisk[]", "vim.version.version10", 0 | F_OPTIONAL),
        ("capacityDisks", "vim.host.ScsiDisk[]", "vim.version.version10", 0),
        ("type", "vim.cluster.VsanDiskGroupCreationType", "vim.version.version10", 0),
    ],
)
CreateDataType(
    "vim.cluster.VSANStretchedClusterFaultDomainConfig",
    "VimClusterVSANStretchedClusterFaultDomainConfig",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("firstFdName", "string", "vim.version.version10", 0),
        ("firstFdHosts", "vim.HostSystem[]", "vim.version.version10", 0),
        ("secondFdName", "string", "vim.version.version10", 0),
        ("secondFdHosts", "vim.HostSystem[]", "vim.version.version10", 0),
    ],
)
CreateDataType(
    "vim.host.VSANStretchedClusterHostInfo",
    "VimHostVSANStretchedClusterHostInfo",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("nodeInfo", "vim.host.VSANCmmdsNodeInfo", "vim.version.version10", 0),
        (
            "faultDomainInfo",
            "vim.host.VSANCmmdsFaultDomainInfo",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
        (
            "preferredFaultDomainInfo",
            "vim.host.VSANCmmdsPreferredFaultDomainInfo",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.vsan.upgradesystem.HigherObjectsPresentDuringDowngradeIssue",
    "VsanHigherObjectsPresentDuringDowngradeIssue",
    "vim.VsanUpgradeSystem.PreflightCheckIssue",
    "vim.version.version10",
    [("uuids", "string[]", "vim.version.version10", 0)],
)
CreateDataType(
    "vim.host.VSANCmmdsFaultDomainInfo",
    "VimHostVSANCmmdsFaultDomainInfo",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("faultDomainId", "string", "vim.version.version10", 0),
        ("faultDomainName", "string", "vim.version.version10", 0),
    ],
)
CreateDataType(
    "vim.fault.VsanNodeNotMaster",
    "VsanNodeNotMaster",
    "vim.fault.VimFault",
    "vim.version.version9",
    [
        ("vsanMasterUuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "cmmdsMasterButNotStatsMaster",
            "boolean",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanHostHealthSystemVersionResult",
    "VsanHostHealthSystemVersionResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0),
        ("version", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("error", "vmodl.MethodFault", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthConfigs",
    "VsanClusterHealthConfigs",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("enableVsanTelemetry", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("vsanTelemetryInterval", "int", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "vsanTelemetryProxy",
            "vim.cluster.VsanClusterTelemetryProxyConfig",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "configs",
            "vim.cluster.VsanClusterHealthResultKeyValuePair[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterWhatifHostFailuresResult",
    "VsanClusterWhatifHostFailuresResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("numFailures", "long", "vim.version.version9", 0),
        ("totalUsedCapacityB", "long", "vim.version.version9", 0),
        ("totalCapacityB", "long", "vim.version.version9", 0),
        ("totalRcReservationB", "long", "vim.version.version9", 0),
        ("totalRcSizeB", "long", "vim.version.version9", 0),
        ("usedComponents", "long", "vim.version.version9", 0),
        ("totalComponents", "long", "vim.version.version9", 0),
        ("componentLimitHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("diskFreeSpaceHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("rcFreeReservationHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanObjectIdentityAndHealth",
    "VsanObjectIdentityAndHealth",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "identities",
            "vim.cluster.VsanObjectIdentity[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "health",
            "vim.host.VsanObjectOverallHealth",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "spaceSummary",
            "vim.cluster.VsanObjectSpaceSummary[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("rawData", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanHclControllerInfo",
    "VsanHclControllerInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("deviceName", "string", "vim.version.version9", 0),
        ("deviceDisplayName", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("driverName", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("driverVersion", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("vendorId", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("deviceId", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("subVendorId", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("subDeviceId", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("extraInfo", "vim.KeyValue[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("deviceOnHcl", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("releaseSupported", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("releasesOnHcl", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("driverVersionsOnHcl", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("driverVersionSupported", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("fwVersionSupported", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("fwVersionOnHcl", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("cacheConfigSupported", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("cacheConfigOnHcl", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("raidConfigSupported", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("raidConfigOnHcl", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("fwVersion", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("raidConfig", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("cacheConfig", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "cimProviderInfo",
            "vim.host.VsanHostCimProviderInfo",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthResultKeyValuePair",
    "VsanClusterHealthResultKeyValuePair",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("key", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("value", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.StorageOperationalStatus",
    "VsanStorageOperationalStatus",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("healthy", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("operationETA", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        ("operationProgress", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("transitional", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanSpaceUsage",
    "VsanSpaceUsage",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("totalCapacityB", "long", "vim.version.version9", 0),
        ("freeCapacityB", "long", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "spaceOverview",
            "vim.cluster.VsanObjectSpaceSummary",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "spaceDetail",
            "vim.cluster.VsanSpaceUsageDetailResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthResultTable",
    "VsanClusterHealthResultTable",
    "vim.cluster.VsanClusterHealthResultBase",
    "vim.version.version9",
    [
        (
            "columns",
            "vim.cluster.VsanClusterHealthResultColumnInfo[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "rows",
            "vim.cluster.VsanClusterHealthResultRow[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterConfig",
    "VsanClusterConfig",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("config", "vim.vsan.cluster.ConfigInfo", "vim.version.version9", 0),
        ("name", "string", "vim.version.version9", 0),
        ("hosts", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.vsan.host.VsanHostCapability",
    "VimVsanHostVsanHostCapability",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("host", "vim.HostSystem", "vim.version.version10", 0),
        ("isSupported", "boolean", "vim.version.version10", 0),
        ("isLicensed", "boolean", "vim.version.version10", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanPerfThreshold",
    "VsanPerfThreshold",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "direction",
            "vim.cluster.VsanPerfThresholdDirectionType",
            "vim.version.version9",
            0,
        ),
        ("yellow", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("red", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanNetworkHealthResult",
    "VsanNetworkHealthResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("host", "vim.HostSystem", "vim.version.version9", 0 | F_OPTIONAL),
        ("hostname", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("vsanVmknicPresent", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("ipSubnets", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("issueFound", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "peerHealth",
            "vim.host.VsanNetworkPeerHealthResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("multicastConfig", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.vsan.ConfigInfoEx",
    "VsanConfigInfoEx",
    "vim.vsan.cluster.ConfigInfo",
    "vim.version.version10",
    [
        (
            "dataEfficiencyConfig",
            "vim.vsan.DataEfficiencyConfig",
            "vim.version.version10",
            0 | F_OPTIONAL,
        )
    ],
)
CreateDataType(
    "vim.host.VsanVmdkLoadTestResult",
    "VsanVmdkLoadTestResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("success", "boolean", "vim.version.version9", 0),
        ("faultMessage", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("spec", "vim.host.VsanVmdkLoadTestSpec", "vim.version.version9", 0),
        ("actualDurationSec", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("totalBytes", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("iops", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("tputBps", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("avgLatencyUs", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("maxLatencyUs", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("numIoAboveLatencyThreshold", "long", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterVMsHealthOverallResult",
    "VsanClusterVMsHealthOverAllResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "healthStateList",
            "vim.cluster.VsanClusterVMsHealthSummaryResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("overallHealthState", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanHostHealthSystemStatusResult",
    "VsanHostHealthSystemStatusResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0),
        ("status", "string", "vim.version.version9", 0),
        ("issues", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterAdvCfgSyncResult",
    "VsanClusterAdvCfgSyncResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("inSync", "boolean", "vim.version.version9", 0),
        ("name", "string", "vim.version.version9", 0),
        (
            "hostValues",
            "vim.cluster.VsanClusterAdvCfgSyncHostResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.host.VsanQueryResultHostInfo",
    "VsanQueryResultHostInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("uuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("hostnameInCmmds", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("vsanIpv4Addresses", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.vsan.host.DiskMapInfoEx",
    "VimVsanHostDiskMapInfoEx",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("mapping", "vim.vsan.host.DiskMapping", "vim.version.version10", 0),
        ("isMounted", "boolean", "vim.version.version10", 0),
        ("isAllFlash", "boolean", "vim.version.version10", 0),
        ("isDataEfficiency", "boolean", "vim.version.version10", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanVmdkLoadTestSpec",
    "VsanVmdkLoadTestSpec",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "vmdkCreateSpec",
            "vim.VirtualDiskManager.FileBackedVirtualDiskSpec",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "vmdkIOSpec",
            "vim.host.VsanVmdkIOLoadSpec",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "vmdkIOSpecSequence",
            "vim.host.VsanVmdkIOLoadSpec[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("stepDurationSec", "long", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHealthSummary",
    "VsanClusterHealthSummary",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "clusterStatus",
            "vim.cluster.VsanClusterHealthSystemStatusResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("timestamp", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "clusterVersions",
            "vim.cluster.VsanClusterHealthSystemVersionResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "objectHealth",
            "vim.host.VsanObjectOverallHealth",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "vmHealth",
            "vim.cluster.VsanClusterVMsHealthOverallResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "networkHealth",
            "vim.cluster.VsanClusterNetworkHealthResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "limitHealth",
            "vim.cluster.VsanClusterLimitHealthResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "advCfgSync",
            "vim.cluster.VsanClusterAdvCfgSyncResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "createVmHealth",
            "vim.cluster.VsanHostCreateVmHealthTestResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "physicalDisksHealth",
            "vim.host.VsanPhysicalDiskHealthSummary[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "hclInfo",
            "vim.cluster.VsanClusterHclInfo",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "groups",
            "vim.cluster.VsanClusterHealthGroup[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("overallHealth", "string", "vim.version.version9", 0),
        ("overallHealthDescription", "string", "vim.version.version9", 0),
        (
            "clomdLiveness",
            "vim.cluster.VsanClusterClomdLivenessResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "diskBalance",
            "vim.cluster.VsanClusterBalanceSummary",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanPerfEntityType",
    "VsanPerfEntityType",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("name", "string", "vim.version.version9", 0),
        ("id", "string", "vim.version.version9", 0),
        ("graphs", "vim.cluster.VsanPerfGraph[]", "vim.version.version9", 0),
        ("description", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanNetworkLoadTestResult",
    "VsanNetworkLoadTestResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0),
        ("status", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("client", "boolean", "vim.version.version9", 0),
        ("bandwidthBps", "long", "vim.version.version9", 0),
        ("totalBytes", "long", "vim.version.version9", 0),
        ("lostDatagrams", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("lossPct", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("sentDatagrams", "long", "vim.version.version9", 0 | F_OPTIONAL),
        ("jitterMs", "float", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanPhysicalDiskHealthSummary",
    "VsanPhysicalDiskHealthSummary",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("overallHealth", "string", "vim.version.version9", 0),
        (
            "heapsWithIssues",
            "vim.host.VsanResourceHealth[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "slabsWithIssues",
            "vim.host.VsanResourceHealth[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "disks",
            "vim.host.VsanPhysicalDiskHealth[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "componentsWithIssues",
            "vim.host.VsanResourceHealth[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("hostname", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("hostDedupScope", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("error", "vmodl.MethodFault", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.vsan.host.VsanDiskManagementSystemCapability",
    "VimVsanHostVsanDiskManagementSystemCapability",
    "vmodl.DynamicData",
    "vim.version.version10",
    [("version", "string", "vim.version.version10", 0)],
)
CreateDataType(
    "vim.host.VsanHostCimProviderInfo",
    "VsanHostCimProviderInfo",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("cimProviderSupported", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("installedCIMProvider", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("cimProviderOnHcl", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanObjectInformation",
    "VsanObjectInformation",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("directoryName", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("vsanObjectUuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("vsanHealth", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("policyAttributes", "vim.KeyValue[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("spbmProfileUuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("spbmProfileGenerationId", "string", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "spbmComplianceResult",
            "vim.cluster.StorageComplianceResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanObjectIdentity",
    "VsanObjectIdentity",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("uuid", "string", "vim.version.version9", 0),
        ("type", "string", "vim.version.version9", 0),
        ("vmInstanceUuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("vmNsObjectUuid", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("vm", "vim.VirtualMachine", "vim.version.version9", 0 | F_OPTIONAL),
        ("description", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanResourceHealth",
    "VsanResourceHealth",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("resource", "string", "vim.version.version9", 0),
        ("health", "string", "vim.version.version9", 0),
        ("description", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanCapability",
    "VsanCapability",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("target", "vmodl.ManagedObject", "vim.version.version10", 0 | F_OPTIONAL),
        ("capabilities", "string[]", "vim.version.version10", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanHostClomdLivenessResult",
    "VsanHostClomdLivenessResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0),
        ("clomdStat", "string", "vim.version.version9", 0),
        ("error", "vmodl.MethodFault", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanObjectQuerySpec",
    "VsanObjectQuerySpec",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("uuid", "string", "vim.version.version9", 0),
        ("spbmProfileGenerationId", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterLimitHealthResult",
    "VsanClusterLimitHealthResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("issueFound", "boolean", "vim.version.version9", 0),
        ("componentLimitHealth", "string", "vim.version.version9", 0),
        ("diskFreeSpaceHealth", "string", "vim.version.version9", 0),
        ("rcFreeReservationHealth", "string", "vim.version.version9", 0),
        (
            "hostResults",
            "vim.host.VsanLimitHealthResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "whatifHostFailures",
            "vim.cluster.VsanClusterWhatifHostFailuresResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        ("hostsCommFailure", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanStorageWorkloadType",
    "VsanStorageWorkloadType",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("specs", "vim.host.VsanVmdkLoadTestSpec[]", "vim.version.version9", 0),
        ("typeId", "string", "vim.version.version9", 0),
        ("name", "string", "vim.version.version9", 0),
        ("description", "string", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterAdvCfgSyncHostResult",
    "VsanClusterAdvCfgSyncHostResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("hostname", "string", "vim.version.version9", 0),
        ("value", "string", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.vsan.upgradesystem.ObjectPolicyIssue",
    "VsanObjectPolicyIssue",
    "vim.VsanUpgradeSystem.PreflightCheckIssue",
    "vim.version.version10",
    [("uuids", "string[]", "vim.version.version10", 0)],
)
CreateDataType(
    "vim.cluster.VsanPerfTopEntities",
    "VsanPerfTopEntities",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("metricId", "vim.cluster.VsanPerfMetricId", "vim.version.version9", 0),
        ("entities", "vim.cluster.VsanPerfTopEntity[]", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.host.VsanProactiveRebalanceInfoEx",
    "VsanProactiveRebalanceInfoEx",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("running", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
        ("startTs", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        ("stopTs", "vmodl.DateTime", "vim.version.version9", 0 | F_OPTIONAL),
        ("varianceThreshold", "float", "vim.version.version9", 0 | F_OPTIONAL),
        ("timeThreshold", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("rateThreshold", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("hostname", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("error", "vmodl.MethodFault", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterProactiveTestResult",
    "VsanClusterProactiveTestResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("overallStatus", "string", "vim.version.version9", 0),
        ("overallStatusDescription", "string", "vim.version.version9", 0),
        ("timestamp", "vmodl.DateTime", "vim.version.version9", 0),
        (
            "healthTest",
            "vim.cluster.VsanClusterHealthTest",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.host.VSANCmmdsPreferredFaultDomainInfo",
    "VimHostVSANCmmdsPreferredFaultDomainInfo",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        ("preferredFaultDomainId", "string", "vim.version.version10", 0),
        ("preferredFaultDomainName", "string", "vim.version.version10", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanFaultDomainsConfigSpec",
    "VimClusterVsanFaultDomainsConfigSpec",
    "vmodl.DynamicData",
    "vim.version.version10",
    [
        (
            "faultDomains",
            "vim.cluster.VsanFaultDomainSpec[]",
            "vim.version.version10",
            0,
        ),
        (
            "witness",
            "vim.cluster.VsanWitnessSpec",
            "vim.version.version10",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterHostVmknicMapping",
    "VsanClusterHostVmknicMapping",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("host", "string", "vim.version.version9", 0),
        ("vmknic", "string", "vim.version.version9", 0),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterVmdkLoadTestResult",
    "VsanClusterVmdkLoadTestResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("task", "vim.Task", "vim.version.version9", 0 | F_OPTIONAL),
        (
            "clusterResult",
            "vim.cluster.VsanClusterProactiveTestResult",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
        (
            "hostResults",
            "vim.host.VsanHostVmdkLoadTestResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterVMsHealthSummaryResult",
    "VsanClusterVMsHealthSummaryResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("numVMs", "int", "vim.version.version9", 0),
        ("state", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("health", "string", "vim.version.version9", 0),
        ("vmInstanceUuids", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VSANStretchedClusterHostCapability",
    "VimHostVSANStretchedClusterHostCapability",
    "vmodl.DynamicData",
    "vim.version.version10",
    [("featureVersion", "string", "vim.version.version10", 0)],
)
CreateDataType(
    "vim.host.VsanFailedRepairObjectResult",
    "VsanFailedRepairObjectResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("uuid", "string", "vim.version.version9", 0),
        ("errMessage", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterCreateVmHealthTestResult",
    "VsanClusterCreateVmHealthTestResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "clusterResult",
            "vim.cluster.VsanClusterProactiveTestResult",
            "vim.version.version9",
            0,
        ),
        (
            "hostResults",
            "vim.cluster.VsanHostCreateVmHealthTestResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.host.VsanObjectHealth",
    "VsanObjectHealth",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("numObjects", "int", "vim.version.version9", 0),
        ("health", "vim.host.VsanObjectHealthState", "vim.version.version9", 0),
        ("objUuids", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterBalanceSummary",
    "VsanClusterBalanceSummary",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("varianceThreshold", "long", "vim.version.version9", 0),
        (
            "disks",
            "vim.cluster.VsanClusterBalancePerDiskInfo[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterTelemetryProxyConfig",
    "VsanClusterTelemetryProxyConfig",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("host", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("port", "int", "vim.version.version9", 0 | F_OPTIONAL),
        ("user", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("password", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("autoDiscovered", "boolean", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanVmdkIOLoadSpec",
    "VsanVmdkIOLoadSpec",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("readPct", "int", "vim.version.version9", 0),
        ("oio", "int", "vim.version.version9", 0),
        ("iosizeB", "int", "vim.version.version9", 0),
        ("dataSizeMb", "long", "vim.version.version9", 0),
        ("random", "boolean", "vim.version.version9", 0),
        ("startOffsetB", "long", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.host.VsanVsanPcapResult",
    "VsanVsanPcapResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        ("calltime", "float", "vim.version.version9", 0),
        ("vmknic", "string", "vim.version.version9", 0),
        ("tcpdumpFilter", "string", "vim.version.version9", 0),
        ("snaplen", "int", "vim.version.version9", 0),
        ("pkts", "string[]", "vim.version.version9", 0 | F_OPTIONAL),
        ("pcap", "string", "vim.version.version9", 0 | F_OPTIONAL),
        ("error", "vmodl.MethodFault", "vim.version.version9", 0 | F_OPTIONAL),
        ("hostname", "string", "vim.version.version9", 0 | F_OPTIONAL),
    ],
)
CreateDataType(
    "vim.cluster.VsanClusterNetworkLoadTestResult",
    "VsanClusterNetworkLoadTestResult",
    "vmodl.DynamicData",
    "vim.version.version9",
    [
        (
            "clusterResult",
            "vim.cluster.VsanClusterProactiveTestResult",
            "vim.version.version9",
            0,
        ),
        (
            "hostResults",
            "vim.host.VsanNetworkLoadTestResult[]",
            "vim.version.version9",
            0 | F_OPTIONAL,
        ),
    ],
)
CreateDataType(
    "vim.vsan.upgradesystem.HostPropertyRetrieveIssue",
    "VsanHostPropertyRetrieveIssue",
    "vim.VsanUpgradeSystem.PreflightCheckIssue",
    "vim.version.version10",
    [("hosts", "vim.HostSystem[]", "vim.version.version10", 0)],
)
CreateEnumType(
    "vim.host.VsanObjectHealthState",
    "VsanObjectHealthState",
    "vim.version.version9",
    [
        "inaccessible",
        "reducedavailabilitywithnorebuild",
        "reducedavailabilitywithnorebuilddelaytimer",
        "reducedavailabilitywithactiverebuild",
        "datamove",
        "nonavailabilityrelatedreconfig",
        "nonavailabilityrelatedincompliance",
        "healthy",
    ],
)
CreateEnumType(
    "vim.cluster.VsanObjectTypeEnum",
    "VsanObjectTypeEnum",
    "vim.version.version9",
    [
        "vmswap",
        "vdisk",
        "namespace",
        "vmem",
        "statsdb",
        "iscsi",
        "other",
        "fileSystemOverhead",
        "dedupOverhead",
        "checksumOverhead",
    ],
)
CreateEnumType(
    "vim.cluster.VsanCapabilityType",
    "VsanCapabilityType",
    "vim.version.version10",
    [
        "capability",
        "allflash",
        "stretchedcluster",
        "dataefficiency",
        "clusterconfig",
        "upgrade",
        "objectidentities",
    ],
)
CreateEnumType(
    "vim.cluster.VsanHealthLogLevelEnum",
    "VsanHealthLogLevelEnum",
    "vim.version.version9",
    [
        "INFO",
        "WARNING",
        "ERROR",
        "DEBUG",
        "CRITICAL",
    ],
)
CreateEnumType(
    "vim.cluster.VsanPerfSummaryType",
    "VsanPerfSummaryType",
    "vim.version.version9",
    [
        "average",
        "maximum",
        "minimum",
        "latest",
        "summation",
        "none",
    ],
)
CreateEnumType(
    "vim.cluster.StorageComplianceStatus",
    "VsanStorageComplianceStatus",
    "vim.version.version9",
    [
        "compliant",
        "nonCompliant",
        "unknown",
        "notApplicable",
    ],
)
CreateEnumType(
    "vim.cluster.VsanPerfStatsUnitType",
    "VsanPerfStatsUnitType",
    "vim.version.version9",
    [
        "number",
        "time_ms",
        "percentage",
        "size_bytes",
        "rate_bytes",
    ],
)
CreateEnumType(
    "vim.cluster.VsanPerfThresholdDirectionType",
    "VsanPerfThresholdDirectionType",
    "vim.version.version9",
    [
        "upper",
        "lower",
    ],
)
CreateEnumType(
    "vim.cluster.VsanPerfStatsType",
    "VsanPerfStatsType",
    "vim.version.version9",
    [
        "absolute",
        "delta",
        "rate",
    ],
)
CreateEnumType(
    "vim.vsan.host.DiskMappingCreationType",
    "VimVsanHostDiskMappingCreationType",
    "vim.version.version10",
    [
        "hybrid",
        "allFlash",
    ],
)
CreateEnumType(
    "vim.cluster.VsanClusterHealthActionIdEnum",
    "VsanClusterHealthActionIdEnum",
    "vim.version.version9",
    [
        "RepairClusterObjectsAction",
        "UploadHclDb",
        "UpdateHclDbFromInternet",
        "EnableHealthService",
        "DiskBalance",
        "StopDiskBalance",
        "RemediateDedup",
        "UpgradeVsanDiskFormat",
    ],
)
CreateEnumType(
    "vim.cluster.VsanDiskGroupCreationType",
    "VimClusterVsanDiskGroupCreationType",
    "vim.version.version10",
    [
        "allflash",
        "hybrid",
    ],
)
