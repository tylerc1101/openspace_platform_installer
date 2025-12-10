# Requirements

## Host System Requirements

### Operating System
- RHEL 9, Rocky Linux 9, or compatible Linux distribution
- Kernel 4.18+ (for container support)

### Hardware
- **CPU**: 4+ cores recommended
- **RAM**: 8 GB minimum, 16 GB recommended
- **Disk Space**: 50 GB minimum for container images and environments

### For Basekit Deployments
The management KVM host must have:
- **CPU**: Hardware virtualization support (Intel VT-x or AMD-V)
- **RAM**: Enough to run all VMs + overhead (calculate VM requirements + 8 GB)
- **Disk**: Enough for all VM disks + images
- **Network**: Multiple network interfaces (WAN + management)

## Software Dependencies

### Required on Host System

```bash
# Container runtime (one of):
- Docker 20.10+
- Podman 4.0+

# Python
- Python 3.9+
- python3-pip

# Git (for version control)
- git

# Optional but recommended
- yamllint (for validating deployment.yml)
```

### Installation Commands

**RHEL/Rocky Linux:**
```bash
# Install Podman (recommended for RHEL/Rocky)
sudo dnf install -y podman python3 python3-pip git

# Or install Docker
sudo dnf install -y docker python3 python3-pip git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER  # Log out and back in
```

**Ubuntu/Debian:**
```bash
# Install Docker
sudo apt-get update
sudo apt-get install -y docker.io python3 python3-pip git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER  # Log out and back in
```

### Inside Container (Automatically Installed)

The onboarder container includes:
- Rocky Linux 9
- Ansible 2.14+
- Python 3.9+
- Task (Taskfile runner)
- jq, yq (YAML/JSON processors)
- openssh-clients
- sshpass (for password-based SSH)
- Custom RPMs for STIG compliance

## Network Requirements

### Connectivity

- **SSH access** to all target hosts (port 22)
- **Network connectivity** from installer host to:
  - Management KVM host (for basekit)
  - All cluster nodes
  - Any external services (DNS, NTP, etc.)

### Firewall Rules

Ensure these ports are accessible:

**SSH (all hosts)**:
- Port 22 (TCP)

**Kubernetes API (cluster nodes)**:
- Port 6443 (TCP)

**RKE2 Supervisor**:
- Port 9345 (TCP)

**Harbor Registry (MCM)**:
- Port 80, 443 (TCP)

**Rancher (MCM)**:
- Port 443 (TCP)

### DNS

- DNS servers must be reachable
- Forward and reverse DNS recommended for cluster nodes
- Wildcard DNS entry for ingresses (optional but recommended)

## Access Requirements

### SSH Access

**For Basekit Deployments**:
- SSH access to management KVM host
- User with sudo privileges
- Password for initial access (SSH keys generated automatically)

**For Baremetal Deployments**:
- SSH access to all cluster nodes
- User with sudo privileges
- Password for initial access

### SSH Key Distribution

The installer handles SSH key generation and distribution automatically:
1. On first run, SSH keys are generated for each cluster
2. Keys are distributed to nodes using password authentication
3. Subsequent operations use key-based authentication

### Sudo Access

- User specified in `ssh.user` must have sudo privileges
- Can use either:
  - Passwordless sudo (recommended)
  - Sudo with password (specify in `ssh.pass`)

## Target Host Requirements

### For All Cluster Nodes

**Operating System**:
- RHEL 9.x or Rocky Linux 9.x
- Minimal or Server installation
- SELinux can be enforcing (installer is SELinux-aware)

**Hardware** (minimum per node):
- CPU: 4 cores
- RAM: 8 GB
- Disk: 100 GB

**Hardware** (recommended for production):
- CPU: 8+ cores
- RAM: 16+ GB
- Disk: 200+ GB (SSD preferred)

**Network**:
- Static IP address
- Network connectivity to other cluster nodes
- Access to DNS servers
- Access to NTP server

### For Management KVM Host (Basekit Only)

**Hardware**:
- CPU: Intel VT-x or AMD-V (virtualization support)
- Cores: 32+ (to run all VMs)
- RAM: 128+ GB (to run all VMs + overhead)
- Disk: 1+ TB (for all VM disks)
- Network: 2+ physical network interfaces

**Software**:
- RHEL 9 or Rocky Linux 9
- libvirt/KVM will be installed by installer
- Bridge networking will be configured by installer

**Base VM Image**:
- Rocky Linux 9 or RHEL 9 qcow2 image
- Located on KVM host (path specified in deployment.yml `backing_store`)
- Cloud-init enabled (optional but recommended)

## Images and Artifacts

### OPNsense ISO (Basekit Only)

Required for basekit deployments:
```
images/opnsense/OPNsense-<version>.iso
```

Download from: https://opnsense.org/download/

### RKE2 and Container Images

For air-gapped/dark site deployments:
- RKE2 install script and binaries
- Container images for all platform components
- Harbor, Rancher, Gitea, ArgoCD images

See darksite preparation documentation for details.

## Permissions and Security

### Container Permissions

- User running `onboarder-run.py` must have access to Docker/Podman
- Either:
  - Member of `docker` group (for Docker)
  - Rootless Podman configured
  - Or run as root (not recommended)

### SELinux

The installer works with SELinux in enforcing mode:
- Container volumes use appropriate SELinux labels
- Ansible playbooks are SELinux-aware
- STIG-hardened RHEL 9 supported

### Firewalld

If firewalld is enabled on target hosts:
- Installer will configure necessary rules
- Or disable firewalld if not needed (deployment-specific)

## Optional Components

### For NFS Storage

If using NFS storage (`storage.nfs.enabled: true`):
- NFS server accessible from all cluster nodes
- NFS export configured and accessible
- Ports 111, 2049 (TCP/UDP)

### For IDRAC/BMC Access

If using out-of-band management:
- Network connectivity to IDRAC network
- IDRAC credentials configured on hosts

## Verification Checklist

Before starting deployment, verify:

- [ ] Container runtime (Docker/Podman) installed and running
- [ ] Python 3.9+ installed
- [ ] SSH access to all target hosts
- [ ] Sudo privileges on target hosts
- [ ] Network connectivity verified (ping all hosts)
- [ ] DNS servers accessible
- [ ] NTP server accessible
- [ ] Sufficient disk space on installer host (50+ GB)
- [ ] (Basekit) Management KVM host has virtualization enabled
- [ ] (Basekit) Base VM image available on KVM host
- [ ] (Basekit) OPNsense ISO available in `images/opnsense/`
- [ ] deployment.yml created and validated

## Quick Verification Commands

```bash
# Check container runtime
docker --version || podman --version

# Check Python version
python3 --version

# Check disk space
df -h .

# Test SSH to all hosts
# (Replace with your hosts)
ssh user@mgmt-kvm hostname
ssh user@mcm1 hostname
ssh user@osms1 hostname

# Check network connectivity
ping -c 3 mgmt-kvm
ping -c 3 mcm1
ping -c 3 osms1

# Validate deployment.yml
python3 -c "import yaml; yaml.safe_load(open('environments/myenv/myenv.deployment.yml'))"
```

## Troubleshooting Common Requirement Issues

### Docker/Podman Not Running

```bash
sudo systemctl start docker
# or
sudo systemctl start podman
```

### Permission Denied (Docker)

```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### SSH Connection Refused

- Check SSH is running: `sudo systemctl status sshd`
- Check firewall allows SSH: `sudo firewall-cmd --list-services`
- Verify correct IP address

### Insufficient Disk Space

```bash
# Clean up Docker/Podman
docker system prune -a
# or
podman system prune -a

# Free up space on target hosts
ssh user@host "df -h"
```
