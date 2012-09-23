/tmp/salttest/issue-1879:
    
  file.append:
    - text: |
        # enable bash completion in interactive shells
        if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
            . /etc/bash_completion
        fi
        
