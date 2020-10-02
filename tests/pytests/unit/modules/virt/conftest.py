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


@pytest.fixture(autouse=True)
def setup_loader():
    # Create libvirt mock and connection mock
    mock_libvirt = LibvirtMock()
    mock_conn = MagicMock()
    mock_conn.getStoragePoolCapabilities.return_value = "<storagepoolCapabilities/>"

    mock_libvirt.openAuth.return_value = mock_conn
    setup_loader_modules = {
        virt: {
            "libvirt": mock_libvirt,
            "__salt__": {"config.get": config.get, "config.option": config.option},
        },
        config: {},
    }
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


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
        domain_mock = virt.libvirt.virDomain()
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
