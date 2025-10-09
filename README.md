# OpenSpace Platform Installer

A configuration-driven infrastructure deployment system that orchestrates installation workflows using containerized execution.

## 📁 Directory Structure

```
openspace_platform_installer/
├── images/                      # Large binary files
│   ├── rpms/                   # RPMs to install in container (e.g., sshpass)
│   └── onboarder/              # Container images
├── data/                        # Installation logic (reusable)
│   ├── main.py                 # Main orchestrator
│   ├── ansible.cfg             # Ansible configuration (STIG-compatible)
│   ├── profiles/               # Profile definitions
│   │   ├── basekit/
│   │   │   └── default.yml
│   │   ├── baremetal/
│   │   └── aws/
│   ├── tasks/                  # Ansible playbooks & scripts
│   │   ├── common/
│   │   │   └── copy_ssh_key.yml
│   │   └── basekit/
│   │       ├── bootstrap-mgmt-kvm.yml
│   │       ├── deploy-vms.yml
│   │       └── deploy-opnsense.py
│   └── files/
│       └── kratos.repo
├── usr_home/                    # Environment configurations (customizable)
│   ├── <your_environment>/
│   │   ├── config.yml          # Ansible inventory
│   │   ├── group_vars/         # Variables per profile/group/host
│   │   │   ├── basekit.yml    # Profile config (profile_kind, profile_name, images)
│   │   │   ├── mgmt_svr.yml   # Group-specific vars (interfaces, etc.)
│   │   │   └── vms.yml
│   │   ├── .ssh/               # SSH keys
│   │   └── logs/               # Execution logs
│   └── sample_basekit/         # Template environments
└── onboarder-run.py            # Runner script
```

## 🚀 Quick Start

### 1. Create Your Environment

```bash
# Copy a sample environment
cp -r usr_home/sample_basekit usr_home/my_deployment

# Edit configuration
cd usr_home/my_deployment
vim config.yml              # Set IPs, hostnames, passwords
vim group_vars/basekit.yml  # Set profile_kind, profile_name, image versions
```

### 2. Configure Your Environment

**`group_vars/basekit.yml`** - Main configuration:
```yaml
profile_kind: "basekit"      # Profile type: basekit, baremetal, or aws
profile_name: "default"      # Which profile variant to use

# Image references
onboarder: "onboarder-full.v3.5.0-rc7.tar.gz"
basekit: "openspace-base-kit-1.0.1-config.tar.gz"
osms: "openspace-1.9.0-295.os-app"
```

**`config.yml`** - Inventory with hosts and credentials:
```yaml
all:
  children:
    basekit:
      vars:
        domain_name: "base-kit.kratos"
        customer_network:
          gateway: "10.243.76.1"
          cidr: "/23"
      children:
        mgmt_svr:
          hosts:
            mgmt_kvm:
              ansible_host: 10.243.77.212
              ansible_user: kratos
              ansible_ssh_pass: "your_password"  # For initial bootstrap
```

### 3. Validate Configuration

```bash
python3 onboarder-run.py --env=my_deployment --validate-only
```

This checks:
- ✓ Required files exist
- ✓ YAML syntax is valid
- ✓ Profile structure is correct
- ✓ All task files exist

### 4. Run the Deployment

```bash
# Interactive environment selection
python3 onboarder-run.py

# Or specify environment
python3 onboarder-run.py --env=my_deployment

# Resume from last successful step after fixing issues
python3 onboarder-run.py --env=my_deployment --resume

# Verbose output for debugging
python3 onboarder-run.py --env=my_deployment --verbose
```

## 📋 Profile Structure

Profiles define the installation workflow. Located in `data/profiles/<profile_kind>/<profile_name>.yml`

```yaml
metadata:
  name: "Base-Kit Default"
  version: "1.0.0"
  description: "Deploys management KVM with VMs"
  profile_kind: basekit

requirements:
  # Validate these exist before running
  inventory_groups:
    - mgmt_kvm
  files:
    - "/install/usr_home/{env}/.ssh/onboarder_ssh_key.pub"

steps:
  - id: copy_ssh_key
    description: "Copy SSH Key to mgmt_kvm"
    kind: ansible                    # ansible, python3, bash, shell, sh
    file: "tasks/common/copy_ssh_key.yml"
    args:
      - "-e env_name={env}"          # Variables are substituted
      - "-e target_hosts=mgmt_kvm"
    on_failure: fail                 # fail (default), continue, retry
    required: true                   # Cannot be skipped
    timeout: 300                     # Seconds (optional)

  - id: bootstrap_mgmt_kvm
    description: "Bootstrap Mgmt KVM"
    kind: ansible
    file: "tasks/basekit/bootstrap-mgmt-kvm.yml"
    timeout: 1800
```

### Variable Substitution

These placeholders are replaced in step arguments:
- `{env}` - Environment name (e.g., `my_deployment`)
- `{profile}` - Profile name (e.g., `default`)
- `{profile_kind}` - Profile kind (e.g., `basekit`)
- `{variable}` - Any variable from `group_vars/basekit.yml` (e.g., `{onboarder}`)

## 🔧 Command Options

```bash
python3 onboarder-run.py [OPTIONS]

Options:
  --env=NAME          Environment name (or select interactively)
  --validate-only     Only validate, don't run
  --resume            Resume from last successful step
  --verbose, -v       Enable debug logging
  --help, -h          Show help
```

## 📊 Log Files

Logs are stored in `usr_home/<env>/logs/`:

```
logs/
├── onboarder.log                                    # Main orchestrator log
├── state.json                                       # Progress tracking
├── 00-install-rpms.log                             # RPM installation
├── copy_ssh_key-Copy_SSH_Key_to_mgmt_kvm.log      # Step 1
├── bootstrap_mgmt_kvm-Bootstrap_Mgmt_KVM.log       # Step 2
└── deploy_vms-Deploy_VMs.log                       # Step 3
```

## 🔄 State Management

Progress is tracked in `state.json`:
```json
{
  "env": "my_deployment",
  "profile_kind": "basekit",
  "profile_name": "default",
  "steps": {
    "copy_ssh_key": {
      "status": "ok",
      "exit_code": 0,
      "log": "/install/logs/copy_ssh_key.log"
    },
    "bootstrap_mgmt_kvm": {
      "status": "running"
    }
  }
}
```

Use `--resume` to skip completed steps and continue from where you left off.

## 🛠️ How It Works

1. **Environment Selection** - Choose which environment to deploy
2. **Profile Detection** - Reads `profile_kind` and `profile_name` from `group_vars/basekit.yml`
3. **Validation** - Checks config files, profile structure, and file existence
4. **RPM Installation** - Installs any RPMs from `images/rpms/` (e.g., sshpass)
5. **Step Execution** - Runs each step in the profile sequentially
6. **Progress Tracking** - Saves state after each step for resume capability

### Container Execution

The runner script:
1. Detects container runtime (podman or docker)
2. Loads the onboarder container image
3. Mounts necessary directories:
   - `/install/data` → `./data/`
   - `/install/images` → `./images/`
   - `/install/usr_home/{env}` → `./usr_home/{env}/`
   - `/install/logs` → `./usr_home/{env}/logs/`
4. Executes `main.py` inside the container

## 📝 Configuration Guide

### Ansible Inventory Best Practices

**Use underscores in host/group names:**
```yaml
# ✅ Correct
mgmt_kvm:
  ansible_host: 10.243.77.212

# ❌ Wrong - hyphens cause issues
mgmt-kvm:
  ansible_host: 10.243.77.212
```

**Group Variables Hierarchy:**

Ansible loads variables in this order:
1. `group_vars/all.yml` - All hosts
2. `group_vars/basekit.yml` - Profile-level config
3. `group_vars/mgmt_svr.yml` - Group-specific vars
4. `host_vars/mgmt_kvm.yml` - Host-specific vars (optional)

### Adding RPMs to Container

Place RPMs in `images/rpms/` and they'll be installed automatically:
```bash
images/rpms/
├── sshpass-1.09-4.el9.x86_64.rpm
└── any-other-package.rpm
```

### DISA STIG Compatibility

The included `ansible.cfg` is configured for DISA STIG hardened RHEL 9 systems:
- STIG-approved ciphers (aes128-ctr, aes256-ctr, aes-gcm)
- STIG-approved MACs (hmac-sha2-256, hmac-sha2-512)
- STIG-approved key exchange algorithms
- Proper SSH connection settings

## 🐛 Troubleshooting

### "Could not determine profile kind"
**Cause:** Missing or incorrect `profile_kind` in group_vars

**Fix:**
```bash
# Ensure group_vars/basekit.yml has:
profile_kind: "basekit"
profile_name: "default"
```

### "Variable X is undefined"
**Cause:** Variable referenced in playbook doesn't exist in inventory

**Fix:** Check that:
1. Variable is defined in appropriate group_vars file
2. Group name in group_vars matches your inventory structure
3. Variable uses correct format (underscores, not hyphens in Jinja2)

### "Invalid/incorrect password"
**Cause:** SSH password authentication failing

**Fix:**
1. Verify `ansible_ssh_pass` is set in inventory for the host
2. Ensure sshpass RPM is in `images/rpms/`
3. Test manually: `sshpass -p 'password' ssh user@host`

### Step Failed - How to Resume
1. Check the log file mentioned in the error
2. Fix the underlying issue
3. Run with `--resume` to skip completed steps:
   ```bash
   python3 onboarder-run.py --env=my_deployment --resume
   ```

### Validate Before Running
Always validate first to catch 90% of issues:
```bash
python3 onboarder-run.py --env=my_deployment --validate-only
```

## 🎯 Exit Codes

- `0` - Success
- `2` - Configuration error (missing files, bad YAML)
- `3` - File not found
- `4` - Unsupported step kind
- `5` - Step execution failed
- `6` - Validation failed

## 🔐 Security Notes

### SSH Password Storage

**Development/Testing:**
```yaml
# Store in plaintext (NOT for production)
ansible_ssh_pass: "your_password"
```

**Production:**
```yaml
# Use Ansible Vault
ansible_ssh_pass: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  ...
```

**Best Practice:**
After initial SSH key deployment, remove passwords from inventory since key-based auth will be used.

## 📚 Example Workflows

### New Deployment

```bash
# 1. Create environment from template
cp -r usr_home/sample_basekit usr_home/production

# 2. Edit configuration
cd usr_home/production
vim config.yml                    # Set IPs and credentials
vim group_vars/basekit.yml        # Set profile and image versions

# 3. Validate
cd ../..
python3 onboarder-run.py --env=production --validate-only

# 4. Deploy
python3 onboarder-run.py --env=production
```

### Resuming After Failure

```bash
# 1. Check what failed
cat usr_home/production/logs/state.json
cat usr_home/production/logs/<failed_step>.log

# 2. Fix the issue (update config, fix network, etc.)

# 3. Resume from where it stopped
python3 onboarder-run.py --env=production --resume
```

### Multiple Environments

```bash
# Deploy to different environments
python3 onboarder-run.py --env=dev
python3 onboarder-run.py --env=staging  
python3 onboarder-run.py --env=production
```

## 🚧 Creating Custom Profiles

### 1. Create Profile File

`data/profiles/basekit/custom.yml`:
```yaml
metadata:
  name: "My Custom Profile"
  version: "1.0.0"
  description: "Custom deployment workflow"
  profile_kind: basekit

steps:
  - id: custom_step
    description: "My custom step"
    kind: ansible
    file: "tasks/basekit/my-custom-task.yml"
    timeout: 600
```

### 2. Reference in Environment

`usr_home/my_env/group_vars/basekit.yml`:
```yaml
profile_kind: "basekit"
profile_name: "custom"  # ← Use your custom profile
```

### 3. Deploy

```bash
python3 onboarder-run.py --env=my_env
```

## 🎨 Features

- ✅ **Configuration-driven** - All logic in `data/`, all config in `usr_home/`
- ✅ **Variable substitution** - Use `{env}`, `{profile}`, and custom variables
- ✅ **Validation** - Catch errors before running
- ✅ **Idempotent** - Safe to run multiple times
- ✅ **Resumable** - Continue from last successful step
- ✅ **Progress tracking** - State saved after each step
- ✅ **Multiple profiles** - basekit, baremetal, aws
- ✅ **Container isolation** - Consistent execution environment
- ✅ **Detailed logging** - Per-step logs + main orchestrator log
- ✅ **STIG-compatible** - Works with hardened RHEL 9 systems
- ✅ **Clean output** - Easy to see progress at a glance

## 🤝 Contributing

### Adding a New Step

1. Create the task file in `data/tasks/<profile>/`
2. Add to profile: `data/profiles/<profile>/<name>.yml`
3. Test with `--validate-only`

### Adding a New Profile Type

1. Create directory: `data/profiles/<new_type>/`
2. Create profile: `data/profiles/<new_type>/default.yml`
3. Create tasks in: `data/tasks/<new_type>/`
4. Test with sample environment

## 📖 Version History

- **v1.0.0** - Initial release with basekit profile
  - Python-based orchestrator
  - Profile system
  - Validation and resume capabilities
  - STIG-compatible Ansible configuration

---

**Need Help?** Check the logs in `usr_home/<env>/logs/` or run with `--verbose` for detailed output.