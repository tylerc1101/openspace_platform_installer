# Getting Started

## Quick Start Guide

### 1. Prepare Your Environment

#### Ensure Required Repositories
```bash
# Ensure you have both repositories
ls -la
# You should see:
# openspace_platform_installer/
# openspace_platform_installer_images/
```

#### Create Your Environment Directory
```bash
cd openspace_platform_installer

# Create environment structure
mkdir -p environments/<your_environment>
cd environments/<your_environment>

# Create required directories
mkdir -p group_vars
mkdir -p .ssh
mkdir -p .cache/logs

# Create configuration files
touch Taskfile.yml
touch config.yml
touch group_vars/all.yml
```

### 2. Configure Your Deployment

#### Create Main Taskfile (`Taskfile.yml`)
```yaml
version: '3'

vars:
  ENV: <your_environment>
  DATA_DIR: /docker-workspace/data
  DEPLOYMENT_TYPE: basekit
  DEPLOYMENT_VERSION: 1.0.1

includes:
  deployment:
    taskfile: ../../data/{{.DEPLOYMENT_TYPE}}/{{.DEPLOYMENT_VERSION}}/main.yml
    vars:
      ENV: '{{.ENV}}'
      DATA_DIR: '{{.DATA_DIR}}'
      
  node-prep:
    taskfile: ../../data/node_prep/1.0.1/main.yml
    vars:
      DATA_DIR: '{{.DATA_DIR}}'

tasks:
  prep:
    desc: Complete environment preparation workflow
    cmds:
      - task: prep-onboarder-container
      - task: run-deployment-setup

  deploy-mcm:
    desc: Deploy Management Cluster
    cmds:
      - task: infrastructure_cluster_prep
      - task: infrastructure_node_prep
      - task: run-onboarder
```

#### Edit Ansible Inventory (`config.yml`)
```yaml
all:
  children:
    infrastructure_cluster:
      hosts:
        mcm1:
          ansible_host: 192.168.1.10
          ansible_user: rancher
          ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key
    
    downstream_clusters:
      hosts:
        osms1:
          ansible_host: 192.168.2.20
        osdc1:
          ansible_host: 192.168.2.21
```

#### Configure Variables (`group_vars/all.yml`)
```yaml
# Cluster configuration
cluster_domain: "example.com"

# Network settings
dns_servers:
  - "8.8.8.8"
  - "8.8.4.4"

# Deployment settings
rke2_version: "v1.28.0+rke2r1"
rancher_version: "2.8.0"
```

### 3. Set Up SSH Keys

```bash
# Generate SSH key pair if needed
ssh-keygen -t rsa -b 4096 -f .ssh/rancher_ssh_key -N ""

# Copy public key to target systems
ssh-copy-id -i .ssh/rancher_ssh_key.pub rancher@192.168.1.10

# Set proper permissions
chmod 700 .ssh
chmod 600 .ssh/rancher_ssh_key
chmod 644 .ssh/rancher_ssh_key.pub
```

### 4. Start Container and Setup Environment

```bash
# From repository root
python3 onboarder-run.py

# Inside container, symlink your environment to 'install'
cd /docker-workspace
ln -s config/<your_environment> install
cd install
```

### 5. Run the Deployment

#### List Available Tasks
```bash
# See all available tasks
task --list

# See task descriptions
task --list-all
```

#### Run Full Deployment
```bash
# Complete workflow
task prep                    # Prepare environment
task deploy-mcm             # Deploy management cluster
task deploy-prod-osms       # Deploy OSMS cluster
task deploy-prod-osdc       # Deploy OSDC cluster
```

#### Run Individual Phases
```bash
# Infrastructure preparation
task infrastructure_cluster_prep

# Node preparation
task infrastructure_node_prep

# Onboarder deployment
task run-onboarder
```

### 6. Monitor Progress

The deployment provides real-time output and detailed logging:

#### Real-time Output
```bash
# Task execution shows live output
task deploy-mcm

# Output streams in real-time as Ansible runs
TASK [Copy SSH Key] ************************************************************
ok: [mcm1]

PLAY RECAP *********************************************************************
mcm1                       : ok=5    changed=2    unreachable=0    failed=0
```

#### Check Logs
```bash
# View logs directory
ls -lh .cache/logs/

# Tail specific task log
tail -f .cache/logs/task_copy-ssh-key.log

# View state tracking
cat .cache/state.json
```

### 7. Resume After Interruption

Tasks automatically track completion state:

```bash
# If deployment stops, just re-run the task
task deploy-mcm

# Completed tasks are skipped
# Only incomplete/failed tasks will run
```

#### Manual State Reset
```bash
# Clear state to re-run all tasks
rm .cache/state.json

# Now all tasks will run fresh
task deploy-mcm
```

## Next Steps

Once your initial deployment completes:

1. **Verify Infrastructure**: SSH to deployed systems and verify services
2. **Review Logs**: Check `.cache/logs/` for any warnings
3. **Explore Tasks**: Use `task --list` to see all available operations
4. **Customize Workflow**: Modify `Taskfile.yml` to add custom tasks
5. **Version Control**: Commit your environment configuration (excluding secrets!)
6. **Document Environment**: Add README to your environment directory

## Common First-Time Issues

### Container Not Starting
```bash
# Ensure Docker/Podman is running
sudo systemctl status podman

# Check for image
podman images | grep onboarder
```

### Task Not Found
```
Error: task: Task "deploy-mcm" not found
```
**Solution**: Ensure you're in the correct directory with Taskfile.yml:
```bash
cd /docker-workspace/install
task --list
```

### SSH Connection Fails
```
FAILED! => {"msg": "Failed to connect to the host via ssh: Permission denied"}
```

**Solution**: Test SSH manually first:
```bash
# Test from inside container
ssh -i .ssh/rancher_ssh_key rancher@target-host

# Check key permissions
ls -la .ssh/
chmod 600 .ssh/rancher_ssh_key
```

### Ansible Inventory Not Found
```
ERROR! Unable to retrieve file contents
```

**Solution**: Ensure config.yml exists and symlink is correct:
```bash
ls -la /docker-workspace/install/config.yml
ls -la /docker-workspace/config/<your_env>/config.yml
```

### Variable Not Defined
```
Error: required variable HOSTS is not set
```

**Solution**: Check task requirements and pass variables:
```yaml
# In Taskfile.yml
task: subtask
vars:
  HOSTS: '{{.HOSTS}}'
```

### State File Issues
```bash
# If state tracking seems wrong, reset it
rm .cache/state.json

# Re-run tasks fresh
task deploy-mcm
```
