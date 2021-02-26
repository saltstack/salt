import pytest
import salt.utils.hub as hub

pytest.importorskip("pop", reason="Test requires pop to be installed")
pytest.importorskip("heist", reason="Test requires heist to be installed")


@pytest.fixture()
def configure_loader_modules():
    return {hub: {"__context__": {}}}


@pytest.fixture()
def test_hub():
    """
    Test the hub using the heist project
    """
    return hub.hub(
        "heist",
        subs=["acct", "artifact", "rend", "roster", "service", "tunne"],
        sub_dirs=["heist", "service"],
        confs=["heist", "acct"],
    )


@pytest.mark.parametrize("sub", ["config", "heist"])
def test_subs(sub, test_hub):
    assert hasattr(test_hub, sub)


@pytest.mark.parametrize("sub_dir", ["heist", "service"])
def test_sub_dirs(sub_dir, test_hub):
    assert hasattr(test_hub, sub_dir)


@pytest.mark.parametrize("conf", ["heist", "acct"])
def test_confs(conf, test_hub):
    hasattr(test_hub.OPT, conf)
