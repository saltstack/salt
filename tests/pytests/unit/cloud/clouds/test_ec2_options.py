"""
Documentation-tracking tests for the EC2 driver.

Backed by issue #60679: the ``register_image`` function previously documented
only a single-snapshot CLI example and did not list the kwargs accepted by
the function. The replacement docstring must list every kwarg consulted by
the function body so the generated reference page is complete.
"""

from salt.cloud.clouds import ec2

REGISTER_IMAGE_DOCUMENTED_KWARGS = (
    "ami_name",
    "description",
    "architecture",
    "virtualization_type",
    "root_device_name",
    "snapshot_id",
    "volume_type",
    "block_device_mapping",
)


def test_register_image_documents_every_kwarg():
    doc = ec2.register_image.__doc__ or ""
    for option in REGISTER_IMAGE_DOCUMENTED_KWARGS:
        assert option in doc, (
            f"register_image() kwarg {option!r} consulted by the function "
            "but absent from the docstring"
        )


def test_register_image_documents_multi_volume_cli_example():
    doc = ec2.register_image.__doc__ or ""
    # The shell parsing caveat described in #60679 must be documented so
    # users know to pass block_device_mapping as JSON/YAML.
    assert "block_device_mapping=" in doc
    assert "DeviceName" in doc and "SnapshotId" in doc
    assert "/dev/xvda" in doc and "/dev/sdb" in doc


def test_register_image_documents_single_snapshot_example():
    doc = ec2.register_image.__doc__ or ""
    assert "snapshot_id=snap-xxxxxxxx" in doc
    assert "ami_name=my_ami" in doc
