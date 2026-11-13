import subprocess
import sys

from tests.support.paths import CODE_DIR


def test_module_can_be_imported_before_salt_master():
    """
    salt.master imports salt.utils.channel, so salt.utils.channel must not
    import salt.master at module level. Run in a new interpreter so that
    modules imported by other tests cannot hide a circular import.
    """
    ret = subprocess.run(
        [sys.executable, "-c", "import salt.utils.channel"],
        cwd=CODE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ret.returncode == 0, ret.stderr
