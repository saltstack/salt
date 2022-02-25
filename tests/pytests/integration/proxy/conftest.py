import pytest


@pytest.fixture(scope="module")
def salt_proxy(salt_master, salt_proxy_factory):
    """
    A running salt-proxy fixture
    """
    assert salt_master.is_running()
    with salt_proxy_factory.started():
        yield salt_proxy_factory


@pytest.fixture(scope="module")
def deltaproxy_pillar_tree(salt_master, salt_delta_proxy_factory):
    """
    Create the pillar files for controlproxy and two dummy proxy minions
    """
    proxy_one, proxy_two = pytest.helpers.proxy.delta_proxy_minion_ids()
    top_file = """
    base:
      {control}:
        - controlproxy
      {one}:
        - {one}
      {two}:
        - {two}
    """.format(
        control=salt_delta_proxy_factory.id,
        one=proxy_one,
        two=proxy_two,
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        ids:
          - {}
          - {}
    """.format(
        proxy_one, proxy_two
    )

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: dummy
    """

    dummy_proxy_two_pillar_file = """
    proxy:
      proxytype: dummy
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        "{}.sls".format(proxy_one), dummy_proxy_one_pillar_file
    )
    dummy_proxy_two_tempfile = salt_master.pillar_tree.base.temp_file(
        "{}.sls".format(proxy_two), dummy_proxy_two_pillar_file
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile, dummy_proxy_two_tempfile:
        yield


@pytest.fixture(scope="module")
def salt_delta_proxy(salt_master, salt_delta_proxy_factory, deltaproxy_pillar_tree):
    """
    A running salt-proxy fixture
    """
    assert salt_master.is_running()
    with salt_delta_proxy_factory.started():
        yield salt_delta_proxy_factory
