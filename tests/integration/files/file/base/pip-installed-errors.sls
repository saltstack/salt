supervisord-pip:
    pip.installed:
      - name: supervisor
      - mirrors: http://testpypi.python.org/pypi
      - bin_env: /tmp/pip-installed-errors
