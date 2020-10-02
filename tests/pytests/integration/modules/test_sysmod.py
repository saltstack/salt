import fnmatch
import re

from tests.support.helpers import slowTest


@slowTest
def test_valid_docs(salt_call_cli):
    """
    Make sure no functions are exposed that don't have valid docstrings
    """

    allow_failure = (
        "cmd.win_runas",
        "cp.recv",
        "cp.recv_chunked",
        "glance.warn_until",
        "ipset.long_range",
        "libcloud_compute.get_driver",
        "libcloud_dns.get_driver",
        "libcloud_loadbalancer.get_driver",
        "libcloud_storage.get_driver",
        "log.critical",
        "log.debug",
        "log.error",
        "log.exception",
        "log.info",
        "log.warning",
        "lowpkg.bin_pkg_info",
        "lxc.run_cmd",
        "mantest.install",
        "mantest.search",
        "nspawn.restart",
        "nspawn.stop",
        "pkg.expand_repo_def",
        "pip.iteritems",
        "pip.parse_version",
        "peeringdb.clean_kwargs",
        "runtests_decorators.depends",
        "runtests_decorators.depends_will_fallback",
        "runtests_decorators.missing_depends",
        "runtests_decorators.missing_depends_will_fallback",
        "state.apply",
        "status.list2cmdline",
        "swift.head",
        "test.rand_str",
        "travisci.parse_qs",
        "vsphere.clean_kwargs",
        "vsphere.disconnect",
        "vsphere.get_service_instance_via_proxy",
        "vsphere.gets_service_instance_via_proxy",
        "vsphere.supports_proxies",
        "vsphere.test_vcenter_connection",
        "vsphere.wraps",
    )
    allow_failure_glob = (
        "runtests_decorators.*",
        "runtests_helpers.*",
        "vsphere.*",
    )
    missing_example = set()
    missing_docstring = set()
    ret = salt_call_cli.run("sys.doc")
    assert ret.exitcode == 0, ret

    example_regex = re.compile(r"([E|e]xample(?:s)?)+(?:.*):?")
    for fun, docstring in ret.json.items():
        if fun in allow_failure:
            continue
        else:
            for pat in allow_failure_glob:
                if fnmatch.fnmatch(fun, pat):
                    matched_glob = True
                    break
            else:
                matched_glob = False
            if matched_glob:
                continue
        if not isinstance(docstring, str):
            missing_docstring.add(fun)
        elif isinstance(docstring, dict) and not example_regex.search(docstring):
            missing_example.add(fun)

        missing_docstring_error = "The following functions do not have a docstring: {}".format(
            ",".join([repr(func) for func in sorted(missing_docstring)])
        )
        assert not missing_docstring, missing_docstring_error
        missing_example_error = "The following functions do not have a CLI example: {}".format(
            ",".join([repr(func) for func in sorted(missing_example)])
        )
        assert not missing_example, missing_example_error
