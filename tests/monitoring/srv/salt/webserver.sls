install_apache:
  pkg.installed:
    - name: apache2

apache_service:
  service.running:
    - name: apache2
    - enable: True
    - require:
      - pkg: install_apache

welcome_page:
  file.managed:
    - name: /var/www/html/index.html
    - contents: "Hello from {{ grains['id'] }}"
    - require:
      - pkg: install_apache
