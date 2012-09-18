supervisord-pip:
    pip.installed:
      - name: supervisor
      - bin_env: /tmp/issue-2028-virtualenv/bin/pip
      - require:
        - pkg: python-dev

python-dev:
  pkg.installed
