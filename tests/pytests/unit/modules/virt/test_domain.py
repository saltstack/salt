import os.path
import xml.etree.ElementTree as ET

import pytest

import salt.modules.virt as virt
import salt.syspaths
import salt.utils.xmlutil as xmlutil
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, patch

from .conftest import loader_modules_config
from .test_helpers import append_to_XMLDesc, assert_called, assert_equal_unit, strip_xml


@pytest.fixture
def configure_loader_modules():
    return loader_modules_config()


@pytest.mark.parametrize(
    "loader",
    [
        "/usr/lib/grub2/x86_64-xen/grub.xen",
        "/usr/share/grub2/x86_64-xen/grub.xen",
        None,
    ],
)
def test_gen_xml_for_xen_default_profile(loader, minion_opts):
    """
    Test virt._gen_xml(), XEN PV default profile case
    """
    diskp = virt._disk_profile(
        virt.libvirt.openAuth.return_value, "default", "xen", [], "hello"
    )
    nicp = virt._nic_profile("default", "xen")
    with patch.dict(
        virt.__grains__, {"os_family": "Suse"}  # pylint: disable=no-member
    ):
        os_mock = MagicMock(spec=virt.os)

        def fake_exists(path):
            return loader and path == loader

        os_mock.path.exists = MagicMock(side_effect=fake_exists)

        with patch.dict(virt.__dict__, {"os": os_mock}):
            if loader:
                xml_data = virt._gen_xml(
                    virt.libvirt.openAuth.return_value,
                    "hello",
                    1,
                    512,
                    diskp,
                    nicp,
                    "xen",
                    "xen",
                    "x86_64",
                    boot=None,
                )
                root = ET.fromstring(xml_data)
                assert root.attrib["type"] == "xen"
                assert root.find("vcpu").text == "1"
                assert root.find("memory").text == str(512 * 1024)
                assert root.find("memory").attrib["unit"] == "KiB"
                assert root.find(".//kernel").text == loader

                disks = root.findall(".//disk")
                assert len(disks) == 1
                disk = disks[0]
                root_dir = salt.syspaths.ROOT_DIR
                assert disk.find("source").attrib["file"].startswith(root_dir)
                assert "hello_system" in disk.find("source").attrib["file"]
                assert disk.find("target").attrib["dev"] == "xvda"
                assert disk.find("target").attrib["bus"] == "xen"
                assert disk.find("driver").attrib["name"] == "qemu"
                assert disk.find("driver").attrib["type"] == "qcow2"

                interfaces = root.findall(".//interface")
                assert len(interfaces) == 1
                iface = interfaces[0]
                assert iface.attrib["type"] == "bridge"
                assert iface.find("source").attrib["bridge"] == "br0"
                assert iface.find("model") is None
            else:
                with pytest.raises(CommandExecutionError):
                    xml_data = virt._gen_xml(
                        virt.libvirt.openAuth.return_value,
                        "hello",
                        1,
                        512,
                        diskp,
                        nicp,
                        "xen",
                        "xen",
                        "x86_64",
                        boot=None,
                    )


def test_update_xen_disk_volumes(make_mock_vm, make_mock_storage_pool):
    xml_def = """
        <domain type='xen'>
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>linux</type>
            <kernel>/usr/lib/grub2/x86_64-xen/grub.xen</kernel>
          </os>
          <devices>
            <disk type='file' device='disk'>
              <driver name='qemu' type='qcow2' cache='none' io='native'/>
              <source file='/path/to/default/my_vm_system'/>
              <target dev='xvda' bus='xen'/>
            </disk>
            <disk type='block' device='disk'>
              <driver name='qemu' type='raw' cache='none' io='native'/>
              <source dev='/path/to/my-iscsi/unit:0:0:1'/>
              <target dev='xvdb' bus='xen'/>
            </disk>
            <controller type='xenbus' index='0'/>
          </devices>
        </domain>"""
    domain_mock = make_mock_vm(xml_def)
    make_mock_storage_pool("default", "dir", ["my_vm_system"])
    make_mock_storage_pool("my-iscsi", "iscsi", ["unit:0:0:1"])
    make_mock_storage_pool("vdb", "disk", ["vdb1"])

    ret = virt.update(
        "my_vm",
        disks=[
            {"name": "system", "pool": "default"},
            {"name": "iscsi-data", "pool": "my-iscsi", "source_file": "unit:0:0:1"},
            {"name": "vdb-data", "pool": "vdb", "source_file": "vdb1"},
            {"name": "file-data", "pool": "default", "size": "10240"},
        ],
    )

    assert ret["definition"]
    virt.libvirt.openAuth().defineXML = virt.libvirt.openAuth().defineXML
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find(".//disk[3]").get("type") == "block"
    assert setxml.find(".//disk[3]/source").get("dev") == "/path/to/vdb/vdb1"

    # Note that my_vm-file-data was not an existing volume before the update
    assert setxml.find(".//disk[4]").get("type") == "file"
    assert (
        setxml.find(".//disk[4]/source").get("file")
        == "/path/to/default/my_vm_file-data"
    )


def test_get_disks(make_mock_vm, make_mock_storage_pool):
    # test with volumes
    vm_def = """<domain type='kvm' id='3'>
      <name>srv01</name>
      <devices>
        <disk type='volume' device='disk'>
          <driver name='qemu' type='qcow2' cache='none' io='native'/>
          <source pool='default' volume='srv01_system'/>
          <backingStore/>
          <target dev='vda' bus='virtio'/>
          <alias name='virtio-disk0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x04' function='0x0'/>
        </disk>
        <disk type='volume' device='disk'>
          <driver name='qemu' type='qcow2' cache='none' io='native'/>
          <source pool='default' volume='srv01_data'/>
          <backingStore type='file' index='1'>
            <format type='qcow2'/>
            <source file='/var/lib/libvirt/images/vol01'/>
            <backingStore/>
          </backingStore>
          <target dev='vdb' bus='virtio'/>
          <alias name='virtio-disk1'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0'/>
        </disk>
        <disk type='volume' device='disk'>
          <driver name='qemu' type='qcow2' cache='none' io='native'/>
          <source pool='default' volume='vm05_system'/>
          <backingStore type='file' index='1'>
            <format type='qcow2'/>
            <source file='/var/lib/libvirt/images/vm04_system.qcow2'/>
            <backingStore type='file' index='2'>
              <format type='raw'/>
              <source file='/var/testsuite-data/disk-image-template.raw'/>
              <backingStore/>
            </backingStore>
          </backingStore>
          <target dev='vdc' bus='virtio'/>
          <alias name='virtio-disk0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x04' function='0x0'/>
        </disk>
        <disk type='volume' device='disk'>
          <driver name='qemu' type='qcow2' cache='none' io='native'/>
          <source pool='stopped' volume='vm05_data'/>
          <target dev='vdd' bus='virtio'/>
        </disk>
        <disk type='network' device='cdrom'>
          <driver name='qemu' type='raw' cache='none' io='native'/>
          <source protocol='http' name='/pub/iso/myimage.iso' query='foo=bar&amp;baz=flurb' index='1'>
            <host name='dev-srv.tf.local' port='80'/>
          </source>
          <target dev='hda' bus='ide'/>
          <readonly/>
          <alias name='ide0-0-0'/>
          <address type='drive' controller='0' bus='0' target='0' unit='0'/>
        </disk>
      </devices>
    </domain>
    """
    make_mock_vm(vm_def)

    pool_mock = make_mock_storage_pool(
        "default", "dir", ["srv01_system", "srv01_data", "vm05_system"]
    )
    make_mock_storage_pool("stopped", "dir", [])

    # Append backing store to srv01_data volume XML description
    srv1data_mock = pool_mock.storageVolLookupByName("srv01_data")
    append_to_XMLDesc(
        srv1data_mock,
        """
        <backingStore>
          <path>/var/lib/libvirt/images/vol01</path>
          <format type="qcow2"/>
        </backingStore>""",
    )

    assert virt.get_disks("srv01") == {
        "vda": {
            "type": "disk",
            "file": "default/srv01_system",
            "file format": "qcow2",
            "disk size": 12345,
            "virtual size": 1234567,
        },
        "vdb": {
            "type": "disk",
            "file": "default/srv01_data",
            "file format": "qcow2",
            "disk size": 12345,
            "virtual size": 1234567,
            "backing file": {
                "file": "/var/lib/libvirt/images/vol01",
                "file format": "qcow2",
            },
        },
        "vdc": {
            "type": "disk",
            "file": "default/vm05_system",
            "file format": "qcow2",
            "disk size": 12345,
            "virtual size": 1234567,
            "backing file": {
                "file": "/var/lib/libvirt/images/vm04_system.qcow2",
                "file format": "qcow2",
                "backing file": {
                    "file": "/var/testsuite-data/disk-image-template.raw",
                    "file format": "raw",
                },
            },
        },
        "vdd": {"type": "disk", "file": "stopped/vm05_data", "file format": "qcow2"},
        "hda": {
            "type": "cdrom",
            "file format": "raw",
            "file": "http://dev-srv.tf.local:80/pub/iso/myimage.iso?foo=bar&baz=flurb",
        },
    }


def test_get_disk_convert_volumes(make_mock_vm, make_mock_storage_pool):
    vm_def = """<domain type='kvm' id='3'>
      <name>srv01</name>
      <devices>
        <disk type='file' device='disk'>
          <driver name='qemu' type='qcow2' cache='none' io='native'/>
          <source file='/path/to/default/srv01_system'/>
          <target dev='vda' bus='virtio'/>
          <alias name='virtio-disk0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x04' function='0x0'/>
        </disk>
        <disk type='block' device='disk'>
          <driver name='qemu' type='raw'/>
          <source dev='/path/to/default/srv01_data'/>
          <target dev='vdb' bus='virtio'/>
          <alias name='virtio-disk1'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0'/>
        </disk>
        <disk type='file' device='disk'>
          <driver name='qemu' type='qcow2' cache='none' io='native'/>
          <source file='/path/to/srv01_extra'/>
          <target dev='vdc' bus='virtio'/>
          <alias name='virtio-disk1'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0'/>
        </disk>
      </devices>
    </domain>
    """
    domain_mock = make_mock_vm(vm_def)

    pool_mock = make_mock_storage_pool("default", "dir", ["srv01_system", "srv01_data"])

    subprocess_mock = MagicMock()
    popen_mock = MagicMock(spec=virt.subprocess.Popen)
    popen_mock.return_value.communicate.return_value = [
        """[
        {
            "virtual-size": 214748364800,
            "filename": "/path/to/srv01_extra",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 340525056,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false,
                    "refcount-bits": 16,
                    "corrupt": false
                }
            },
            "dirty-flag": false
        }
    ]
    """,
        "",
    ]
    popen_mock.return_value.returncode = 0
    subprocess_mock.Popen = popen_mock

    with patch.dict(virt.__dict__, {"subprocess": subprocess_mock}):
        assert virt.get_disks("srv01") == {
            "vda": {
                "type": "disk",
                "file": "default/srv01_system",
                "file format": "qcow2",
                "disk size": 12345,
                "virtual size": 1234567,
            },
            "vdb": {
                "type": "disk",
                "file": "default/srv01_data",
                "file format": "raw",
                "disk size": 12345,
                "virtual size": 1234567,
            },
            "vdc": {
                "type": "disk",
                "file": "/path/to/srv01_extra",
                "file format": "qcow2",
                "cluster size": 65536,
                "disk size": 340525056,
                "virtual size": 214748364800,
            },
        }


def test_get_disk_missing(make_mock_vm):
    """
    Test virt.get_disks when the file doesn't exist
    """
    vm_def = """<domain type='kvm' id='3'>
      <name>srv01</name>
      <devices>
        <disk type='file' device='disk'>
          <driver name='qemu' type='qcow2' cache='none' io='native'/>
          <source file='/path/to/default/srv01_system'/>
          <target dev='vda' bus='virtio'/>
        </disk>
      </devices>
    </domain>
    """
    domain_mock = make_mock_vm(vm_def)

    subprocess_mock = MagicMock()
    popen_mock = MagicMock(spec=virt.subprocess.Popen)
    popen_mock.return_value.communicate.return_value = ("", "File not found")
    popen_mock.return_value.returncode = 1
    subprocess_mock.Popen = popen_mock

    with patch.dict(virt.__dict__, {"subprocess": subprocess_mock}):
        assert virt.get_disks("srv01") == {
            "vda": {
                "type": "disk",
                "file": "/path/to/default/srv01_system",
                "file format": "qcow2",
                "error": "File not found",
            },
        }


def test_get_disk_no_qemuimg(make_mock_vm):
    """
    Test virt.get_disks when qemu_img can't be found
    """
    vm_def = """<domain type='kvm' id='3'>
      <name>srv01</name>
      <devices>
        <disk type='file' device='disk'>
          <driver name='qemu' type='qcow2' cache='none' io='native'/>
          <source file='/path/to/default/srv01_system'/>
          <target dev='vda' bus='virtio'/>
        </disk>
      </devices>
    </domain>
    """
    domain_mock = make_mock_vm(vm_def)

    subprocess_mock = MagicMock()
    subprocess_mock.Popen = MagicMock(
        side_effect=FileNotFoundError("No such file or directory: 'qemu-img'")
    )

    with patch.dict(virt.__dict__, {"subprocess": subprocess_mock}):
        assert virt.get_disks("srv01") == {
            "vda": {
                "type": "disk",
                "file": "/path/to/default/srv01_system",
                "file format": "qcow2",
                "error": "qemu-img not found",
            },
        }


def test_update_approx_mem(make_mock_vm):
    """
    test virt.update with memory parameter unchanged thought not exactly equals to the current value.
    This may happen since libvirt sometimes rounds the memory value.
    """
    xml_def = """
        <domain type="kvm">
          <name>my_vm</name>
          <memory unit='KiB'>3177680</memory>
          <currentMemory unit='KiB'>3177680</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>hvm</type>
          </os>
          <on_reboot>restart</on_reboot>
        </domain>
    """
    domain_mock = make_mock_vm(xml_def)

    ret = virt.update("my_vm", mem={"boot": "3253941043B", "current": "3253941043B"})
    assert not ret["definition"]


def test_gen_hypervisor_features():
    """
    Test the virt._gen_xml hypervisor_features handling
    """
    xml_data = virt._gen_xml(
        virt.libvirt.openAuth.return_value,
        "hello",
        1,
        512,
        {},
        {},
        "kvm",
        "hvm",
        "x86_64",
        hypervisor_features={"kvm-hint-dedicated": True},
    )
    root = ET.fromstring(xml_data)
    assert root.find("features/kvm/hint-dedicated").attrib["state"] == "on"


def test_update_hypervisor_features(make_mock_vm):
    """
    Test changing the hypervisor features of a guest
    """
    xml_def = """
        <domain type="kvm">
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>linux</type>
            <kernel>/usr/lib/grub2/x86_64-xen/grub.xen</kernel>
          </os>
          <features>
            <kvm>
              <hint-dedicated state="on"/>
            </kvm>
          </features>
          <on_reboot>restart</on_reboot>
        </domain>
    """
    domain_mock = make_mock_vm(xml_def)

    # Update with no change to the features
    ret = virt.update("my_vm", hypervisor_features={"kvm-hint-dedicated": True})
    assert not ret["definition"]

    # Alter the features
    ret = virt.update("my_vm", hypervisor_features={"kvm-hint-dedicated": False})
    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("features/kvm/hint-dedicated").get("state") == "off"

    # Add the features
    xml_def = """
        <domain type="kvm">
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>linux</type>
            <kernel>/usr/lib/grub2/x86_64-xen/grub.xen</kernel>
          </os>
        </domain>
    """
    domain_mock = make_mock_vm(xml_def)
    ret = virt.update("my_vm", hypervisor_features={"kvm-hint-dedicated": True})
    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("features/kvm/hint-dedicated").get("state") == "on"


def test_gen_clock():
    """
    Test the virt._gen_xml clock property
    """
    # Localtime with adjustment
    xml_data = virt._gen_xml(
        virt.libvirt.openAuth.return_value,
        "hello",
        1,
        512,
        {},
        {},
        "kvm",
        "hvm",
        "x86_64",
        clock={"adjustment": 3600, "utc": False},
    )
    root = ET.fromstring(xml_data)
    assert root.find("clock").get("offset") == "localtime"
    assert root.find("clock").get("adjustment") == "3600"

    # Specific timezone
    xml_data = virt._gen_xml(
        virt.libvirt.openAuth.return_value,
        "hello",
        1,
        512,
        {},
        {},
        "kvm",
        "hvm",
        "x86_64",
        clock={"timezone": "CEST"},
    )
    root = ET.fromstring(xml_data)
    assert root.find("clock").get("offset") == "timezone"
    assert root.find("clock").get("timezone") == "CEST"

    # UTC
    xml_data = virt._gen_xml(
        virt.libvirt.openAuth.return_value,
        "hello",
        1,
        512,
        {},
        {},
        "kvm",
        "hvm",
        "x86_64",
        clock={"utc": True},
    )
    root = ET.fromstring(xml_data)
    assert root.find("clock").get("offset") == "utc"

    # Timers
    xml_data = virt._gen_xml(
        virt.libvirt.openAuth.return_value,
        "hello",
        1,
        512,
        {},
        {},
        "kvm",
        "hvm",
        "x86_64",
        clock={
            "timers": {
                "tsc": {"frequency": 3504000000, "mode": "native"},
                "rtc": {
                    "tickpolicy": "catchup",
                    "slew": 4636,
                    "threshold": 123,
                    "limit": 2342,
                },
                "hpet": {"present": False},
            },
        },
    )
    root = ET.fromstring(xml_data)
    assert root.find("clock").get("offset") == "utc"
    assert root.find("clock/timer[@name='tsc']").get("frequency") == "3504000000"
    assert root.find("clock/timer[@name='tsc']").get("mode") == "native"
    assert root.find("clock/timer[@name='rtc']").get("tickpolicy") == "catchup"
    assert root.find("clock/timer[@name='rtc']/catchup").attrib == {
        "slew": "4636",
        "threshold": "123",
        "limit": "2342",
    }
    assert root.find("clock/timer[@name='hpet']").get("present") == "no"


def test_update_clock(make_mock_vm):
    """
    test virt.update with clock parameter
    """
    xml_def = """
        <domain type="kvm">
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>linux</type>
            <kernel>/usr/lib/grub2/x86_64-xen/grub.xen</kernel>
          </os>
          <clock offset="localtime" adjustment="-3600">
            <timer name="tsc" frequency="3504000000" mode="native" />
            <timer name="kvmclock" present="no" />
          </clock>
          <on_reboot>restart</on_reboot>
        </domain>
    """
    domain_mock = make_mock_vm(xml_def)

    # Update with no change to the features
    ret = virt.update(
        "my_vm",
        clock={
            "utc": False,
            "adjustment": -3600,
            "timers": {
                "tsc": {"frequency": 3504000000, "mode": "native"},
                "kvmclock": {"present": False},
            },
        },
    )
    assert not ret["definition"]

    # Update
    ret = virt.update(
        "my_vm",
        clock={
            "timezone": "CEST",
            "timers": {
                "rtc": {
                    "track": "wall",
                    "tickpolicy": "catchup",
                    "slew": 4636,
                    "threshold": 123,
                    "limit": 2342,
                },
                "hpet": {"present": True},
            },
        },
    )
    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("clock").get("offset") == "timezone"
    assert setxml.find("clock").get("timezone") == "CEST"
    assert {t.get("name") for t in setxml.findall("clock/timer")} == {"rtc", "hpet"}
    assert setxml.find("clock/timer[@name='rtc']").get("tickpolicy") == "catchup"
    assert setxml.find("clock/timer[@name='rtc']").get("track") == "wall"
    assert setxml.find("clock/timer[@name='rtc']/catchup").attrib == {
        "slew": "4636",
        "threshold": "123",
        "limit": "2342",
    }
    assert setxml.find("clock/timer[@name='hpet']").get("present") == "yes"

    # Revert to UTC
    ret = virt.update("my_vm", clock={"utc": True, "adjustment": None, "timers": None})
    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("clock").attrib == {"offset": "utc"}
    assert setxml.find("clock/timer") is None


def test_update_stop_on_reboot_reset(make_mock_vm):
    """
    Test virt.update to remove the on_reboot=destroy flag
    """
    xml_def = """
        <domain type='kvm'>
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <on_reboot>destroy</on_reboot>
          <os>
            <type arch='x86_64'>hvm</type>
          </os>
        </domain>"""
    domain_mock = make_mock_vm(xml_def)

    ret = virt.update("my_vm")

    assert ret["definition"]
    virt.libvirt.openAuth().defineXML = virt.libvirt.openAuth().defineXML
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("./on_reboot").text == "restart"


def test_update_stop_on_reboot(make_mock_vm):
    """
    Test virt.update to add the on_reboot=destroy flag
    """
    xml_def = """
        <domain type='kvm'>
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>hvm</type>
          </os>
        </domain>"""
    domain_mock = make_mock_vm(xml_def)

    ret = virt.update("my_vm", stop_on_reboot=True)

    assert ret["definition"]
    virt.libvirt.openAuth().defineXML = virt.libvirt.openAuth().defineXML
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("./on_reboot").text == "destroy"


def test_init_no_stop_on_reboot(make_capabilities):
    """
    Test virt.init to add the on_reboot=restart flag
    """
    make_capabilities()
    with patch.dict(virt.os.__dict__, {"chmod": MagicMock(), "makedirs": MagicMock()}):
        with patch.dict(virt.__salt__, {"cmd.run": MagicMock()}):
            virt.init("test_vm", 2, 2048, start=False)
            virt.libvirt.openAuth().defineXML = virt.libvirt.openAuth().defineXML
            setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
            assert setxml.find("./on_reboot").text == "restart"


def test_init_stop_on_reboot(make_capabilities):
    """
    Test virt.init to add the on_reboot=destroy flag
    """
    make_capabilities()
    with patch.dict(virt.os.__dict__, {"chmod": MagicMock(), "makedirs": MagicMock()}):
        with patch.dict(virt.__salt__, {"cmd.run": MagicMock()}):
            virt.init("test_vm", 2, 2048, stop_on_reboot=True, start=False)
            virt.libvirt.openAuth().defineXML = virt.libvirt.openAuth().defineXML
            setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
            assert setxml.find("./on_reboot").text == "destroy"


def test_init_hostdev_usb(make_capabilities, make_mock_device):
    """
    Test virt.init with USB host device passed through
    """
    make_capabilities()
    make_mock_device(
        """
        <device>
          <name>usb_3_1_3</name>
          <path>/sys/devices/pci0000:00/0000:00:1d.6/0000:06:00.0/0000:07:02.0/0000:3e:00.0/usb3/3-1/3-1.3</path>
          <devnode type='dev'>/dev/bus/usb/003/004</devnode>
          <parent>usb_3_1</parent>
          <driver>
            <name>usb</name>
          </driver>
          <capability type='usb_device'>
            <bus>3</bus>
            <device>4</device>
            <product id='0x6006'>AUKEY PC-LM1E Camera</product>
            <vendor id='0x0458'>KYE Systems Corp. (Mouse Systems)</vendor>
          </capability>
        </device>
    """
    )
    with patch.dict(virt.os.__dict__, {"chmod": MagicMock(), "makedirs": MagicMock()}):
        with patch.dict(virt.__salt__, {"cmd.run": MagicMock()}):
            virt.init("test_vm", 2, 2048, host_devices=["usb_3_1_3"], start=False)
            define_mock = virt.libvirt.openAuth().defineXML
            setxml = ET.fromstring(define_mock.call_args[0][0])
            expected_xml = strip_xml(
                """
                <hostdev mode='subsystem' type='usb'>
                  <source>
                    <vendor id='0x0458'/>
                    <product id='0x6006'/>
                  </source>
                </hostdev>
                """
            )
            assert (
                strip_xml(ET.tostring(setxml.find("./devices/hostdev"))) == expected_xml
            )


def test_init_hostdev_pci(make_capabilities, make_mock_device):
    """
    Test virt.init with PCI host device passed through
    """
    make_capabilities()
    make_mock_device(
        """
        <device>
          <name>pci_1002_71c4</name>
          <parent>pci_8086_27a1</parent>
          <capability type='pci'>
            <class>0xffffff</class>
            <domain>0</domain>
            <bus>1</bus>
            <slot>0</slot>
            <function>0</function>
            <product id='0x71c4'>M56GL [Mobility FireGL V5200]</product>
            <vendor id='0x1002'>ATI Technologies Inc</vendor>
            <numa node='1'/>
          </capability>
        </device>
    """
    )
    with patch.dict(virt.os.__dict__, {"chmod": MagicMock(), "makedirs": MagicMock()}):
        with patch.dict(virt.__salt__, {"cmd.run": MagicMock()}):
            virt.init("test_vm", 2, 2048, host_devices=["pci_1002_71c4"], start=False)
            define_mock = virt.libvirt.openAuth().defineXML
            setxml = ET.fromstring(define_mock.call_args[0][0])
            expected_xml = strip_xml(
                """
                <hostdev mode='subsystem' type='pci' managed='yes'>
                  <source>
                    <address domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
                  </source>
                </hostdev>
                """
            )
            assert (
                strip_xml(ET.tostring(setxml.find("./devices/hostdev"))) == expected_xml
            )


def test_update_hostdev_nochange(make_mock_device, make_mock_vm):
    """
    Test the virt.update function with no host device changes
    """
    xml_def = """
        <domain type='kvm'>
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>hvm</type>
          </os>
          <on_reboot>restart</on_reboot>
          <devices>
            <hostdev mode='subsystem' type='pci' managed='yes'>
              <source>
                <address domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
              </source>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
            </hostdev>
            <hostdev mode='subsystem' type='usb' managed='no'>
              <source>
                <vendor id='0x0458'/>
                <product id='0x6006'/>
                <address bus='3' device='4'/>
              </source>
              <alias name='hostdev0'/>
              <address type='usb' bus='0' port='1'/>
            </hostdev>
          </devices>
        </domain>"""
    domain_mock = make_mock_vm(xml_def)

    make_mock_device(
        """
        <device>
          <name>usb_3_1_3</name>
          <path>/sys/devices/pci0000:00/0000:00:1d.6/0000:06:00.0/0000:07:02.0/0000:3e:00.0/usb3/3-1/3-1.3</path>
          <devnode type='dev'>/dev/bus/usb/003/004</devnode>
          <parent>usb_3_1</parent>
          <driver>
            <name>usb</name>
          </driver>
          <capability type='usb_device'>
            <bus>3</bus>
            <device>4</device>
            <product id='0x6006'>AUKEY PC-LM1E Camera</product>
            <vendor id='0x0458'>KYE Systems Corp. (Mouse Systems)</vendor>
          </capability>
        </device>
    """
    )
    make_mock_device(
        """
        <device>
          <name>pci_1002_71c4</name>
          <parent>pci_8086_27a1</parent>
          <capability type='pci'>
            <class>0xffffff</class>
            <domain>0</domain>
            <bus>1</bus>
            <slot>0</slot>
            <function>0</function>
            <product id='0x71c4'>M56GL [Mobility FireGL V5200]</product>
            <vendor id='0x1002'>ATI Technologies Inc</vendor>
            <numa node='1'/>
          </capability>
        </device>
    """
    )

    ret = virt.update("my_vm", host_devices=["pci_1002_71c4", "usb_3_1_3"])

    assert not ret["definition"]
    define_mock = virt.libvirt.openAuth().defineXML
    define_mock.assert_not_called()


@pytest.mark.parametrize(
    "running,live",
    [(False, False), (True, False), (True, True)],
    ids=["stopped, no live", "running, no live", "running, live"],
)
def test_update_hostdev_changes(running, live, make_mock_device, make_mock_vm, test):
    """
    Test the virt.update function with host device changes
    """
    xml_def = """
        <domain type='kvm'>
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>hvm</type>
          </os>
          <on_reboot>restart</on_reboot>
          <devices>
            <hostdev mode='subsystem' type='pci' managed='yes'>
              <source>
                <address domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
              </source>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
            </hostdev>
          </devices>
        </domain>"""
    domain_mock = make_mock_vm(xml_def, running)

    make_mock_device(
        """
        <device>
          <name>usb_3_1_3</name>
          <path>/sys/devices/pci0000:00/0000:00:1d.6/0000:06:00.0/0000:07:02.0/0000:3e:00.0/usb3/3-1/3-1.3</path>
          <devnode type='dev'>/dev/bus/usb/003/004</devnode>
          <parent>usb_3_1</parent>
          <driver>
            <name>usb</name>
          </driver>
          <capability type='usb_device'>
            <bus>3</bus>
            <device>4</device>
            <product id='0x6006'>AUKEY PC-LM1E Camera</product>
            <vendor id='0x0458'>KYE Systems Corp. (Mouse Systems)</vendor>
          </capability>
        </device>
    """
    )

    make_mock_device(
        """
            <device>
              <name>pci_1002_71c4</name>
              <parent>pci_8086_27a1</parent>
              <capability type='pci'>
                <class>0xffffff</class>
                <domain>0</domain>
                <bus>1</bus>
                <slot>0</slot>
                <function>0</function>
                <product id='0x71c4'>M56GL [Mobility FireGL V5200]</product>
                <vendor id='0x1002'>ATI Technologies Inc</vendor>
                <numa node='1'/>
              </capability>
            </device>
        """
    )

    ret = virt.update("my_vm", host_devices=["usb_3_1_3"], test=test, live=live)
    define_mock = virt.libvirt.openAuth().defineXML
    assert_called(define_mock, not test)

    # Test that the XML is updated with the proper devices
    usb_device_xml = strip_xml(
        """
        <hostdev mode="subsystem" type="usb">
          <source>
           <vendor id="0x0458" />
           <product id="0x6006" />
          </source>
        </hostdev>
        """
    )
    if not test:
        set_xml = ET.fromstring(define_mock.call_args[0][0])
        actual_hostdevs = [
            ET.tostring(xmlutil.strip_spaces(node))
            for node in set_xml.findall("./devices/hostdev")
        ]
        assert actual_hostdevs == [usb_device_xml]

    if not test and live:
        attach_xml = strip_xml(domain_mock.attachDevice.call_args[0][0])
        assert attach_xml == usb_device_xml

        pci_device_xml = strip_xml(
            """
                <hostdev mode='subsystem' type='pci' managed='yes'>
                  <source>
                    <address domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
                  </source>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
                </hostdev>
            """
        )
        detach_xml = strip_xml(domain_mock.detachDevice.call_args[0][0])
        assert detach_xml == pci_device_xml
    else:
        domain_mock.attachDevice.assert_not_called()
        domain_mock.detachDevice.assert_not_called()


def test_diff_nics():
    """
    Test virt._diff_nics()
    """
    old_nics = ET.fromstring(
        """
        <devices>
           <interface type='network'>
             <mac address='52:54:00:39:02:b1'/>
             <source network='default'/>
             <model type='virtio'/>
             <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
           </interface>
           <interface type='network'>
             <mac address='52:54:00:39:02:b2'/>
             <source network='admin'/>
             <model type='virtio'/>
             <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
           </interface>
           <interface type='network'>
             <mac address='52:54:00:39:02:b3'/>
             <source network='admin'/>
             <model type='virtio'/>
             <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
           </interface>
        </devices>
    """
    ).findall("interface")

    new_nics = ET.fromstring(
        """
        <devices>
           <interface type='network'>
             <mac address='52:54:00:39:02:b1'/>
             <source network='default'/>
             <model type='virtio'/>
           </interface>
           <interface type='network'>
             <mac address='52:54:00:39:02:b2'/>
             <source network='default'/>
             <model type='virtio'/>
           </interface>
           <interface type='network'>
             <mac address='52:54:00:39:02:b4'/>
             <source network='admin'/>
             <model type='virtio'/>
           </interface>
        </devices>
    """
    ).findall("interface")
    ret = virt._diff_interface_lists(old_nics, new_nics)
    assert [nic.find("mac").get("address") for nic in ret["unchanged"]] == [
        "52:54:00:39:02:b1"
    ]
    assert [nic.find("mac").get("address") for nic in ret["new"]] == [
        "52:54:00:39:02:b2",
        "52:54:00:39:02:b4",
    ]
    assert [nic.find("mac").get("address") for nic in ret["deleted"]] == [
        "52:54:00:39:02:b2",
        "52:54:00:39:02:b3",
    ]


def test_diff_nics_live_nochange():
    """
    Libvirt alters the NICs of network type when running the guest, test the virt._diff_nics()
    function with no change in such a case.
    """
    old_nics = ET.fromstring(
        """
        <devices>
          <interface type='direct'>
            <mac address='52:54:00:03:02:15'/>
            <source network='test-vepa' portid='8377df4f-7c72-45f3-9ba4-a76306333396' dev='eth1' mode='vepa'/>
            <target dev='macvtap0'/>
            <model type='virtio'/>
            <alias name='net0'/>
            <address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0'/>
          </interface>
          <interface type='bridge'>
            <mac address='52:54:00:ea:2e:89'/>
            <source network='default' portid='b97ec5b7-25fd-4697-ae45-06af8cc1a964' bridge='br0'/>
            <target dev='vnet0'/>
            <model type='virtio'/>
            <alias name='net0'/>
            <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
          </interface>
        </devices>
        """
    ).findall("interface")

    new_nics = ET.fromstring(
        """
        <devices>
           <interface type='network'>
             <source network='test-vepa'/>
             <model type='virtio'/>
           </interface>
           <interface type='network'>
             <source network='default'/>
             <model type='virtio'/>
           </interface>
        </devices>
        """
    )
    ret = virt._diff_interface_lists(old_nics, new_nics)
    assert [nic.find("mac").get("address") for nic in ret["unchanged"]] == [
        "52:54:00:03:02:15",
        "52:54:00:ea:2e:89",
    ]


def test_update_nic_hostdev_nochange(make_mock_network, make_mock_vm, test):
    """
    Test the virt.update function with a running host with hostdev nic
    """
    xml_def_template = """
        <domain type='kvm'>
          <name>my_vm</name>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <os>
            <type arch='x86_64'>hvm</type>
          </os>
          <on_reboot>restart</on_reboot>
          <devices>
            {}
          </devices>
        </domain>
    """
    inactive_nic = """
        <interface type='hostdev' managed='yes'>
          <mac address='52:54:00:67:b2:08'/>
          <driver name='vfio'/>
          <source network="test-hostdev"/>
          <model type='virtio'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
        </interface>
    """
    running_nic = """
        <interface type='hostdev' managed='yes'>
          <mac address='52:54:00:67:b2:08'/>
          <driver name='vfio'/>
          <source>
            <address type='pci' domain='0x0000' bus='0x3d' slot='0x02' function='0x0'/>
          </source>
          <model type='virtio'/>
          <alias name='hostdev0'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
        </interface>
    """
    domain_mock = make_mock_vm(
        xml_def_template.format(running_nic),
        running="running",
        inactive_def=xml_def_template.format(inactive_nic),
    )

    make_mock_network(
        """
        <network connections='1'>
          <name>test-hostdev</name>
          <uuid>51d0aaa5-7530-4c60-8498-5bc3ab8c655b</uuid>
          <forward mode='hostdev' managed='yes'>
            <pf dev='eth0'/>
            <address type='pci' domain='0x0000' bus='0x3d' slot='0x02' function='0x0'/>
            <address type='pci' domain='0x0000' bus='0x3d' slot='0x02' function='0x1'/>
          </forward>
        </network>
        """
    )

    ret = virt.update(
        "my_vm",
        interfaces=[{"name": "eth0", "type": "network", "source": "test-hostdev"}],
        test=test,
        live=True,
    )
    assert not ret.get("definition")
    assert not ret.get("interface").get("attached")
    assert not ret.get("interface").get("detached")
    define_mock = virt.libvirt.openAuth().defineXML
    define_mock.assert_not_called()
    domain_mock.attachDevice.assert_not_called()
    domain_mock.detachDevice.assert_not_called()


def test_update_no_param(make_mock_vm):
    """
    Test virt.update(), no parameter passed
    """
    domain_mock = make_mock_vm()
    ret = virt.update("my_vm")
    assert not ret["definition"]
    assert not ret.get("mem")
    assert not ret.get("cpu")


def test_update_cpu_and_mem(make_mock_vm):
    """
    Test virt.update(), update both cpu and memory
    """
    domain_mock = make_mock_vm()
    ret = virt.update("my_vm", mem=2048, cpu=2)
    assert ret["definition"]
    assert ret["mem"]
    assert ret["cpu"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("vcpu").text == "2"
    assert setxml.find("memory").text == "2147483648"
    assert domain_mock.setMemoryFlags.call_args[0][0] == 2048 * 1024
    assert domain_mock.setVcpusFlags.call_args[0][0] == 2


def test_update_cpu_simple(make_mock_vm):
    """
    Test virt.update(), simple cpu count update
    """
    domain_mock = make_mock_vm()
    ret = virt.update("my_vm", cpu=2)
    assert ret["definition"]
    assert ret["cpu"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("vcpu").text == "2"
    assert domain_mock.setVcpusFlags.call_args[0][0] == 2


def test_update_autostart(make_mock_vm):
    """
    Test virt.update(), simple autostart update
    """
    domain_mock = make_mock_vm()
    virt.update("my_vm", autostart=True)
    domain_mock.setAutostart.assert_called_with(1)


def test_update_add_cpu_topology(make_mock_vm):
    """
    Test virt.update(), add cpu topology settings
    """
    domain_mock = make_mock_vm()
    ret = virt.update(
        "my_vm",
        cpu={
            "placement": "static",
            "cpuset": "0-11",
            "current": 5,
            "maximum": 12,
            "vcpus": {
                "0": {"enabled": True, "hotpluggable": False, "order": 1},
                "1": {"enabled": False, "hotpluggable": True},
            },
            "mode": "custom",
            "match": "exact",
            "check": "full",
            "model": {
                "name": "coreduo",
                "fallback": "allow",
                "vendor_id": "Genuine20201",
            },
            "vendor": "Intel",
            "topology": {"sockets": 1, "cores": 12, "threads": 1},
            "cache": {"mode": "emulate", "level": 3},
            "features": {"lahf": "optional", "pcid": "disable"},
            "numa": {
                "0": {
                    "cpus": "0-3",
                    "memory": "1g",
                    "discard": True,
                    "distances": {0: 10, 1: 21, 2: 31, 3: 41},
                },
                "1": {
                    "cpus": "4-6",
                    "memory": "0.5g",
                    "discard": False,
                    "memAccess": "shared",
                    "distances": {0: 21, 1: 10, 2: 15, 3: 30},
                },
            },
        },
    )
    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])

    assert setxml.find("vcpu").text == "12"
    assert setxml.find("vcpu").get("placement") == "static"
    assert setxml.find("vcpu").get("cpuset") == "0,1,2,3,4,5,6,7,8,9,10,11"
    assert setxml.find("vcpu").get("current") == "5"

    assert setxml.find("./vcpus/vcpu/[@id='0']").get("id") == "0"
    assert setxml.find("./vcpus/vcpu/[@id='0']").get("enabled") == "yes"
    assert setxml.find("./vcpus/vcpu/[@id='0']").get("hotpluggable") == "no"
    assert setxml.find("./vcpus/vcpu/[@id='0']").get("order") == "1"
    assert setxml.find("./vcpus/vcpu/[@id='1']").get("id") == "1"
    assert setxml.find("./vcpus/vcpu/[@id='1']").get("enabled") == "no"
    assert setxml.find("./vcpus/vcpu/[@id='1']").get("hotpluggable") == "yes"
    assert setxml.find("./vcpus/vcpu/[@id='1']").get("order") is None

    assert setxml.find("cpu").get("mode") == "custom"
    assert setxml.find("cpu").get("match") == "exact"
    assert setxml.find("cpu").get("check") == "full"

    assert setxml.find("cpu/model").get("vendor_id") == "Genuine20201"
    assert setxml.find("cpu/model").get("fallback") == "allow"
    assert setxml.find("cpu/model").text == "coreduo"

    assert setxml.find("cpu/vendor").text == "Intel"

    assert setxml.find("cpu/topology").get("sockets") == "1"
    assert setxml.find("cpu/topology").get("cores") == "12"
    assert setxml.find("cpu/topology").get("threads") == "1"

    assert setxml.find("cpu/cache").get("level") == "3"
    assert setxml.find("cpu/cache").get("mode") == "emulate"

    assert setxml.find("./cpu/feature[@name='pcid']").get("policy") == "disable"
    assert setxml.find("./cpu/feature[@name='lahf']").get("policy") == "optional"

    assert setxml.find("./cpu/numa/cell/[@id='0']").get("cpus") == "0,1,2,3"
    assert setxml.find("./cpu/numa/cell/[@id='0']").get("memory") == str(1024**3)
    assert setxml.find("./cpu/numa/cell/[@id='0']").get("unit") == "bytes"
    assert setxml.find("./cpu/numa/cell/[@id='0']").get("discard") == "yes"
    assert (
        setxml.find("./cpu/numa/cell/[@id='0']/distances/sibling/[@id='0']").get(
            "value"
        )
        == "10"
    )
    assert (
        setxml.find("./cpu/numa/cell/[@id='0']/distances/sibling/[@id='1']").get(
            "value"
        )
        == "21"
    )
    assert (
        setxml.find("./cpu/numa/cell/[@id='0']/distances/sibling/[@id='2']").get(
            "value"
        )
        == "31"
    )
    assert (
        setxml.find("./cpu/numa/cell/[@id='0']/distances/sibling/[@id='3']").get(
            "value"
        )
        == "41"
    )
    assert setxml.find("./cpu/numa/cell/[@id='1']").get("cpus") == "4,5,6"
    assert setxml.find("./cpu/numa/cell/[@id='1']").get("memory") == str(
        int(1024**3 / 2)
    )
    assert setxml.find("./cpu/numa/cell/[@id='1']").get("unit") == "bytes"
    assert setxml.find("./cpu/numa/cell/[@id='1']").get("discard") == "no"
    assert setxml.find("./cpu/numa/cell/[@id='1']").get("memAccess") == "shared"
    assert (
        setxml.find("./cpu/numa/cell/[@id='1']/distances/sibling/[@id='0']").get(
            "value"
        )
        == "21"
    )
    assert (
        setxml.find("./cpu/numa/cell/[@id='1']/distances/sibling/[@id='1']").get(
            "value"
        )
        == "10"
    )
    assert (
        setxml.find("./cpu/numa/cell/[@id='1']/distances/sibling/[@id='2']").get(
            "value"
        )
        == "15"
    )
    assert (
        setxml.find("./cpu/numa/cell/[@id='1']/distances/sibling/[@id='3']").get(
            "value"
        )
        == "30"
    )


@pytest.mark.parametrize("boot_dev", ["hd", "cdrom network hd"])
def test_update_bootdev_unchanged(make_mock_vm, boot_dev):
    """
    Test virt.update(), unchanged boot devices case
    """
    domain_mock = make_mock_vm(
        """
            <domain type='kvm' id='7'>
              <name>my_vm</name>
              <memory unit='KiB'>1048576</memory>
              <currentMemory unit='KiB'>1048576</currentMemory>
              <vcpu placement='auto'>1</vcpu>
              <on_reboot>restart</on_reboot>
              <os>
                <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
                <boot dev="hd"/>
              </os>
            </domain>
        """
    )
    ret = virt.update("my_vm", boot_dev=boot_dev)
    assert ret["definition"] == (boot_dev != "hd")
    if boot_dev == "hd":
        virt.libvirt.openAuth().defineXML.assert_not_called()
    else:
        setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
        assert [node.get("dev") for node in setxml.findall("os/boot")] == [
            "cdrom",
            "network",
            "hd",
        ]


def test_update_boot_kernel_paths(make_mock_vm):
    """
    Test virt.update(), change boot with kernel/initrd path and kernel params
    """
    domain_mock = make_mock_vm()
    ret = virt.update(
        "my_vm",
        boot={
            "kernel": "/root/f8-i386-vmlinuz",
            "initrd": "/root/f8-i386-initrd",
            "cmdline": "console=ttyS0 ks=http://example.com/f8-i386/os/",
        },
    )
    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("os/kernel").text == "/root/f8-i386-vmlinuz"
    assert setxml.find("os/initrd").text == "/root/f8-i386-initrd"
    assert (
        setxml.find("os/cmdline").text
        == "console=ttyS0 ks=http://example.com/f8-i386/os/"
    )


def test_update_boot_uefi_paths(make_mock_vm):
    """
    Test virt.update(), add boot with uefi loader and nvram paths
    """
    domain_mock = make_mock_vm()

    ret = virt.update(
        "my_vm",
        boot={
            "loader": "/usr/share/OVMF/OVMF_CODE.fd",
            "nvram": "/usr/share/OVMF/OVMF_VARS.ms.fd",
        },
    )

    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("os/loader").text == "/usr/share/OVMF/OVMF_CODE.fd"
    assert setxml.find("os/loader").get("readonly") == "yes"
    assert setxml.find("os/loader").get("type") == "pflash"
    assert setxml.find("os/nvram").get("template") == "/usr/share/OVMF/OVMF_VARS.ms.fd"


def test_update_boot_uefi_auto(make_mock_vm):
    """
    Test virt.update(), change boot with efi value (automatic discovery of loader)
    """
    domain_mock = make_mock_vm()

    ret = virt.update("my_vm", boot={"efi": True})
    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("os").get("firmware") == "efi"


def test_update_boot_uefi_auto_nochange(make_mock_vm):
    """
    Test virt.update(), change boot with efi value and no change.
    libvirt converts the efi=True value into a loader and nvram config with path.
    """
    domain_mock = make_mock_vm(
        """
        <domain type='kvm' id='1'>
          <name>my_vm</name>
          <uuid>27434df0-706d-4603-8ad7-5a88d19a3417</uuid>
          <memory unit='KiB'>524288</memory>
          <currentMemory unit='KiB'>524288</currentMemory>
          <vcpu placement='static'>1</vcpu>
          <resource>
            <partition>/machine</partition>
          </resource>
          <os>
            <type arch='x86_64' machine='pc-i440fx-4.2'>hvm</type>
            <loader readonly='yes' type='pflash'>/usr/share/qemu/edk2-x86_64-code.fd</loader>
            <nvram template='/usr/share/qemu/edk2-i386-vars.fd'>/var/lib/libvirt/qemu/nvram/vm01_VARS.fd</nvram>
          </os>
          <on_reboot>restart</on_reboot>
        </domain>
        """
    )

    ret = virt.update("my_vm", boot={"efi": True})
    assert not ret["definition"]
    virt.libvirt.openAuth().defineXML.assert_not_called()


def test_update_boot_invalid(make_mock_vm):
    """
    Test virt.update(), change boot, invalid values
    """
    domain_mock = make_mock_vm()

    with pytest.raises(SaltInvocationError):
        virt.update(
            "my_vm",
            boot={
                "loader": "/usr/share/OVMF/OVMF_CODE.fd",
                "initrd": "/root/f8-i386-initrd",
            },
        )

    with pytest.raises(SaltInvocationError):
        virt.update("my_vm", boot={"efi": "Not a boolean value"})


def test_update_add_memtune(make_mock_vm):
    """
    Test virt.update(), add memory tune config case
    """
    domain_mock = make_mock_vm()
    ret = virt.update(
        "my_vm",
        mem={
            "soft_limit": "0.5g",
            "hard_limit": "1024",
            "swap_hard_limit": "2048m",
            "min_guarantee": "1 g",
        },
    )

    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert_equal_unit(setxml.find("memtune/soft_limit"), int(0.5 * 1024**3), "bytes")
    assert_equal_unit(setxml.find("memtune/hard_limit"), 1024 * 1024**2, "bytes")
    assert_equal_unit(setxml.find("memtune/swap_hard_limit"), 2048 * 1024**2, "bytes")
    assert_equal_unit(setxml.find("memtune/min_guarantee"), 1 * 1024**3, "bytes")


def test_update_add_memtune_invalid_unit(make_mock_vm):
    """
    Test virt.update(), add invalid unit to memory tuning config
    """
    domain_mock = make_mock_vm()

    with pytest.raises(SaltInvocationError):
        virt.update("my_vm", mem={"soft_limit": "2HB"})

    with pytest.raises(SaltInvocationError):
        virt.update("my_vm", mem={"soft_limit": "3.4.MB"})


def test_update_add_numatune(make_mock_vm):
    """
    Test virt.update(), add numatune config case
    """
    domain_mock = make_mock_vm()
    ret = virt.update(
        "my_vm",
        numatune={
            "memory": {"mode": "strict", "nodeset": 1},
            "memnodes": {
                0: {"mode": "strict", "nodeset": 1},
                1: {"mode": "preferred", "nodeset": 2},
            },
        },
    )

    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("numatune/memory").get("mode") == "strict"
    assert setxml.find("numatune/memory").get("nodeset") == "1"
    assert setxml.find("./numatune/memnode/[@cellid='0']").get("mode") == "strict"
    assert setxml.find("./numatune/memnode/[@cellid='0']").get("nodeset") == "1"
    assert setxml.find("./numatune/memnode/[@cellid='1']").get("mode") == "preferred"
    assert setxml.find("./numatune/memnode/[@cellid='1']").get("nodeset") == "2"


def test_update_mem_simple(make_mock_vm):
    """
    Test virt.update(), simple memory amount change
    """
    domain_mock = make_mock_vm()
    ret = virt.update("my_vm", mem=2048)
    assert ret["definition"]
    assert ret["mem"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("memory").text == str(2048 * 1024**2)
    assert setxml.find("memory").get("unit") == "bytes"
    assert domain_mock.setMemoryFlags.call_args[0][0] == 2048 * 1024


def test_update_mem(make_mock_vm):
    """
    Test virt.update(), advanced memory amounts changes
    """
    domain_mock = make_mock_vm()

    ret = virt.update(
        "my_vm",
        mem={"boot": "0.5g", "current": "2g", "max": "1g", "slots": 12},
    )
    assert ret["definition"]
    assert ret["mem"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("memory").get("unit") == "bytes"
    assert setxml.find("memory").text == str(int(0.5 * 1024**3))
    assert setxml.find("maxMemory").text == str(1 * 1024**3)
    assert setxml.find("currentMemory").text == str(2 * 1024**3)


def test_update_add_mem_backing(make_mock_vm):
    """
    Test virt.update(), add memory backing case
    """
    domain_mock = make_mock_vm()
    ret = virt.update(
        "my_vm",
        mem={
            "hugepages": [
                {"nodeset": "1-5,^4", "size": "1g"},
                {"nodeset": "4", "size": "2g"},
            ],
            "nosharepages": True,
            "locked": True,
            "source": "file",
            "access": "shared",
            "allocation": "immediate",
            "discard": True,
        },
    )

    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert {
        p.get("nodeset"): {"size": p.get("size"), "unit": p.get("unit")}
        for p in setxml.findall("memoryBacking/hugepages/page")
    } == {
        "1,2,3,5": {"size": str(1024**3), "unit": "bytes"},
        "4": {"size": str(2 * 1024**3), "unit": "bytes"},
    }
    assert setxml.find("./memoryBacking/nosharepages") is not None
    assert setxml.find("./memoryBacking/nosharepages").text is None
    assert setxml.find("./memoryBacking/nosharepages").keys() == []
    assert setxml.find("./memoryBacking/locked") is not None
    assert setxml.find("./memoryBacking/locked").text is None
    assert setxml.find("./memoryBacking/locked").keys() == []
    assert setxml.find("./memoryBacking/source").attrib["type"] == "file"
    assert setxml.find("./memoryBacking/access").attrib["mode"] == "shared"
    assert setxml.find("./memoryBacking/discard") is not None


def test_update_add_iothreads(make_mock_vm):
    """
    Test virt.update(), add iothreads
    """
    domain_mock = make_mock_vm()
    ret = virt.update("my_vm", cpu={"iothreads": 5})
    assert ret["definition"]
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("iothreads").text == "5"


def test_update_add_cputune(make_mock_vm):
    """
    Test virt.update(), adding CPU tuning parameters
    """
    domain_mock = make_mock_vm()
    cputune = {
        "shares": 2048,
        "period": 122000,
        "quota": -1,
        "global_period": 1000000,
        "global_quota": -3,
        "emulator_period": 1200000,
        "emulator_quota": -10,
        "iothread_period": 133000,
        "iothread_quota": -1,
        "vcpupin": {0: "1-4,^2", 1: "0,1", 2: "2,3", 3: "0,4"},
        "emulatorpin": "1-3",
        "iothreadpin": {1: "5-6", 2: "7-8"},
        "vcpusched": [
            {"scheduler": "fifo", "priority": 1, "vcpus": "0"},
            {"scheduler": "fifo", "priotity": 2, "vcpus": "1"},
            {"scheduler": "idle", "priotity": 3, "vcpus": "2"},
        ],
        "iothreadsched": [{"scheduler": "batch", "iothreads": "7"}],
        "cachetune": {
            "0-3": {
                0: {"level": 3, "type": "both", "size": 3},
                1: {"level": 3, "type": "both", "size": 3},
                "monitor": {1: 3, "0-3": 3},
            },
            "4-5": {"monitor": {4: 3, 5: 2}},
        },
        "memorytune": {"0-2": {0: 60}, "3-4": {0: 50, 1: 70}},
    }
    assert virt.update("my_vm", cpu={"tuning": cputune}) == {
        "definition": True,
        "disk": {"attached": [], "detached": [], "updated": []},
        "interface": {"attached": [], "detached": []},
    }
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("cputune/shares").text == "2048"
    assert setxml.find("cputune/period").text == "122000"
    assert setxml.find("cputune/quota").text == "-1"
    assert setxml.find("cputune/global_period").text == "1000000"
    assert setxml.find("cputune/global_quota").text == "-3"
    assert setxml.find("cputune/emulator_period").text == "1200000"
    assert setxml.find("cputune/emulator_quota").text == "-10"
    assert setxml.find("cputune/iothread_period").text == "133000"
    assert setxml.find("cputune/iothread_quota").text == "-1"
    assert setxml.find("cputune/vcpupin[@vcpu='0']").get("cpuset") == "1,3,4"
    assert setxml.find("cputune/vcpupin[@vcpu='1']").get("cpuset") == "0,1"
    assert setxml.find("cputune/vcpupin[@vcpu='2']").get("cpuset") == "2,3"
    assert setxml.find("cputune/vcpupin[@vcpu='3']").get("cpuset") == "0,4"
    assert setxml.find("cputune/emulatorpin").get("cpuset") == "1,2,3"
    assert setxml.find("cputune/iothreadpin[@iothread='1']").get("cpuset") == "5,6"
    assert setxml.find("cputune/iothreadpin[@iothread='2']").get("cpuset") == "7,8"
    assert setxml.find("cputune/vcpusched[@vcpus='0']").get("priority") == "1"
    assert setxml.find("cputune/vcpusched[@vcpus='0']").get("scheduler") == "fifo"
    assert setxml.find("cputune/iothreadsched").get("iothreads") == "7"
    assert setxml.find("cputune/iothreadsched").get("scheduler") == "batch"
    assert (
        setxml.find("./cputune/cachetune[@vcpus='0,1,2,3']/cache[@id='0']").get("level")
        == "3"
    )
    assert (
        setxml.find("./cputune/cachetune[@vcpus='0,1,2,3']/cache[@id='0']").get("type")
        == "both"
    )
    assert (
        setxml.find("./cputune/cachetune[@vcpus='0,1,2,3']/monitor[@vcpus='1']").get(
            "level"
        )
        == "3"
    )
    assert (
        setxml.find("./cputune/cachetune[@vcpus='4,5']/monitor[@vcpus='4']").get(
            "level"
        )
        == "3"
    )
    assert (
        setxml.find("./cputune/cachetune[@vcpus='4,5']/monitor[@vcpus='5']").get(
            "level"
        )
        == "2"
    )
    assert (
        setxml.find("./cputune/memorytune[@vcpus='0,1,2']/node[@id='0']").get(
            "bandwidth"
        )
        == "60"
    )
    assert (
        setxml.find("./cputune/memorytune[@vcpus='3,4']/node[@id='0']").get("bandwidth")
        == "50"
    )
    assert (
        setxml.find("./cputune/memorytune[@vcpus='3,4']/node[@id='1']").get("bandwidth")
        == "70"
    )


def test_update_graphics(make_mock_vm):
    """
    Test virt.update(), graphics update case
    """
    domain_mock = make_mock_vm(
        """
        <domain type='kvm' id='7'>
          <name>my_vm</name>
          <memory unit='KiB'>1048576</memory>
          <currentMemory unit='KiB'>1048576</currentMemory>
          <vcpu placement='auto'>1</vcpu>
          <on_reboot>restart</on_reboot>
          <os>
            <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
          </os>
          <devices>
            <graphics type='spice' listen='127.0.0.1' autoport='yes'>
              <listen type='address' address='127.0.0.1'/>
            </graphics>
          </devices>
        </domain>
        """
    )
    assert virt.update("my_vm", graphics={"type": "vnc"}) == {
        "definition": True,
        "disk": {"attached": [], "detached": [], "updated": []},
        "interface": {"attached": [], "detached": []},
    }
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("devices/graphics").get("type") == "vnc"


def test_update_console(make_mock_vm):
    """
    Test virt.update(), console and serial devices update case
    """
    domain_mock = make_mock_vm(
        """
        <domain type='kvm' id='7'>
          <name>my_vm</name>
          <memory unit='KiB'>1048576</memory>
          <currentMemory unit='KiB'>1048576</currentMemory>
          <vcpu placement='auto'>1</vcpu>
          <on_reboot>restart</on_reboot>
          <os>
            <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
          </os>
          <devices>
            <serial type='pty'>
              <source path='/dev/pts/4'/>
            </serial>
            <console type='pty'/>
          </devices>
        </domain>
        """
    )

    assert virt.update(
        "my_vm", serials=[{"type": "tcp"}], consoles=[{"type": "tcp"}]
    ) == {
        "definition": True,
        "disk": {"attached": [], "detached": [], "updated": []},
        "interface": {"attached": [], "detached": []},
    }
    setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
    assert setxml.find("devices/serial").attrib["type"] == "tcp"
    assert setxml.find("devices/console").attrib["type"] == "tcp"


def test_update_disks(make_mock_vm):
    """
    Test virt.udpate() with disk device changes
    """
    root_dir = os.path.join(salt.syspaths.ROOT_DIR, "srv", "salt-images")
    xml_def = """
        <domain type='kvm' id='7'>
          <name>my_vm</name>
          <memory unit='KiB'>1048576</memory>
          <currentMemory unit='KiB'>1048576</currentMemory>
          <vcpu placement='auto'>1</vcpu>
          <on_reboot>restart</on_reboot>
          <os>
            <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
          </os>
          <devices>
            <disk type='file' device='disk'>
              <driver name='qemu' type='qcow2'/>
              <source file='{}{}my_vm_system.qcow2'/>
              <backingStore/>
              <target dev='vda' bus='virtio'/>
              <alias name='virtio-disk0'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x0'/>
            </disk>
            <disk type="network" device="disk">
              <driver name='raw' type='qcow2'/>
              <source protocol='rbd' name='libvirt-pool/my_vm_data2'>
                <host name='ses2.tf.local'/>
              </source>
              <target dev='vdc' bus='virtio'/>
              <alias name='virtio-disk2'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x2'/>
            </disk>
          </devices>
        </domain>
    """.format(
        root_dir, os.sep
    )
    domain_mock = make_mock_vm(xml_def)

    mock_chmod = MagicMock()
    mock_run = MagicMock()
    with patch.dict(os.__dict__, {"chmod": mock_chmod, "makedirs": MagicMock()}):
        with patch.dict(virt.__salt__, {"cmd.run": mock_run}):
            ret = virt.update(
                "my_vm",
                disk_profile="default",
                disks=[
                    {
                        "name": "cddrive",
                        "device": "cdrom",
                        "source_file": None,
                        "model": "ide",
                    },
                    {"name": "added", "size": 2048, "io": "threads"},
                ],
            )
            added_disk_path = os.path.join(
                virt.__salt__["config.get"]("virt:images"), "my_vm_added.qcow2"
            )
            assert (
                mock_run.call_args[0][0]
                == f'qemu-img create -f qcow2 "{added_disk_path}" 2048M'
            )
            assert mock_chmod.call_args[0][0] == added_disk_path
            assert [
                (
                    ET.fromstring(disk).find("source").get("file")
                    if str(disk).find("<source") > -1
                    else None
                )
                for disk in ret["disk"]["attached"]
            ] == [None, os.path.join(root_dir, "my_vm_added.qcow2")]

            assert [
                ET.fromstring(disk).find("source").get("volume")
                or ET.fromstring(disk).find("source").get("name")
                for disk in ret["disk"]["detached"]
            ] == ["libvirt-pool/my_vm_data2"]
            assert domain_mock.attachDevice.call_count == 2
            assert domain_mock.detachDevice.call_count == 1

            setxml = ET.fromstring(virt.libvirt.openAuth().defineXML.call_args[0][0])
            assert setxml.find("devices/disk[3]/driver").get("io") == "threads"


def test_update_disks_existing_block(make_mock_vm):
    """
    Test virt.udpate() when adding existing block devices
    """
    root_dir = os.path.join(salt.syspaths.ROOT_DIR, "srv", "salt-images")
    xml_def = """
        <domain type='kvm' id='7'>
          <name>my_vm</name>
          <memory unit='KiB'>1048576</memory>
          <currentMemory unit='KiB'>1048576</currentMemory>
          <vcpu placement='auto'>1</vcpu>
          <on_reboot>restart</on_reboot>
          <os>
            <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
          </os>
          <devices>
            <disk type='file' device='disk'>
              <driver name='qemu' type='qcow2'/>
              <source file='{}{}my_vm_system.qcow2'/>
              <backingStore/>
              <target dev='vda' bus='virtio'/>
              <alias name='virtio-disk0'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x0'/>
            </disk>
          </devices>
        </domain>
    """.format(
        root_dir, os.sep
    )
    domain_mock = make_mock_vm(xml_def)

    mock_chmod = MagicMock()
    mock_run = MagicMock()
    with patch.dict(os.__dict__, {"chmod": mock_chmod, "makedirs": MagicMock()}):
        with patch.dict(
            os.path.__dict__,
            {
                "exists": MagicMock(return_value=True),
                "isfile": MagicMock(return_value=False),
            },
        ):
            with patch.dict(virt.__salt__, {"cmd.run": mock_run}):
                ret = virt.update(
                    "my_vm",
                    disk_profile="default",
                    disks=[
                        {
                            "name": "data",
                            "format": "raw",
                            "source_file": "/dev/ssd/data",
                        },
                    ],
                )
                assert [
                    (
                        ET.fromstring(disk).find("source").get("file")
                        if str(disk).find("<source") > -1
                        else None
                    )
                    for disk in ret["disk"]["attached"]
                ] == ["/dev/ssd/data"]

                assert domain_mock.attachDevice.call_count == 1
                assert domain_mock.detachDevice.call_count == 0


def test_update_nics(make_mock_vm):
    """
    Test virt.update() with NIC device changes
    """
    domain_mock = make_mock_vm(
        """
        <domain type='kvm' id='7'>
          <name>my_vm</name>
          <memory unit='KiB'>1048576</memory>
          <currentMemory unit='KiB'>1048576</currentMemory>
          <vcpu placement='auto'>1</vcpu>
          <on_reboot>restart</on_reboot>
          <os>
            <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
          </os>
          <devices>
            <interface type='network'>
              <mac address='52:54:00:39:02:b1'/>
              <source network='default' bridge='virbr0'/>
              <target dev='vnet0'/>
              <model type='virtio'/>
              <alias name='net0'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
            </interface>
            <interface type='network'>
              <mac address='52:54:00:39:02:b2'/>
              <source network='oldnet' bridge='virbr1'/>
              <target dev='vnet1'/>
              <model type='virtio'/>
              <alias name='net1'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x1'/>
            </interface>
          </devices>
        </domain>
        """
    )
    mock_config = salt.utils.yaml.safe_load(
        """
          virt:
             nic:
                myprofile:
                   - network: default
                     name: eth0
        """
    )
    with patch.dict(salt.modules.config.__opts__, mock_config):
        ret = virt.update(
            "my_vm",
            nic_profile="myprofile",
            interfaces=[
                {
                    "name": "eth0",
                    "type": "network",
                    "source": "default",
                    "mac": "52:54:00:39:02:b1",
                },
                {"name": "eth1", "type": "network", "source": "newnet"},
            ],
        )
        assert [
            ET.fromstring(nic).find("source").get("network")
            for nic in ret["interface"]["attached"]
        ] == ["newnet"]
        assert [
            ET.fromstring(nic).find("source").get("network")
            for nic in ret["interface"]["detached"]
        ] == ["oldnet"]
        domain_mock.attachDevice.assert_called_once()
        domain_mock.detachDevice.assert_called_once()


def test_update_remove_disks_nics(make_mock_vm):
    """
    Test virt.update() when removing nics and disks even if that may sound silly
    """
    root_dir = os.path.join(salt.syspaths.ROOT_DIR, "srv", "salt-images")
    xml_def = """
        <domain type='kvm' id='7'>
          <name>my_vm</name>
          <memory unit='KiB'>1048576</memory>
          <currentMemory unit='KiB'>1048576</currentMemory>
          <vcpu placement='auto'>1</vcpu>
          <on_reboot>restart</on_reboot>
          <os>
            <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
          </os>
          <devices>
            <disk type='file' device='disk'>
              <driver name='qemu' type='qcow2'/>
              <source file='{}{}my_vm_system.qcow2'/>
              <backingStore/>
              <target dev='vda' bus='virtio'/>
              <alias name='virtio-disk0'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x0'/>
            </disk>
            <interface type='network'>
              <mac address='52:54:00:39:02:b1'/>
              <source network='default' bridge='virbr0'/>
              <target dev='vnet0'/>
              <model type='virtio'/>
              <alias name='net0'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
            </interface>
          </devices>
        </domain>
    """.format(
        root_dir, os.sep
    )
    domain_mock = make_mock_vm(xml_def)

    ret = virt.update(
        "my_vm", nic_profile=None, interfaces=[], disk_profile=None, disks=[]
    )
    assert ret["interface"].get("attached", []) == []
    assert len(ret["interface"]["detached"]) == 1
    assert ret["disk"].get("attached", []) == []
    assert len(ret["disk"]["detached"]) == 1

    domain_mock.attachDevice.assert_not_called()
    assert domain_mock.detachDevice.call_count == 2


def test_update_no_change(make_mock_vm, make_mock_storage_pool):
    """
    Test virt.update() with no change
    """
    root_dir = os.path.join(salt.syspaths.ROOT_DIR, "srv", "salt-images")
    xml_def = """
        <domain type='kvm' id='7'>
          <name>my_vm</name>
          <memory unit='KiB'>1048576</memory>
          <currentMemory unit='KiB'>1048576</currentMemory>
          <vcpu placement='auto'>1</vcpu>
          <on_reboot>restart</on_reboot>
          <os>
            <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
            <boot dev="hd"/>
          </os>
          <devices>
            <disk type='file' device='disk'>
              <driver name='qemu' type='qcow2'/>
              <source file='{}{}my_vm_system.qcow2'/>
              <backingStore/>
              <target dev='vda' bus='virtio'/>
              <alias name='virtio-disk0'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x0'/>
            </disk>
            <disk type='volume' device='disk'>
              <driver name='qemu' type='qcow2'/>
              <source pool='default' volume='my_vm_data'/>
              <backingStore/>
              <target dev='vdb' bus='virtio'/>
              <alias name='virtio-disk1'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x1'/>
            </disk>
            <disk type="network" device="disk">
              <driver name='raw' type='qcow2'/>
              <source protocol='rbd' name='libvirt-pool/my_vm_data2'>
                <host name='ses2.tf.local'/>
                <host name='ses3.tf.local' port='1234'/>
                <auth username='libvirt'>
                  <secret type='ceph' usage='pool_test-rbd'/>
                </auth>
              </source>
              <target dev='vdc' bus='virtio'/>
              <alias name='virtio-disk2'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x2'/>
            </disk>
            <interface type='network'>
              <mac address='52:54:00:39:02:b1'/>
              <source network='default' bridge='virbr0'/>
              <target dev='vnet0'/>
              <model type='virtio'/>
              <alias name='net0'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
            </interface>
            <graphics type='spice' listen='127.0.0.1' autoport='yes'>
              <listen type='address' address='127.0.0.1'/>
            </graphics>
            <video>
              <model type='qxl' ram='65536' vram='65536' vgamem='16384' heads='1' primary='yes'/>
              <alias name='video0'/>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x0'/>
            </video>
            <serial type='pty'/>
            <console type='pty'/>
          </devices>
        </domain>
    """.format(
        root_dir, os.sep
    )
    domain_mock = make_mock_vm(xml_def)

    make_mock_storage_pool("default", "dir", ["my_vm_data"])
    make_mock_storage_pool(
        "test-rbd",
        "rbd",
        ["my_vm_data2"],
        source="""
            <host name='ses2.tf.local'/>
            <host name='ses3.tf.local' port='1234'/>
            <name>libvirt-pool</name>
            <auth type='ceph' username='libvirt'>
              <secret usage='pool_test-rbd'/>
            </auth>
        """,
    )
    assert virt.update(
        "my_vm",
        cpu=1,
        mem=1024,
        disk_profile="default",
        disks=[
            {"name": "data", "size": 2048, "pool": "default"},
            {"name": "data2", "size": 4096, "pool": "test-rbd", "format": "raw"},
        ],
        nic_profile="myprofile",
        interfaces=[
            {
                "name": "eth0",
                "type": "network",
                "source": "default",
                "mac": "52:54:00:39:02:b1",
            },
        ],
        graphics={
            "type": "spice",
            "listen": {"type": "address", "address": "127.0.0.1"},
        },
    ) == {
        "definition": False,
        "disk": {"attached": [], "detached": [], "updated": []},
        "interface": {"attached": [], "detached": []},
    }


def test_update_failure(make_mock_vm):
    """
    Test virt.update() with errors
    """
    domain_mock = make_mock_vm()
    virt.libvirt.openAuth().defineXML.side_effect = virt.libvirt.libvirtError(
        "Test error"
    )
    with pytest.raises(virt.libvirt.libvirtError):
        virt.update("my_vm", mem=2048)

    # Failed single update failure case
    virt.libvirt.openAuth().defineXML = MagicMock(return_value=True)
    domain_mock.setMemoryFlags.side_effect = virt.libvirt.libvirtError(
        "Failed to live change memory"
    )

    domain_mock.setVcpusFlags.return_value = 0
    assert virt.update("my_vm", cpu=4, mem=2048) == {
        "definition": True,
        "errors": ["Failed to live change memory"],
        "cpu": True,
        "disk": {"attached": [], "detached": [], "updated": []},
        "interface": {"attached": [], "detached": []},
    }


@pytest.mark.parametrize("hypervisor", ["kvm", "xen"])
def test_gen_xml_spice_default(hypervisor):
    """
    Test virt._gen_xml() with default spice graphics device
    """
    xml_data = virt._gen_xml(
        virt.libvirt.openAuth.return_value,
        "hello",
        1,
        512,
        {},
        {},
        hypervisor,
        "hvm",
        "x86_64",
        graphics={"type": "spice"},
    )
    root = ET.fromstring(xml_data)
    assert root.find("devices/graphics").attrib["type"] == "spice"
    assert root.find("devices/graphics").attrib["autoport"] == "yes"
    assert root.find("devices/graphics").attrib["listen"] == "0.0.0.0"
    assert root.find("devices/graphics/listen").attrib["type"] == "address"
    assert root.find("devices/graphics/listen").attrib["address"] == "0.0.0.0"
    if hypervisor == "kvm":
        assert (
            root.find(".//channel[@type='spicevmc']/target").get("name")
            == "com.redhat.spice.0"
        )
    else:
        assert root.find(".//channel[@type='spicevmc']") is None


def test_gen_xml_spice():
    """
    Test virt._gen_xml() with spice graphics device
    """
    xml_data = virt._gen_xml(
        virt.libvirt.openAuth.return_value,
        "hello",
        1,
        512,
        {},
        {},
        "kvm",
        "hvm",
        "x86_64",
        graphics={
            "type": "spice",
            "port": 1234,
            "tls_port": 5678,
            "listen": {"type": "none"},
        },
    )
    root = ET.fromstring(xml_data)
    assert root.find("devices/graphics").attrib["type"] == "spice"
    assert root.find("devices/graphics").attrib["autoport"] == "no"
    assert root.find("devices/graphics").attrib["port"] == "1234"
    assert root.find("devices/graphics").attrib["tlsPort"] == "5678"
    assert "listen" not in root.find("devices/graphics").attrib
    assert root.find("devices/graphics/listen").attrib["type"] == "none"
    assert "address" not in root.find("devices/graphics/listen").attrib
