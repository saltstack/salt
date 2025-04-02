#
# Author: Tyler Johnson <tjohnson@saltstack.com>
#

"""
Idem Support
============

This state provides access to idem states

.. versionadded:: 3002
"""
import pathlib
import re

__virtualname__ = "idem"


def __virtual__():
    if "idem.hub" in __utils__:
        return __virtualname__
    else:
        return False, "idem is not available"


def _get_refs(sources, tree):
    """
    Determine where the sls sources are
    """
    sls_sources = []
    SLSs = []
    if tree:
        sls_sources.append(f"file://{tree}")
    for sls in sources:
        path = pathlib.Path(sls)
        if path.is_file():
            ref = str(path.stem if path.suffix == ".sls" else path.name)
            SLSs.append(ref)
            implied = f"file://{path.parent}"
            if implied not in sls_sources:
                sls_sources.append(implied)
        else:
            SLSs.append(sls)
    return sls_sources, SLSs


def _get_low_data(low_data):
    """
    Get salt-style low data from an idem state name
    """
    # state_|-id_|-name_|-function
    match = re.match(r"(.+)_\|-(.+)_\|-(.+)_\|-(.+)", low_data)
    return {
        "state": match.group(1),
        "__id__": match.group(2),
        "name": match.group(3),
        "fun": match.group(4),
    }


def state(
    name,
    sls,
    acct_file=None,
    acct_key=None,
    acct_profile=None,
    cache_dir=None,
    render=None,
    runtime=None,
    source_dir=None,
    test=False,
):
    """
    Execute an idem sls file through a salt state

    sls
        A list of idem sls files or sources

    acct_file
        Path to the acct file used in generating idem ctx parameters.
        Defaults to the value in the ACCT_FILE environment variable.

    acct_key
        Key used to decrypt the acct file.
        Defaults to the value in the ACCT_KEY environment variable.

    acct_profile
        Name of the profile to add to idem's ctx.acct parameter
        Defaults to the value in the ACCT_PROFILE environment variable.

    cache_dir
        The location to use for the cache directory

    render
        The render pipe to use, this allows for the language to be specified (jinja|yaml)

    runtime
        Select which execution runtime to use (serial|parallel)

    source_dir
        The directory containing sls files

    .. code-block:: yaml

        cheese:
            idem.state:
                - runtime: parallel
                - sls:
                    - idem_state.sls
                    - sls_source

    :maturity:      new
    :depends:       acct, pop, pop-config, idem
    :platform:      all
    """
    hub = __utils__["idem.hub"]()

    if isinstance(sls, str):
        sls = [sls]

    sls_sources, SLSs = _get_refs(sls, source_dir or hub.OPT.idem.tree)

    coro = hub.idem.state.apply(
        name=name,
        sls_sources=sls_sources,
        render=render or hub.OPT.idem.render,
        runtime=runtime or hub.OPT.idem.runtime,
        subs=["states"],
        cache_dir=cache_dir or hub.OPT.idem.cache_dir,
        sls=SLSs,
        test=test,
        acct_file=acct_file or hub.OPT.acct.acct_file,
        acct_key=acct_key or hub.OPT.acct.acct_key,
        acct_profile=acct_profile or hub.OPT.acct.acct_profile or "default",
    )
    hub.pop.Loop.run_until_complete(coro)

    errors = hub.idem.RUNS[name]["errors"]
    success = not errors

    running = []
    for idem_name, idem_return in hub.idem.RUNS[name]["running"].items():
        standardized_idem_return = {
            "name": idem_return["name"],
            "changes": idem_return["changes"],
            "result": idem_return["result"],
            "comment": idem_return.get("comment"),
            "low": _get_low_data(idem_name),
        }
        running.append(standardized_idem_return)

    return {
        "name": name,
        "result": success,
        "comment": f"Ran {len(running)} idem states" if success else errors,
        "changes": {},
        "sub_state_run": running,
    }
