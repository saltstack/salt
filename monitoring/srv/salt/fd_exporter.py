import http.server
import os
import subprocess
import time


class FDHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence logs
        return

    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()

            master_fds = 0
            master_procs = 0
            master_rss = 0
            api_fds = 0
            api_procs = 0
            api_rss = 0

            try:
                # Iterate over /proc directly once for efficiency
                for pid_dir in os.listdir("/proc"):
                    if not pid_dir.isdigit():
                        continue

                    try:
                        pid = pid_dir
                        with open(f"/proc/{pid}/cmdline", "rb") as f:
                            cmdline = (
                                f.read().replace(b"\0", b" ").decode(errors="ignore")
                            )

                        # Skip if it's the exporter itself
                        if "fd_exporter.py" in cmdline:
                            continue

                        is_master = "salt-master" in cmdline
                        is_api = "salt-api" in cmdline

                        if is_master or is_api:
                            # FD count
                            try:
                                fd_count = len(os.listdir(f"/proc/{pid}/fd"))
                            except:
                                fd_count = 0

                            # RSS Memory (from /proc/[pid]/stat, field 24 is RSS in pages)
                            try:
                                with open(f"/proc/{pid}/stat") as f:
                                    stat = f.read().split()
                                    rss_pages = int(stat[23])
                                    rss_bytes = rss_pages * 4096  # Assuming 4KB pages
                            except:
                                rss_bytes = 0

                            if is_master:
                                master_fds += fd_count
                                master_procs += 1
                                master_rss += rss_bytes
                            if is_api:
                                api_fds += fd_count
                                api_procs += 1
                                api_rss += rss_bytes
                    except (FileNotFoundError, ProcessLookupError, PermissionError):
                        # Process died while we were reading it
                        continue
                    except Exception:
                        continue
            except Exception:
                pass

            lines = [
                f"# HELP salt_master_open_fds Number of open file descriptors for master",
                f"# TYPE salt_master_open_fds gauge",
                f"salt_master_open_fds {master_fds}",
                f"# HELP salt_master_process_count Number of master processes",
                f"# TYPE salt_master_process_count gauge",
                f"salt_master_process_count {master_procs}",
                f"# HELP salt_master_rss_bytes RSS memory usage for master in bytes",
                f"# TYPE salt_master_rss_bytes gauge",
                f"salt_master_rss_bytes {master_rss}",
                f"# HELP salt_api_open_fds Number of open file descriptors for salt-api",
                f"# TYPE salt_api_open_fds gauge",
                f"salt_api_open_fds {api_fds}",
                f"# HELP salt_api_process_count Number of salt-api processes",
                f"# TYPE salt_api_process_count gauge",
                f"salt_api_process_count {api_procs}",
                f"# HELP salt_api_rss_bytes RSS memory usage for salt-api in bytes",
                f"# TYPE salt_api_rss_bytes gauge",
                f"salt_api_rss_bytes {api_rss}",
            ]
            self.wfile.write(("\n".join(lines) + "\n").encode())
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    port = 8001
    print(f"Starting FD and Memory Exporter on port {port}...")
    http.server.HTTPServer(("0.0.0.0", port), FDHandler).serve_forever()
