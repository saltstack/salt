"""
Default worker pool configuration for Salt master.

This module defines the default worker pool routing configuration.
Users can override this in their master config file.
"""

# Default worker pool routing configuration
# This provides maximum backward compatibility by using a single pool
# with a catchall pattern that handles all commands (identical to current behavior)
DEFAULT_WORKER_POOLS = {
    "default": {
        "worker_count": 5,  # Same as current worker_threads default
        "commands": ["*"],  # Catchall - handles all commands
    },
}

# Optional: Performance-optimized pools for users who want better out-of-box performance
# Users can enable this via worker_pools_optimized: True
OPTIMIZED_WORKER_POOLS = {
    "lightweight": {
        "worker_count": 2,
        "commands": [
            "ping",
            "get_token",
            "mk_token",
            "verify_minion",
            "_master_opts",
            "_master_tops",
            "_file_hash",
            "_file_hash_and_stat",
        ],
    },
    "medium": {
        "worker_count": 2,
        "commands": [
            "_mine_get",
            "_mine",
            "_mine_delete",
            "_mine_flush",
            "_file_find",
            "_file_list",
            "_file_list_emptydirs",
            "_dir_list",
            "_symlink_list",
            "pub_ret",
            "minion_pub",
            "minion_publish",
            "wheel",
            "runner",
        ],
    },
    "heavy": {
        "worker_count": 1,
        "commands": [
            "publish",
            "_pillar",
            "_return",
            "_syndic_return",
            "_file_recv",
            "_serve_file",
            "minion_runner",
            "revoke_auth",
        ],
    },
}


def validate_worker_pools_config(opts):
    """
    Validate worker pools configuration at master startup.

    Args:
        opts: Master configuration dictionary

    Returns:
        True if valid

    Raises:
        ValueError: If configuration is invalid with detailed error messages
    """
    if not opts.get("worker_pools_enabled", True):
        # Legacy mode, no validation needed
        return True

    # Get the effective worker pools (handles defaults and backward compat)
    worker_pools = get_worker_pools_config(opts)

    # If pools are disabled, no validation needed
    if worker_pools is None:
        return True

    default_pool = opts.get("worker_pool_default")

    errors = []

    # 1. Validate pool structure
    if not isinstance(worker_pools, dict):
        errors.append("worker_pools must be a dictionary")
        raise ValueError("\n".join(errors))

    if not worker_pools:
        errors.append("worker_pools cannot be empty")
        raise ValueError("\n".join(errors))

    # 2. Validate each pool
    cmd_to_pool = {}
    catchall_pool = None

    for pool_name, pool_config in worker_pools.items():
        if not isinstance(pool_config, dict):
            errors.append(f"Pool '{pool_name}': configuration must be a dictionary")
            continue

        # Check worker_count
        worker_count = pool_config.get("worker_count")
        if not isinstance(worker_count, int) or worker_count < 1:
            errors.append(
                f"Pool '{pool_name}': worker_count must be integer >= 1, "
                f"got {worker_count}"
            )

        # Check commands list
        commands = pool_config.get("commands", [])
        if not isinstance(commands, list):
            errors.append(f"Pool '{pool_name}': commands must be a list")
            continue

        if not commands:
            errors.append(f"Pool '{pool_name}': commands list cannot be empty")
            continue

        # Check for duplicate command mappings and catchall
        for cmd in commands:
            if not isinstance(cmd, str):
                errors.append(f"Pool '{pool_name}': command '{cmd}' must be a string")
                continue

            if cmd == "*":
                # Found catchall pool
                if catchall_pool is not None:
                    errors.append(
                        f"Multiple pools have catchall ('*'): "
                        f"'{catchall_pool}' and '{pool_name}'. "
                        "Only one pool can use catchall."
                    )
                catchall_pool = pool_name
                continue

            if cmd in cmd_to_pool:
                errors.append(
                    f"Command '{cmd}' mapped to multiple pools: "
                    f"'{cmd_to_pool[cmd]}' and '{pool_name}'"
                )
            else:
                cmd_to_pool[cmd] = pool_name

    # 3. Validate default pool exists (if no catchall)
    if catchall_pool is None:
        if default_pool is None:
            errors.append(
                "No catchall pool ('*') found and worker_pool_default not specified. "
                "Either use a catchall pool or specify worker_pool_default."
            )
        elif default_pool not in worker_pools:
            errors.append(
                f"No catchall pool ('*') found and default pool '{default_pool}' "
                f"not found in worker_pools. Available: {list(worker_pools.keys())}"
            )

    if errors:
        raise ValueError(
            "Worker pools configuration validation failed:\n  - "
            + "\n  - ".join(errors)
        )

    return True


def get_worker_pools_config(opts):
    """
    Get the effective worker pools configuration.

    Handles backward compatibility with worker_threads and applies
    worker_pools_optimized if requested.

    Args:
        opts: Master configuration dictionary

    Returns:
        Dictionary of worker pools configuration
    """
    # If pools explicitly disabled, return None (legacy mode)
    if not opts.get("worker_pools_enabled", True):
        return None

    # Check if user wants optimized pools
    if opts.get("worker_pools_optimized", False):
        return opts.get("worker_pools", OPTIMIZED_WORKER_POOLS)

    # Check if worker_pools is explicitly configured AND not empty
    if "worker_pools" in opts and opts["worker_pools"]:
        return opts["worker_pools"]

    # Backward compatibility: convert worker_threads to single catchall pool
    if "worker_threads" in opts:
        worker_count = opts["worker_threads"]
        return {
            "default": {
                "worker_count": worker_count,
                "commands": ["*"],
            }
        }

    # Use default configuration
    return DEFAULT_WORKER_POOLS
