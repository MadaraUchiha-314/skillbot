# Architecture: Host vs Container Execution

## High-Level Overview

```mermaid
graph TD
    subgraph HOST["HOST MACHINE"]
        CLI["CLI / TUI<br/>(cli.py, tui.py)"]
        A2A["A2A HTTP Server<br/>(a2a_server.py)"]
        SUP["Supervisor Executor<br/>(supervisor.py)"]

        subgraph AGENT["Agent Framework — LangGraph"]
            FRS["find_relevant_skills<br/>(LLM call)"]
            LS["load_skills<br/>(disk I/O)"]
            LM["load_memories<br/>(disk I/O)"]
            PE["plan_and_execute<br/>(LLM + tool calls)"]
            REF["reflect<br/>(LLM call)"]
            CM["create_memories<br/>(LLM call)"]
            SUM["summarize<br/>(LLM call)"]

            FRS --> LS --> LM --> PE --> REF
            REF -- "done" --> CM
            REF -- "not done" --> SUM
            SUM -- "loop back" --> FRS
        end

        MEM["Memory Manager<br/>(memory.py)"]
        CMGR["Container Manager<br/>(manager.py)"]
        SKL["Skill Loader<br/>(loader.py)"]
        CFG["Config / State<br/>(config.py, state.py)"]
        DB["SQLite Store<br/>(task store, checkpoints)"]

        CLI --> A2A --> SUP --> FRS
        CM --> MEM
        PE -- "StructuredTool.invoke()" --> CMGR
    end

    subgraph CONTAINER["CONTAINER — Podman (skillbot-{user_id})"]
        direction TB
        IMG["Image: python:3.13-slim<br/>+ nodejs + npm + tsx"]
        MOUNTS["Mounts:<br/>/workspace (read-write)<br/>/skills/*/scripts (read-only)"]
        EXEC["Script Execution:<br/>.py → python | .sh → bash<br/>.js → node | .ts → tsx<br/>Timeout: 60s"]
        DEPS["Installed at startup:<br/>pip packages | npm packages"]
        SEC["Security:<br/>--cap-drop=ALL<br/>User: skillbot (1000:1000)<br/>--network=none (default)"]

        IMG --- MOUNTS --- EXEC --- DEPS --- SEC
    end

    CMGR -- "podman exec" --> EXEC
    EXEC -- "stdout / stderr" --> CMGR
```

## Container Lifecycle

A **single container** is created per user and reused for the entire agent lifecycle. Scripts are never executed by spawning new containers — instead, `podman exec` sends commands into the already-running container.

```mermaid
stateDiagram-v2
    [*] --> Removed: Agent not started

    state "CLI start command" as CLIPull {
        [*] --> CheckImage: ensure_image()
        CheckImage --> PullImage: not found locally
        CheckImage --> ImageReady: already present
        PullImage --> ImageReady: podman pull
        ImageReady --> [*]
    }

    CLIPull --> Init: image ready

    state "SupervisorExecutor.__init__()" as Init {
        Removed --> EnsureImage: ensure_running() called
        EnsureImage --> Stopping: image confirmed (no-op if already pulled)

        Stopping --> Creating: podman rm -f (clean slate)

        state "Container Setup" as Creating {
            [*] --> PodmanRun: podman run -d ... sleep infinity
            PodmanRun --> InstallPip: pip install (all skills' deps)
            InstallPip --> InstallNpm: npm install -g (all skills' deps)
            InstallNpm --> [*]
        }
    }

    Creating --> Running: Container ready

    state "Running (sleep infinity)" as Running {
        [*] --> Idle
        Idle --> Executing: podman exec (skill script)
        Executing --> Idle: stdout/stderr returned (60s timeout)

        note right of Idle
            One long-lived container handles
            ALL script executions across
            multiple user requests and
            agent loop iterations.
        end note
    }

    Running --> Removed: Agent process exits / next ensure_running()
    Removed --> [*]
```

**Key points:**
- `ensure_running()` is called **once** during `SupervisorExecutor.__init__()`, not per script.
- The container image is auto-pulled by the CLI `start` command before the server spawns (`podman image exists` → `podman pull`). `ensure_running()` also checks as a safety net.
- The MVP always recreates the container on init (`stop → remove → create`) to avoid config drift (e.g. a skill with network access added after container was created without it).
- The container runs `sleep infinity` as its entrypoint — it stays alive and idle between script executions.
- Each `exec_script()` call runs `podman exec` against the existing container, not `podman run`.
- All skill dependencies (pip + npm) from **all** configured skills are installed at container startup, not on-demand.

## Request Flow

```mermaid
sequenceDiagram
    participant User
    participant TUI as CLI / TUI (Host)
    participant Server as A2A Server (Host)
    participant Sup as SupervisorExecutor (Host)
    participant Agent as Agent Framework (Host)
    participant CMgr as ContainerManager (Host)
    participant Container as Container (Podman)

    User->>TUI: types message
    TUI->>Server: HTTP request (A2A)
    Server->>Sup: execute(context, event_queue)
    Sup->>Agent: graph.ainvoke(initial_state)

    Agent->>Agent: 1. find_relevant_skills (LLM)
    Agent->>Agent: 2. load_skills (disk I/O)
    Agent->>Agent: 3. load_memories (disk I/O)
    Agent->>Agent: 4. plan_and_execute (LLM)

    loop Tool calls (up to 10 rounds)
        Agent->>CMgr: StructuredTool.invoke(args)
        CMgr->>Container: podman exec {interpreter} {script}
        Container-->>CMgr: stdout / stderr
        CMgr-->>Agent: ToolMessage with result
    end

    Agent->>Agent: 5. reflect (LLM)

    alt Task complete
        Agent->>Agent: create_memories
    else Not complete & iterations < 3
        Agent->>Agent: summarize → loop back to step 1
    end

    Agent-->>Sup: final response
    Sup-->>Server: TaskUpdater.complete(message)
    Server-->>TUI: A2A response
    TUI-->>User: display response
```

## Security Boundary

```mermaid
graph LR
    subgraph HOST["HOST (trusted)"]
        direction TB
        H1["LLM reasoning & planning"]
        H2["Skill discovery & selection"]
        H3["Memory read/write"]
        H4["Config & state management"]
        H5["HTTP server & A2A protocol"]
        H6["Container orchestration"]
        H7["SQLite persistence"]
        H8["User interface"]
    end

    subgraph CONTAINER["CONTAINER (untrusted)"]
        direction TB
        C1["Skill script execution"]
        C2["File I/O in /workspace"]
        C3["Network (if permitted)"]
        C4["Installed dependencies"]
        R["Restrictions:<br/>--cap-drop=ALL<br/>Non-root user<br/>--network=none (default)<br/>Read-only scripts<br/>60s timeout"]
    end

    HOST -- "podman exec<br/>(stdin/stdout)" --> CONTAINER
```

## Key Files by Execution Location

### Host-Only

| File | Role |
|------|------|
| `skillbot/cli/cli.py` | Entry point, CLI commands |
| `skillbot/cli/tui.py` | Terminal user interface |
| `skillbot/server/a2a_server.py` | FastAPI HTTP server |
| `skillbot/framework/agent.py` | LangGraph agent with all 7 nodes |
| `skillbot/agents/supervisor.py` | A2A AgentExecutor |
| `skillbot/container/manager.py` | Podman lifecycle & `exec_script()` |
| `skillbot/skills/loader.py` | Skill discovery & tool wrapping |
| `skillbot/config/config.py` | Configuration loading |
| `skillbot/framework/state.py` | Agent state definition |
| `skillbot/channels/chat.py` | A2A client primitives |
| `skillbot/memory/memory.py` | Memory file read/write |
| `skillbot/server/sqlite_task_store.py` | Task & checkpoint persistence |

### Container-Only

| File | Role |
|------|------|
| `Containerfile` | Defines container image (python:3.13-slim + node) |
| `skills/*/scripts/*.py` | Python skill scripts |
| `skills/*/scripts/*.sh` | Bash skill scripts |
| `skills/*/scripts/*.js` | Node.js skill scripts |
| `skills/*/scripts/*.ts` | TypeScript skill scripts |

### Bridging Host and Container

| Component | Description |
|-----------|-------------|
| `ContainerManager.exec_script()` | Translates host tool calls into `podman exec` commands |
| `ContainerManager.ensure_running()` | Creates container with mounts, network, and security settings |
| Volume mount: `/workspace` | Shared read-write workspace between host and container |
| Volume mount: `/skills/*/scripts` | Read-only skill scripts accessible inside container |
