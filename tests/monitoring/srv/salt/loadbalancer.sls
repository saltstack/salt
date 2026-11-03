install_haproxy:
  pkg.installed:
    - name: haproxy

haproxy_cfg:
  file.managed:
    - name: /etc/haproxy/haproxy.cfg
    - source: salt://haproxy.cfg.jinja
    - template: jinja
    - require:
      - pkg: install_haproxy

haproxy_service:
  service.running:
    - name: haproxy
    - enable: True
    - watch:
      - file: haproxy_cfg
