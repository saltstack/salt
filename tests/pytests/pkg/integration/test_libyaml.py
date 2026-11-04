"""
Verify the onedir bundle ships a libyaml-linked PyYAML.

Regression cover for #69907 / PR #69950 (3006.x) and #69949 (3008.x):
the Linux onedir build was source-compiling PyYAML under a relenv toolchain
that has no libyaml, so `yaml.CSafeLoader`/`yaml.CSafeDumper` were absent
and every YAML load fell back to the ~10-20x slower pure-Python parser.

The test asserts libyaml is present in whatever onedir is installed at run
time. All currently-supported downgrade targets (v3006.28, v3007.15,
v3008.3+) include PR #69950, so the invariant holds across the install /
upgrade / downgrade package-test flavors.
"""

import subprocess
import sys
import textwrap

import pytest


@pytest.fixture
def python_script_bin(install_salt):
    return install_salt.binary_paths["python"]


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
    install_salt, python_script_bin, check_libyaml_file
):
    ret = install_salt.proc.run(
        *(python_script_bin + [str(check_libyaml_file)]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 0, (
        f"libyaml expected present in the onedir but the probe "
        f"failed:\n{ret.stderr}"
    )


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Only the Linux onedir build passes --no-binary=:all:; "
    "Windows/macOS already pick libyaml-linked wheels.",
)
def test_salt_yamlloader_matches_installed_version(
    install_salt, python_script_bin, tmp_path
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
    assert ret.returncode == 0, (
        "salt.utils.yamlloader.BaseLoader should be yaml.CSafeLoader in "
        "the onedir; it resolved to the pure-Python loader instead."
    )
