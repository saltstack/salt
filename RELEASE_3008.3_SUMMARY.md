# Salt 3008.3 Release Summary

**Release Date**: September 30, 2026 | **Previous Release**: v3008.2 (July 1, 2026)

---

## Critical Fixes

**Production Stability**
- Fixed severe resource leaks (EventPublisher sockets, file descriptors, memory growth)
- Fixed master cluster authentication errors and key validation issues
- Fixed minion nonce verification errors and RPM upgrade deadlocks

**Security (Multiple CVEs)**
- Salt-API token revocation vulnerability (HIGH severity)
- GitPython RCE, urllib3 decompression-bomb, OpenSSL, expat, Tornado patches
- **Whitelist module improvements**: Extended enforcement to states/beacons/engines, fixed Jinja bypass, new `whitelist_state_modules` option

---

## Performance & Features

**Performance**: Significant throughput improvements (eliminated redundant serialization, cached objects, deferred imports, faster YAML parsing)

**New Features**
- NetworkManager provider for RHEL 8+/Fedora
- Netplan provider for Ubuntu 18.04+/Debian
- New async options: `master_async_mworker`, `master_mworker_max_inflight`, `ipc_write_buffer`

**Module Fixes**: NAPALM, X.509, pgjsonb returner, dnf5, pip.installed, pkg.installed

---

## Breaking Changes

1. **Python 3.11 onedir (3007.x)**: Reinstall salt-pip extensions after upgrade
2. **pyOpenSSL 26+**: salt.modules.tls disabled (migrate to x509 module)
3. **whitelist_modules**: Now blocks Jinja attribute-style access (`salt.cmd.run` → `salt['cmd.run']`)
4. **Resources loader**: Deny-by-default for resource-typed minions

---

**Dependencies**: Python 3.11.15, GitPython 3.1.60, pip 26.2, cryptography ≥48.0.1, relenv 0.22.27
