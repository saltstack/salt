"""
Structural validation of the HAProxy reference configuration in
``doc/topics/tutorials/master-cluster-reference.rst``.

We do not require ``haproxy -c -f`` to be installed in CI -- the test
parses the documented config with a small structural parser and asserts
the invariants that matter for a master-cluster front-end:

* Both required frontends (``salt-master-pub`` and ``salt-master-req``)
  exist and ``bind`` on the documented ports (``4505`` and ``4506``).
* Each frontend has a matching backend with every cluster peer listed
  as a ``server`` line on the right port.
* ``mode tcp`` everywhere (HTTP mode would reject ZMTP / Salt TCP
  transport on the wire).
* ``balance roundrobin`` (round-robin is intentional; sticky sessions
  would concentrate load on whichever peer a minion first hashed to).
* The publish frontend's ``timeout client`` / publish backend's
  ``timeout server`` are >= the default ``publish_session`` (86400s).
* The cluster-internal ``cluster_pool_port`` (4520) is NOT bound by
  any frontend -- exposing the Raft RPC port through the minion LB
  would break the cluster majority calculation.
"""

import pathlib
import re

import pytest

DOC_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "doc"
    / "topics"
    / "tutorials"
    / "master-cluster-reference.rst"
)


def _extract_haproxy_config():
    """
    Return the HAProxy block from the reference page as a plain string.
    The block is the only ``.. code-block:: text`` in the file and the
    body is 4-space indented under the directive.
    """
    text = DOC_PATH.read_text()
    pattern = re.compile(
        r"^\.\. code-block:: text\s*\n\s*\n((?:(?: {4,}|\t).*\n|\s*\n)+)",
        re.MULTILINE,
    )
    matches = pattern.findall(text)
    assert matches, "No HAProxy ``code-block:: text`` block found"
    # The HAProxy block contains ``global`` / ``defaults`` / ``frontend``
    # / ``backend`` keywords; the existing-tutorial page also has a
    # text block but only with ``frontend`` blocks.  Pick the most
    # complete one (the longest).
    raw = max(matches, key=len)
    return "\n".join(
        line[4:] if line.startswith("    ") else line for line in raw.splitlines()
    )


class HAProxySection:
    """Simple holder for one named HAProxy section (frontend/backend)."""

    def __init__(self, kind, name):
        self.kind = kind
        self.name = name
        self.lines = []
        self.servers = []  # list of (name, ip, port)
        self.binds = []  # list of (ip, port)

    def directives(self, name):
        """
        Return every line in this section whose leading tokens match
        ``name`` (one OR two-word directive, e.g. ``mode`` or
        ``timeout client``).
        """
        wanted = name.split()
        result = []
        for ln in self.lines:
            tokens = ln.split()
            if tokens[: len(wanted)] == wanted:
                result.append(ln)
        return result

    def directive_value(self, name):
        d = self.directives(name)
        if not d:
            return None
        wanted_words = len(name.split())
        return " ".join(d[0].split()[wanted_words:])


def _parse_haproxy(config_text):
    """
    Minimal HAProxy parser: split into named sections, collect
    ``server`` and ``bind`` lines into structured form.
    """
    sections = []
    current = None
    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split()
        if head[0] in ("global", "defaults"):
            current = HAProxySection(head[0], head[0])
            sections.append(current)
            continue
        if head[0] in ("frontend", "backend") and len(head) >= 2:
            current = HAProxySection(head[0], head[1])
            sections.append(current)
            continue
        if current is None:
            continue
        current.lines.append(line)
        if head[0] == "server" and len(head) >= 3:
            srv_name = head[1]
            addr = head[2]
            m = re.match(r"^([\d.]+):(\d+)$", addr)
            if m:
                current.servers.append((srv_name, m.group(1), int(m.group(2))))
        elif head[0] == "bind" and len(head) >= 2:
            m = re.match(r"^([\d.]+):(\d+)$", head[1])
            if m:
                current.binds.append((m.group(1), int(m.group(2))))
    return sections


@pytest.fixture(scope="module")
def haproxy_sections():
    return _parse_haproxy(_extract_haproxy_config())


@pytest.fixture(scope="module")
def section_by_name(haproxy_sections):
    return {(s.kind, s.name): s for s in haproxy_sections}


def test_required_sections_exist(section_by_name):
    required = {
        ("global", "global"),
        ("defaults", "defaults"),
        ("frontend", "salt-master-pub"),
        ("backend", "salt-master-pub-backend"),
        ("frontend", "salt-master-req"),
        ("backend", "salt-master-req-backend"),
    }
    missing = required - set(section_by_name)
    assert not missing, f"Missing HAProxy sections: {missing}"


def test_publish_frontend_binds_4505(section_by_name):
    pub = section_by_name[("frontend", "salt-master-pub")]
    bound_ports = [port for _, port in pub.binds]
    assert (
        4505 in bound_ports
    ), f"Publish frontend must bind 4505, binds were: {pub.binds}"


def test_request_frontend_binds_4506(section_by_name):
    req = section_by_name[("frontend", "salt-master-req")]
    bound_ports = [port for _, port in req.binds]
    assert (
        4506 in bound_ports
    ), f"Request frontend must bind 4506, binds were: {req.binds}"


def test_cluster_pool_port_not_exposed(haproxy_sections):
    """``cluster_pool_port`` (4520) MUST NOT appear on any frontend."""
    for section in haproxy_sections:
        if section.kind != "frontend":
            continue
        for _, port in section.binds:
            assert port != 4520, (
                f"Frontend {section.name} binds the cluster RPC port "
                f"4520 -- exposing it through the minion LB will "
                f"break Raft majority calculation."
            )


def test_backends_use_tcp_mode(section_by_name):
    for key in (
        ("frontend", "salt-master-pub"),
        ("backend", "salt-master-pub-backend"),
        ("frontend", "salt-master-req"),
        ("backend", "salt-master-req-backend"),
    ):
        section = section_by_name[key]
        # mode can come from the section directly OR from the defaults
        # block; the reference page sets ``mode tcp`` in defaults and
        # also re-asserts it per section.
        mode = section.directive_value("mode")
        defaults_mode = section_by_name[("defaults", "defaults")].directive_value(
            "mode"
        )
        effective = mode or defaults_mode
        assert effective == "tcp", (
            f"{key} must be mode tcp (got {effective!r}); ZMTP and the "
            f"Salt TCP transport are not HTTP."
        )


def test_backends_use_roundrobin(section_by_name):
    for key in (
        ("backend", "salt-master-pub-backend"),
        ("backend", "salt-master-req-backend"),
    ):
        balance = section_by_name[key].directive_value("balance")
        assert balance == "roundrobin", (
            f"{key} should balance roundrobin (got {balance!r}); "
            f"sticky sessions defeat horizontal scaling across cluster "
            f"peers."
        )


def test_backend_server_counts_match(section_by_name):
    pub_servers = section_by_name[("backend", "salt-master-pub-backend")].servers
    req_servers = section_by_name[("backend", "salt-master-req-backend")].servers
    pub_names = sorted(n for n, _, _ in pub_servers)
    req_names = sorted(n for n, _, _ in req_servers)
    assert pub_names == req_names, (
        f"Publish and request backends must list the same server "
        f"names: pub={pub_names} req={req_names}"
    )
    assert len(pub_names) >= 2, (
        f"Reference cluster must have at least 2 servers (got " f"{len(pub_names)})"
    )


def test_backend_servers_use_correct_ports(section_by_name):
    for _, _, port in section_by_name[("backend", "salt-master-pub-backend")].servers:
        assert port == 4505, (
            f"Publish backend servers must hit master :4505 " f"(got {port})"
        )
    for _, _, port in section_by_name[("backend", "salt-master-req-backend")].servers:
        assert port == 4506, (
            f"Request backend servers must hit master :4506 " f"(got {port})"
        )


def test_publish_session_timeout_long_enough(section_by_name):
    """
    The publish channel's ``publish_session`` default is 86400s; if the
    LB tears down idle subscribers earlier than that we'll see
    spurious reconnects.  Both ``frontend salt-master-pub`` and
    ``backend salt-master-pub-backend`` should override the defaults
    block with >= 86400s timeouts.
    """
    pub_front = section_by_name[("frontend", "salt-master-pub")]
    pub_back = section_by_name[("backend", "salt-master-pub-backend")]

    client_timeout = pub_front.directive_value("timeout client")
    assert client_timeout is not None, "Publish frontend must override timeout client"
    assert int(client_timeout.rstrip("s")) >= 86400, (
        f"Publish frontend ``timeout client`` should be >= 86400s "
        f"(got {client_timeout!r})"
    )

    server_timeout = pub_back.directive_value("timeout server")
    assert server_timeout is not None, "Publish backend must override timeout server"
    assert int(server_timeout.rstrip("s")) >= 86400, (
        f"Publish backend ``timeout server`` should be >= 86400s "
        f"(got {server_timeout!r})"
    )


def test_health_checks_enabled_on_backends(section_by_name):
    """Every backend ``server`` line should end with ``check``."""
    for key in (
        ("backend", "salt-master-pub-backend"),
        ("backend", "salt-master-req-backend"),
    ):
        for line in section_by_name[key].lines:
            if line.startswith("server "):
                assert line.rstrip().endswith(
                    " check"
                ), f"{key}: server line missing health check: {line!r}"
