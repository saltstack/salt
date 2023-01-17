import hashlib
import logging
import sys

import pytest

log = logging.getLogger(__name__)


@pytest.mark.usefixtures("version")
def test_hashes(install_salt, salt_cli, salt_minion):
    """
    Test the hashes generated for both single binary
    and the onedir packages.
    """
    if not install_salt.compressed:
        pytest.skip("This test requires the single binary or onedir package")

    hashes = install_salt.salt_hashes
    pkg = install_salt.pkgs[0]

    with open(pkg, "rb") as fh:
        file_bytes = fh.read()

    delimiter = "/"
    if sys.platform.startswith("win"):
        delimiter = "\\"

    for _hash in hashes.keys():
        hash_file = hashes[_hash]["file"]
        found_hash = False
        with open(hash_file) as fp:
            for line in fp:
                if pkg.rsplit(delimiter, 1)[-1] in line:
                    found_hash = True
                    assert (
                        getattr(hashlib, _hash.lower())(file_bytes).hexdigest()
                        == line.split()[0]
                    )

        if not found_hash:
            assert False, f"A {_hash} hash was not found in {hash_file} for pkg {pkg}"
