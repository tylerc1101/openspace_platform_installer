# OpenSpace Platform Installer - Overview

## What It Does

The OpenSpace Platform Installer (codename "Onboarder") is a stateful, containerized deployment orchestration system that automates complex OpenSpace infrastructure deployments using a declarative configuration approach. Define your entire infrastructure in a single `deployment.yml` file, and the installer handles the rest.

## Key Capabilities

### 1. Declarative Infrastructure Configuration
- **Single source of truth**: All infrastructure defined in `<env>.deployment.yml`
- **Automatic generation**: inventory, Taskfiles, variables, and SSH keys created from deployment.yml
- **Version controlled**: Track infrastructure changes in git
- **No manual configuration**: First-run script generates everything needed

### 2. Multi-Cluster Infrastructure Deployment
Deploy complete OpenSpace platform infrastructure:
- **Base Infrastructure** (Basekit): Management KVM hosts, OPNsense firewalls, virtual machines, networking
- **MCM (Management Cluster)**: RKE2-based Kubernetes with Harbor registry, Rancher, Gitea, and ArgoCD
- **OSMS (OpenSpace Management System)**: Management plane cluster
- **OSDC (OpenSpace Data Cluster)**: Data plane cluster

### 3. Multiple Deployment Types

#### Basekit Deployment
- Deploys full infrastructure from scratch on a management KVM host
- Creates OPNsense firewall VM
- Deploys MCM, OSMS, and OSDC as virtual machines
- Configures networking and storage
- Suitable for lab environments and proof-of-concepts

#### Baremetal Deployment
- Deploys to existing bare metal servers
- Assumes servers are already provisioned
- Configures OS and installs Kubernetes
- Suitable for production environments

#### AWS Deployment
- Cloud-based deployment (future)
- Provisions AWS resources
- Deploys clusters to EC2 instances

### 4. Containerized Execution Environment

#### Container Features
- **Isolated execution**: All deployments run in Podman/Docker container
- **Consistent dependencies**: Pre-installed Ansible, Python, Task, and utilities
- **Volume mounts**: Access to data, images, and environment configurations
- **Air-gapped support**: Works in disconnected environments
- **First-run initialization**: Automatic environment setup on first container start

#### What's in the Container
- Rocky Linux 9 base image
- Python 3.9+
- Ansible 2.14+
- Task (Taskfile runner)
- Required system utilities (jq, yq, etc.)
- Custom RPMs for STIG compliance

### 5. Stateful Execution

The installer provides robust state management:
- **Task tracking**: Completed tasks recorded in `.cache/state.json`
- **Resume capability**: Automatically skip completed tasks on re-run
- **Idempotent operations**: Safe to run tasks multiple times
- **Granular control**: Reset state to re-run specific tasks
- **Per-task logging**: Each task logs to `.cache/logs/task_<id>.log`

### 6. Real-Time Monitoring

#### Live Output Streaming
- **Real-time feedback**: See Ansible output as it happens
- **Progress tracking**: Clear indication of task completion
- **Duration tracking**: Know how long each task takes

#### Detailed Logging
- **Per-task logs**: Each task logs to `.cache/logs/task_<id>.log`
- **Persistent logs**: Logs survive container restarts
- **Structured state**: JSON state file for programmatic access

### 7. Versioned Onboarder Logic

Deployment logic is versioned in `data/onboarders/<version>/`:
- **3.5.0-rc7**: Current release
- **Future versions**: Can coexist, select in deployment.yml
- **Separate concerns**: Deployment logic separate from environments
- **Reproducible**: Same version produces same results

### 8. Automatic Configuration Generation

From a single deployment.yml, the system generates:
- **inventory.yml**: Ansible inventory with all hosts and groups
- **Taskfile.yml**: Environment-specific task orchestration
- **group_vars/**: Ansible variables for all components
- **.ssh/**: SSH key pairs for cluster access
- **Network configs**: OPNsense firewall configuration (for basekit)

## Use Cases

### Initial Infrastructure Deployment
Bootstrap complete OpenSpace infrastructure from scratch:
1. Create deployment.yml configuration
2. Launch onboarder container
3. Run `task prep && task deploy-mcm`
4. Deploy downstream clusters (OSMS, OSDC)

### Infrastructure Updates
Apply changes to existing infrastructure:
- Update cluster configurations
- Deploy new downstream clusters
- Scale existing resources
- Apply security patches

### Disaster Recovery
Rebuild infrastructure from configuration:
- All deployment logic is version-controlled
- deployment.yml can be backed up
- Reproducible deployments with consistent results

### Development and Testing
Test infrastructure changes safely:
- Create test environments quickly
- Validate changes before production
- Consistent deployment across dev/staging/prod

## Workflows

### Basekit Workflow (Full Infrastructure)

```
1. Create deployment.yml
   ├─> Define networks
   ├─> Define infrastructure hosts (mgmt_kvm, opnsense)
   ├─> Define cluster nodes (MCM, OSMS, OSDC)
   └─> Define VM specifications

2. Launch container (python3 onboarder-run.py)
   ├─> Select environment
   ├─> First-run initialization (if new)
   │   ├─> Generate inventory.yml
   │   ├─> Generate Taskfile.yml
   │   ├─> Generate group_vars/
   │   └─> Generate SSH keys
   └─> Drop into interactive shell

3. Run deployment
   ├─> task prep
   │   └─> Prepare onboarder container
   │
   ├─> task deploy-mcm
   │   ├─> Copy SSH keys to mgmt KVM
   │   ├─> Bootstrap management KVM
   │   ├─> Configure OPNsense firewall
   │   ├─> Deploy OPNsense VM
   │   ├─> Deploy cluster VMs (MCM, OSMS, OSDC)
   │   ├─> Configure VM partitions
   │   ├─> Copy SSH keys to cluster nodes
   │   ├─> Prepare nodes (OS config, SELinux)
   │   ├─> Deploy RKE2 cluster
   │   ├─> Deploy Harbor registry
   │   ├─> Deploy Rancher
   │   ├─> Bootstrap Rancher with Terraform
   │   ├─> Deploy Gitea
   │   └─> Deploy ArgoCD
   │
   ├─> task deploy-prod-osms
   │   ├─> Copy SSH keys to OSMS nodes
   │   ├─> Prepare OSMS nodes
   │   └─> Deploy OSMS cluster via Rancher
   │
   └─> task deploy-prod-osdc
       ├─> Copy SSH keys to OSDC nodes
       ├─> Prepare OSDC nodes
       └─> Deploy OSDC cluster via Rancher

4. Retrieve kubeconfigs
   ├─> task get-kubeconfig-mcm
   ├─> task get-kubeconfig-osms
   └─> task get-kubeconfig-osdc
```

### Baremetal Workflow (Existing Servers)

```
1. Create deployment.yml
   ├─> Define networks
   ├─> Define cluster nodes (MCM, OSMS, OSDC)
   └─> No VM specifications needed

2. Launch container (python3 onboarder-run.py)
   └─> (same as basekit)

3. Run deployment
   ├─> task prep
   │
   ├─> task deploy-mcm
   │   ├─> Copy SSH keys to MCM nodes
   │   ├─> Prepare nodes
   │   ├─> Deploy RKE2 cluster
   │   └─> Deploy platform components
   │
   ├─> task deploy-prod-osms
   │   └─> (same as basekit)
   │
   └─> task deploy-prod-osdc
       └─> (same as basekit)
```

## Architecture Benefits

### Separation of Concerns
- **Deployment logic** (data/onboarders/) - reusable, version-controlled
- **Deployment config** (deployment.yml) - declarative infrastructure definition
- **Generated config** (environments/) - ephemeral, can be regenerated
- **Images** (images/) - large binaries, separate repository
- **Execution engine** (run_task.py) - state management and logging

### Maintainability
- Single file defines infrastructure
- Clear task hierarchy with explicit dependencies
- Versioned deployment logic
- Easy to update or rollback

### Reliability
- State tracking prevents re-running completed work
- Idempotent operations safe to retry
- Real-time output for monitoring
- Detailed logs for troubleshooting

### Flexibility
- Support multiple deployment types
- Extensible onboarder system
- Mix Ansible, shell, and other execution types
- Easy to customize per environment

## What Gets Deployed

### MCM (Management Cluster)
- **RKE2 Kubernetes**: Production-grade Kubernetes distribution
- **Harbor**: Container image registry for air-gapped deployments
- **Rancher**: Multi-cluster Kubernetes management
- **Gitea**: Git source control for GitOps
- **ArgoCD**: GitOps continuous delivery

### OSMS (OpenSpace Management System)
- Downstream Kubernetes cluster
- Managed by Rancher
- Management plane for OpenSpace applications

### OSDC (OpenSpace Data Cluster)
- Downstream Kubernetes cluster
- Managed by Rancher
- Data plane for OpenSpace workloads

### Base Infrastructure (Basekit Only)
- **Management KVM**: Hypervisor running all VMs
- **OPNsense**: Firewall and router VM
- **Virtual Machines**: MCM, OSMS, OSDC VMs
- **Networking**: Bridges, VLANs, routing
