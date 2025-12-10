# Getting Started

This guide walks you through your first deployment with the OpenSpace Platform Installer.

## Prerequisites

Before you begin, ensure you have:
- Docker or Podman installed
- Python 3.9+ installed
- Network access to target infrastructure
- See [Requirements](REQUIREMENTS.md) for full details

## Quick Start Overview

1. Create a deployment.yml configuration file
2. Launch the onboarder container
3. Run the deployment tasks
4. Retrieve kubeconfigs

## Step 1: Create Your Deployment Configuration

### Copy the Sample Configuration

```bash
# Create environment directory
mkdir -p environments/myenv

# Copy sample deployment configuration
cp test.deployment.yml environments/myenv/myenv.deployment.yml
```

### Edit Your deployment.yml

```bash
vim environments/myenv/myenv.deployment.yml
```

The deployment.yml file has several key sections. Here's a minimal example:

```yaml
deployment:
  name: "my-deployment"
  type: "basekit"  # or "baremetal"
  onboarder_version: "3.5.0-rc7"
  osms_tooling_version: "1.8.x"

ssh:
  user: "rancher"
  pass: "your-password"
  become: "rancher"

networks:
  customer:
    gateway: "10.10.10.1"
    cidr: "/24"
    dns_servers:
      - "8.8.8.8"
  management:
    network: "192.168.1"
    cidr: "/24"

# For basekit deployments
infrastructure:
  mgmt_kvm:
    wan_ip: "10.10.10.10"
    mgmt_ip: "192.168.1.1"
  opnsense:
    wan_ip: "10.10.10.1"
    mgmt_ip: "192.168.1.254"

# MCM cluster nodes
management_cluster:
  clusters:
    - cluster_name: "local"
      ssh_key: "mcm_ssh_key"
      nodes:
        - name: "mcm1"
          mgmt_ip: "192.168.1.10"
          roles: ["controlplane", "etcd", "worker"]

# OSMS cluster nodes
openspace_management_system:
  clusters:
    - cluster_name: "osms"
      ssh_key: "osms_ssh_key"
      nodes:
        - name: "osms1"
          mgmt_ip: "192.168.1.20"
          roles: ["controlplane", "etcd", "worker"]

# For basekit: VM specifications
virtual_machines:
  mcm:
    memory: 16384
    vcpus: 8
    disk_size: 100
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"
  osms:
    memory: 16384
    vcpus: 8
    disk_size: 100
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"
```

See [Configuration Guide](CONFIGURATION.md) for complete documentation of all deployment.yml options.

## Step 2: Launch the Onboarder Container

### Start the Container

```bash
python3 onboarder-run.py
```

The script will:
1. Detect your container runtime (Podman or Docker)
2. Show a menu of available environments (finds all *.deployment.yml files)
3. Load or build the onboarder container image
4. Mount necessary volumes
5. Start an interactive shell inside the container

### What Happens on First Run

If this is the first time running your environment, the container will automatically:
1. Create the install directory structure
2. Copy your deployment.yml into the container
3. Generate all configuration files from deployment.yml:
   - `inventory.yml` - Ansible inventory
   - `Taskfile.yml` - Task orchestration workflow
   - `group_vars/all.yml` - Ansible variables
   - `.ssh/` - SSH key pairs
4. Run prep_onboarder_container.yml playbook
5. Mark environment as initialized

This is all done by the `scripts/first-run.sh` script.

### Inside the Container

You'll see a prompt like:
```
[onboarder@container install]$
```

You're now in `/docker-workspace/install`, which is linked to your environment directory.

## Step 3: Verify Generated Configuration

Before deploying, take a moment to verify the generated configuration:

### Check Generated Inventory

```bash
cat inventory.yml
```

You should see all your hosts organized into groups like:
- `infrastructure_cluster` (MCM nodes)
- `osms` (OSMS nodes)
- `osdc` (OSDC nodes, if configured)

### Check Generated Taskfile

```bash
cat Taskfile.yml
```

This file defines the deployment workflow tasks.

### Check Generated SSH Keys

```bash
ls -la .ssh/
```

You should see SSH key pairs that were automatically generated.

## Step 4: Run the Deployment

### List Available Tasks

```bash
task --list
```

You'll see tasks like:
- `prep` - Prepare environment
- `deploy-mcm` - Deploy management cluster
- `deploy-prod-osms` - Deploy OSMS cluster
- `deploy-prod-osdc` - Deploy OSDC cluster

### Full Deployment Workflow

For a complete basekit deployment from scratch:

```bash
# Step 1: Prepare environment
task prep

# Step 2: Deploy MCM (includes VM creation for basekit)
task deploy-mcm

# Step 3: Deploy OSMS
task deploy-prod-osms

# Step 4: Deploy OSDC (if configured)
task deploy-prod-osdc
```

### For Baremetal Deployments

The workflow is the same, but VMs are not created:

```bash
task prep
task deploy-mcm
task deploy-prod-osms
task deploy-prod-osdc
```

## Step 5: Monitor Progress

### Real-Time Output

Tasks stream output in real-time as they execute. You'll see Ansible playbook output directly:

```
TASK [Copy SSH Key] ************************************************************
ok: [mcm1]

PLAY RECAP *********************************************************************
mcm1                       : ok=5    changed=2    unreachable=0    failed=0
```

### Check Logs

Each task creates a log file:

```bash
# List logs
ls -lh .cache/logs/

# View specific task log
tail -f .cache/logs/task_copy-ssh-key.log

# View logs for currently running task
tail -f .cache/logs/task_*.log
```

### Check State

The state file tracks completed tasks:

```bash
cat .cache/state.json
```

Example state file:
```json
{
  "completed_tasks": {
    "copy-ssh-key-mcm": {
      "completed_at": "2025-12-10T10:30:00Z",
      "duration_seconds": 5.2,
      "status": "success"
    }
  }
}
```

## Step 6: Handle Interruptions

### Automatic Resume

If a task fails or is interrupted, just re-run the same command:

```bash
task deploy-mcm
```

The installer will:
- Load the state file
- Skip completed tasks
- Resume from where it left off

### Manual State Reset

To start fresh and re-run all tasks:

```bash
# Remove state file
rm .cache/state.json

# All tasks will run again
task deploy-mcm
```

## Step 7: Retrieve Kubeconfigs

After deployment completes, download the kubeconfig files:

```bash
# Get MCM kubeconfig
task get-kubeconfig-mcm

# Get OSMS kubeconfig
task get-kubeconfig-osms

# Get OSDC kubeconfig (if deployed)
task get-kubeconfig-osdc
```

Kubeconfigs are saved to your environment directory and can be used from your host:

```bash
# Exit container
exit

# On host, use kubeconfigs
export KUBECONFIG=environments/myenv/kubeconfig-mcm
kubectl get nodes
```

## Common First-Time Issues

### Issue: Container Fails to Start

```
Error: Cannot start container
```

**Possible causes:**
- Docker/Podman not running
- Insufficient permissions
- Port conflicts

**Solution:**
```bash
# Check Docker/Podman status
sudo systemctl status docker
# or
sudo systemctl status podman

# Start if needed
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

### Issue: Environment Not Found

```
No deployment.yml files found in environments/
```

**Solution:**
Make sure your deployment file is named correctly:
```bash
# Must end with .deployment.yml
ls environments/myenv/*.deployment.yml
```

### Issue: Task Not Found

```
task: Task "deploy-mcm" not found
```

**Possible causes:**
- Not in the correct directory
- Taskfile.yml not generated

**Solution:**
```bash
# Make sure you're in install directory
cd /docker-workspace/install
pwd  # Should show /docker-workspace/install

# Check if Taskfile.yml exists
ls -la Taskfile.yml

# If missing, regenerate configs
# First delete marker file
rm .first_run_complete
# Exit and restart container
```

### Issue: SSH Connection Fails

```
FAILED! => {"msg": "Failed to connect to the host via ssh: Permission denied"}
```

**Possible causes:**
- Wrong IP address in deployment.yml
- Wrong SSH credentials
- Target host not accessible

**Solution:**
```bash
# Test SSH manually from inside container
ssh -i .ssh/mcm_ssh_key rancher@192.168.1.10

# If that fails, check:
# 1. IP address is correct
# 2. Target host is reachable
# 3. SSH credentials are correct in deployment.yml
```

### Issue: Ansible Playbook Fails

```
FAILED! => {"msg": "Some error message"}
```

**Solution:**
1. Check the detailed error message in the log file
2. Check `.cache/logs/task_<id>.log` for full error
3. Fix the issue (often network, permissions, or configuration)
4. Re-run the task - it will resume from where it failed

## Next Steps

Once your deployment completes:

1. **Access Your Clusters**
   ```bash
   # Use kubeconfigs to access clusters
   kubectl --kubeconfig=kubeconfig-mcm get nodes
   ```

2. **Access Rancher**
   - Find Rancher URL in MCM cluster
   - Login with bootstrap credentials

3. **Deploy Applications**
   - Use ArgoCD for GitOps deployments
   - Use Rancher for cluster management

4. **Explore Tasks**
   ```bash
   task --list-all
   ```

5. **Customize Deployment**
   - Modify deployment.yml for your needs
   - Regenerate config and redeploy

## Tips for Success

### Use Version Control

```bash
# Track your deployment configuration
cd environments/myenv
git init
git add myenv.deployment.yml
git commit -m "Initial deployment configuration"

# DO NOT commit generated files or secrets
echo "inventory.yml" >> .gitignore
echo "Taskfile.yml" >> .gitignore
echo "group_vars/" >> .gitignore
echo ".ssh/" >> .gitignore
echo ".cache/" >> .gitignore
```

### Document Your Environment

Create a README in your environment directory:

```bash
cat > environments/myenv/README.md <<EOF
# My Environment

Deployment: my-deployment
Type: basekit
Onboarder Version: 3.5.0-rc7

## Networks
- Customer: 10.10.10.0/24
- Management: 192.168.1.0/24

## Clusters
- MCM: 192.168.1.10
- OSMS: 192.168.1.20
- OSDC: 192.168.1.30

## Deployment Commands
\`\`\`
python3 onboarder-run.py
task prep && task deploy-mcm && task deploy-prod-osms
\`\`\`
EOF
```

### Test in Stages

Don't run all tasks at once on first deployment. Run step by step:

```bash
# Run and verify each phase
task prep
# Verify prep succeeded

task deploy-mcm
# Verify MCM is healthy

task deploy-prod-osms
# Verify OSMS is healthy
```

### Keep Logs

Logs are valuable for troubleshooting:

```bash
# Archive logs after successful deployment
tar -czf logs-$(date +%Y%m%d).tar.gz .cache/logs/
```

## Getting Help

If you run into issues:

1. Check logs in `.cache/logs/`
2. Review [Troubleshooting Guide](TROUBLESHOOTING.md)
3. Check [Configuration Reference](CONFIGURATION.md)
4. Review [Architecture Documentation](ARCHITECTURE.md)

## What's Next?

- [Configuration Reference](CONFIGURATION.md) - Learn all deployment.yml options
- [Taskfiles Guide](TASKFILES.md) - Understand the task system
- [Architecture](ARCHITECTURE.md) - Deep dive into how it works
- [Troubleshooting](TROUBLESHOOTING.md) - Fix common issues
