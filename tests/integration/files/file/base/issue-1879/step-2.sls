{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('issue-1879') }}:
  file.append:
    - text: |
        # enable bash completion in interactive shells
        if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
            . /etc/bash_completion
        fi

