.. option:: -u USER, --user=USER

    Specify user to run |salt-daemon|

.. option:: -d, --daemon

    Run |salt-daemon| as a daemon

.. option:: --pid-file PIDFILE

    Specify the location of the pidfile. Default: /var/run/|salt-daemon|.pid

.. option:: --disable-keepalive

    Disable the automatic restart mechanism for |salt-daemon|. By default, the
    daemon runs in a subprocess with automatic restart capabilities if it exits
    with a keepalive signal. This option disables that behavior and runs the
    daemon directly without the keepalive wrapper. Useful when an external
    process manager like systemd handles restarts, or in containerized
    environments where the container runtime manages the process lifecycle
