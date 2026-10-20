"""
Verify the onedir bundle ships a libyaml-linked PyYAML.

Regression cover for #69907 / PR #69950 (3006.x) and #69949 (3008.x):
the Linux onedir build was source-compiling PyYAML under a relenv toolchain
that has no libyaml, so `yaml.CSafeLoader`/`yaml.CSafeDumper` were absent
and every YAML load fell back to the ~10-20x slower pure-Python parser.

The test asserts the invariant that matches whatever salt is installed at
run time, so it works uniformly across the install / upgrade / downgrade
package-test flavors:

- install / post-upgrade: current onedir is on disk, expect libyaml present
- post-downgrade: previous onedir is on disk. That release predates the
  fix, so expect libyaml absent (documenting the pre-fix state so a silent
  regression on the previous branch is still caught).
"""

import subprocess
import sys
import textwrap

import pytest


@pytest.fixture
def python_script_bin(install_salt):
    return install_salt.binary_paths["python"]


@pytest.fixture
def libyaml_expected(install_salt):
    """Current onedir (install/upgrade) ships libyaml; the previous release
    (post-downgrade validation) predates PR #69950 and does not."""
    return not install_salt.use_prev_version


@pytest.fixture
def check_libyaml_file(tmp_path):
    script_path = tmp_path / "check_libyaml.py"
    script_path.write_text(
        textwrap.dedent(
            """
        import sys
        import yaml

        assert hasattr(yaml, "CSafeLoader"), "yaml.CSafeLoader missing"
        assert hasattr(yaml, "CSafeDumper"), "yaml.CSafeDumper missing"
        assert hasattr(yaml, "CLoader"), "yaml.CLoader missing"
        assert hasattr(yaml, "CDumper"), "yaml.CDumper missing"

        import _yaml  # noqa: F401  # PyYAML C extension

        loader = yaml.CSafeLoader("key: value\\n")
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()
        assert data == {"key": "value"}, data
        sys.exit(0)
        """
        )
    )
    return script_path


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only the Linux onedir build passes --no-binary=:all:; "
    "Windows/macOS already pick libyaml-linked wheels.",
)
def test_libyaml_matches_installed_version(
    install_salt, python_script_bin, check_libyaml_file, libyaml_expected
):
    ret = install_salt.proc.run(
        *(python_script_bin + [str(check_libyaml_file)]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    if libyaml_expected:
        assert ret.returncode == 0, (
            f"libyaml expected present in the current onedir but the probe "
            f"failed:\n{ret.stderr}"
        )
    else:
        assert ret.returncode != 0, (
            "libyaml unexpectedly present in the previous-release onedir. "
            "If PR #69950 was backported earlier than 3006.28, drop this "
            "test's downgrade branch."
        )


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only the Linux onedir build passes --no-binary=:all:; "
    "Windows/macOS already pick libyaml-linked wheels.",
)
def test_salt_yamlloader_matches_installed_version(
    install_salt, python_script_bin, tmp_path, libyaml_expected
):
    script_path = tmp_path / "check_yamlloader.py"
    script_path.write_text(
        textwrap.dedent(
            """
        import sys
        import yaml
        import salt.utils.yamlloader

        sys.exit(0 if salt.utils.yamlloader.BaseLoader is getattr(yaml, "CSafeLoader", None) else 1)
        """
        )
    )
    ret = install_salt.proc.run(
        *(python_script_bin + [str(script_path)]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    if libyaml_expected:
        assert ret.returncode == 0, (
            "salt.utils.yamlloader.BaseLoader should be yaml.CSafeLoader in "
            "the current onedir; it resolved to the pure-Python loader "
            "instead."
        )
    else:
        assert ret.returncode != 0, (
            "salt.utils.yamlloader.BaseLoader unexpectedly resolves to "
            "yaml.CSafeLoader in the previous-release onedir. If PR #69950 "
            "was backported earlier than 3006.28, drop this test's downgrade "
            "branch."
        )
