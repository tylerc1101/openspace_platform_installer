# Taskfile System

## Overview

The OpenSpace Platform Installer uses [Taskfile](https://taskfile.dev/) (aka Task) for workflow orchestration. The system uses automatically-generated Taskfiles that define deployment workflows based on your `deployment.yml` configuration.

## Key Concepts

### Generated Taskfiles

Taskfiles are **automatically generated** from your `deployment.yml` file:
- Located in `environments/<env>/Taskfile.yml`
- Created on first container run by `scripts/first-run.sh`
- Regenerated when you delete `.first_run_complete` and restart container

### Onboarder Taskfiles

Pre-built taskfiles in `data/onboarders/<version>/`:
- `main.yml` - Main orchestration tasks
- `basekit.yml` - Basekit-specific deployment tasks
- `baremetal.yml` - Baremetal-specific deployment tasks
- These are included by your generated Taskfile.yml

## Why Taskfile?

- **Simple YAML syntax**: Easy to read and modify
- **Task dependencies**: Clear declaration of execution order
- **Variable passing**: Configuration flows from deployment.yml
- **Includes**: Modular organization with versioned onboarders
- **Platform agnostic**: Works in any environment
- **Built-in parallelization**: Run independent tasks concurrently

## Taskfile Structure

### Basic Task Definition

```yaml
version: '3'

tasks:
  task-name:
    desc: Human-readable description
    cmds:
      - echo "Command to execute"
      - echo "Another command"
```

### Task with Variables

```yaml
tasks:
  deploy:
    desc: Deploy application
    vars:
      APP_NAME: myapp
      VERSION: 1.0.0
    cmds:
      - echo "Deploying {{.APP_NAME}} version {{.VERSION}}"
```

### Calling Other Tasks

```yaml
tasks:
  prep:
    desc: Prepare environment
    cmds:
      - task: install-deps
      - task: configure-system
      
  install-deps:
    desc: Install dependencies
    cmds:
      - echo "Installing dependencies"
```

## Generated Environment Taskfile

Your environment's `Taskfile.yml` is automatically generated from `deployment.yml`. Here's an example of what it looks like:

```yaml
# environments/myenv/Taskfile.yml (GENERATED - DO NOT EDIT MANUALLY)
version: '3'

vars:
  ENV: myenv
  DATA_DIR: /docker-workspace/data
  DEPLOYMENT_TYPE: basekit  # From deployment.yml deployment.type
  ONBOARDER_VERSION: 3.5.0-rc7  # From deployment.yml deployment.onboarder_version

includes:
  onboarder:
    taskfile: ../../data/onboarders/{{.ONBOARDER_VERSION}}/main.yml
    vars:
      ENV: '{{.ENV}}'
      DATA_DIR: '{{.DATA_DIR}}'
      DEPLOYMENT_TYPE: '{{.DEPLOYMENT_TYPE}}'

tasks:
  prep:
    desc: Complete environment preparation workflow
    cmds:
      - task: onboarder:prep-onboarder-container

  deploy-mcm:
    desc: Deploy Management Cluster (MCM)
    cmds:
      - task: onboarder:deploy-mcm-{{.DEPLOYMENT_TYPE}}

  deploy-prod-osms:
    desc: Deploy OSMS Cluster
    cmds:
      - task: onboarder:deploy-osms

  deploy-prod-osdc:
    desc: Deploy OSDC Cluster (if configured)
    cmds:
      - task: onboarder:deploy-osdc

  get-kubeconfig-mcm:
    desc: Retrieve MCM kubeconfig
    cmds:
      - task: onboarder:get-kubeconfig-mcm

  get-kubeconfig-osms:
    desc: Retrieve OSMS kubeconfig
    cmds:
      - task: onboarder:get-kubeconfig-osms

  get-kubeconfig-osdc:
    desc: Retrieve OSDC kubeconfig
    cmds:
      - task: onboarder:get-kubeconfig-osdc
```

**Important**: This file is generated. To modify it, update your `deployment.yml` and regenerate configuration.

## Included Taskfiles

### Data Taskfiles

Included taskfiles live in `data/<component>/<version>/main.yml` and define reusable task libraries:

```yaml
# data/basekit/1.0.1/main.yml
version: '3'

tasks:
  deploy-all:
    desc: Deploy basekit infrastructure
    requires:
      vars: [HOSTS, DATA_DIR]
    cmds:
      - task: bootstrap-mgmt
        vars:
          HOSTS: '{{.HOSTS}}'
      - task: deploy-vms
        vars:
          HOSTS: '{{.HOSTS}}'
          
  bootstrap-mgmt:
    desc: Bootstrap management server with KVM
    requires:
      vars: [HOSTS, DATA_DIR]
    vars:
      FILE: '{{.DATA_DIR}}/basekit/1.0.1/tasks/bootstrap_mgmt_kvm.yml'
      KIND: ansible
    cmds:
      - python3 {{.DATA_DIR}}/run_task.py --task-id=bootstrap-mgmt --hosts={{.HOSTS}} --file={{.FILE}} --kind={{.KIND}}
```

## Integration with run_task.py

Tasks that perform actual work call `run_task.py` for execution with state management:

```yaml
copy-ssh-key:
  desc: Copy SSH Key to Nodes
  requires:
    vars: [HOSTS, DATA_DIR]
  vars:
    FILE: '{{.DATA_DIR}}/common/copy_ssh_key.yml'
    KIND: ansible
    ARGS: "-e ssh_pubkey_path=/docker-workspace/config/install/.ssh/rancher_ssh_key.pub"
  cmds:
    - python3 {{.DATA_DIR}}/run_task.py --task-id=copy-ssh-key --hosts={{.HOSTS}} --file={{.FILE}} --kind={{.KIND}} --args="{{.ARGS}}"
```

### run_task.py Arguments

- `--task-id`: Unique identifier for state tracking
- `--hosts`: Ansible inventory group or host to target
- `--file`: Path to Ansible playbook or script
- `--kind`: Execution type (`ansible`, `shell`, `make`)
- `--args`: Additional arguments (e.g., Ansible extra vars)

### State Management

run_task.py tracks completed tasks in `.cache/state.json`:

```json
{
  "completed_tasks": {
    "copy-ssh-key": {
      "completed_at": "2025-11-21T10:30:00Z",
      "duration_seconds": 5.2,
      "status": "success"
    }
  }
}
```

If a task has already completed successfully, it will be skipped on subsequent runs.

## Variable Passing

### Declaring Required Variables

Use `requires.vars` to declare dependencies:

```yaml
deploy-cluster:
  desc: Deploy Kubernetes cluster
  requires:
    vars: [HOSTS, CLUSTER_NAME, DATA_DIR]
  cmds:
    - echo "Deploying {{.CLUSTER_NAME}} to {{.HOSTS}}"
```

### Passing Variables to Subtasks

Always explicitly pass variables to subtasks:

```yaml
parent-task:
  vars:
    HOSTS: infrastructure_cluster
  cmds:
    - task: child-task
      vars:
        HOSTS: '{{.HOSTS}}'  # Explicit pass-through
```

### Variable Precedence

1. Task-level vars (highest)
2. Include-level vars
3. Global vars (in main Taskfile)
4. Environment variables (lowest)

## Common Patterns

### Sequential Workflow

```yaml
full-deployment:
  desc: Complete deployment workflow
  cmds:
    - task: prep
    - task: deploy-infrastructure
    - task: deploy-applications
    - task: validate
```

### Conditional Execution

```yaml
deploy:
  desc: Deploy based on environment
  cmds:
    - task: deploy-dev
      when: '{{eq .ENV "dev"}}'
    - task: deploy-prod
      when: '{{eq .ENV "prod"}}'
```

### Parallel Execution

```yaml
deploy-clusters:
  desc: Deploy multiple clusters in parallel
  deps:
    - deploy-osms
    - deploy-osdc
```

### Error Handling

```yaml
deploy:
  desc: Deploy with retry
  cmds:
    - task: attempt-deploy
  ignore_error: true
  cmds:
    - echo "First attempt failed, retrying..."
    - task: attempt-deploy
```

## Task Organization

### Environment Structure

```
environments/<env>/
├── Taskfile.yml           # Main orchestration
├── config.yml             # Ansible inventory
├── group_vars/
│   └── all.yml           # Ansible variables
└── .cache/
    ├── state.json        # Task completion tracking
    └── logs/             # Task execution logs
```

### Data Structure

```
data/
├── run_task.py           # Task execution engine
├── basekit/
│   └── 1.0.1/
│       ├── main.yml     # Basekit taskfile
│       └── tasks/       # Ansible playbooks
├── cluster_deployment/
│   └── 1.0.1/
│       ├── main.yml     # Cluster taskfile
│       └── tasks/       # Ansible playbooks
└── common/
    └── *.yml            # Shared Ansible playbooks
```

## Best Practices

### 1. Use Descriptive Task Names

```yaml
# Good
infrastructure_cluster_prep:
  desc: Prepare infrastructure cluster nodes

# Avoid
prep:
  desc: Prep
```

### 2. Declare Variable Requirements

```yaml
deploy:
  requires:
    vars: [HOSTS, VERSION, DATA_DIR]
  cmds:
    - echo "Deploying version {{.VERSION}}"
```

### 3. Keep Tasks Focused

```yaml
# Good - Single responsibility
copy-ssh-key:
  desc: Copy SSH key to nodes
  cmds:
    - python3 run_task.py --task-id=copy-ssh-key ...

# Avoid - Multiple responsibilities
setup:
  cmds:
    - copy keys
    - install packages
    - configure firewall
```

### 4. Use Includes for Modularity

```yaml
includes:
  database:
    taskfile: ./modules/database.yml
  webserver:
    taskfile: ./modules/webserver.yml
```

### 5. Explicit Variable Passing

```yaml
# Good - Explicit
parent:
  vars:
    HOST: server1
  cmds:
    - task: child
      vars:
        HOST: '{{.HOST}}'

# Avoid - Implicit (unreliable)
parent:
  vars:
    HOST: server1
  cmds:
    - task: child  # Assumes child can see HOST
```

## Debugging Taskfiles

### List Available Tasks

```bash
task --list
task --list-all  # Include internal tasks
```

### Dry Run

```bash
task --dry deploy-mcm
```

### Verbose Output

```bash
task --verbose deploy-mcm
```

### Task Summary

```bash
task --summary deploy-mcm
```

## Common Issues

### Variable Not Passed to Subtask

**Problem**: Subtask doesn't see parent's variables

```yaml
parent:
  vars:
    HOSTS: cluster
  cmds:
    - task: child  # Child can't see HOSTS
```

**Solution**: Explicitly pass variables

```yaml
parent:
  vars:
    HOSTS: cluster
  cmds:
    - task: child
      vars:
        HOSTS: '{{.HOSTS}}'
```

### Task Not Found

**Problem**: `task: Task "xyz" not found`

**Solution**: Check task is defined or included correctly

```yaml
includes:
  module:
    taskfile: ./path/to/module.yml

tasks:
  run:
    cmds:
      - task: module:xyz  # Must use namespace prefix
```

### Circular Dependency

**Problem**: Task A calls Task B which calls Task A

**Solution**: Restructure to break the cycle or use deps instead of cmds

```yaml
# Instead of mutual calls, use deps
task-a:
  deps: [common-prep]
  cmds:
    - echo "Task A"
    
task-b:
  deps: [common-prep]
  cmds:
    - echo "Task B"
```

## Advanced Features

### Task Aliases

```yaml
tasks:
  deploy:
    aliases: [d]
    cmds:
      - echo "Deploying..."
```

```bash
task d  # Runs 'deploy'
```

### Dynamic Variables

```yaml
tasks:
  deploy:
    vars:
      TIMESTAMP:
        sh: date +%Y%m%d%H%M%S
    cmds:
      - echo "Deploying at {{.TIMESTAMP}}"
```

### Preconditions

```yaml
tasks:
  deploy:
    preconditions:
      - test -f config.yml
      - sh: "[ -d .ssh ]"
        msg: "SSH directory not found"
    cmds:
      - echo "All checks passed"
```

### Status Checks

```yaml
tasks:
  build:
    status:
      - test -f output/binary
    cmds:
      - make build
```

Task will skip if status check passes (file exists).

## Migration from Profiles

The old profile-based system has been replaced with Taskfile orchestration:

| Old System | New System |
|------------|------------|
| `data/profiles/basekit/default.yml` | `data/basekit/1.0.1/main.yml` |
| `main.py --profile=basekit` | `task deploy-mcm` |
| `.installer_state` | `.cache/state.json` |
| Step-by-step execution | Task-based execution |
| Python orchestrator | Taskfile + run_task.py |

## Resources

- [Taskfile Documentation](https://taskfile.dev/)
- [Taskfile GitHub](https://github.com/go-task/task)
- [Installation Guide](https://taskfile.dev/installation/)
