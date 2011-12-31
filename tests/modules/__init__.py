from salt.cli.caller import Caller
from salt.config import minion_config

defaults = {
    'module_dirs': '',
    'log_level': 'warning',
}
config = minion_config('/etc/salt/minion')

def run_module(name, *args):
    opts = defaults.copy()
    opts.update(config, fun=name, arg=args)
    return Caller(opts).call()
