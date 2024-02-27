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
def deltaproxy_parallel_startup():
    yield from [True, False]


@pytest.fixture(
    scope="module",
    params=[True, False],
    ids=["parallel_startup=True", "parallel_startup=False"],
)
def deltaproxy_pillar_tree(request, salt_master, salt_delta_proxy_factory):
    """
    Create the pillar files for controlproxy and two dummy proxy minions
    """
    (
        proxy_one,
        proxy_two,
        proxy_three,
        proxy_four,
    ) = pytest.helpers.proxy.delta_proxy_minion_ids()

    top_file = """
    base:
      {control}:
        - controlproxy
      {one}:
        - {one}
      {two}:
        - {two}
      {three}:
        - {three}
      {four}:
        - {four}
    """.format(
        control=salt_delta_proxy_factory.id,
        one=proxy_one,
        two=proxy_two,
        three=proxy_three,
        four=proxy_four,
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        parallel_startup: {}
        ids:
          - {}
          - {}
          - {}
          - {}
    """.format(
        request.param,
        proxy_one,
        proxy_two,
        proxy_three,
        proxy_four,
    )

    dummy_proxy_pillar_file = """
    proxy:
      proxytype: dummy
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_one}.sls", dummy_proxy_pillar_file
    )
    dummy_proxy_two_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_two}.sls", dummy_proxy_pillar_file
    )
    dummy_proxy_three_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_three}.sls", dummy_proxy_pillar_file
    )
    dummy_proxy_four_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_four}.sls", dummy_proxy_pillar_file
    )
    with (
        top_tempfile
    ), (
        controlproxy_tempfile
    ), (
        dummy_proxy_one_tempfile
    ), dummy_proxy_two_tempfile, dummy_proxy_three_tempfile, dummy_proxy_four_tempfile:
        yield


@pytest.fixture(scope="module")
def salt_delta_proxy(salt_master, salt_delta_proxy_factory, deltaproxy_pillar_tree):
    """
    A running salt-proxy fixture
    """
    assert salt_master.is_running()
    with salt_delta_proxy_factory.started():
        yield salt_delta_proxy_factory
