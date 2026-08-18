# Salt Architecture

## What is Salt?

Salt is a Python-based configuration management system using a master-minion architecture:
- **Master**: Central server that manages configuration and sends commands
- **Minion**: Agent running on managed systems that executes commands
- **Event Bus**: Real-time communication system between components
- **Loader System**: Dynamic plugin system for extending functionality

## Module Types

Salt uses a loader system to discover and load different types of modules:

### Execution Modules (`salt/modules/`)
Functions executed on minions (e.g., `pkg.install`, `file.read`). There are 264+ execution modules providing the CLI commands available via Salt.

**Examples:**
- `salt/modules/pkg.py` - Package management (virtual module)
- `salt/modules/file.py` - File operations
- `salt/modules/cmd.py` - Command execution
- `salt/modules/systemd_service.py` - systemd service management

### State Modules (`salt/states/`)
Declarative configuration management (e.g., `pkg.installed`, `file.managed`). There are 126+ state modules providing idempotent configuration.

**Examples:**
- `salt/states/pkg.py` - Package installation states
- `salt/states/file.py` - File management states
- `salt/states/service.py` - Service management states

### Runner Modules (`salt/runners/`)
Master-side operations (e.g., `salt-run jobs.list_jobs`). Runners execute on the Salt master.

### Wheel Modules (`salt/wheel/`)
Master configuration management (key management, config). Used for managing the Salt master itself.

### Grain Modules (`salt/grains/`)
Static system information collection. Grains provide facts about the minion system (OS, CPU, memory, etc.).

### Pillar Modules (`salt/pillar/`)
Dynamic configuration data backends. Pillars provide secure, targeted data to minions.

### Beacon Modules (`salt/beacons/`)
System monitoring triggers (watch for events). Beacons monitor system events and fire events on the event bus.

### Engine Modules (`salt/engines/`)
Long-running processes on master or minion. Engines provide persistent functionality.

### Returner Modules (`salt/returners/`)
Store or send command output to external systems (databases, message queues, etc.).

### Renderer Modules (`salt/renderers/`)
Template engines (Jinja, Mako, YAML, JSON). Renderers process state files.

### Matcher Modules (`salt/matchers/`)
Target matching (glob, pcre, grain, pillar, compound). Matchers determine which minions execute commands.

### Utility Modules (`salt/utils/`)
Shared utility functions (170+ modules). Utilities provide common functionality across Salt.

## Directory Structure

```
salt/
├── master.py, minion.py, state.py  # Core daemon implementations
├── loader/                         # Plugin loader system (LazyLoader)
├── modules/                        # 264+ execution modules
├── states/                         # 126+ state modules
├── runners/, wheel/                # Master operations and config
├── beacons/, engines/              # Monitoring triggers, long-running processes
├── grains/, pillar/                # System info, config data backends
├── renderers/, returners/          # Template engines, return data storage
├── matchers/, transport/           # Targeting systems, communication layer
├── utils/                          # 170+ utility modules
└── ext/                            # Vendored third-party code

tests/
├── pytests/
│   ├── unit/                       # Fast tests, no daemons/network
│   ├── functional/                 # End-to-end, no external deps
│   ├── integration/                # With daemons/network
│   ├── scenarios/                  # Scenario-based testing
│   └── pkg/                        # Package install/upgrade tests
└── support/                        # Test helpers and fixtures
```

## Key Architectural Components

### State Compiler

`salt/state.py` compiles YAML/Jinja templates into execution chunks. Uses **NetworkX** for dependency graph management with requisites:

- `require`: Must run after
- `watch`: Run if watched state changes
- `onchanges`: Run only if watched state changes
- `onfail`: Run if watched state fails
- `listen`: Listen for notifications
- `prereq`: Run before (with test mode check)

All state operations are idempotent and support test mode (`test=True`).

### Transport Layer

`salt/transport/` handles communication between master and minions:

- **ZeroMQ** (default): High-performance messaging
- **TCP**: Alternative transport
- **WebSocket**: For browser-based access

### Security

- **PKI-based authentication** (`salt/crypt.py`)
- **AES encryption** for all payloads
- **Master key acceptance workflow** prevents unauthorized access
- **External auth (eauth)** for Salt API access

### Event Bus

`salt/utils/event.py` provides ZeroMQ pub/sub with namespaced event tags for real-time communication between all components.

Events are namespaced with tags like:
- `salt/job/<jid>/new` - New job started
- `salt/job/<jid>/ret/<minion_id>` - Job return from minion
- `salt/auth` - Authentication events
- `salt/minion/<minion_id>/start` - Minion started

### Loader System

The loader system (`salt/loader/`) dynamically discovers and loads modules at runtime. Key features:

- **LazyLoader**: Loads modules on first access, not import
- **Virtual names**: Modules can override their name via `__virtual__()`
- **Dunder injection**: Injects `__salt__`, `__opts__`, `__grains__`, etc.
- **Caching**: Modules are cached after first load

## Async/Await Transition

Salt is transitioning from **Tornado** coroutines to native **asyncio**:
- Use native `async`/`await` syntax, not `@tornado.gen.coroutine`
- Prefer asyncio patterns over Tornado patterns
- Be aware of mixed async code during transition

## Master-Minion Communication

1. Minion authenticates with master via PKI
2. Master accepts minion key
3. Minion connects to master on port 4506 (request server)
4. Master publishes commands on port 4505 (publish server)
5. Minions subscribe to master's publish port
6. Commands are encrypted with AES
7. Results return via request server

## File Server

Salt includes a file server that serves files to minions:
- `salt://` URLs reference files on the file server
- Multiple backends: local, git, S3, HTTP, etc.
- Files are cached on minions

## Targeting

Minions can be targeted in multiple ways:
- **Glob**: `*`, `web*.example.com`
- **Grain**: `os:Ubuntu`, `kernel:Linux`
- **Pillar**: `role:webserver`
- **Compound**: `G@os:Ubuntu and webserver*`
- **List**: `web1,web2,web3`
- **PCRE**: Regular expressions

## Performance Considerations

### Lazy Loading
Modules only load on first access. Import-time side effects may not occur until first use of a module function.

### Context Caching
Use `__context__` to cache expensive operations within a Salt run (single execution).

### Module Discovery
- Module directories need `__init__.py`
- Filename becomes namespace: `salt/modules/pkg.py` → `pkg.*`
- Use `__virtualname__` for different name than filename
- **Performance tip**: Filename should match virtualname when possible

## Additional Resources

### Documentation
- Module development: `doc/topics/development/modules/developing.rst`
- State writing guide: `doc/ref/states/writing.rst`
- Contributing guidelines: `CONTRIBUTING.rst`

### Example Modules
- Simple execution module: `salt/modules/test.py`
- Complex execution module: `salt/modules/file.py`
- Package manager: `salt/modules/aptpkg.py`, `salt/modules/yumpkg.py`
- Service manager: `salt/modules/systemd_service.py`
- Simple state: `salt/states/pkg.py`
- Complex state: `salt/states/file.py`
