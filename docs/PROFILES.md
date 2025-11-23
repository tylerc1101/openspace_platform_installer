# Profile System

## Overview

Profiles define deployment workflows as a series of steps. Each profile is a YAML file that specifies:
- What tasks to run
- In what order
- With what timeouts
- Using which execution method (ansible, python, shell)

## Profile Structure

```
data/profiles/
├── basekit/
│   ├── default.yml
│   └── custom.yml
├── baremetal/
│   └── default.yml
└── aws/
    └── default.yml
```

## Profile File Format

### Basic Structure
```yaml
metadata:
  name: "Profile Display Name"
  version: "1.0.0"
  description: "What this profile does"
  profile_kind: basekit             # Must match directory name

steps:
  - id: step_identifier              # Unique ID for this step
    description: "Human-readable description"
    kind: ansible                    # ansible | python | shell
    file: "tasks/basekit/task.yml"   # Path relative to data/
    timeout: 600                     # Seconds (optional, default: 300)
    
  - id: another_step
    description: "Another step"
    kind: python
    file: "tasks/basekit/script.py"
    timeout: 1800
```

### Complete Example
```yaml
# data/profiles/basekit/default.yml

metadata:
  name: "Base Kit Default Deployment"
  version: "1.0.0"
  description: "Complete infrastructure deployment for base kit configuration"
  profile_kind: basekit
  author: "Infrastructure Team"
  last_updated: "2024-01-15"

steps:
  # Step 1: Initial setup
  - id: copy_ssh_keys
    description: "Copy SSH keys to target hosts"
    kind: ansible
    file: "tasks/common/copy_ssh_key.yml"
    timeout: 300
    
  # Step 2: Management server
  - id: bootstrap_mgmt
    description: "Bootstrap management server with KVM/libvirt"
    kind: ansible
    file: "tasks/basekit/bootstrap-mgmt-kvm.yml"
    timeout: 600
    
  # Step 3: Network infrastructure
  - id: deploy_opnsense
    description: "Deploy and configure OPNsense firewall"
    kind: python
    file: "tasks/basekit/deploy-opnsense.py"
    timeout: 900
    
  # Step 4: Virtual machines
  - id: deploy_vms
    description: "Deploy virtual machines for OpenSpace components"
    kind: ansible
    file: "tasks/basekit/deploy-vms.yml"
    timeout: 1200
    
  # Step 5: Kubernetes
  - id: install_kubernetes
    description: "Install and configure Kubernetes cluster"
    kind: ansible
    file: "tasks/basekit/install-k8s.yml"
    timeout: 1800
    
  # Step 6: Application deployment
  - id: deploy_apps
    description: "Deploy OpenSpace applications"
    kind: ansible
    file: "tasks/basekit/deploy-apps.yml"
    timeout: 1200
```

## Step Types

### Ansible Steps (`kind: ansible`)
```yaml
- id: configure_network
  description: "Configure network interfaces"
  kind: ansible
  file: "tasks/common/configure-network.yml"
  timeout: 300
```

**Requirements:**
- File must be a valid Ansible playbook
- Playbook has access to all inventory and variables
- Uses containerized Ansible execution

**Best for:**
- Configuration management
- Multi-host orchestration
- Idempotent operations

### Python Steps (`kind: python`)
```yaml
- id: custom_logic
  description: "Run custom deployment logic"
  kind: python
  file: "tasks/basekit/custom-script.py"
  timeout: 600
```

**Requirements:**
- File must be executable Python script
- Script has access to environment variables
- Can import standard Python libraries

**Best for:**
- Complex logic
- API interactions
- Data processing

### Shell Steps (`kind: shell`)
```yaml
- id: system_check
  description: "Verify system requirements"
  kind: shell
  file: "tasks/common/system-check.sh"
  timeout: 120
```

**Requirements:**
- File must be executable shell script
- Uses bash shell by default
- Has access to environment variables

**Best for:**
- Simple commands
- System operations
- Quick checks

## Variable Substitution in Profiles

### Basic Substitution
```yaml
steps:
  - id: deploy_app
    description: "Deploy {app_name} version {app_version}"
    kind: ansible
    file: "tasks/{profile_kind}/deploy-app.yml"
```

Available substitutions:
- `{env}` - Environment name (from --env flag)
- `{profile}` - Full profile path (e.g., "basekit/default")
- `{profile_kind}` - Profile type (e.g., "basekit")
- `{profile_name}` - Profile name (e.g., "default")
- Any variable from group_vars/

### Conditional Steps (Advanced)
```yaml
steps:
  - id: optional_step
    description: "Optional configuration"
    kind: ansible
    file: "tasks/common/optional.yml"
    when: "{{ enable_optional_features | default(false) }}"
```

## Creating a Custom Profile

### Step 1: Create Profile File
```bash
# Create new profile
cat > data/profiles/basekit/production.yml << 'EOF'
metadata:
  name: "Production Deployment"
  version: "1.0.0"
  description: "Hardened production deployment with monitoring"
  profile_kind: basekit

steps:
  - id: security_baseline
    description: "Apply security baseline"
    kind: ansible
    file: "tasks/basekit/security-baseline.yml"
    timeout: 600
    
  - id: deploy_core
    description: "Deploy core infrastructure"
    kind: ansible
    file: "tasks/basekit/deploy-core.yml"
    timeout: 1200
    
  - id: configure_monitoring
    description: "Set up monitoring stack"
    kind: ansible
    file: "tasks/basekit/monitoring.yml"
    timeout: 900
EOF
```

### Step 2: Create Required Task Files
```bash
# Create tasks referenced in profile
touch data/tasks/basekit/security-baseline.yml
touch data/tasks/basekit/deploy-core.yml
touch data/tasks/basekit/monitoring.yml
```

### Step 3: Configure Environment to Use Profile
```yaml
# usr_home/my_prod_env/group_vars/basekit.yml
profile_kind: "basekit"
profile_name: "production"  # ← Use your custom profile
```

### Step 4: Test and Deploy
```bash
# Validate configuration
python3 onboarder-run.py --env=my_prod_env --validate-only

# Run deployment
python3 onboarder-run.py --env=my_prod_env
```

## Profile Best Practices

### 1. Logical Grouping
Group related steps together:
```yaml
# Good: Logical flow
steps:
  - id: prep_infrastructure
  - id: deploy_storage
  - id: configure_network
  - id: deploy_compute
  - id: validate_deployment

# Avoid: Random order
steps:
  - id: deploy_compute
  - id: prep_infrastructure
  - id: validate_deployment
  - id: configure_network
```

### 2. Reasonable Timeouts
Set timeouts based on expected duration plus buffer:
```yaml
# Quick tasks: 5 minutes
- id: copy_files
  timeout: 300

# Medium tasks: 10-20 minutes
- id: install_packages
  timeout: 1200

# Long tasks: 30+ minutes
- id: deploy_cluster
  timeout: 1800
```

### 3. Clear Descriptions
Use actionable, specific descriptions:
```yaml
# Good
- id: install_k8s
  description: "Install Kubernetes v1.28 on cluster nodes"

# Avoid
- id: install_k8s
  description: "Do Kubernetes stuff"
```

### 4. Idempotent Steps
Design steps to be safely re-runnable:
```yaml
# Ansible playbooks should use:
# - Check if resource exists before creating
# - Use state: present vs state: absent
# - Leverage Ansible's idempotency features
```

### 5. Error Handling
```yaml
# In your playbooks/scripts:
# - Check prerequisites before running
# - Provide clear error messages
# - Leave system in recoverable state on failure
```

## Profile Selection

### At Environment Level
Most common: Set in `group_vars/basekit.yml`:
```yaml
profile_kind: "basekit"
profile_name: "default"
```

### Override for Testing
```bash
# Temporarily use different profile (if supported)
python3 onboarder-run.py --env=test --profile=basekit/experimental
```

## State Management

The installer tracks which steps have completed:
```
usr_home/my_env/.installer_state
```

State file example:
```json
{
  "profile": "basekit/default",
  "completed_steps": [
    "copy_ssh_keys",
    "bootstrap_mgmt",
    "deploy_opnsense"
  ],
  "last_run": "2024-01-15T10:30:00",
  "status": "in_progress"
}
```

### Resume Behavior
When resuming:
1. Loads state file
2. Skips completed steps
3. Starts from first incomplete step
4. Updates state after each successful step

### Reset State
```bash
# Start fresh (re-run all steps)
python3 onboarder-run.py --env=my_env --reset-state
```

## Advanced Profile Features

### Multi-Profile Deployments
For complex scenarios requiring multiple profile types:
```yaml
# Environment with multiple profiles
all:
  children:
    basekit:
      # ... basekit hosts
    aws:
      # ... aws hosts
```

### Profile Inheritance (Future Feature)
```yaml
# Concept: Extend base profile
metadata:
  extends: "basekit/default"

steps:
  # Additional steps beyond base profile
  - id: custom_step
```

### Conditional Execution (Future Feature)
```yaml
steps:
  - id: optional_step
    when: "{{ deploy_monitoring | default(false) }}"
```

## Troubleshooting Profiles

### Profile Not Found
```
Error: Profile 'basekit/custom' not found
```
Check:
1. File exists: `data/profiles/basekit/custom.yml`
2. Correct `profile_name` in `group_vars/basekit.yml`
3. YAML syntax is valid

### Step Fails
```
Error: Step 'deploy_vms' failed with exit code 2
```
Check:
1. Log file: `usr_home/my_env/logs/step_3_deploy_vms.log`
2. Task file exists and is valid
3. Required variables are defined
4. Timeout is sufficient

### Variables Not Substituting
```
Error: File not found: tasks/{profile_kind}/task.yml
```
Check:
1. Variable is defined in group_vars
2. Correct syntax: `{var_name}` not `{{ var_name }}`
3. Use `--verbose` to see actual values
