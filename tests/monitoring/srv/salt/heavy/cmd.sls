run_noisy_command:
  cmd.run:
    - shell: /bin/bash
    - name: |
        for i in {1..50}; do
          echo "Batch $i output start"
          ps aux
          ls -R /etc
          echo "Batch $i output end"
        done
