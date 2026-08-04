# pylint: disable=resource-leakage
"""HTTP exporter that scrapes /proc for salt-master and salt-api processes.

Emits three tiers of gauges:

* Aggregate counters (unchanged from the original):
  ``salt_master_rss_bytes``, ``salt_master_open_fds``,
  ``salt_master_process_count`` and their ``salt_api_*`` counterparts.

* Per-process gauges labelled by process name (not pid) so restart of a
  worker or the ``Maintenance`` process continues the same Prometheus
  series rather than starting a new line on the dashboard:
  ``salt_master_process_rss_bytes{process="MWorker-default-0"}`` etc.
  Parallel ``salt_api_process_*`` metrics cover the salt-api side.

Process names come from the trailing tokens of ``/proc/<pid>/cmdline``
(salt renames its worker processes via ``setproctitle`` so the last
argv slot holds the process's role -- e.g. ``EventPublisher``,
``RequestServer MWorker-default-2``, ``PubServerChannel._publish_daemon``).
The main master/api MainProcess is disambiguated by whether ``salt-api``
appears anywhere in the argv.
"""
import http.server
import os


def _classify(cmdline):
    """Return ``(daemon, process_name)`` for a salt-master/salt-api pid.

    ``daemon`` is either ``"master"`` or ``"api"``.  ``process_name`` is
    the label the caller emits into
    ``salt_{daemon}_process_rss_bytes{process="..."}``.

    Returns ``None`` if ``cmdline`` does not belong to a salt master or
    salt-api process (or is the exporter itself).
    """
    if not cmdline:
        return None
    if "fd_exporter.py" in cmdline:
        return None

    is_api = "salt-api" in cmdline
    is_master = "salt-master" in cmdline and not is_api
    if not (is_api or is_master):
        return None

    # Skip the entrypoint shell wrapper (docker-compose runs the master
    # under ``sh -c '... salt-master -d && salt-api'``, which matches
    # both keywords but is not itself a salt daemon).
    if cmdline.startswith(("sh -c", "/bin/sh -c", "/usr/bin/tini")):
        return None

    daemon = "api" if is_api else "master"

    # Salt's ``setproctitle`` payload lands in the trailing argv slots
    # (space-separated inside the null-terminated ``cmdline`` blob we've
    # already normalised to spaces by the caller).  Look at the tail.
    tokens = cmdline.split()

    # ``RequestServer MWorker-default-2`` -> just ``MWorker-default-2``.
    # ``PubServerChannel._publish_daemon`` stays intact.
    # ``ReqServer_ProcessManager`` stays intact.
    # ``Maintenance``, ``EventPublisher``, ``EventMonitor``,
    # ``BatchManager``, ``FileServerUpdate`` all stand alone.
    if not tokens:
        return daemon, "unknown"

    last = tokens[-1]

    # Bare ``salt-api`` / ``salt-master`` invocations with no proctitle
    # suffix mean the process hasn't renamed itself yet (or is the
    # top-level launcher).  Collapse to a stable label.
    if last.endswith("salt-api"):
        return daemon, "salt-api-launcher"
    if last.endswith("salt-master") or last == "-d":
        return daemon, "master-launcher"

    if last == "MainProcess":
        return daemon, "salt-api-main" if is_api else "master-main"

    # ``RunNetapi(salt.loaded.int.netapi.rest_cherrypy)`` and its
    # siblings all identify a CherryPy-serving api worker; the parens
    # payload varies per module so collapse on the ``RunNetapi`` prefix.
    if is_api and last.startswith("RunNetapi"):
        return daemon, "salt-api-cherrypy"

    # ``RequestServer MWorker-default-2`` -> daemon label
    # ``MWorker-default-2``.  ``MWorkerQueue`` stands alone.
    if len(tokens) >= 2 and tokens[-2] == "RequestServer":
        return daemon, last

    return daemon, last


def _read_cmdline(pid):
    with open(f"/proc/{pid}/cmdline", "rb") as fh:
        return fh.read().replace(b"\0", b" ").decode(errors="ignore")


def _read_rss_bytes(pid):
    """Return RSS in bytes from ``/proc/<pid>/stat`` field 24 (pages)."""
    with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
        stat = fh.read().split()
    rss_pages = int(stat[23])
    return rss_pages * 4096  # Linux page size on all supported CI runners


def _read_pss_bytes(pid):
    """Return PSS (Proportional Set Size) in bytes from ``/proc/<pid>/smaps_rollup``.

    PSS divides each shared page by the number of processes mapping it, so
    ``sum(PSS across sibling forks) ~= physical RAM used`` -- unlike naive
    RSS which double-counts every COW-shared page and inflates the total
    ~2x for a many-process salt-master.
    """
    with open(f"/proc/{pid}/smaps_rollup", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("Pss:"):
                # ``Pss:        12345 kB``
                return int(line.split()[1]) * 1024
    return 0


def _count_fds(pid):
    return len(os.listdir(f"/proc/{pid}/fd"))


def _format_series(name, help_text, samples):
    """Return the # HELP/# TYPE header plus one line per label value.

    ``samples`` is ``{process_label: value}``.  Only currently-live
    processes appear -- when a process exits Prometheus interpolates
    across the gap and, when a replacement forks under the same
    process name, the series continues naturally.
    """
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} gauge"]
    for process, value in sorted(samples.items()):
        # Escape backslash and double-quote per the Prometheus text
        # exposition spec.  Salt daemon names never contain either but
        # the escape keeps this defensive.
        safe = process.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{name}{{process="{safe}"}} {value}')
    return lines


class FDHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence logs
        return

    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

        master_fds = 0
        master_procs = 0
        master_rss = 0
        master_pss = 0
        api_fds = 0
        api_procs = 0
        api_rss = 0
        api_pss = 0

        # Per-process buckets.  A given label may appear on multiple pids
        # transiently (e.g. an old Maintenance pid is exiting while its
        # replacement has just forked); sum in that case so the series
        # never dips artificially.
        master_proc_rss = {}
        master_proc_pss = {}
        master_proc_fds = {}
        api_proc_rss = {}
        api_proc_pss = {}
        api_proc_fds = {}

        try:
            for pid_dir in os.listdir("/proc"):
                if not pid_dir.isdigit():
                    continue
                pid = pid_dir
                try:
                    cmdline = _read_cmdline(pid)
                except (
                    FileNotFoundError,
                    ProcessLookupError,
                    PermissionError,
                    OSError,
                ):
                    continue

                classified = _classify(cmdline)
                if classified is None:
                    continue
                daemon, process_name = classified

                try:
                    fd_count = _count_fds(pid)
                except (
                    FileNotFoundError,
                    ProcessLookupError,
                    PermissionError,
                    OSError,
                ):
                    fd_count = 0

                try:
                    rss_bytes = _read_rss_bytes(pid)
                except (
                    FileNotFoundError,
                    ProcessLookupError,
                    PermissionError,
                    ValueError,
                    IndexError,
                    OSError,
                ):
                    rss_bytes = 0

                try:
                    pss_bytes = _read_pss_bytes(pid)
                except (
                    FileNotFoundError,
                    ProcessLookupError,
                    PermissionError,
                    ValueError,
                    IndexError,
                    OSError,
                ):
                    pss_bytes = 0

                if daemon == "master":
                    master_fds += fd_count
                    master_procs += 1
                    master_rss += rss_bytes
                    master_pss += pss_bytes
                    master_proc_rss[process_name] = (
                        master_proc_rss.get(process_name, 0) + rss_bytes
                    )
                    master_proc_pss[process_name] = (
                        master_proc_pss.get(process_name, 0) + pss_bytes
                    )
                    master_proc_fds[process_name] = (
                        master_proc_fds.get(process_name, 0) + fd_count
                    )
                else:
                    api_fds += fd_count
                    api_procs += 1
                    api_rss += rss_bytes
                    api_pss += pss_bytes
                    api_proc_rss[process_name] = (
                        api_proc_rss.get(process_name, 0) + rss_bytes
                    )
                    api_proc_pss[process_name] = (
                        api_proc_pss.get(process_name, 0) + pss_bytes
                    )
                    api_proc_fds[process_name] = (
                        api_proc_fds.get(process_name, 0) + fd_count
                    )
        except OSError:
            pass

        lines = [
            "# HELP salt_master_open_fds Number of open file descriptors for master",
            "# TYPE salt_master_open_fds gauge",
            f"salt_master_open_fds {master_fds}",
            "# HELP salt_master_process_count Number of master processes",
            "# TYPE salt_master_process_count gauge",
            f"salt_master_process_count {master_procs}",
            "# HELP salt_master_rss_bytes RSS memory usage for master in bytes (sum of per-process RSS -- over-counts COW-shared pages ~Nx)",
            "# TYPE salt_master_rss_bytes gauge",
            f"salt_master_rss_bytes {master_rss}",
            "# HELP salt_master_pss_bytes PSS (Proportional Set Size) for master in bytes (shared pages divided by N -- sum approximates actual physical RAM)",
            "# TYPE salt_master_pss_bytes gauge",
            f"salt_master_pss_bytes {master_pss}",
            "# HELP salt_api_open_fds Number of open file descriptors for salt-api",
            "# TYPE salt_api_open_fds gauge",
            f"salt_api_open_fds {api_fds}",
            "# HELP salt_api_process_count Number of salt-api processes",
            "# TYPE salt_api_process_count gauge",
            f"salt_api_process_count {api_procs}",
            "# HELP salt_api_rss_bytes RSS memory usage for salt-api in bytes (sum of per-process RSS -- over-counts COW-shared pages)",
            "# TYPE salt_api_rss_bytes gauge",
            f"salt_api_rss_bytes {api_rss}",
            "# HELP salt_api_pss_bytes PSS for salt-api in bytes (sum approximates actual physical RAM)",
            "# TYPE salt_api_pss_bytes gauge",
            f"salt_api_pss_bytes {api_pss}",
        ]
        lines.extend(
            _format_series(
                "salt_master_process_rss_bytes",
                "RSS bytes per salt-master process, labelled by process name (over-counts COW-shared pages -- prefer PSS for aggregate math)",
                master_proc_rss,
            )
        )
        lines.extend(
            _format_series(
                "salt_master_process_pss_bytes",
                "PSS (Proportional Set Size) bytes per salt-master process, labelled by process name (shared pages divided by N -- sum approximates actual physical RAM)",
                master_proc_pss,
            )
        )
        lines.extend(
            _format_series(
                "salt_master_process_fds",
                "Open FDs per salt-master process, labelled by process name",
                master_proc_fds,
            )
        )
        lines.extend(
            _format_series(
                "salt_api_process_rss_bytes",
                "RSS bytes per salt-api process, labelled by process name (over-counts COW-shared pages -- prefer PSS for aggregate math)",
                api_proc_rss,
            )
        )
        lines.extend(
            _format_series(
                "salt_api_process_pss_bytes",
                "PSS (Proportional Set Size) bytes per salt-api process, labelled by process name",
                api_proc_pss,
            )
        )
        lines.extend(
            _format_series(
                "salt_api_process_fds",
                "Open FDs per salt-api process, labelled by process name",
                api_proc_fds,
            )
        )
        self.wfile.write(("\n".join(lines) + "\n").encode())


if __name__ == "__main__":
    port = 8002
    print(f"Starting FD and Memory Exporter on port {port}...")
    http.server.HTTPServer(("0.0.0.0", port), FDHandler).serve_forever()
