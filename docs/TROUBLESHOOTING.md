# Troubleshooting Guide

## General Debugging Approach

### 1. Check Validation First
```bash
python3 onboarder-run.py --env=<env> --validate-only
```

### 2. Run with Verbose Output
```bash
python3 onboarder-run.py --env=<env> --verbose
```

### 3. Review Logs
```bash
# Main orchestrator log
tail -f usr_home/<env>/logs/main_orchestrator.log

# Specific step log
cat usr_home/<env>/logs/step_3_deploy_vms.log
```

### 4. Check State File
```bash
cat usr_home/<env>/.installer_state
```

## Common Issues

### Configuration Issues

#### Profile Not Found
```
Error: Profile 'basekit/custom' not found at data/profiles/basekit/custom.yml
```

**Causes:**
- Typo in `profile_name` in group_vars/basekit.yml
- Profile file doesn't exist
- Wrong directory structure

**Solution:**
```bash
# Check what profiles exist
ls -la data/profiles/basekit/

# Verify profile_name setting
cat usr_home/<env>/group_vars/basekit.yml | grep profile_name

# Create missing profile or fix typo
vim usr_home/<env>/group_vars/basekit.yml
```

#### Invalid YAML Syntax
```
Error: Invalid YAML in config.yml: mapping values are not allowed here
```

**Causes:**
- Incorrect indentation
- Missing colons or quotes
- Invalid characters

**Solution:**
```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('usr_home/<env>/config.yml'))"

# Use a YAML linter
yamllint usr_home/<env>/config.yml
```

#### Missing Required Variables
```
Error: Variable 'cluster_domain' is not defined
```

**Causes:**
- Variable referenced in playbook but not defined
- Typo in variable name
- Variable in wrong file

**Solution:**
```bash
# Search for variable definitions
grep -r "cluster_domain" usr_home/<env>/group_vars/

# Add missing variable
vim usr_home/<env>/group_vars/basekit.yml
```

#### Variable Substitution Not Working
```
Error: File not found: tasks/{profile_kind}/task.yml
```

**Causes:**
- Wrong substitution syntax ({{ }} instead of { })
- Variable not available at substitution time
- Misspelled variable name

**Solution:**
```yaml
# Correct syntax for profile substitutions
file: "tasks/{profile_kind}/task.yml"  # ✅ Correct

# Wrong syntax
file: "tasks/{{ profile_kind }}/task.yml"  # ❌ Wrong
```

### Container Issues

#### Container Build Fails
```
Error: Failed to build container image
```

**Causes:**
- Docker/Podman not running
- Network issues downloading base image
- Insufficient disk space

**Solution:**
```bash
# Check Docker/Podman status
sudo systemctl status docker
# or
sudo systemctl status podman

# Try building manually
cd data
docker build -t onboarder:1.0.0 .

# Check disk space
df -h
```

#### Container Start Fails
```
Error: Cannot start container: permission denied
```

**Causes:**
- SELinux blocking access
- Wrong permissions on mounted directories
- User doesn't have Docker/Podman permissions

**Solution:**
```bash
# Check SELinux (if enabled)
getenforce
# Temporarily set to permissive for testing
sudo setenforce 0

# Fix directory permissions
chmod 755 usr_home/<env>
chmod 700 usr_home/<env>/.ssh
chmod 600 usr_home/<env>/.ssh/id_rsa

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

#### Volume Mount Fails
```
Error: Cannot mount volume: no such file or directory
```

**Causes:**
- Directory doesn't exist
- Wrong path in mount command
- Relative vs absolute path issues

**Solution:**
```bash
# Use absolute paths
pwd  # Get current directory
# Adjust paths in onboarder-run.py

# Ensure directories exist
mkdir -p usr_home/<env>/logs
```

### SSH Connection Issues

#### SSH Key Not Found
```
Error: file not found: /usr_home/<env>/.ssh/id_rsa
```

**Causes:**
- SSH key not generated
- Key file in wrong location
- Wrong path in inventory

**Solution:**
```bash
# Generate SSH key
ssh-keygen -t rsa -b 4096 -f usr_home/<env>/.ssh/id_rsa -N ""

# Verify key exists
ls -la usr_home/<env>/.ssh/

# Check permissions
chmod 600 usr_home/<env>/.ssh/id_rsa
```

#### SSH Permission Denied
```
FAILED! => {"msg": "Failed to connect to the host via ssh: Permission denied (publickey,password)."}
```

**Causes:**
- Public key not on target host
- Wrong password
- SSH key passphrase not provided
- User doesn't have access

**Solution:**
```bash
# Copy public key to target
ssh-copy-id -i usr_home/<env>/.ssh/id_rsa.pub root@target-host

# Test SSH manually
ssh -i usr_home/<env>/.ssh/id_rsa root@target-host

# If using password, check ansible_password in config.yml
```

#### SSH Host Key Verification Failed
```
FAILED! => {"msg": "Failed to connect: Host key verification failed"}
```

**Causes:**
- Host key not in known_hosts
- Host key changed (security warning!)
- StrictHostKeyChecking enabled

**Solution:**
```bash
# Option 1: Add to known_hosts
ssh-keyscan -H target-host >> ~/.ssh/known_hosts

# Option 2: Disable strict checking (not recommended for production)
# In config.yml:
ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
```

#### SSH Connection Timeout
```
FAILED! => {"msg": "Failed to connect: Connection timed out"}
```

**Causes:**
- Host unreachable
- Firewall blocking SSH
- Wrong IP address
- Network issues

**Solution:**
```bash
# Check connectivity
ping target-host

# Check port
nc -zv target-host 22

# Test SSH
ssh -vvv -i usr_home/<env>/.ssh/id_rsa root@target-host

# Check firewall
# On target:
sudo firewall-cmd --list-all
```

### Ansible Execution Issues

#### Ansible Playbook Syntax Error
```
ERROR! Syntax Error while loading YAML.
```

**Causes:**
- Invalid YAML in playbook
- Incorrect indentation
- Missing quotes around special characters

**Solution:**
```bash
# Validate playbook syntax
ansible-playbook --syntax-check data/tasks/basekit/task.yml

# Check YAML
python3 -c "import yaml; yaml.safe_load(open('data/tasks/basekit/task.yml'))"
```

#### Module Not Found
```
FAILED! => {"msg": "The module community.general.xyz was not found"}
```

**Causes:**
- Ansible collection not installed in container
- Typo in module name
- Wrong Ansible version

**Solution:**
```bash
# Install collection in container
# Add to data/requirements.yml:
collections:
  - name: community.general
    version: ">=5.0.0"

# Rebuild container to include collection
```

#### Become (sudo) Fails
```
FAILED! => {"msg": "Missing sudo password"}
```

**Causes:**
- ansible_become_password not set
- User doesn't have sudo access
- sudo requires password but none provided

**Solution:**
```yaml
# In config.yml or group_vars:
ansible_become: true
ansible_become_method: sudo
ansible_become_password: "SudoPassword"

# Or use passwordless sudo on target
# On target: sudo visudo
# Add: username ALL=(ALL) NOPASSWD: ALL
```

#### Variable Not Defined in Ansible
```
FAILED! => {"msg": "The task includes an option with an undefined variable. The error was: 'cluster_domain' is undefined"}
```

**Causes:**
- Variable not in group_vars/host_vars
- Variable in wrong scope
- Typo in variable name

**Solution:**
```bash
# Check variable is defined
ansible-inventory -i usr_home/<env>/config.yml --list | grep cluster_domain

# Add to appropriate group_vars file
echo "cluster_domain: example.com" >> usr_home/<env>/group_vars/basekit.yml
```

### Execution Issues

#### Step Timeout
```
Error: Step 'deploy_vms' exceeded timeout of 600 seconds
```

**Causes:**
- Operation taking longer than expected
- Timeout too short for operation
- Step hung on user input
- Infrastructure performance issues

**Solution:**
```yaml
# Increase timeout in profile
# data/profiles/basekit/default.yml
steps:
  - id: deploy_vms
    timeout: 1800  # Increase to 30 minutes
```

#### Step Fails Repeatedly
```
Error: Step 'install_k8s' failed with exit code 2
```

**Causes:**
- Underlying infrastructure issue
- Missing prerequisite
- Non-idempotent operation failing on re-run
- Resource constraints (disk, memory)

**Solution:**
```bash
# Check detailed logs
cat usr_home/<env>/logs/step_X_install_k8s.log

# SSH to target and check
ssh -i usr_home/<env>/.ssh/id_rsa root@target
# Check disk: df -h
# Check memory: free -m
# Check processes: ps aux
# Check logs: journalctl -xe

# Fix underlying issue, then resume
python3 onboarder-run.py --env=<env>
```

#### State File Corrupted
```
Error: Cannot parse state file: Invalid JSON
```

**Causes:**
- Installer killed mid-write
- Manual editing of state file
- Filesystem issues

**Solution:**
```bash
# Backup corrupted state
cp usr_home/<env>/.installer_state usr_home/<env>/.installer_state.bak

# Remove state to start fresh
rm usr_home/<env>/.installer_state

# Or manually fix JSON
vim usr_home/<env>/.installer_state
```

### Resource Issues

#### Disk Space Exhausted
```
Error: No space left on device
```

**Causes:**
- Large logs
- Container images using space
- VM disk images filling partition

**Solution:**
```bash
# Check disk usage
df -h

# Clean up Docker/Podman
docker system prune -a

# Clean old logs
find usr_home/*/logs -mtime +30 -delete

# Move images to larger partition
```

#### Out of Memory
```
Error: Cannot allocate memory
```

**Causes:**
- Too many concurrent operations
- VMs using too much memory
- Memory leak

**Solution:**
```bash
# Check memory usage
free -m

# Adjust VM memory allocations
# In config.yml, reduce vm_memory values

# Add swap if needed
sudo dd if=/dev/zero of=/swapfile bs=1G count=8
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Debugging Techniques

#### Enable Ansible Verbose Mode
```yaml
# In data/ansible.cfg (temporarily):
[defaults]
verbosity = 2
```

#### Enable SSH Debug
```yaml
# In config.yml:
ansible_ssh_common_args: '-vvv'
```

#### Test Ansible Connectivity
```bash
# From within container or with ansible-playbook:
ansible -i usr_home/<env>/config.yml -m ping all
```

#### Manual Step Execution
```bash
# Run Ansible playbook manually
ansible-playbook -i usr_home/<env>/config.yml data/tasks/basekit/task.yml -vvv

# Run Python script manually
python3 data/tasks/basekit/script.py

# Run shell script manually
bash data/tasks/common/script.sh
```

#### Check Ansible Facts
```bash
ansible -i usr_home/<env>/config.yml -m setup target_host
```

### Getting Help

#### Information to Collect
When asking for help, provide:
1. Full error message
2. Command that failed
3. Relevant logs (`usr_home/<env>/logs/`)
4. State file (`usr_home/<env>/.installer_state`)
5. Configuration (sanitize secrets!)
6. Profile being used
7. Environment (OS, Python version, Docker/Podman version)

#### Log Sanitization
```bash
# Remove passwords before sharing
sed 's/ansible_password:.*/ansible_password: REDACTED/' config.yml > config_sanitized.yml
```

## Quick Reference

### Reset Everything
```bash
# Start completely fresh
python3 onboarder-run.py --env=<env> --reset-state
```

### Check Configuration
```bash
# Validate without executing
python3 onboarder-run.py --env=<env> --validate-only
```

### View Inventory
```bash
# See parsed inventory
ansible-inventory -i usr_home/<env>/config.yml --list --yaml
```

### Test Single Host
```bash
# Test connectivity to one host
ansible -i usr_home/<env>/config.yml -m ping target_host
```

### Manual Resume
```bash
# Edit state file to resume from specific step
vim usr_home/<env>/.installer_state
# Remove steps after the one you want to resume from
```
