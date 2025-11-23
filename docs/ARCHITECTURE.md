# Architecture

## System Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Host Machine (RHEL/Rocky)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  onboarder-run.py (launches container)                          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         Podman/Docker Container                        │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │  Volumes Mounted:                                       │    │
│  │  • /docker-workspace/data → data/                      │    │
│  │  • /docker-workspace/config/<env> → environments/<env>│    │
│  │  • /install/images → images/                           │    │
│  │                                                         │    │
│  │  Working Directory: /docker-workspace/install          │    │
│  │  (symlink to /docker-workspace/config/<env>)           │    │
│  │                                                         │    │
│  │  ┌──────────────────────────────────────────────┐     │    │
│  │  │  Taskfile Orchestration                      │     │    │
│  │  │  • Environment Taskfile.yml                  │     │    │
│  │  │  • Includes data taskfiles                   │     │    │
│  │  │  • Variables & dependencies                  │     │    │
│  │  └──────────────┬───────────────────────────────┘     │    │
│  │                 │                                       │    │
│  │                 ▼                                       │    │
│  │  ┌──────────────────────────────────────────────┐     │    │
│  │  │  run_task.py                                 │     │    │
│  │  │  • State management (.cache/state.json)     │     │    │
│  │  │  • Task execution                            │     │    │
│  │  │  • Logging (.cache/logs/)                   │     │    │
│  │  └──────────────┬───────────────────────────────┘     │    │
│  │                 │                                       │    │
│  │   ┌─────────────┴──────────────┐                      │    │
│  │   ▼                            ▼                      │    │
│  │  ┌──────────────┐          ┌──────────────┐          │    │
│  │  │   Ansible    │          │    Shell     │          │    │
│  │  │  Playbooks   │          │   Commands   │          │    │
│  │  └──────────────┘          └──────────────┘          │    │
│  └───────────────────────────────────────────────────────┘    │
│                          │ SSH                                 │
└──────────────────────────┼─────────────────────────────────────┘
                           │
        ┌──────────────────▼─────────────────────────────┐
        │         Target Infrastructure                   │
        ├────────────────────────────────────────────────┤
        │  Management KVM Host                           │
        │  ├─> MCM Cluster (RKE2 Kubernetes)            │
        │  ├─> OSMS Cluster                             │
        │  ├─> OSDC Cluster                             │
        │  └─> OPNsense Firewall                        │
        └────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Container Launcher (`onboarder-run.py`)

**Responsibilities:**
- Detect available container runtime (Podman/Docker)
- Present environment selection menu
- Build/load onboarder container image
- Mount volumes to container
- Launch interactive shell in container

**Key Functions:**
```python
def select_environment():
    """Interactive environment selection"""
    
def get_container_runtime():
    """Detect podman or docker"""
    
def run_container(runtime, env):
    """Launch container with proper mounts"""
```

### 2. Taskfile Orchestration

**Environment Taskfile** (`environments/<env>/Taskfile.yml`):
- Defines overall deployment workflow
- Sets global variables (ENV, DATA_DIR, etc.)
- Includes modular taskfiles from data/
- Passes variables to included tasks

**Included Taskfiles** (`data/<component>/<version>/main.yml`):
- Group related tasks by function
- Define reusable task libraries
- Declare variable requirements
- Call run_task.py for execution

### 3. Task Execution Engine (`run_task.py`)

**Responsibilities:**
- Execute Ansible playbooks, shell scripts, make commands
- Track task completion in state file
- Generate detailed logs for each task
- Stream output in real-time
- Handle errors and exit codes

**Key Functions:**
```python
def load_state():
    """Load .cache/state.json"""
    
def execute_task(task_id, kind, file, hosts, args):
    """Run task and capture output"""
    
def save_state(task_id, status):
    """Update state.json with completion"""
```

### 4. Container Runtime

**Base Image:**
- RHEL 9 or Rocky Linux
- Python 3.9+
- Ansible 2.14+
- Task (Taskfile runner)
- Required system utilities

**Volume Mounts:**
```
Host Path                              → Container Path
─────────────────────────────────────────────────────────
./data                                → /docker-workspace/data
./environments/<env>                  → /docker-workspace/config/<env>
./images                              → /install/images
```

**Working Directory:**
```
/docker-workspace/install → symlink to /docker-workspace/config/<env>
```

**Runtime Configuration:**
- Interactive shell (bash)
- Environment variables passed through
- Read-write access to environment directory
- Read-only for data and images

## Data Flow

### Deployment Execution Flow

```
1. Start
   ├─> Launch onboarder-run.py
   └─> Select environment from menu
   
2. Container Launch
   ├─> Detect runtime (podman/docker)
   ├─> Mount volumes
   │   ├─> /docker-workspace/data
   │   ├─> /docker-workspace/config/<env>
   │   └─> /install/images
   └─> Start interactive shell
   
3. Environment Setup (inside container)
   ├─> Navigate to /docker-workspace
   ├─> Create symlink: install → config/<env>
   └─> Navigate to install/
   
4. Task Execution
   ├─> Run: task <task-name>
   ├─> Taskfile loads includes
   ├─> Variables passed through hierarchy
   └─> For each subtask:
       ├─> Check state file (.cache/state.json)
       ├─> If completed: skip
       └─> If not completed:
           ├─> Execute via run_task.py
           ├─> Stream output in real-time
           ├─> Log to .cache/logs/task_<id>.log
           ├─> On success: Mark complete in state
           └─> On failure: Exit with error
           
5. State Management
   ├─> Each completed task recorded
   ├─> State persists between runs
   └─> Re-running skips completed tasks
   
6. Completion
   ├─> All tasks successful
   └─> Infrastructure deployed
```

### Variable Flow

```
Taskfile.yml (environment)
    ↓
vars:
  ENV: <environment>
  DATA_DIR: /docker-workspace/data
    ↓
includes:
  deployment:
    vars:
      ENV: '{{.ENV}}'
      DATA_DIR: '{{.DATA_DIR}}'
    ↓
tasks:
  infrastructure_prep:
    vars:
      HOSTS: infrastructure_cluster
    cmds:
      - task: deployment:copy-ssh-key
        vars:
          HOSTS: '{{.HOSTS}}'
    ↓
run_task.py
  --hosts=infrastructure_cluster
  --file=/docker-workspace/data/common/copy_ssh_key.yml
    ↓
Ansible Playbook
  inventory: config.yml
  extra_vars: from --args
    ↓
Target Infrastructure
```

## Security Architecture

### Isolation Layers

1. **Filesystem Isolation**
   - Container has limited view of host filesystem
   - Only mounted volumes accessible
   - Read-only mounts for code and images
   - Read-write only for environment-specific data

2. **Network Isolation**
   - Container network separate from host
   - SSH connections originate from container
   - No direct host network access

3. **Privilege Separation**
   - Container runs as non-root user (where possible)
   - Ansible uses privilege escalation (become) as needed
   - SSH keys scoped to environment

### Secret Management

**Secrets Location:**
```
usr_home/<env>/
├── .ssh/                 # SSH keys
│   ├── id_rsa           # Private key (chmod 600)
│   └── id_rsa.pub       # Public key
├── group_vars/
│   └── vault.yml        # Ansible vault encrypted secrets
└── secrets.yml          # Environment secrets (gitignored)
```

**Best Practices:**
- SSH keys never in version control
- Passwords encrypted with ansible-vault
- Secrets files in .gitignore
- Container has read-only access to code
- Sensitive data only in usr_home/

## State Management

### State File Format
```json
{
  "completed_tasks": {
    "copy-ssh-key": {
      "completed_at": "2025-11-21T10:30:00Z",
      "duration_seconds": 5.2,
      "status": "success",
      "hosts": "infrastructure_cluster"
    },
    "bootstrap-mgmt": {
      "completed_at": "2025-11-21T10:35:00Z",
      "duration_seconds": 287.5,
      "status": "success",
      "hosts": "infrastructure_cluster"
    }
  },
  "last_updated": "2025-11-21T10:35:00Z"
}
```

### State Location
```
environments/<env>/.cache/state.json
```

### State Operations

**Load State:**
```python
# run_task.py loads state before execution
state = load_state()
if task_id in state['completed_tasks']:
    print(f"Task {task_id} already completed, skipping")
    return 0
```

**Save State:**
```python
# After successful task execution
save_state(task_id, {
    'completed_at': datetime.now().isoformat(),
    'duration_seconds': duration,
    'status': 'success',
    'hosts': hosts
})
```

**Reset State:**
```bash
# Manual state reset
rm .cache/state.json

# All tasks will re-run
task deploy-mcm
```

## Logging Architecture

### Log Hierarchy
```
environments/<env>/.cache/logs/
├── task_copy-ssh-key.log         # Per-task detailed logs
├── task_bootstrap-mgmt.log
├── task_deploy-cluster.log
└── ...
```

### Log Levels
- **Task execution**: Full command output, Ansible verbose output
- **Real-time streaming**: Output shown as it happens
- **Persistent logs**: All output saved to task-specific log files

### Log Format
```
# Real-time console output
TASK [Copy SSH Key] ************************************************************
ok: [mcm1]

PLAY RECAP *********************************************************************
mcm1                       : ok=5    changed=2    unreachable=0    failed=0

# Log file includes timestamps and full output
[2025-11-21 10:30:00] Starting Ansible playbook: copy_ssh_key.yml
[2025-11-21 10:30:01] Target hosts: infrastructure_cluster
[2025-11-21 10:30:05] Task completed successfully
[2025-11-21 10:30:05] Duration: 5.2 seconds
```

## Extensibility Points

### 1. New Task Types
Current types: ansible, shell, make

Add new execution types in run_task.py:
```python
if kind == 'terraform':
    cmd = ['terraform', 'apply', '-auto-approve']
elif kind == 'kubectl':
    cmd = ['kubectl', 'apply', '-f', file]
```

### 2. Custom Taskfiles
Create new included taskfiles:
```yaml
# data/custom_component/1.0.0/main.yml
version: '3'
tasks:
  custom-task:
    desc: My custom deployment
    cmds:
      - python3 {{.DATA_DIR}}/run_task.py ...
```

Include in environment:
```yaml
includes:
  custom:
    taskfile: ../../data/custom_component/1.0.0/main.yml
```

### 3. Pre/Post Hooks (Future)
```yaml
tasks:
  deploy:
    deps:
      - pre-deploy-checks
    cmds:
      - task: actual-deployment
    postcmds:
      - task: post-deploy-validation
```

## Performance Considerations

### Container Reuse
- Container stays running between tasks
- No startup overhead for each task
- Fast task execution

### State Caching
- State checked before each task
- Completed tasks skipped instantly
- Minimal overhead for state file I/O

### Parallel Execution
Task supports parallel task execution:
```yaml
deploy-clusters:
  deps:
    - deploy-osms  # Runs in parallel
    - deploy-osdc  # with this task
```

## Error Handling

### Error Categories
1. **Task execution errors**: Non-zero exit codes from playbooks/scripts
2. **Missing files**: Taskfile or playbook not found
3. **Variable errors**: Required variables not set
4. **Connection errors**: SSH failures to targets

### Recovery Strategies
1. **Automatic skip**: Completed tasks not re-run
2. **Manual state reset**: Clear state.json to force re-run
3. **Idempotent tasks**: Safe to retry failed tasks
4. **Detailed logs**: Debug information in .cache/logs/
