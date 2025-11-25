# OpenSpace Platform Installer

A stateful, containerized deployment orchestration system for OpenSpace infrastructure using Taskfile-based workflows.

## Quick Links

- [**Getting Started**](docs/GETTING_STARTED.md) - Quick start guide for first-time users
- [**Requirements**](docs/REQUIREMENTS.md) - Prerequisites and dependencies
- [**Overview**](docs/OVERVIEW.md) - What the installer does and how it works
- [**Configuration**](docs/CONFIGURATION.md) - Detailed configuration reference
- [**Taskfiles**](docs/TASKFILES.md) - Understanding and creating deployment workflows
- [**Architecture**](docs/ARCHITECTURE.md) - System design and technical details
- [**Troubleshooting**](docs/TROUBLESHOOTING.md) - Common issues and solutions

## What Is This?

The OpenSpace Platform Installer ("Onboarder") provides a reproducible, stateful deployment system for complex OpenSpace infrastructure. It orchestrates:

- **Base infrastructure** (Management KVM, OPNsense firewall, networking)
- **MCM (Management Cluster)** - RKE2-based Kubernetes infrastructure cluster
- **OSMS (OpenSpace Management System)** - Management plane cluster
- **OSDC (OpenSpace Data Cluster)** - Data plane cluster

### Key Technologies

- **Taskfile**: YAML-based task runner for workflow orchestration
- **Python orchestration**: run_task.py for state management and logging
- **Containerized execution**: All deployments run in isolated Podman/Docker container
- **Ansible playbooks**: Infrastructure configuration management
- **Stateful tracking**: Resume deployments after interruptions

## Features

✅ **Taskfile-based orchestration** - Readable YAML workflows with clear task dependencies  
✅ **Stateful execution** - Tracks completed tasks, resumes after failures  
✅ **Containerized isolation** - All dependencies pre-installed, consistent environment  
✅ **Real-time logging** - Stream output from long-running tasks  
✅ **Modular design** - Separate taskfiles for each deployment phase  
✅ **Idempotent operations** - Safe to re-run without side effects  
✅ **Air-gapped support** - Works in disconnected environments  
✅ **Variable inheritance** - Pass configuration through task hierarchies  
✅ **Ansible integration** - Leverage existing playbooks and roles  

## Directory Structure

```
openspace_platform_installer/
├── data/                          # Deployment logic and tasks
│   ├── run_task.py               # Task execution engine with state management
│   ├── basekit/
│   │   └── 1.0.1/
│   │       ├── main.yml          # Basekit taskfile definitions
│   │       └── tasks/            # Ansible playbooks
│   ├── cluster_deployment/
│   │   └── 1.0.1/
│   │       ├── main.yml          # Cluster deployment taskfile
│   │       └── tasks/            # Cluster-specific playbooks
│   ├── common/                    # Shared Ansible playbooks
│   │   ├── copy_ssh_key.yml
│   │   └── ...
│   └── node_prep/                 # Node preparation tasks
│       └── 1.0.1/
│           ├── main.yml
│           └── tasks/
├── images/                        # Container images and ISOs
│   ├── onboarder/                # Onboarder container image
│   ├── rpms/                     # RPMs to install in container
│   └── opnsense/                 # OPNsense ISO
├── environments/                  # Environment-specific configurations
│   └── <environment_name>/
│       ├── Taskfile.yml          # Main orchestration workflow
│       ├── config.yml            # Ansible inventory
│       ├── group_vars/           # Ansible variables
│       │   └── all.yml
│       ├── .ssh/                 # SSH keys
│       └── logs/                 # Execution logs (auto-created)
└── onboarder-run.py              # Container launcher script
```

## Quick Start

### 1. Prepare Container
```bash
# Start the onboarder container
python3 onboarder-run.py

# Inside container, symlink your environment
cd /docker-workspace
ln -s config/<your_environment> install
cd install
```

### 2. Configure Environment
```bash
# Edit Ansible inventory
vim config.yml

# Edit Ansible variables
vim group_vars/all.yml

# Ensure SSH keys are present
ls -la .ssh/
```

### 3. Run Deployment
```bash
# Run full deployment workflow
task prep
task deploy-mcm
task deploy-prod-osms
task deploy-prod-osdc

# Or run specific tasks
task infrastructure_cluster_prep
task run-node-prep
```

### 4. Monitor Progress
```bash
# Logs are in the environment directory
tail -f .cache/logs/task_<task-id>.log

# Check state
cat .cache/state.json
```

## Usage Examples

### Full Deployment Workflow
```bash
# Complete infrastructure deployment
task prep                    # Prepare environment
task deploy-mcm             # Deploy management cluster
task deploy-prod-osms       # Deploy OSMS cluster
task deploy-prod-osdc       # Deploy OSDC cluster
```

### Individual Task Execution
```bash
# Run specific infrastructure prep
task infrastructure_cluster_prep

# Run node preparation
task run-node-prep

# Deploy onboarder
task run-onboarder
```

### Checking Status
```bash
# View task state
cat .cache/state.json

# View logs
ls -lh .cache/logs/
tail -f .cache/logs/task_copy-ssh-key.log
```

### Resuming After Failure
```bash
# State is automatically tracked
# Just re-run the task - it will skip completed subtasks
task deploy-mcm
```

## Documentation

### For New Users
Start here:
1. [Requirements](REQUIREMENTS.md) - What you need installed
2. [Getting Started](GETTING_STARTED.md) - Step-by-step first deployment
3. [Configuration](CONFIGURATION.md) - How to configure your environment

### For Operators
Day-to-day usage:
1. [Configuration](CONFIGURATION.md) - Configuration reference
2. [Profiles](PROFILES.md) - Understanding workflows
3. [Troubleshooting](TROUBLESHOOTING.md) - Fixing common issues

### For Developers
Understanding the system:
1. [Overview](OVERVIEW.md) - High-level architecture
2. [Architecture](ARCHITECTURE.md) - Technical details
3. [Profiles](PROFILES.md) - Creating custom profiles

## Common Tasks

### View Available Tasks
```bash
# List all tasks
task --list

# List tasks with descriptions
task --list-all
```

### Check Task Dependencies
```bash
# See what a task will run
task --dry deploy-mcm
```

### Reset State
```bash
# Clear completed task tracking
rm .cache/state.json

# Tasks will re-run from beginning
```

### Debug Task Execution
```bash
# View task log
tail -f .cache/logs/task_<task-id>.log

# Check Ansible inventory
ansible-inventory -i config.yml --list
```

## Deployment Phases

### Phase 1: Infrastructure Prep (prep)
- Prepare onboarder container
- Set up deployment environment
- Validate configurations

### Phase 2: MCM Deployment (deploy-mcm)
- Copy SSH keys to infrastructure nodes
- Prepare nodes (OS configuration)
- Deploy RKE2 Kubernetes cluster
- Configure cluster networking

### Phase 3: OSMS Deployment (deploy-prod-osms)
- Prepare downstream cluster nodes
- Deploy OSMS cluster via Rancher
- Configure OSMS-specific settings

### Phase 4: OSDC Deployment (deploy-prod-osdc)
- Prepare downstream cluster nodes
- Deploy OSDC cluster via Rancher
- Configure OSDC-specific settings

## Support

### Getting Help

1. **Check Logs**: Start with `.cache/logs/` directory
2. **Review State**: Check `.cache/state.json` for completed tasks
3. **Documentation**: See individual documentation files
4. **Troubleshooting**: Refer to [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### Reporting Issues

When reporting problems, include:
- Task command that failed
- Relevant log file from `.cache/logs/`
- State file `.cache/state.json`
- Environment configuration (sanitize secrets!)
- Container and host OS details

## Key Concepts

### Taskfile Orchestration
Workflows are defined in Taskfile.yml using a hierarchical task structure:
```yaml
tasks:
  prep:
    desc: Complete environment preparation
    cmds:
      - task: prep-onboarder-container
      - task: run-deployment-setup
```

### Task Execution with State Management
Tasks are executed via run_task.py which provides:
- **State tracking**: Completed tasks are recorded in `.cache/state.json`
- **Logging**: Each task logs to `.cache/logs/task_<id>.log`
- **Idempotency**: Safe to re-run, skips completed tasks
- **Real-time output**: Stream logs as tasks execute

### Included Taskfiles
Complex deployments are broken into modules:
```yaml
includes:
  deployment:
    taskfile: ../../data/basekit/1.0.1/main.yml
    vars:
      DATA_DIR: /docker-workspace/data
```

### Variable Passing
Variables flow through task hierarchies:
```yaml
vars:
  HOSTS: infrastructure_cluster
cmds:
  - task: subtask
    vars:
      HOSTS: '{{.HOSTS}}'  # Pass through
```

## Support

### Getting Help

1. **Check Documentation**: Start with [Troubleshooting](TROUBLESHOOTING.md)
2. **Review Logs**: Check `usr_home/<env>/logs/`
3. **Validate Configuration**: Run with `--validate-only`
4. **Enable Verbose Mode**: Use `--verbose` flag

### Reporting Issues

When reporting problems, include:
- Full error message
- Relevant logs (sanitize secrets!)
- Configuration files (sanitize secrets!)
- Environment details (OS, Python version, etc.)

### Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines on:
- Adding new profiles
- Creating tasks
- Improving documentation
- Submitting bug fixes

## Security Notes

### SSH Key Management
```bash
# Always set proper permissions
chmod 700 .ssh
chmod 600 .ssh/*_rsa
chmod 644 .ssh/*_rsa.pub
```

### Container Isolation
- All deployments run in isolated container
- Host system remains unaffected
- SSH keys mounted read-only
- Logs persist on host

### Ansible Inventory
```yaml
# Use SSH keys (recommended)
ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key

# Avoid plaintext passwords in version control
# Use ansible-vault or external secrets management
```

## Version History

### v1.0.1 - Current Release
- Taskfile-based orchestration
- run_task.py for state management
- Real-time log streaming
- Modular taskfile includes
- Support for MCM, OSMS, OSDC deployments
- Air-gapped environment support

## Architecture Overview

```
Environment Taskfile.yml
    ↓
Included Taskfiles (basekit/main.yml, cluster_deployment/main.yml)
    ↓
run_task.py (state tracking, logging)
    ↓
Task Execution (Ansible playbooks, shell commands)
    ↓
State Saved (.cache/state.json)
```

**Key Components:**
- **Taskfile.yml**: Main workflow orchestration
- **run_task.py**: Execution engine with state management
- **Ansible playbooks**: Infrastructure automation
- **State tracking**: Resume capability

---

**Ready to get started?** Head to [Getting Started](docs/GETTING_STARTED.md)!

**Need help?** Check out [Troubleshooting](docs/TROUBLESHOOTING.md)!

**Last Updated**: November 2025  
**Version**: 1.0.1  
**Maintained By**: Infrastructure Team
