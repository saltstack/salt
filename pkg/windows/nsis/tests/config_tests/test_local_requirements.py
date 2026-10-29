"""Run the real NSIS requirements hook with a recording salt-pip executable."""

import json
import subprocess
from pathlib import Path

import psutil
import pytest


@pytest.fixture
def install_dir(tmp_path, request):
    path = tmp_path / "Salt runtime" if request.param else Path(pytest.INST_DIR)
    assert pytest.helpers.clean_env(str(path))
    try:
        if request.param:
            # Exercise an upgrade from a running service at a custom install path.
            pytest.helpers.install_salt(["/S", f'/install-dir="{path}"'])
            assert psutil.win_service_get("salt-minion").status() == "running"
        yield path
    finally:
        assert pytest.helpers.clean_env(str(path))


@pytest.mark.parametrize(
    "install_dir", [False, True], indirect=True, ids=["fresh", "upgrade-custom-path"]
)
@pytest.mark.parametrize(
    "requirements,pip_exit",
    [
        pytest.param(None, 0, id="absent"),
        pytest.param("", 0, id="empty"),
        pytest.param("pymysql==1.1.1\n", 0, id="success"),
        pytest.param("unavailable-package\n", 17, id="failure"),
    ],
)
def test_local_requirements(install_dir, tmp_path, monkeypatch, requirements, pip_exit):
    pytest.helpers.existing_config()
    config = Path(pytest.DATA_DIR) / "conf"
    requirements_file = config / "local-requirements.txt"
    if requirements is not None:
        requirements_file.write_text(requirements)

    log = tmp_path / "pip calls.jsonl"
    monkeypatch.setenv("NSIS_TEST_PIP_LOG", str(log))
    monkeypatch.setenv("NSIS_TEST_PIP_EXIT", str(pip_exit))
    # An inherited value must be replaced with the installer's actual config dir.
    monkeypatch.setenv("SALT_CONFIG_DIR", str(tmp_path / "wrong config"))

    # DEVNULL avoids inheritable pipe handles being held open by service children.
    result = subprocess.run(
        f'"{pytest.INST_BIN}" /S /start-minion=1 /install-dir="{install_dir}"',
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )
    assert result.returncode == (1 if pip_exit else 0)
    if requirements is None:
        assert not log.exists(), "salt-pip must not run without local requirements"
    else:
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        assert len(calls) == 1
        call = calls[0]
        assert Path(call["executable"]) == install_dir / "salt-pip.exe"
        assert call["args"] == ["install", "--requirement", str(requirements_file)]
        assert Path(call["config_dir"]) == config
        assert call["service"] == "SERVICE_STOPPED"
        assert requirements_file.read_text() == requirements

    # Successful hooks allow startup; a pip failure must leave the service stopped.
    service = psutil.win_service_get("salt-minion")
    assert service.status() == ("stopped" if pip_exit else "running")
