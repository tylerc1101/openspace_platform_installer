# Requirements

## System Requirements

- **Operating System**: RHEL 9 or compatible Linux distribution
- **Python**: Python 3.9+
- **Container Runtime**: Docker or Podman
- **Disk Space**: Minimum 20GB for container images and installation files

## Software Dependencies

### Required Packages
- `python3`
- `python3-pip`
- `docker` or `podman`
- `ansible` (installed in container)
- `sshpass` (for password-based SSH, installed via RPM in container)

### Python Dependencies
The installer handles Python dependencies automatically within the container. Key libraries include:
- `pyyaml` - YAML configuration parsing
- `jinja2` - Template rendering

## Network Requirements

- SSH access to target infrastructure
- Network connectivity between installer host and deployment targets
- Appropriate firewall rules configured for:
  - SSH (port 22)
  - Kubernetes API (port 6443)
  - Any application-specific ports

## Access Requirements

### SSH Keys
- SSH key pairs for target systems (placed in `usr_home/<env>/.ssh/`)
- Proper permissions on private keys (chmod 600)

### Credentials
- Root or sudo access on target systems
- Kubernetes cluster credentials (kubeconfig) if managing existing clusters

## Optional Components

### For Bare Metal Deployments
- KVM/libvirt access on management server
- Network infrastructure supporting PXE boot (if using automated provisioning)

### For AWS Deployments
- AWS credentials configured
- Appropriate IAM permissions for resource creation

### For Base Kit Deployments
- Management server with KVM/libvirt installed
- OPNsense firewall image (if deploying network infrastructure)
- Required VM images for OpenSpace components

## STIG Compatibility Notes

The installer is designed to work with STIG-hardened RHEL 9 systems:
- Custom `ansible.cfg` with STIG-compatible settings
- Containerized execution to avoid conflicting with system hardening
- SSH connection strategies compatible with hardened SSH configurations
