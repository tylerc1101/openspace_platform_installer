# OpenSpace Platform Installer - Overview

## What It Does

The OpenSpace Platform Installer (codename "Onboarder") is a stateful, containerized deployment orchestration system that automates complex OpenSpace infrastructure deployments using Taskfile-based workflows.

## Key Capabilities

### 1. Multi-Cluster Infrastructure Deployment
Deploy complete OpenSpace platform infrastructure:
- **Base Infrastructure**: Management KVM hosts, networking, OPNsense firewalls
- **MCM (Management Cluster)**: RKE2-based Kubernetes infrastructure cluster
- **OSMS (OpenSpace Management System)**: Management plane cluster
- **OSDC (OpenSpace Data Cluster)**: Data plane cluster

### 2. Taskfile-Based Orchestration
- Clear, readable YAML workflow definitions
- Hierarchical task structure with dependencies
- Modular taskfile includes for reusable components
- Variable passing through task hierarchies
- Built-in parallelization support

### 3. Stateful Execution
The installer provides robust state management:
- **Task tracking**: Completed tasks recorded in `.cache/state.json`
- **Resume capability**: Automatically skip completed tasks on re-run
- **Idempotent operations**: Safe to run tasks multiple times
- **Granular control**: Reset state to re-run specific tasks

### 4. Execution Features

#### Containerized Environment
- **Isolated execution**: All deployments run in Podman/Docker container
- **Consistent dependencies**: Pre-installed Ansible, Python, Task, and utilities
- **Volume mounts**: Access to data, images, and environment configurations
- **Air-gapped support**: Works in disconnected environments

#### Real-Time Monitoring
- **Live output streaming**: See Ansible output as it happens
- **Detailed logging**: Each task logs to `.cache/logs/task_<id>.log`
- **Progress tracking**: Clear indication of task completion
- **Duration tracking**: Know how long each task takes

#### Task Execution (run_task.py)
- **State management**: Track completed tasks in JSON state file
- **Multiple execution types**: Ansible playbooks, shell scripts, make commands
- **Argument passing**: Extra vars and parameters to tasks
- **Error handling**: Proper exit codes and error messages

### 5. Modular Design

Task workflows are organized hierarchically:
```
Environment Taskfile.yml
    ↓
Included Taskfiles (basekit, cluster_deployment, node_prep)
    ↓
Individual Tasks (copy-ssh-key, deploy-cluster, etc.)
    ↓
run_task.py Execution
    ↓
Ansible Playbooks / Shell Scripts
```

Each component has a single responsibility:
- **Environment Taskfile**: Orchestrates overall deployment flow
- **Included Taskfiles**: Group related tasks by function
- **Individual Tasks**: Perform specific operations
- **run_task.py**: Execute tasks with state tracking
- **Playbooks/Scripts**: Actual infrastructure automation

### 6. Variable Management

Variables flow through multiple layers:
- **Taskfile global vars**: Set once, used everywhere
- **Include-level vars**: Passed to included taskfiles
- **Task-level vars**: Specific to individual tasks
- **Ansible vars**: In config.yml and group_vars/

Variables are explicitly passed between tasks:
```yaml
parent-task:
  vars:
    HOSTS: infrastructure_cluster
  cmds:
    - task: child-task
      vars:
        HOSTS: '{{.HOSTS}}'
```

## Use Cases

### Initial Infrastructure Deployment
Bootstrap complete OpenSpace infrastructure from scratch:
1. Prepare management infrastructure
2. Deploy MCM (Management Cluster) with RKE2
3. Deploy OSMS (Management System) cluster
4. Deploy OSDC (Data Cluster) cluster
5. Configure networking and security

### Infrastructure Updates
Apply changes to existing infrastructure:
- Update cluster configurations
- Deploy new downstream clusters
- Scale existing resources
- Apply security patches

### Disaster Recovery
Rebuild infrastructure from configuration:
- All deployment logic is version-controlled
- Environment configurations can be backed up
- Reproducible deployments with consistent results

### Development and Testing
Test infrastructure changes safely:
- Create test environments quickly
- Validate changes before production
- Consistent deployment across dev/staging/prod

## Architecture Benefits

### Separation of Concerns
- **Deployment logic** (data/) - reusable, version-controlled taskfiles
- **Environment config** (environments/) - per-environment customization
- **Images** (images/) - large binaries, separate repository
- **Execution engine** (run_task.py) - state management and logging

### Maintainability
- Clear task hierarchy with explicit dependencies
- Each task has single responsibility
- Easy to add new tasks or modify existing ones
- Readable YAML instead of complex Python code

### Reliability
- State tracking prevents re-running completed work
- Idempotent operations safe to retry
- Real-time output for monitoring
- Detailed logs for troubleshooting

### Flexibility
- Support multiple deployment types
- Extensible taskfile system
- Mix Ansible, shell, and other execution types
- Easy to customize per environment
