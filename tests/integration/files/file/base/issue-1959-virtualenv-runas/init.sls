{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('issue-1959-virtualenv-runas') }}:
  virtualenv.managed:
    - requirements: salt://issue-1959-virtualenv-runas/requirements.txt
    - user: issue-1959
    {%- if grains.get('pythonversion') > [2,] %}
    {#- wheels are disabled because the pip cache dir will not be owned by the above issue-1959 user. Need to check this ASAP #}
    - use_wheel: False
    - no_use_wheel: True
    {%- endif %}
