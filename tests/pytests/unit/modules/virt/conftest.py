import pytest
import salt.modules.config as config
import salt.modules.virt as virt
from salt._compat import ElementTree as ET
from tests.support.mock import MagicMock


class LibvirtMock(MagicMock):  # pylint: disable=too-many-ancestors
    """
    Libvirt library mock
    """

    class virDomain(MagicMock):
        """
        virDomain mock
        """

    class libvirtError(Exception):
        """
        libvirtError mock
        """

        def __init__(self, msg):
            super().__init__(msg)
            self.msg = msg

        def get_error_message(self):
            return self.msg


class MappedResultMock(MagicMock):
    """
    Mock class consistently return the same mock object based on the first argument.
    """

    _instances = {}

    def __init__(self):
        def mapped_results(*args, **kwargs):
            if args[0] not in self._instances.keys():
                raise virt.libvirt.libvirtError("Not found: {}".format(args[0]))
            return self._instances[args[0]]

        super().__init__(side_effect=mapped_results)

    def add(self, name):
        self._instances[name] = MagicMock()


def loader_modules_config():
    # Create libvirt mock and connection mock
    mock_libvirt = LibvirtMock()
    mock_conn = MagicMock()
    mock_conn.getStoragePoolCapabilities.return_value = "<storagepoolCapabilities/>"

    mock_libvirt.openAuth.return_value = mock_conn
    return {
        virt: {
            "libvirt": mock_libvirt,
            "__salt__": {"config.get": config.get, "config.option": config.option},
        },
        config: {},
    }


@pytest.fixture
def make_mock_vm():
    def _make_mock_vm(xml_def):
        mocked_conn = virt.libvirt.openAuth.return_value

        doc = ET.fromstring(xml_def)
        name = doc.find("name").text
        os_type = "hvm"
        os_type_node = doc.find("os/type")
        if os_type_node is not None:
            os_type = os_type_node.text

        mocked_conn.listDefinedDomains.return_value = [name]

        # Configure the mocked domain
        if not isinstance(mocked_conn.lookupByName, MappedResultMock):
            mocked_conn.lookupByName = MappedResultMock()
        mocked_conn.lookupByName.add(name)
        domain_mock = mocked_conn.lookupByName(name)
        domain_mock.XMLDesc.return_value = xml_def
        domain_mock.OSType.return_value = os_type

        # Return state as shutdown
        domain_mock.info.return_value = [
            4,
            2048 * 1024,
            1024 * 1024,
            2,
            1234,
        ]
        domain_mock.ID.return_value = 1
        domain_mock.name.return_value = name

        domain_mock.attachDevice.return_value = 0
        domain_mock.detachDevice.return_value = 0

        return domain_mock

    return _make_mock_vm


@pytest.fixture
def make_mock_storage_pool():
    def _make_mock_storage_pool(name, type, volumes):
        mocked_conn = virt.libvirt.openAuth.return_value

        # Append the pool name to the list of known mocked pools
        all_pools = mocked_conn.listStoragePools.return_value
        if not isinstance(all_pools, list):
            all_pools = []
        all_pools.append(name)
        mocked_conn.listStoragePools.return_value = all_pools

        # Ensure we have mapped results for the pools
        if not isinstance(mocked_conn.storagePoolLookupByName, MappedResultMock):
            mocked_conn.storagePoolLookupByName = MappedResultMock()

        # Configure the pool
        mocked_conn.storagePoolLookupByName.add(name)
        mocked_pool = mocked_conn.storagePoolLookupByName(name)
        source = ""
        if type == "disk":
            source = "<device path='/dev/{}'/>".format(name)
        pool_path = "/path/to/{}".format(name)
        mocked_pool.XMLDesc.return_value = """
            <pool type='{}'>
                <source>
                {}
                </source>
                <target>
                    <path>{}</path>
                </target>
            </pool>
            """.format(
            type, source, pool_path
        )
        mocked_pool.name.return_value = name
        mocked_pool.info.return_value = [
            virt.libvirt.VIR_STORAGE_POOL_RUNNING,
        ]

        # Append the pool to the listAllStoragePools list
        all_pools_obj = mocked_conn.listAllStoragePools.return_value
        if not isinstance(all_pools_obj, list):
            all_pools_obj = []
        all_pools_obj.append(mocked_pool)
        mocked_conn.listAllStoragePools.return_value = all_pools_obj

        # Configure the volumes
        if not isinstance(mocked_pool.storageVolLookupByName, MappedResultMock):
            mocked_pool.storageVolLookupByName = MappedResultMock()
        mocked_pool.listVolumes.return_value = volumes

        all_volumes = []
        for volume in volumes:
            mocked_pool.storageVolLookupByName.add(volume)
            mocked_vol = mocked_pool.storageVolLookupByName(volume)
            vol_path = "{}/{}".format(pool_path, volume)
            mocked_vol.XMLDesc.return_value = """
            <volume>
                <target>
                    <path>{}</path>
                </target>
            </volume>
            """.format(
                vol_path,
            )
            mocked_vol.path.return_value = vol_path
            mocked_vol.name.return_value = volume

            mocked_vol.info.return_value = [
                0,
                1234567,
                12345,
            ]
            all_volumes.append(mocked_vol)

        # Set the listAllVolumes return_value
        mocked_pool.listAllVolumes.return_value = all_volumes
        return mocked_pool

    return _make_mock_storage_pool


@pytest.fixture
def make_capabilities():
    def _make_capabilities():
        mocked_conn = virt.libvirt.openAuth.return_value
        mocked_conn.getCapabilities.return_value = """
<capabilities>
  <host>
    <uuid>44454c4c-3400-105a-8033-b3c04f4b344a</uuid>
    <cpu>
      <arch>x86_64</arch>
      <model>Nehalem</model>
      <vendor>Intel</vendor>
      <microcode version='25'/>
      <topology sockets='1' cores='4' threads='2'/>
      <feature name='vme'/>
      <feature name='ds'/>
      <feature name='acpi'/>
      <pages unit='KiB' size='4'/>
      <pages unit='KiB' size='2048'/>
    </cpu>
    <power_management>
      <suspend_mem/>
      <suspend_disk/>
      <suspend_hybrid/>
    </power_management>
    <migration_features>
      <live/>
      <uri_transports>
        <uri_transport>tcp</uri_transport>
        <uri_transport>rdma</uri_transport>
      </uri_transports>
    </migration_features>
    <topology>
      <cells num='1'>
        <cell id='0'>
          <memory unit='KiB'>12367120</memory>
          <pages unit='KiB' size='4'>3091780</pages>
          <pages unit='KiB' size='2048'>0</pages>
          <distances>
            <sibling id='0' value='10'/>
          </distances>
          <cpus num='8'>
            <cpu id='0' socket_id='0' core_id='0' siblings='0,4'/>
            <cpu id='1' socket_id='0' core_id='1' siblings='1,5'/>
            <cpu id='2' socket_id='0' core_id='2' siblings='2,6'/>
            <cpu id='3' socket_id='0' core_id='3' siblings='3,7'/>
            <cpu id='4' socket_id='0' core_id='0' siblings='0,4'/>
            <cpu id='5' socket_id='0' core_id='1' siblings='1,5'/>
            <cpu id='6' socket_id='0' core_id='2' siblings='2,6'/>
            <cpu id='7' socket_id='0' core_id='3' siblings='3,7'/>
          </cpus>
        </cell>
      </cells>
    </topology>
    <cache>
      <bank id='0' level='3' type='both' size='8' unit='MiB' cpus='0-7'/>
    </cache>
    <secmodel>
      <model>apparmor</model>
      <doi>0</doi>
    </secmodel>
    <secmodel>
      <model>dac</model>
      <doi>0</doi>
      <baselabel type='kvm'>+487:+486</baselabel>
      <baselabel type='qemu'>+487:+486</baselabel>
    </secmodel>
  </host>

  <guest>
    <os_type>hvm</os_type>
    <arch name='i686'>
      <wordsize>32</wordsize>
      <emulator>/usr/bin/qemu-system-i386</emulator>
      <machine maxCpus='255'>pc-i440fx-2.6</machine>
      <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
      <machine maxCpus='255'>pc-0.12</machine>
      <domain type='qemu'/>
      <domain type='kvm'>
        <emulator>/usr/bin/qemu-kvm</emulator>
        <machine maxCpus='255'>pc-i440fx-2.6</machine>
        <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
        <machine maxCpus='255'>pc-0.12</machine>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <disksnapshot default='on' toggle='no'/>
      <acpi default='on' toggle='yes'/>
      <apic default='on' toggle='no'/>
      <pae/>
      <nonpae/>
    </features>
  </guest>

  <guest>
    <os_type>hvm</os_type>
    <arch name='x86_64'>
      <wordsize>64</wordsize>
      <emulator>/usr/bin/qemu-system-x86_64</emulator>
      <machine maxCpus='255'>pc-i440fx-2.6</machine>
      <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
      <machine maxCpus='255'>pc-0.12</machine>
      <domain type='qemu'/>
      <domain type='kvm'>
        <emulator>/usr/bin/qemu-kvm</emulator>
        <machine maxCpus='255'>pc-i440fx-2.6</machine>
        <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
        <machine maxCpus='255'>pc-0.12</machine>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <disksnapshot default='on' toggle='no'/>
      <acpi default='on' toggle='yes'/>
      <apic default='on' toggle='no'/>
    </features>
  </guest>

</capabilities>"""

    return _make_capabilities


@pytest.fixture
def make_mock_network():
    def _make_mock_net(xml_def):
        mocked_conn = virt.libvirt.openAuth.return_value

        doc = ET.fromstring(xml_def)
        name = doc.find("name").text

        if not isinstance(mocked_conn.networkLookupByName, MappedResultMock):
            mocked_conn.networkLookupByName = MappedResultMock()
        mocked_conn.networkLookupByName.add(name)
        net_mock = mocked_conn.networkLookupByName(name)
        net_mock.XMLDesc.return_value = xml_def

        # libvirt defaults the autostart to unset
        net_mock.autostart.return_value = 0
        return net_mock

    return _make_mock_net


@pytest.fixture
def make_mock_device():
    """
    Create a mock host device
    """

    def _make_mock_device(xml_def):
        mocked_conn = virt.libvirt.openAuth.return_value
        if not isinstance(mocked_conn.nodeDeviceLookupByName, MappedResultMock):
            mocked_conn.nodeDeviceLookupByName = MappedResultMock()

        doc = ET.fromstring(xml_def)
        name = doc.find("./name").text

        mocked_conn.nodeDeviceLookupByName.add(name)
        mocked_device = mocked_conn.nodeDeviceLookupByName(name)
        mocked_device.name.return_value = name
        mocked_device.XMLDesc.return_value = xml_def
        mocked_device.listCaps.return_value = [
            cap.get("type") for cap in doc.findall("./capability")
        ]
        return mocked_device

    return _make_mock_device
