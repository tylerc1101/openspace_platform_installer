# How It Works

Technical details for those who want to understand the installer architecture or contribute to it.

## Architecture Overview

```
deployment.yml (your infrastructure definition)
    ↓
onboarder-run.py (container launcher)
    ↓
First-run: scripts/first-run.sh
    ↓
generate_config.yml (creates inventory, Taskfile, vars, SSH keys)
    ↓
Taskfile.yml (generated orchestration)
    ↓
data/onboarders/3.5.0-rc7/ (versioned deployment logic)
    ↓
run_task.py (state tracking + logging)
    ↓
Ansible playbooks (actual infrastructure work)
    ↓
.cache/state.json (tracks what's done)
```

## Key Components

### 1. deployment.yml - Single Source of Truth

Everything is defined in one YAML file:
- Deployment type (basekit, baremetal, AWS)
- Network configuration
- Host/VM specifications
- Cluster definitions
- Storage settings

This file is the **only** thing you need to edit.

### 2. Automatic Configuration Generation

On first container start, `scripts/first-run.sh` runs and generates:
- **inventory.yml** - Ansible inventory with all hosts
- **Taskfile.yml** - Deployment workflow tasks
- **group_vars/all.yml** - Ansible variables
- **.ssh/** - SSH key pairs for each cluster

These files are **generated** and should not be manually edited. To change them, edit deployment.yml and regenerate.

### 3. Versioned Onboarder Logic

Deployment logic lives in `data/onboarders/<version>/`:
```
data/onboarders/3.5.0-rc7/
├── main.yml          # Main task orchestration
├── basekit.yml       # Basekit-specific tasks
├── baremetal.yml     # Baremetal-specific tasks
└── tasks/            # Ansible playbooks
    ├── bootstrap-mgmt-kvm.yml
    ├── deploy-vms.yml
    ├── deploy_clusters.yml
    ├── generate_config.yml
    └── ...
```

Multiple versions can coexist. Select version in deployment.yml.

### 4. Stateful Execution

`data/run_task.py` tracks completed tasks in `.cache/state.json`:
```json
{
  "completed_tasks": {
    "copy-ssh-key-mcm": {
      "completed_at": "2025-12-10T10:30:00Z",
      "status": "success"
    }
  }
}
```

When you re-run a task:
- Checks state file
- Skips completed tasks
- Continues from where it failed

This makes deployments resumable and idempotent.

### 5. Container Isolation

Everything runs in a container:
- Rocky Linux 9 base
- Ansible, Python, Task pre-installed
- Mounts:
  - `data/` → `/docker-workspace/data` (deployment logic)
  - `environments/<env>/` → `/docker-workspace/config/<env>/` (your config)
  - `images/` → `/docker-workspace/images` (ISOs, images)

## Deployment Workflows

### Basekit Workflow

```
task deploy-mcm
├── copy-ssh-key-mgmt-kvm
├── bootstrap-mgmt-kvm (install KVM, configure networking)
├── configure-opnsense (generate firewall config)
├── deploy-opnsense-vm
├── deploy-vms (create MCM, OSMS, OSDC VMs)
├── configure-vm-partitions
├── copy-ssh-key-mcm
├── node-prep-mcm (OS config, SELinux)
└── run-onboarder
    ├── deploy-rke2-cluster
    ├── deploy-harbor
    ├── load-darksite-bundles
    ├── deploy-rancher
    ├── bootstrap-rancher (Terraform)
    ├── deploy-gitea
    └── deploy-argocd
```

### Baremetal Workflow

```
task deploy-mcm
├── copy-ssh-key-mcm
├── node-prep-mcm
└── run-onboarder
    ├── deploy-rke2-cluster
    ├── deploy-harbor
    ├── deploy-rancher
    ├── deploy-gitea
    └── deploy-argocd
```

### OSMS/OSDC Workflow

```
task deploy-prod-osms
├── copy-ssh-key-osms
├── node-prep-osms
└── deploy-cluster-via-rancher
```

## What Each Task Does

### copy-ssh-key

Distributes SSH public key to target hosts using password auth. After this, all communication uses key-based auth.

### bootstrap-mgmt-kvm (basekit only)

- Installs libvirt/KVM
- Configures network bridges
- Sets up storage pools

### deploy-vms (basekit only)

Creates VMs from base image:
- Clones base qcow2 image
- Resizes disk
- Sets CPU/RAM
- Attaches to network bridge
- Starts VM

### node-prep

Prepares nodes for Kubernetes:
- Configures OS (sysctl, modules)
- Installs RKE2 SELinux module
- Disables swap
- Configures firewall

### run-onboarder

Deploys entire platform stack:
- RKE2 cluster via Ansible
- Harbor registry (for air-gapped)
- Rancher (multi-cluster management)
- Gitea (Git source control)
- ArgoCD (GitOps)

## File Locations

```
openspace_platform_installer/
├── onboarder-run.py              # Container launcher
├── data/
│   ├── run_task.py              # State management
│   └── onboarders/3.5.0-rc7/    # Deployment logic
├── scripts/
│   └── first-run.sh             # First-run initialization
├── images/
│   └── onboarder/               # Container definition
└── environments/<env>/
    ├── <env>.deployment.yml     # Your config (edit this)
    ├── inventory.yml            # Generated
    ├── Taskfile.yml             # Generated
    ├── group_vars/              # Generated
    ├── .ssh/                    # Generated
    └── .cache/
        ├── state.json           # State tracking
        └── logs/                # Task logs
```

## Deployment Configuration Reference

See [DEPLOY_BASEKIT.md](DEPLOY_BASEKIT.md) and [DEPLOY_BAREMETAL.md](DEPLOY_BAREMETAL.md) for complete examples.

### deployment.yml Structure

```yaml
deployment:              # Metadata
  name: "..."
  type: "basekit|baremetal|aws"
  onboarder_version: "3.5.0-rc7"

ssh:                     # Credentials
  user: "..."
  pass: "..."
  become: "..."

networks:                # Network topology
  customer: {...}
  management: {...}

infrastructure:          # Physical hosts (basekit only)
  mgmt_kvm: {...}
  opnsense: {...}

management_cluster:      # MCM nodes
  clusters:
    - cluster_name: "local"
      nodes: [...]

openspace_management_system:  # OSMS nodes
  clusters: [...]

openspace_data_cluster:       # OSDC nodes (optional)
  clusters: [...]

virtual_machines:        # VM specs (basekit only)
  mcm: {...}
  osms: {...}

storage:                 # Storage backend
  nfs: {...}
```

## Taskfile System

Tasks are defined in YAML:

```yaml
tasks:
  deploy-mcm:
    desc: "Deploy MCM"
    cmds:
      - task: onboarder:deploy-mcm-{{.DEPLOYMENT_TYPE}}
```

Tasks call `run_task.py` which:
1. Checks if task already completed
2. Runs Ansible playbook or shell command
3. Logs output to `.cache/logs/task_<id>.log`
4. Saves completion to `.cache/state.json`

## State Management

State file tracks completed tasks:

**Load state:**
```python
state = json.load(open('.cache/state.json'))
if task_id in state['completed_tasks']:
    return  # Skip, already done
```

**Save state:**
```python
state['completed_tasks'][task_id] = {
    'completed_at': datetime.now().isoformat(),
    'status': 'success'
}
json.dump(state, open('.cache/state.json', 'w'))
```

**Reset state:**
```bash
rm .cache/state.json  # Start fresh
```

## Logging

Each task logs to its own file:
```
.cache/logs/
├── task_copy-ssh-key-mcm.log
├── task_bootstrap-mgmt-kvm.log
├── task_deploy-vms.log
└── ...
```

Logs include:
- Task start time
- Full Ansible output
- Task end time
- Duration

## Container Details

**Base image:** Rocky Linux 9

**Installed packages:**
- ansible
- python3
- task (Taskfile runner)
- jq, yq
- openssh-clients
- sshpass
- Custom RPMs for STIG compliance

**Volumes:**
- Read-only: data/, images/
- Read-write: environments/<env>/

**Working directory:** `/docker-workspace/install` → symlink to `/docker-workspace/config/<env>/`

## How to Contribute

### Adding a New Task

1. Create Ansible playbook in `data/onboarders/<version>/tasks/`
2. Add task definition to `data/onboarders/<version>/<type>.yml`
3. Call via `run_task.py` for state tracking

Example:
```yaml
# In basekit.yml
tasks:
  my-new-task:
    desc: "Do something new"
    cmds:
      - python3 {{.DATA_DIR}}/run_task.py
          --task-id=my-new-task
          --hosts=infrastructure_cluster
          --file={{.DATA_DIR}}/onboarders/{{.ONBOARDER_VERSION}}/tasks/my_task.yml
          --kind=ansible
```

### Adding a New Onboarder Version

1. Copy `data/onboarders/3.5.0-rc7/` to `data/onboarders/3.6.0/`
2. Make your changes
3. Update deployment.yml: `onboarder_version: "3.6.0"`

### Modifying Configuration Generation

Edit `data/onboarders/<version>/tasks/generate_config.yml`

This Jinja2 template generates:
- inventory.yml
- Taskfile.yml
- group_vars/all.yml

### Testing Changes

1. Create test deployment.yml
2. Run in test environment
3. Check `.cache/logs/` for issues
4. Verify `.cache/state.json` tracking works

## Air-Gapped / Darksite Deployments

For disconnected environments:

1. Pre-load container images in `images/`
2. Set up local mirror repos
3. Configure in group_vars:
```yaml
darksite_mode: true
registry_mirror: "harbor.local.example.com"
```

4. Run normal deployment - will use local resources

## Debugging

**Enable verbose Ansible:**
```yaml
# In generated Taskfile, add to task:
ANSIBLE_VERBOSITY: "2"
```

**Run Ansible playbook manually:**
```bash
ansible-playbook -i inventory.yml \
  data/onboarders/3.5.0-rc7/tasks/some_task.yml -vvv
```

**Check generated inventory:**
```bash
ansible-inventory -i inventory.yml --list
```

**Test connectivity:**
```bash
ansible -i inventory.yml -m ping all
```

## Security Notes

**SSH Keys:**
- Generated per-cluster
- Private keys: chmod 600
- Stored in `.ssh/` (gitignored)

**Secrets:**
- Never commit deployment.yml with real passwords
- Use Ansible Vault for sensitive vars
- Or external secret management

**Container Isolation:**
- Runs as non-root where possible
- Limited host filesystem access
- Read-only deployment logic

## Performance

**State tracking overhead:** Minimal (< 1s per task)

**Parallel execution:** Tasks can run in parallel:
```yaml
deps:
  - task-a
  - task-b  # Runs parallel with task-a
```

**Container reuse:** Container stays running, no startup overhead between tasks
