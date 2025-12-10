# Troubleshooting Guide

Quick fixes for common issues.

## General Debugging Steps

### 1. Check Logs

```bash
# Inside container
cd /docker-workspace/install

# View most recent log
ls -t .cache/logs/ | head -1 | xargs -I {} tail -f .cache/logs/{}

# Or specific task
tail -f .cache/logs/task_<task-name>.log
```

### 2. Check What's Completed

```bash
# View state
cat .cache/state.json

# List completed tasks
jq '.completed_tasks | keys' .cache/state.json
```

### 3. Reset and Retry

```bash
# Start fresh
rm .cache/state.json
task deploy-mcm
```

## Common Issues

### Container Won't Start

**Error:** `Cannot start container` or `Permission denied`

**Fix:**
```bash
# Check Docker/Podman is running
sudo systemctl status docker
# or
sudo systemctl status podman

# Start if needed
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

### No Environments Found

**Error:** `No deployment.yml files found in environments/`

**Fix:**
```bash
# Ensure file ends with .deployment.yml
mv environments/myenv/config.yml environments/myenv/myenv.deployment.yml

# Check it exists
ls environments/myenv/*.deployment.yml
```

### SSH Connection Fails

**Error:** `Failed to connect to the host via ssh: Permission denied`

**Causes:**
- Wrong IP address
- Wrong username/password
- Host not reachable

**Fix:**
```bash
# Test SSH manually from inside container
ssh -i .ssh/mcm_ssh_key rancher@192.168.1.10

# If that fails:
# 1. Check IP is correct in deployment.yml
# 2. Check host is pingable: ping 192.168.1.10
# 3. Check username/password in deployment.yml
# 4. Try password auth: ssh rancher@192.168.1.10
```

**For baremetal:** Ensure all servers are accessible
```bash
# Test all servers
for ip in 192.168.1.{11..19}; do
  ssh -o ConnectTimeout=5 rancher@$ip hostname
done
```

### Task Not Found

**Error:** `task: Task "deploy-mcm" not found`

**Causes:**
- Not in correct directory
- Taskfile.yml not generated

**Fix:**
```bash
# Check you're in install directory
pwd  # Should be /docker-workspace/install

# Check Taskfile exists
ls -la Taskfile.yml

# If missing, regenerate
rm .first_run_complete
exit
python3 onboarder-run.py
```

### VM Creation Fails (Basekit)

**Error:** `Failed to create VM` or `backing store not found`

**Causes:**
- Base image doesn't exist on KVM host
- Wrong path in deployment.yml

**Fix:**
```bash
# SSH to KVM host and check
ssh rancher@<kvm-host-ip>
ls -lh /var/lib/libvirt/images/rocky9.qcow2

# If missing, download Rocky 9:
wget https://download.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2
mv Rocky-9-GenericCloud-Base.latest.x86_64.qcow2 /var/lib/libvirt/images/rocky9.qcow2

# Update deployment.yml with correct path
```

### Insufficient Resources

**Error:** `Cannot allocate memory` or VM creation fails

**Fix:**
```yaml
# Reduce VM resources in deployment.yml
virtual_machines:
  mcm:
    memory: 8192    # Reduced from 16384
    vcpus: 4        # Reduced from 8
```

### Ansible Playbook Fails

**Error:** Various Ansible errors

**Fix:**
```bash
# Check detailed log
tail -100 .cache/logs/task_<failed-task>.log

# Common issues:
# - Missing variables: Check deployment.yml
# - Permission denied: Check sudo access
# - Host unreachable: Check network/firewall
```

### Node Not Ready

**Error:** Kubernetes node shows NotReady

**Fix:**
```bash
# Check node status
kubectl --kubeconfig=kubeconfig-mcm get nodes

# Describe node for details
kubectl --kubeconfig=kubeconfig-mcm describe node <node-name>

# Common causes:
# - CNI not ready: Wait a few minutes
# - Disk pressure: Check disk space on node
# - Network issues: Check node can reach others
```

### RKE2 Install Fails

**Error:** RKE2 installation fails

**Fix:**
```bash
# SSH to the node
ssh -i .ssh/mcm_ssh_key rancher@<node-ip>

# Check RKE2 logs
sudo journalctl -u rke2-server -n 100

# Common issues:
# - Port 6443 blocked: Check firewall
# - SELinux blocking: Check audit log
# - Disk full: df -h
```

### Harbor Not Accessible

**Error:** Cannot access Harbor registry

**Fix:**
```bash
# Check Harbor pods
kubectl --kubeconfig=kubeconfig-mcm get pods -n harbor

# Check ingress
kubectl --kubeconfig=kubeconfig-mcm get ingress -n harbor

# Get Harbor URL
kubectl --kubeconfig=kubeconfig-mcm get ingress -n harbor \
  -o jsonpath='{.items[0].spec.rules[0].host}'
```

### Rancher Not Accessible

**Error:** Cannot access Rancher UI

**Fix:**
```bash
# Check Rancher pods
kubectl --kubeconfig=kubeconfig-mcm get pods -n cattle-system

# Get Rancher URL
kubectl --kubeconfig=kubeconfig-mcm get ingress -n cattle-system rancher \
  -o jsonpath='{.spec.rules[0].host}'

# Get bootstrap password
kubectl --kubeconfig=kubeconfig-mcm get secret -n cattle-system bootstrap-secret \
  -o jsonpath='{.data.bootstrapPassword}' | base64 -d
```

### Configuration Looks Wrong

**Error:** Generated inventory.yml or Taskfile.yml is incorrect

**Fix:**
```bash
# Edit deployment.yml
vim environments/myenv/myenv.deployment.yml

# Regenerate everything
rm .first_run_complete
exit
python3 onboarder-run.py

# Check generated files
cat inventory.yml
cat Taskfile.yml
```

### Deployment Stuck

**Error:** Task hangs or takes too long

**Fix:**
```bash
# Open another terminal, check container
docker ps
docker exec -it <container-id> bash

# Check what's running
ps aux

# Check logs
tail -f .cache/logs/task_*.log

# If truly stuck, kill and restart
# Ctrl+C in original terminal
# Re-run same command - it will resume
```

## Validation Commands

### Before Deployment

```bash
# Validate deployment.yml syntax
python3 -c "import yaml; yaml.safe_load(open('environments/myenv/myenv.deployment.yml'))"

# Check Docker/Podman
docker --version
podman --version

# Test SSH to all hosts (update IPs)
for ip in 192.168.1.10 192.168.1.11; do
  ssh -o ConnectTimeout=5 user@$ip hostname
done
```

### During Deployment

```bash
# Inside container

# Check generated inventory
ansible-inventory -i inventory.yml --list

# Test Ansible connectivity
ansible -i inventory.yml -m ping all

# Check state
cat .cache/state.json

# Monitor logs
tail -f .cache/logs/task_*.log
```

### After Deployment

```bash
# Check clusters
kubectl --kubeconfig=kubeconfig-mcm get nodes
kubectl --kubeconfig=kubeconfig-osms get nodes

# Check pods
kubectl --kubeconfig=kubeconfig-mcm get pods -A

# Check services
kubectl --kubeconfig=kubeconfig-mcm get svc -A
```

## Reset Procedures

### Reset State Only

```bash
# Inside container
rm .cache/state.json
# Re-run deployment - all tasks run again
```

### Reset All Generated Config

```bash
# Inside container
rm .first_run_complete
exit

# Restart container
python3 onboarder-run.py
# Regenerates everything
```

### Complete Clean Slate

```bash
# Remove entire environment
rm -rf environments/myenv

# Start over
mkdir -p environments/myenv
cp docs/examples/basekit.deployment.yml environments/myenv/myenv.deployment.yml
vim environments/myenv/myenv.deployment.yml
python3 onboarder-run.py
```

## Getting Help

When asking for help, provide:

1. **What you're trying to do:**
   - Deployment type (basekit/baremetal)
   - Step that failed

2. **Error message:**
   ```bash
   tail -50 .cache/logs/task_<failed-task>.log
   ```

3. **Your environment:**
   - OS version: `cat /etc/os-release`
   - Container runtime: `docker --version` or `podman --version`
   - Python version: `python3 --version`

4. **State file:**
   ```bash
   cat .cache/state.json
   ```

5. **Deployment config (sanitize passwords!):**
   ```bash
   cat environments/myenv/myenv.deployment.yml | grep -v "pass:"
   ```

## Quick Reference

```bash
# View logs
tail -f .cache/logs/task_*.log

# Check state
cat .cache/state.json
jq '.completed_tasks | keys' .cache/state.json

# Reset state
rm .cache/state.json

# Regenerate config
rm .first_run_complete && exit

# Test SSH
ssh -i .ssh/mcm_ssh_key rancher@<host-ip>

# Test Ansible
ansible -i inventory.yml -m ping all

# Check kubeconfig
kubectl --kubeconfig=kubeconfig-mcm get nodes
```
