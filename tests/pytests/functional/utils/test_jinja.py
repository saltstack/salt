import pytest
from jinja2.exceptions import TemplateNotFound

import salt.utils.jinja
from salt.utils.odict import OrderedDict


def test_utils_jinja_cache_removed_file_from_root(temp_salt_minion, tmp_path):
    """
    this tests for a condition where an included jinja template
    is removed from the salt filesystem, but is still loaded from
    the cache.
    """
    opts = temp_salt_minion.config.copy()
    file_root = tmp_path / "root"
    file_root.mkdir(parents=True, exist_ok=True)
    cache_root = tmp_path / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    filename = "jinja_cache"
    sls_file = file_root / f"{filename}.sls"
    jinja_file = file_root / f"{filename}.jinja"
    sls_file.write_text("{% include '" + filename + ".jinja' %}")
    jinja_file.write_text("{% set this = 'that' %}")

    # Stop using OrderedDict once we drop Py3.5 support
    opts["file_roots"] = OrderedDict()
    opts["file_roots"]["base"] = [str(file_root)]
    opts["cachedir"] = str(cache_root)
    opts["master_type"] = "disable"
    opts["file_client"] = "local"

    loader = salt.utils.jinja.SaltCacheLoader(
        opts,
        "base",
    )
    # sls file is in the root
    loader.get_source(None, sls_file.name)
    # jinja file is in the root
    loader.get_source(None, jinja_file.name)
    # both files cached
    assert len(loader.cached) == 2

    # remove the jinja file and reset loader
    jinja_file.unlink()
    loader = salt.utils.jinja.SaltCacheLoader(
        opts,
        "base",
    )
    # sls file is still in the root
    loader.get_source(None, sls_file.name)
    # jinja file is gone from the root
    with pytest.raises(TemplateNotFound):
        loader.get_source(None, jinja_file.name)
    # only one was cached this run
    assert len(loader.cached) == 1
    # the cached jinja file is still present, but not used
    assert (cache_root / "files" / "base" / jinja_file.name).exists()
