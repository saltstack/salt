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
    minion_ids = pytest.helpers.proxy.delta_proxy_minion_ids()

    dummy_proxy_pillar_file = """
    proxy:
      proxytype: dummy"""

    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        parallel_startup: {}
        ids:
    """.format(
        request.param,
    )

    top_file = """
    base:
      {control}:
        - controlproxy""".format(
        control=salt_delta_proxy_factory.id,
    )

    for minion_id in minion_ids:
        top_file += """
      {minion_id}:
        - dummy""".format(
            minion_id=minion_id,
        )

        controlproxy_pillar_file += """
            - {}
        """.format(
            minion_id,
        )

    tempfiles = []
    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    tempfiles = [top_tempfile, controlproxy_tempfile]

    dummy_proxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "dummy.sls", dummy_proxy_pillar_file
    )

    with top_tempfile, controlproxy_tempfile, dummy_proxy_tempfile:
        yield


@pytest.fixture(scope="module")
def salt_delta_proxy(salt_master, salt_delta_proxy_factory, deltaproxy_pillar_tree):
    """
    A running salt-proxy fixture
    """
    assert salt_master.is_running()
    with salt_delta_proxy_factory.started():
        yield salt_delta_proxy_factory
