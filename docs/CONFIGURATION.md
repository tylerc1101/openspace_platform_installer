# Configuration Reference

## Directory Structure

```
environments/<environment>/
├── Taskfile.yml         # Main workflow orchestration
├── config.yml           # Ansible inventory (hosts, groups)
├── group_vars/          # Ansible variables by group
│   └── all.yml         # Common variables
├── .ssh/                # SSH keys for this environment
│   ├── rancher_ssh_key
│   └── rancher_ssh_key.pub
└── .cache/              # Runtime state and logs (auto-created)
    ├── state.json      # Task completion tracking
    └── logs/           # Task execution logs
```

## Environment Taskfile (`Taskfile.yml`)

The main orchestration file that defines your deployment workflow.

### Basic Structure
```yaml
version: '3'

vars:
  ENV: myenvironment
  DATA_DIR: /docker-workspace/data
  DEPLOYMENT_TYPE: basekit
  DEPLOYMENT_VERSION: 1.0.1

includes:
  deployment:
    taskfile: ../../data/{{.DEPLOYMENT_TYPE}}/{{.DEPLOYMENT_VERSION}}/main.yml
    vars:
      ENV: '{{.ENV}}'
      DATA_DIR: '{{.DATA_DIR}}'

tasks:
  prep:
    desc: Prepare environment
    cmds:
      - task: prep-onboarder-container
      
  deploy-mcm:
    desc: Deploy Management Cluster
    cmds:
      - task: infrastructure_cluster_prep
```

### Variables Section
```yaml
vars:
  ENV: afcgi/skcp_bottom              # Environment identifier
  DATA_DIR: /docker-workspace/data     # Path to data directory
  DEPLOYMENT_TYPE: basekit             # Deployment type (basekit, etc.)
  DEPLOYMENT_VERSION: 1.0.1            # Version of deployment taskfiles
```

### Includes Section
```yaml
includes:
  # Include basekit deployment tasks
  deployment:
    taskfile: ../../data/{{.DEPLOYMENT_TYPE}}/{{.DEPLOYMENT_VERSION}}/main.yml
    vars:
      ENV: '{{.ENV}}'
      DATA_DIR: '{{.DATA_DIR}}'
  
  # Include node preparation tasks
  node-prep:
    taskfile: ../../data/node_prep/1.0.1/main.yml
    vars:
      DATA_DIR: '{{.DATA_DIR}}'
  
  # Include cluster deployment tasks
  cluster_deployment:
    taskfile: ../../data/cluster_deployment/1.0.1/main.yml
    vars:
      DATA_DIR: '{{.DATA_DIR}}'
```

### Tasks Section
```yaml
tasks:
  # High-level task that calls multiple subtasks
  deploy-mcm:
    desc: Deploy Management Cluster (MCM)
    cmds:
      - task: infrastructure_cluster_prep
      - task: infrastructure_node_prep
      - task: run-onboarder
  
  # Task that calls included taskfile
  infrastructure_cluster_prep:
    desc: Prepare infrastructure cluster
    cmds:
      - task: copy-ssh-key
        vars:
          HOSTS: infrastructure_cluster
      - task: deployment:deploy-all
        vars:
          HOSTS: infrastructure_cluster
  
  # Task that calls run_task.py directly
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

## Ansible Inventory (`config.yml`)

Defines your infrastructure hierarchy and connection details.

### Basic Structure
```yaml
all:
  children:
    <group_name>:
      hosts:
        <host_name>:
          ansible_host: IP_ADDRESS
          ansible_user: USERNAME
          ansible_ssh_private_key_file: PATH_TO_KEY
```

### Complete Example
```yaml
all:
  children:
    # Management cluster hosts
    infrastructure_cluster:
      hosts:
        mcm1:
          ansible_host: 192.168.1.10
          ansible_user: rancher
          ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key
        mcm2:
          ansible_host: 192.168.1.11
          ansible_user: rancher
          ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key
    
    # Downstream cluster hosts
    downstream_clusters:
      hosts:
        osms1:
          ansible_host: 192.168.2.20
          ansible_user: rancher
          ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key
        osms2:
          ansible_host: 192.168.2.21
          ansible_user: rancher
          ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key
        osdc1:
          ansible_host: 192.168.2.30
          ansible_user: rancher
          ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key
```

### Connection Variables

#### SSH Authentication
```yaml
# Key-based (recommended)
ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key

# Password-based (not recommended for production)
ansible_password: "YourPassword"

# Both (key tried first, then password)
ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key
ansible_password: "FallbackPassword"
```

#### SSH Options
```yaml
# Disable host key checking (for initial setup)
ansible_ssh_common_args: '-o StrictHostKeyChecking=no'

# Use bastion/jump host
ansible_ssh_common_args: '-o ProxyCommand="ssh -W %h:%p -q bastion.example.com"'

# Custom port
ansible_port: 2222
```

#### Connection Behavior
```yaml
# Become (sudo) settings
ansible_become: true
ansible_become_method: sudo
ansible_become_user: root
ansible_become_password: "SudoPassword"

# Connection timeouts
ansible_connection_timeout: 30
ansible_command_timeout: 300
```

## Ansible Variables (`group_vars/all.yml`)

Define variables used by Ansible playbooks.

### Common Variables
```yaml
# Network configuration
cluster_domain: "example.com"
dns_servers:
  - "8.8.8.8"
  - "8.8.4.4"

# Kubernetes settings
rke2_version: "v1.28.0+rke2r1"
rke2_channel: "stable"

# Rancher settings
rancher_version: "2.8.0"
rancher_hostname: "rancher.example.com"

# Cluster names
mcm_cluster_name: "management-cluster"
osms_cluster_name: "osms-production"
osdc_cluster_name: "osdc-production"
```

### Storage Configuration
```yaml
# Storage paths
nfs_server: "192.168.1.100"
nfs_path: "/export/kubernetes"

# Volume sizes
postgres_volume_size: "50Gi"
prometheus_volume_size: "100Gi"
```

### Network Configuration
```yaml
# Pod and service networks
pod_cidr: "10.42.0.0/16"
service_cidr: "10.43.0.0/16"
cluster_dns: "10.43.0.10"

# Load balancer IPs
metallb_ip_range: "192.168.1.200-192.168.1.250"
```

## Variable Passing

### Taskfile Variables
Variables flow through task hierarchies:

```yaml
# Parent task defines variables
parent-task:
  vars:
    HOSTS: infrastructure_cluster
    DATA_DIR: /docker-workspace/data
  cmds:
    - task: child-task
      vars:
        HOSTS: '{{.HOSTS}}'        # Explicit pass-through
        DATA_DIR: '{{.DATA_DIR}}'
```

### Required Variables
Declare variable requirements:

```yaml
deploy-cluster:
  desc: Deploy Kubernetes cluster
  requires:
    vars: [HOSTS, CLUSTER_NAME, DATA_DIR]
  cmds:
    - echo "Deploying {{.CLUSTER_NAME}} to {{.HOSTS}}"
```

### Variable Precedence
1. Task-level vars (highest)
2. Include-level vars
3. Global vars (in Taskfile.yml)
4. Environment variables (lowest)

## SSH Key Management

### Key Location
```bash
environments/<env>/.ssh/
├── rancher_ssh_key       # Private key (chmod 600)
└── rancher_ssh_key.pub   # Public key (chmod 644)
```

### Generating Keys
```bash
# Generate SSH key pair
ssh-keygen -t rsa -b 4096 -f .ssh/rancher_ssh_key -N ""

# Set proper permissions
chmod 700 .ssh
chmod 600 .ssh/rancher_ssh_key
chmod 644 .ssh/rancher_ssh_key.pub
```

### Distributing Keys
```bash
# Copy to target hosts
ssh-copy-id -i .ssh/rancher_ssh_key.pub rancher@target-host

# Or manually
cat .ssh/rancher_ssh_key.pub | ssh rancher@target-host "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### Using Keys in Ansible
```yaml
# In config.yml
hosts:
  mcm1:
    ansible_ssh_private_key_file: /docker-workspace/config/install/.ssh/rancher_ssh_key
```

### Key Path in Container
Keys are mounted into container:
```
Host: environments/<env>/.ssh/rancher_ssh_key
  ↓
Container: /docker-workspace/config/<env>/.ssh/rancher_ssh_key
  ↓
Symlink: /docker-workspace/install/.ssh/rancher_ssh_key
```

## State and Logging

### State File Location
```
environments/<env>/.cache/state.json
```

### State File Format
```json
{
  "completed_tasks": {
    "copy-ssh-key": {
      "completed_at": "2025-11-21T10:30:00Z",
      "duration_seconds": 5.2,
      "status": "success",
      "hosts": "infrastructure_cluster"
    }
  },
  "last_updated": "2025-11-21T10:30:00Z"
}
```

### Log Directory
```
environments/<env>/.cache/logs/
├── task_copy-ssh-key.log
├── task_bootstrap-mgmt.log
└── task_deploy-cluster.log
```

### Viewing Logs
```bash
# List logs
ls -lh .cache/logs/

# Tail specific log
tail -f .cache/logs/task_copy-ssh-key.log

# View state
cat .cache/state.json
```

## Configuration Validation

### Taskfile Syntax Check
```bash
# Validate Taskfile syntax
task --dry <task-name>

# List available tasks
task --list
```

### Ansible Inventory Check
```bash
# View parsed inventory
ansible-inventory -i config.yml --list

# Check specific host
ansible-inventory -i config.yml --host=mcm1
```

### Ansible Connectivity Test
```bash
# Test connection to all hosts
ansible -i config.yml -m ping all

# Test specific group
ansible -i config.yml -m ping infrastructure_cluster
```

## Security Best Practices

### SSH Keys
- Generate unique keys per environment
- Never commit private keys to version control
- Use chmod 600 for private keys
- Rotate keys periodically

### Passwords
- Avoid plaintext passwords in config files
- Use ansible-vault for sensitive data
- Consider external secret management

### File Permissions
```bash
# Proper permissions
chmod 700 .ssh/
chmod 600 .ssh/*_key
chmod 644 .ssh/*_key.pub
chmod 600 config.yml  # If it contains passwords
```

### Version Control
```gitignore
# Add to .gitignore
.ssh/
*.key
*.pem
.cache/
group_vars/vault.yml
```

## Troubleshooting Configuration

### Task Not Found
```
Error: task: Task "xyz" not found
```
Check:
- Task is defined in Taskfile.yml
- Included taskfiles are correct
- Task name spelling

### Variable Not Defined
```
Error: required variable HOSTS is not set
```
Check:
- Variable defined in vars section
- Variable passed to subtask explicitly
- Spelling of variable name

### SSH Connection Failed
```
FAILED! => {"msg": "Failed to connect to the host via ssh"}
```
Check:
- ansible_host IP is correct
- SSH key path is correct
- Key has proper permissions (chmod 600)
- Target host is reachable

### Inventory Not Found
```
ERROR! Unable to retrieve file contents
```
Check:
- config.yml exists in environment directory
- Symlink /docker-workspace/install points to correct location
- File permissions allow reading
