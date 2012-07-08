'''
Execute a command and read the output as YAML
'''

def ext_pillar(command):
    '''
    Execute a command and read the output as YAML
    '''
    out = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            shell=True
            ).communicate()[0]
    return yaml.safe_load(out)
