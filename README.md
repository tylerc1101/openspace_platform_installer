# OpenSpace Platform Installer

A stateful, containerized deployment orchestration system for OpenSpace infrastructure using a declarative deployment configuration and Taskfile-based workflows.

## Quick Links

- [**Getting Started**](docs/GETTING_STARTED.md) - Quick start guide for first-time users
- [**Requirements**](docs/REQUIREMENTS.md) - Prerequisites and dependencies
- [**Overview**](docs/OVERVIEW.md) - What the installer does and how it works
- [**Configuration**](docs/CONFIGURATION.md) - Detailed configuration reference (deployment.yml)
- [**Taskfiles**](docs/TASKFILES.md) - Understanding deployment workflows
- [**Architecture**](docs/ARCHITECTURE.md) - System design and technical details
- [**Troubleshooting**](docs/TROUBLESHOOTING.md) - Common issues and solutions

## What Is This?

The OpenSpace Platform Installer ("Onboarder") provides a reproducible, stateful deployment system for complex OpenSpace infrastructure. Using a single `deployment.yml` configuration file, it orchestrates:

- **Base infrastructure** (Management KVM, OPNsense firewall, virtual machines, networking)
- **MCM (Management Cluster)** - RKE2-based Kubernetes with Harbor, Rancher, Gitea, and ArgoCD
- **OSMS (OpenSpace Management System)** - Management plane cluster
- **OSDC (OpenSpace Data Cluster)** - Data plane cluster

### Key Technologies

- **Declarative Configuration**: Single `deployment.yml` file defines entire infrastructure
- **Containerized execution**: All deployments run in isolated Podman/Docker container
- **Taskfile**: YAML-based task runner for workflow orchestration
- **Python orchestration**: run_task.py for state management and logging
- **Ansible playbooks**: Infrastructure configuration management
- **Stateful tracking**: Automatic resume after interruptions

## Features

✅ **Declarative configuration** - Single deployment.yml file defines entire infrastructure
✅ **Automatic config generation** - All Ansible inventory and vars generated from deployment.yml
✅ **Stateful execution** - Tracks completed tasks, resumes after failures
✅ **Containerized isolation** - All dependencies pre-installed, consistent environment
✅ **Real-time logging** - Stream output from long-running tasks
✅ **Modular onboarder versions** - Versioned deployment logic (3.5.0-rc7, etc.)
✅ **Idempotent operations** - Safe to re-run without side effects
✅ **Air-gapped support** - Works in disconnected environments
✅ **Multiple deployment types** - Supports basekit, baremetal, and AWS deployments
✅ **First-run initialization** - Automatic environment setup on first container start

## Directory Structure

```
openspace_platform_installer/
├── data/                                    # Deployment logic and execution engine
│   ├── run_task.py                         # Task execution engine with state management
│   └── onboarders/                         # Versioned onboarder deployments
│       └── 3.5.0-rc7/                      # Onboarder version
│           ├── main.yml                    # Main taskfile for this version
│           ├── basekit.yml                 # Basekit deployment tasks
│           ├── baremetal.yml               # Baremetal deployment tasks
│           └── tasks/                      # Ansible playbooks
│               ├── bootstrap-mgmt-kvm.yml
│               ├── deploy-vms.yml
│               ├── configure-node.yml
│               ├── copy_ssh_key.yml
│               ├── deploy_clusters.yml
│               ├── generate_config.yml     # Generates config from deployment.yml
│               └── ...
├── images/                                  # Container images and ISOs
│   ├── onboarder/                          # Onboarder container image/Containerfile
│   ├── rpms/                               # RPMs to install in container
│   └── opnsense/                           # OPNsense ISO
├── environments/                            # Environment configurations (generated)
│   └── <environment_name>/
│       ├── <env>.deployment.yml            # Source deployment configuration
│       ├── Taskfile.yml                    # Generated orchestration workflow
│       ├── inventory.yml                   # Generated Ansible inventory
│       ├── group_vars/                     # Generated Ansible variables
│       ├── .ssh/                           # Generated SSH keys
│       └── .cache/                         # Runtime state (auto-created)
│           ├── state.json                  # Task completion tracking
│           └── logs/                       # Task execution logs
├── scripts/
│   └── first-run.sh                        # First-run initialization script
├── onboarder-run.py                        # Container launcher script
└── test.deployment.yml                     # Sample deployment configuration
```

## Quick Start

### 1. Create Deployment Configuration
```bash
# Copy sample deployment configuration
cp test.deployment.yml environments/myenv/myenv.deployment.yml

# Edit deployment configuration
vim environments/myenv/myenv.deployment.yml
```

See [Configuration Guide](docs/CONFIGURATION.md) for details on the deployment.yml format.

### 2. Start Onboarder Container
```bash
# Launch container and select your environment
python3 onboarder-run.py

# The container will:
# - Detect your deployment.yml file
# - Run first-time setup (on first run)
# - Generate all config files from deployment.yml
# - Start an interactive shell
```

### 3. Run Deployment
```bash
# Inside container, navigate to install directory
cd install

# Run full deployment workflow
task prep                    # Prepare environment
task deploy-mcm             # Deploy management cluster
task deploy-prod-osms       # Deploy OSMS cluster
task deploy-prod-osdc       # Deploy OSDC cluster (if configured)
```

### 4. Monitor Progress
```bash
# Real-time output is shown during execution

# View logs for specific task
tail -f .cache/logs/task_<task-id>.log

# Check state
cat .cache/state.json
```

## Usage Examples

### Full Basekit Deployment (from scratch)
```bash
# Complete infrastructure deployment including VMs
task prep                    # Prepare environment
task deploy-mcm             # Deploy management cluster (includes VM creation)
task deploy-prod-osms       # Deploy OSMS cluster
task deploy-prod-osdc       # Deploy OSDC cluster (if configured)
```

### Baremetal Deployment (existing servers)
```bash
# Deploy to existing bare metal servers
task prep                    # Prepare environment
task deploy-mcm             # Deploy management cluster
task deploy-prod-osms       # Deploy OSMS cluster
task deploy-prod-osdc       # Deploy OSDC cluster
```

### Retrieving Kubeconfigs
```bash
# Download kubeconfig files after deployment
task get-kubeconfig-mcm
task get-kubeconfig-osms
task get-kubeconfig-osdc
```

### Checking Status
```bash
# View task state
cat .cache/state.json

# View logs
ls -lh .cache/logs/
tail -f .cache/logs/task_<id>.log

# List available tasks
task --list
```

### Resuming After Failure
```bash
# State is automatically tracked
# Just re-run the task - it will skip completed subtasks
task deploy-mcm

# To start fresh (reset state)
rm .cache/state.json
task deploy-mcm
```

## Documentation

### For New Users
Start here:
1. [Requirements](docs/REQUIREMENTS.md) - Prerequisites and dependencies
2. [Getting Started](docs/GETTING_STARTED.md) - Step-by-step first deployment
3. [Configuration](docs/CONFIGURATION.md) - deployment.yml configuration guide

### For Operators
Day-to-day usage:
1. [Configuration](docs/CONFIGURATION.md) - Configuration reference
2. [Taskfiles](docs/TASKFILES.md) - Understanding workflows
3. [Troubleshooting](docs/TROUBLESHOOTING.md) - Fixing common issues

### For Developers
Understanding the system:
1. [Overview](docs/OVERVIEW.md) - High-level architecture
2. [Architecture](docs/ARCHITECTURE.md) - Technical details
3. [Taskfiles](docs/TASKFILES.md) - Creating custom workflows

## Common Tasks

### View Available Tasks
```bash
# List all tasks
task --list

# List tasks with descriptions
task --list-all
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
tail -f .cache/logs/task_<id>.log

# Check generated inventory
cat inventory.yml

# View generated Taskfile
cat Taskfile.yml
```

## Deployment Phases

### Phase 1: Preparation (prep)
- Generate all configuration from deployment.yml
- Create Ansible inventory
- Create Taskfile
- Generate SSH keys
- Prepare onboarder container

### Phase 2: MCM Deployment (deploy-mcm)
**For Basekit:**
- Bootstrap management KVM host
- Configure OPNsense firewall
- Deploy virtual machines (MCM, OSMS, OSDC)
- Prepare cluster nodes
- Deploy RKE2 cluster
- Deploy Harbor registry
- Deploy Rancher
- Deploy Gitea and ArgoCD

**For Baremetal:**
- Copy SSH keys to nodes
- Prepare nodes (OS configuration)
- Deploy RKE2 cluster
- Deploy platform components

### Phase 3: OSMS Deployment (deploy-prod-osms)
- Prepare OSMS cluster nodes
- Deploy OSMS cluster via Rancher
- Configure OSMS-specific settings

### Phase 4: OSDC Deployment (deploy-prod-osdc)
- Prepare OSDC cluster nodes
- Deploy OSDC cluster via Rancher
- Configure OSDC-specific settings

## Support

### Getting Help

1. **Check Logs**: Start with `.cache/logs/` directory
2. **Review State**: Check `.cache/state.json` for completed tasks
3. **Documentation**: See individual documentation files
4. **Troubleshooting**: Refer to [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

### Reporting Issues

When reporting problems, include:
- Task command that failed
- Relevant log file from `.cache/logs/`
- State file `.cache/state.json`
- Deployment configuration deployment.yml (sanitize secrets!)
- Container and host OS details

## Key Concepts

### Declarative Configuration
All infrastructure is defined in a single `<env>.deployment.yml` file:
```yaml
deployment:
  name: "my-deployment"
  type: "basekit"
  onboarder_version: "3.5.0-rc7"

networks:
  customer:
    gateway: "10.10.10.1"
    cidr: "/24"
  management:
    network: "192.168.1"

management_cluster:
  clusters:
    - cluster_name: "local"
      nodes:
        - name: "mcm1"
          mgmt_ip: "192.168.1.10"
```

### Configuration Generation
On first run, the system automatically generates:
- `inventory.yml` - Ansible inventory with all hosts
- `Taskfile.yml` - Environment-specific task definitions
- `group_vars/` - Ansible variables
- `.ssh/` - SSH keys

### Task Execution with State Management
Tasks are executed via run_task.py which provides:
- **State tracking**: Completed tasks are recorded in `.cache/state.json`
- **Logging**: Each task logs to `.cache/logs/task_<id>.log`
- **Idempotency**: Safe to re-run, skips completed tasks
- **Real-time output**: Stream logs as tasks execute

### Onboarder Versions
Deployment logic is versioned in `data/onboarders/<version>/`:
- `3.5.0-rc7` - Current release
- Future versions can coexist
- Select version in deployment.yml

## Security Notes

### SSH Key Management
SSH keys are automatically generated during first-run:
```bash
# Keys are stored in environment directory
environments/<env>/.ssh/

# Proper permissions are set automatically
# Private keys: chmod 600
# Public keys: chmod 644
```

### Container Isolation
- All deployments run in isolated container
- Host system remains unaffected
- Environment directory mounted for read-write
- Data directory mounted read-only
- Logs persist on host

### Secrets in deployment.yml
```yaml
# SSH credentials
ssh:
  user: "rancher"
  pass: "password"  # Used for initial access
  become: "sudouser"

# Avoid committing passwords to version control
# Use environment variables or external secret management
```

## Version History

### v3.5.0-rc7 - Current Onboarder Release
- Declarative deployment.yml configuration
- Automatic configuration generation
- Support for basekit, baremetal, and AWS deployments
- Virtual machine deployment for basekit
- Improved state management and logging
- First-run initialization script
- Kubeconfig retrieval commands
- Support for darksite/air-gapped deployments

## Architecture Overview

```
deployment.yml (declarative config)
    ↓
first-run.sh (on first container start)
    ↓
generate_config.yml (create inventory, Taskfile, vars)
    ↓
Environment Taskfile.yml (generated)
    ↓
Onboarder Taskfiles (data/onboarders/3.5.0-rc7/*.yml)
    ↓
run_task.py (state tracking, logging)
    ↓
Task Execution (Ansible playbooks)
    ↓
State Saved (.cache/state.json)
```

**Key Components:**
- **deployment.yml**: Declarative infrastructure configuration
- **onboarder-run.py**: Container launcher
- **first-run.sh**: First-time environment setup
- **run_task.py**: Execution engine with state management
- **Ansible playbooks**: Infrastructure automation

---

**Ready to get started?** Head to [Getting Started](docs/GETTING_STARTED.md)!

**Need help?** Check out [Troubleshooting](docs/TROUBLESHOOTING.md)!

**Last Updated**: December 2025
**Version**: 3.5.0-rc7
**Maintained By**: Infrastructure Team
