import subprocess

import pytest

import salt.version
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.helpers import VirtualEnv, dedent

pytestmark = [
    pytest.mark.skip_if_binaries_missing(*KNOWN_BINARY_NAMES, check_all=False),
    pytest.mark.requires_network,
]


@pytest.fixture(scope="module")
def _extra_requirements():
    extra_requirements = []
    for name, version in salt.version.dependency_information():
        if name in ["PyYAML", "packaging", "looseversion"]:
            extra_requirements.append(f"{name}=={version}")
    return extra_requirements


@pytest.mark.slow_test
@pytest.mark.parametrize(
    "pip_contraint",
    [
        # Latest pip 18
        "<19.0",
        # Latest pip 19
        "<20.0",
        # Latest pip 20
        "<21.0",
        # Latest pip
        None,
    ],
)
def test_importable_installation_error(_extra_requirements, pip_contraint):
    code = dedent(
        """\
    import sys
    import traceback
    try:
        import salt.states.pip_state
        salt.states.pip_state.InstallationError
    except ImportError as exc:
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)
    except AttributeError as exc:
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        sys.exit(2)
    except Exception as exc:
        traceback.print_exc(exc, file=sys.stdout)
        sys.stdout.flush()
        sys.exit(3)
    sys.exit(0)
    """
    )
    with VirtualEnv() as venv:
        venv.install(*_extra_requirements)
        if pip_contraint:
            venv.install(f"pip{pip_contraint}")
        try:
            subprocess.check_output([venv.venv_python, "-c", code])
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 1:
                pytest.fail(f"Failed to import pip:\n{exc.output}")
            elif exc.returncode == 2:
                pytest.fail(
                    f"Failed to import InstallationError from pip:\n{exc.output}"
                )
            else:
                pytest.fail(exc.output)
