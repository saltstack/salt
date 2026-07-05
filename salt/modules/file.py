def apply_patch(cmd, cwd=None, test=False, reject_file=None, dry_run=False):
    '''
    Apply a patch using the ``patch`` command.

    Returns a dict with 'retcode', 'stdout', 'stderr'.
    '''
    if test:
        cmd.append('--dry-run')
    if reject_file:
        cmd.extend(['-r', reject_file])
    else:
        cmd.extend(['-r', '-'])
    if dry_run:
        cmd.append('--dry-run')
    
    try:
        result = __salt__['cmd.run_all'](cmd, cwd=cwd, python_shell=False, python_env=False)
    except Exception as e:
        return {'retcode': 1, 'stdout': '', 'stderr': str(e)}
    
    # Handle the case where patch returns exit code 1 but the patch was already applied
    if result['retcode'] != 0:
        stderr_lower = result['stderr'].lower()
        if 'reversed' in stderr_lower and 'previously applied' in stderr_lower:
            # Patch was already applied, treat as success
            result['retcode'] = 0
            result['stdout'] = 'Patch was already applied.\n' + result['stdout']
    
    return result