import salt.modules.virt as virt
from salt._compat import ElementTree as ET


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
              <source file='/path/to/default/vm03_system'/>
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
        ],
    )

    assert ret["definition"]
    define_mock = virt.libvirt.openAuth().defineXML
    setxml = ET.fromstring(define_mock.call_args[0][0])
    assert "block" == setxml.find(".//disk[3]").get("type")
    assert "/path/to/vdb/vdb1" == setxml.find(".//disk[3]/source").get("dev")
