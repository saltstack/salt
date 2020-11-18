import salt.modules.virt as virt
from salt._compat import ElementTree as ET
from tests.support.mock import MagicMock, patch

from .test_helpers import append_to_XMLDesc


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
    define_mock = virt.libvirt.openAuth().defineXML
    setxml = ET.fromstring(define_mock.call_args[0][0])
    assert "block" == setxml.find(".//disk[3]").get("type")
    assert "/path/to/vdb/vdb1" == setxml.find(".//disk[3]/source").get("dev")

    # Note that my_vm-file-data was not an existing volume before the update
    assert "file" == setxml.find(".//disk[4]").get("type")
    assert "/path/to/default/my_vm_file-data" == setxml.find(".//disk[4]/source").get(
        "file"
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
    domain_mock = make_mock_vm(vm_def)

    pool_mock = make_mock_storage_pool(
        "default", "dir", ["srv01_system", "srv01_data", "vm05_system"]
    )

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
    """
    ]
    subprocess_mock.Popen = popen_mock

    with patch.dict(virt.__dict__, {"subprocess": subprocess_mock}):
        assert {
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
        } == virt.get_disks("srv01")
