wait_thirty:
  module.run:
    - name: test.sleep
    - length: 30 

{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('retry_file') }}:
  file:
    - touch
