import salt.config
import salt.runner

opts = salt.config.master_config('/etc/salt/master')
runner = salt.runner.RunnerClient(opts)
print runner.cmd('test.stream', [])
print runner.cmd('jobs.list_jobs', [])
