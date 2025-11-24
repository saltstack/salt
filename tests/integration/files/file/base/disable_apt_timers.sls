{% set apt_units = [
    "apt-daily.service",
    "apt-daily.timer",
    "apt-daily-upgrade.service",
    "apt-daily-upgrade.timer",
] %}

check_apt_timers:
  cmd.run:
    - name: "systemctl list-timers 'apt-daily*'"
    - ignore_retcode: True
    - onlyif: "command -v systemctl"

stop_apt_daily_units:
  service.dead:
    - names:
      - apt-daily.service
      - apt-daily-upgrade.service
    - enable: False
    - require:
      - cmd: check_apt_timers

stop_apt_daily_timers:
  service.dead:
    - names:
      - apt-daily.timer
      - apt-daily-upgrade.timer
    - enable: False
    - require:
      - service: stop_apt_daily_units

mask_apt_daily_units:
  service.masked:
    - names: {{ apt_units }}
    - require:
      - service: stop_apt_daily_timers
