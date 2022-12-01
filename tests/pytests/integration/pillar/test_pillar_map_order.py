import random
import textwrap

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def minion_run(salt_minion, salt_cli):
    """Convenience fixture that runs the ``salt`` CLI targeting the minion."""

    def _run(*args, minion_tgt=salt_minion.id, **kwargs):
        ret = salt_cli.run(*args, minion_tgt=minion_tgt, **kwargs)
        assert ret.returncode == 0
        return ret.data

    yield _run


def test_pillar_map_order(salt_master, minion_run):
    """Test iteration order of YAML map entries in a Pillar ``.sls`` file.

    This test generates a Pillar ``.sls`` file containing an ordinary YAML map
    and tests whether the resulting Python object preserves iteration order.
    Random keys are used to ensure that iteration order does not coincidentally
    match.  The generated Pillar YAML file looks like this:

    .. code-block:: yaml

        data:
          k3334244338: 0
          k3444116829: 1
          k2072366017: 2
          # ... omitted for brevity ...
          k1638299831: 19

    A jinja template iterates over the entries in the resulting object to ensure
    that iteration order is preserved.  The expected output looks like:

    .. code-block:: text

        k3334244338 0
        k3444116829 1
        k2072366017 2
        ... omitted for brevity ...
        k1638299831 19

    Note: Python 3.6 switched to a new ``dict`` implementation that iterates in
    insertion order.  This behavior was made an official part of the ``dict``
    API in Python 3.7:

    * https://docs.python.org/3.6/whatsnew/3.6.html#new-dict-implementation
    * https://mail.python.org/pipermail/python-dev/2017-December/151283.html
    * https://docs.python.org/3.7/whatsnew/3.7.html

    Thus, this test may fail on Python 3.5 and older.  However, Salt currently
    requires a newer version of Python, so this should not be a problem.

    This is a regression test for:
    https://github.com/saltstack/salt/issues/12161
    """
    # Filter the random keys through a set to avoid duplicates.
    keys = list({f"k{random.getrandbits(32)}" for _ in range(20)})
    # Avoid unintended correlation with set()'s iteration order.
    random.shuffle(keys)
    items = [(k, i) for i, k in enumerate(keys)]
    top_yaml = "base: {'*': [data]}\n"
    top_sls = salt_master.pillar_tree.base.temp_file("top.sls", top_yaml)
    data_yaml = "data:\n" + "".join(f"  {k}: {v}\n" for k, v in items)
    data_sls = salt_master.pillar_tree.base.temp_file("data.sls", data_yaml)
    tmpl_jinja = textwrap.dedent(
        """\
            {%- for k, v in pillar['data'].items() %}
            {{ k }} {{ v }}
            {%- endfor %}
        """
    )
    want = "\n" + "".join(f"{k} {v}\n" for k, v in items)
    try:
        with top_sls, data_sls:
            assert minion_run("saltutil.refresh_pillar", wait=True) is True
            got = minion_run(
                "file.apply_template_on_contents",
                tmpl_jinja,
                template="jinja",
                context={},
                defaults={},
                saltenv="base",
            )
            assert got == want
    finally:
        assert minion_run("saltutil.refresh_pillar", wait=True) is True
