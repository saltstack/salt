# Git Workflow and CI

## Commit Guidelines

### CRITICAL RULES

1. **NO attribution lines** - **NEVER** add "Generated with Claude Code", "Co-Authored-By: Claude", or any AI attribution
2. **Use imperative mood** - "Fix bug", not "Fixed bug" or "Fixes bug"
3. **Reference issues** - Use `#NNNN` to reference GitHub issues
4. **Small, focused commits** - One logical change per commit
5. **Rebase before push** - Keep history linear and clean

### Good Commit Message Example

```
Fix loader cache invalidation on module reload

When modules are reloaded, the loader cache was not properly
invalidated, causing stale references. Clear the cache dict
on reload to ensure fresh module imports.

Fixes #12345
```

### Bad Commit Message Example

```
Fixed some bugs

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Why this is bad:**
- Past tense instead of imperative mood
- Vague description
- Contains AI attribution (NEVER do this)

## PR Workflow

### Finding and Checking PRs

```bash
# Find PR by branch name
gh pr list --repo saltstack/salt --head <BRANCH-NAME> --limit 5

# Check PR status
gh pr view <PR-NUMBER> --repo saltstack/salt
gh pr checks <PR-NUMBER> --repo saltstack/salt

# Watch CI run
gh run watch <RUN-ID> --repo saltstack/salt
```

## Branch Strategy

- **Main PR branch**: `master` (not `main`)
- **Release branches**: `3006.x`, `3007.x`, etc.
- **Merge-forward branches**: `merge/3007.x/master-YY-MM-DD`

## CI Failure Reproduction

When CI tests fail, you can reproduce the exact failure locally using containers.

### Prerequisites

- Docker installed and running
- Virtual environment setup (see [development-setup.md](development-setup.md))
- `ptscripts` installed (`pip install python-tools-scripts`)

### Step 1: Download CI Artifacts

First, get the CI artifacts from the failed run:

```bash
./venv310/bin/python -m ptscripts ci download-artifacts --run-id <RUN-ID>
```

The run ID can be found in the GitHub Actions URL or via `gh run list`.

### Step 2: Create Container

Create a container using the same image as CI:

```bash
./venv310/bin/python -m ptscripts container create <IMAGE> --name <NAME>
docker start <NAME>
```

**Example container images:**
- `ghcr.io/saltstack/salt-ci-containers/testing:debian-11`
- `ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-22.04`
- `ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-24.04`
- `ghcr.io/saltstack/salt-ci-containers/testing:rockylinux-8`
- `ghcr.io/saltstack/salt-ci-containers/testing:rockylinux-9`
- `ghcr.io/saltstack/salt-ci-containers/testing:fedora-40`
- `ghcr.io/saltstack/salt-ci-containers/testing:amazonlinux-2`
- `ghcr.io/saltstack/salt-ci-containers/testing:amazonlinux-2023`
- `ghcr.io/saltstack/salt-ci-containers/testing:photonos-3`
- `ghcr.io/saltstack/salt-ci-containers/testing:photonos-4`
- `ghcr.io/saltstack/salt-ci-containers/testing:photonos-5`

### Step 3: Setup Container

```bash
# Decompress dependencies
docker exec <NAME> python3 -m nox -e decompress-dependencies -- linux x86_64

# Create relenv toolchain symlink (Python 3.11+ only)
docker exec <NAME> bash -c "mkdir -p /root/.local/relenv && ln -sf /root/.cache/relenv/toolchains /root/.local/relenv/toolchain"
```

### Step 4: Run Tests

```bash
docker exec <NAME> python3 -m nox -e ci-test-onedir -- <TEST-PATH> --run-slow -x -v
```

**Examples:**
```bash
# Run specific test file
docker exec mycontainer python3 -m nox -e ci-test-onedir -- tests/pytests/unit/modules/test_pkg.py --run-slow -x -v

# Run specific test function
docker exec mycontainer python3 -m nox -e ci-test-onedir -- tests/pytests/unit/modules/test_pkg.py::test_install --run-slow -x -v

# Run with pattern matching
docker exec mycontainer python3 -m nox -e ci-test-onedir -- tests/pytests/unit/ -k test_systemd --run-slow -x -v
```

### Step 5: Debug in Container

If you need to debug interactively:

```bash
# Shell into container
docker exec -it <NAME> bash

# Inside container, activate environment and run tests
cd /salt
python3 -m nox -e ci-test-onedir -- tests/pytests/unit/test_foo.py -x -v
```

### Step 6: Cleanup

```bash
# Stop and remove container
docker stop <NAME>
docker rm <NAME>

# Clean artifacts
rm -rf artifacts/ nox-*.zip nox.*.tar.*
```

## Container Filesystem Behavior

When testing in containers, be aware:

- Changes to `salt/` source are visible immediately (mounted volume)
- Changes to Salt library may need artifact refresh:
  ```bash
  docker exec <NAME> cp /salt/salt/modules/foo.py \
      /salt/artifacts/salt/lib/python3.11/site-packages/salt/modules/
  ```

## Stale Artifacts

Always clean before downloading new CI artifacts:

```bash
rm -rf artifacts/ nox-*.zip nox.*.tar.*
```

Old artifacts can cause confusing test failures.

## Common CI Issues

### Tests Pass Locally But Fail in CI

Possible causes:
1. **Different Python version** - CI uses specific Python versions per branch
2. **Platform differences** - CI runs on Linux, you might be on macOS/Windows
3. **Missing dependencies** - CI containers have exact dependency versions
4. **Timing issues** - CI environment may be slower/faster
5. **Stale artifacts** - Clean and re-download

### Container Setup Fails

If dependency decompression fails:
1. Check you downloaded artifacts for correct run ID
2. Ensure Docker has enough disk space
3. Try removing old containers and images

### Relenv Toolchain Issues

For Python 3.11+ containers, you must create the symlink:

```bash
docker exec <NAME> bash -c "mkdir -p /root/.local/relenv && ln -sf /root/.cache/relenv/toolchains /root/.local/relenv/toolchain"
```

This is a known path mismatch between relenv versions.

## Using MCP Server for CI Workflows

The agents/mcp/salt_test MCP server provides tools for discovering CI failures:

- `ci_pr_failures` - Get all failing tests from a PR
- `ci_run_failures` - Get failures from specific CI run
- `ci_failure_summary` - Get summary of recent failures

See [agents/mcp/salt_test/README.md](../mcp/salt_test/README.md) for details.

## Best Practices

1. **Always clean artifacts** before downloading new ones
2. **Use exact CI container images** for reproduction
3. **Note Python version** - use venv310 for 3006.x/3007.x, venv311 for master
4. **Check run logs** in GitHub Actions for exact command that failed
5. **Test locally first** before pushing to avoid CI churn
6. **Keep commits small** for easier review and debugging
