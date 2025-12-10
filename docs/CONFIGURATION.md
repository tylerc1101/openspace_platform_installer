# Configuration Reference

The OpenSpace Platform Installer uses a single declarative configuration file: `<env>.deployment.yml`. This file defines your entire infrastructure, and all other configuration files are automatically generated from it.

## Configuration File Location

```
environments/<environment_name>/<environment_name>.deployment.yml
```

For example:
```
environments/production/production.deployment.yml
environments/lab/lab.deployment.yml
```

##deployment.yml Structure

The deployment.yml file has the following main sections:

1. **Deployment Metadata** - Basic deployment information
2. **SSH Configuration** - Credentials for accessing hosts
3. **Network Configuration** - Network topology and settings
4. **Domain Configuration** - DNS and domain settings
5. **NTP Configuration** - Time synchronization
6. **Infrastructure Hosts** - Physical infrastructure (basekit only)
7. **Cluster Nodes** - Kubernetes cluster definitions
8. **Storage Configuration** - Storage backend settings
9. **Virtual Machine Configuration** - VM specifications (basekit only)

## Deployment Metadata

```yaml
deployment:
  name: "my-deployment"                    # Deployment name (identifier)
  type: "basekit"                          # Deployment type: basekit, baremetal, or aws
  onboarder_version: "3.5.0-rc7"          # Onboarder version to use
  osms_tooling_version: "1.8.x"           # OSMS tooling version
```

### Fields

| Field | Required | Description | Values |
|-------|----------|-------------|--------|
| `name` | Yes | Unique identifier for this deployment | Any string |
| `type` | Yes | Type of deployment | `basekit`, `baremetal`, `aws` |
| `onboarder_version` | Yes | Version of onboarder to use | `3.5.0-rc7`, etc. |
| `osms_tooling_version` | Yes | Version of OSMS tooling | `1.8.x`, etc. |

## SSH Configuration

```yaml
ssh:
  user: "rancher"         # SSH username
  pass: "password"        # SSH password (initial access)
  become: "rancher"       # Sudo user
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `user` | Yes | SSH username for accessing all hosts |
| `pass` | Yes | SSH password (used for initial access before keys are distributed) |
| `become` | Yes | User for sudo operations |

**Security Note**: The password is used for initial SSH access. After first-run, SSH keys are generated and distributed to all hosts.

## Network Configuration

Networks define the network topology for your deployment.

```yaml
networks:
  # Customer/WAN Network (External connectivity)
  customer:
    gateway: "10.10.10.1"           # Default gateway
    cidr: "/24"                     # Network CIDR
    dns_servers:                    # DNS servers
      - "8.8.8.8"
      - "8.8.4.4"

  # Management Network (Internal cluster communication)
  management:
    network: "192.168.1"            # Network prefix (e.g., 192.168.1.0)
    cidr: "/24"                     # Network CIDR
    gateway: "192.168.1.1"          # Gateway (optional)
    dns_servers:                    # DNS servers
      - "8.8.8.8"
      - "8.8.4.4"

  # IDRAC Network (Out-of-band management)
  idrac:
    network: "192.168.0"            # Network prefix
    cidr: "/24"                     # Network CIDR
    gateway: "192.168.0.1"          # Gateway
```

### Network Types

- **customer**: External/WAN network for public-facing services
- **management**: Internal network for cluster communication
- **idrac**: Out-of-band management network (optional)

## Domain Configuration

```yaml
domain:
  base: "example.com"    # Base domain for the deployment
```

This base domain is used for:
- Rancher hostname
- Kubernetes service DNS
- Application ingresses

## NTP Configuration

```yaml
ntp:
  server: "pool.ntp.org"    # NTP server address
  timezone: "Etc/UTC"       # System timezone
```

## Infrastructure Hosts (Basekit Only)

For basekit deployments, you need to define physical infrastructure hosts.

```yaml
infrastructure:
  # Management Hypervisor
  mgmt_kvm:
    wan_ip: "10.10.10.10"              # WAN/customer network IP
    wan_interface: "eno1"              # WAN network interface
    mgmt_ip: "192.168.1.1"             # Management network IP
    mgmt_interface: "eno2"             # Management network interface
    idrac_ip: "192.168.0.10"           # IDRAC IP (optional)
    idrac_interface: "ens3f0"          # IDRAC interface (optional)
    prov_interface: "eno8303"          # Provisioning interface (optional)

  # OPNsense Firewall
  opnsense:
    wan_ip: "10.10.10.1"               # WAN IP address
    mgmt_ip: "192.168.1.254"           # Management IP address
```

### mgmt_kvm

The management KVM host is the hypervisor that runs all virtual machines.

| Field | Required | Description |
|-------|----------|-------------|
| `wan_ip` | Yes | IP address on customer/WAN network |
| `wan_interface` | Yes | Network interface for WAN |
| `mgmt_ip` | Yes | IP address on management network |
| `mgmt_interface` | Yes | Network interface for management |
| `idrac_ip` | No | IDRAC IP address |
| `idrac_interface` | No | IDRAC network interface |
| `prov_interface` | No | Provisioning network interface |

### opnsense

OPNsense firewall provides routing and security between networks.

| Field | Required | Description |
|-------|----------|-------------|
| `wan_ip` | Yes | IP address on customer/WAN network |
| `mgmt_ip` | Yes | IP address on management network |

## Cluster Nodes

Define all Kubernetes cluster nodes here.

### MCM (Management Cluster)

```yaml
management_cluster:
  clusters:
    - cluster_name: "local"              # Cluster name in Rancher
      ssh_key: "mcm_ssh_key"            # SSH key name for this cluster
      nodes:
        - name: "mcm1"                   # Node hostname
          mgmt_ip: "192.168.1.10"       # Management network IP
          mgmt_interface: "enp1s0"      # Management network interface
          idrac_ip: "192.168.0.11"      # IDRAC IP (optional)
          roles:                         # Node roles
            - "controlplane"
            - "etcd"
            - "worker"

        - name: "mcm2"
          mgmt_ip: "192.168.1.11"
          mgmt_interface: "enp1s0"
          roles: ["controlplane", "etcd", "worker"]

        - name: "mcm3"
          mgmt_ip: "192.168.1.12"
          mgmt_interface: "enp1s0"
          roles: ["controlplane", "etcd", "worker"]
```

### Node Roles

- **controlplane**: Kubernetes control plane components
- **etcd**: etcd database
- **worker**: Worker node for running workloads

For production, use 3+ nodes with all three roles for high availability.

### OSMS (OpenSpace Management System)

```yaml
openspace_management_system:
  clusters:
    - cluster_name: "openspace-osms"
      ssh_key: "osms_ssh_key"
      nodes:
        - name: "osms1"
          mgmt_ip: "192.168.1.20"
          mgmt_interface: "enp1s0"
          idrac_ip: "192.168.0.21"
          roles: ["controlplane", "etcd", "worker"]

        - name: "osms2"
          mgmt_ip: "192.168.1.21"
          mgmt_interface: "enp1s0"
          roles: ["controlplane", "etcd", "worker"]
```

### OSDC (OpenSpace Data Cluster)

```yaml
openspace_data_cluster:
  clusters:
    - cluster_name: "openspace-osdc"
      ssh_key: "osdc_ssh_key"
      nodes:
        - name: "osdc1"
          mgmt_ip: "192.168.1.30"
          mgmt_interface: "enp1s0"
          idrac_ip: "192.168.0.31"
          roles: ["controlplane", "etcd", "worker"]

        - name: "osdc2"
          mgmt_ip: "192.168.1.31"
          mgmt_interface: "enp1s0"
          roles: ["controlplane", "etcd", "worker"]
```

**Note**: OSDC is optional. Omit this section if you don't need a data cluster.

## Storage Configuration

```yaml
storage:
  nfs:
    enabled: false                        # Enable NFS storage
    server: "192.168.1.100"              # NFS server IP
    path: "/exports/kubernetes"           # NFS export path
```

NFS storage is optional. Set `enabled: true` if you have an NFS server.

## Virtual Machine Configuration (Basekit Only)

For basekit deployments, define VM specifications for each cluster.

```yaml
virtual_machines:
  # MCM Virtual Machine
  mcm:
    name: "mcm"                                              # VM name
    memory: 16384                                            # Memory in MB
    vcpus: 8                                                 # Number of vCPUs
    disk_size: 100                                           # Disk size in GB
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"  # Base image path
    os_variant: "rhel9.5"                                   # OS variant for virt-install
    network_bridge: "br-mgmt"                               # Network bridge to use

  # OSMS Virtual Machine
  osms:
    name: "osms"
    memory: 32768      # 32 GB
    vcpus: 16
    disk_size: 100
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"
    os_variant: "rhel9.5"
    network_bridge: "br-mgmt"

  # OSDC Virtual Machine (optional)
  osdc:
    name: "osdc"
    memory: 32768
    vcpus: 16
    disk_size: 200     # Larger disk for data cluster
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"
    os_variant: "rhel9.5"
    network_bridge: "br-mgmt"
```

### VM Fields

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `name` | Yes | VM name | `mcm`, `osms`, `osdc` |
| `memory` | Yes | Memory in MB | `16384` (16 GB) |
| `vcpus` | Yes | Number of vCPUs | `8` |
| `disk_size` | Yes | Disk size in GB | `100` |
| `backing_store` | Yes | Path to base image on mgmt_kvm | `/var/lib/libvirt/images/rocky9.qcow2` |
| `os_variant` | Yes | OS variant for virt-install | `rhel9.5` |
| `network_bridge` | Yes | Network bridge name | `br-mgmt` |

### Resource Recommendations

**MCM (Management Cluster)**:
- Minimum: 8 vCPUs, 16 GB RAM, 100 GB disk
- Recommended: 16 vCPUs, 32 GB RAM, 200 GB disk

**OSMS (Management System)**:
- Minimum: 8 vCPUs, 16 GB RAM, 100 GB disk
- Recommended: 16 vCPUs, 32 GB RAM, 200 GB disk

**OSDC (Data Cluster)**:
- Minimum: 16 vCPUs, 32 GB RAM, 200 GB disk
- Recommended: 32 vCPUs, 64 GB RAM, 500 GB disk

## Complete Example: Basekit Deployment

```yaml
---
deployment:
  name: "production"
  type: "basekit"
  onboarder_version: "3.5.0-rc7"
  osms_tooling_version: "1.8.x"

ssh:
  user: "rancher"
  pass: "SecurePassword123!"
  become: "rancher"

networks:
  customer:
    gateway: "10.10.10.1"
    cidr: "/24"
    dns_servers:
      - "8.8.8.8"
      - "8.8.4.4"
  management:
    network: "192.168.1"
    cidr: "/24"
    dns_servers:
      - "8.8.8.8"
      - "8.8.4.4"
  idrac:
    network: "192.168.0"
    cidr: "/24"
    gateway: "192.168.0.1"

domain:
  base: "example.com"

ntp:
  server: "pool.ntp.org"
  timezone: "Etc/UTC"

infrastructure:
  mgmt_kvm:
    wan_ip: "10.10.10.10"
    wan_interface: "eno1"
    mgmt_ip: "192.168.1.1"
    mgmt_interface: "eno2"
    idrac_ip: "192.168.0.10"
  opnsense:
    wan_ip: "10.10.10.254"
    mgmt_ip: "192.168.1.254"

management_cluster:
  clusters:
    - cluster_name: "local"
      ssh_key: "mcm_ssh_key"
      nodes:
        - name: "mcm1"
          mgmt_ip: "192.168.1.10"
          mgmt_interface: "enp1s0"
          roles: ["controlplane", "etcd", "worker"]

openspace_management_system:
  clusters:
    - cluster_name: "osms"
      ssh_key: "osms_ssh_key"
      nodes:
        - name: "osms1"
          mgmt_ip: "192.168.1.20"
          mgmt_interface: "enp1s0"
          roles: ["controlplane", "etcd", "worker"]

storage:
  nfs:
    enabled: false

virtual_machines:
  mcm:
    name: "mcm"
    memory: 16384
    vcpus: 8
    disk_size: 100
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"
    os_variant: "rhel9.5"
    network_bridge: "br-mgmt"
  osms:
    name: "osms"
    memory: 32768
    vcpus: 16
    disk_size: 100
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"
    os_variant: "rhel9.5"
    network_bridge: "br-mgmt"
```

## Complete Example: Baremetal Deployment

```yaml
---
deployment:
  name: "production-baremetal"
  type: "baremetal"
  onboarder_version: "3.5.0-rc7"
  osms_tooling_version: "1.8.x"

ssh:
  user: "rancher"
  pass: "SecurePassword123!"
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

domain:
  base: "example.com"

ntp:
  server: "pool.ntp.org"
  timezone: "Etc/UTC"

management_cluster:
  clusters:
    - cluster_name: "local"
      ssh_key: "mcm_ssh_key"
      nodes:
        - name: "srv01"
          mgmt_ip: "192.168.1.11"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]
        - name: "srv02"
          mgmt_ip: "192.168.1.12"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]
        - name: "srv03"
          mgmt_ip: "192.168.1.13"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]

openspace_management_system:
  clusters:
    - cluster_name: "osms"
      ssh_key: "osms_ssh_key"
      nodes:
        - name: "srv04"
          mgmt_ip: "192.168.1.14"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]
        - name: "srv05"
          mgmt_ip: "192.168.1.15"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]

storage:
  nfs:
    enabled: true
    server: "192.168.1.100"
    path: "/exports/kubernetes"

# Note: No infrastructure or virtual_machines sections for baremetal
```

## Generated Configuration Files

When you run the onboarder container for the first time, it automatically generates the following files from your deployment.yml:

### inventory.yml

Ansible inventory with all hosts and groups:

```yaml
all:
  children:
    infrastructure_cluster:
      hosts:
        mcm1:
          ansible_host: 192.168.1.10
          ansible_user: rancher
          ansible_ssh_private_key_file: /docker-workspace/install/.ssh/mcm_ssh_key
    osms:
      hosts:
        osms1:
          ansible_host: 192.168.1.20
          ansible_user: rancher
          ansible_ssh_private_key_file: /docker-workspace/install/.ssh/osms_ssh_key
```

### Taskfile.yml

Task orchestration workflow with deployment-specific variables.

### group_vars/all.yml

Ansible variables for all hosts:

```yaml
cluster_domain: example.com
dns_servers:
  - 8.8.8.8
  - 8.8.4.4
ntp_server: pool.ntp.org
timezone: Etc/UTC
# ... many more variables
```

### SSH Keys

SSH key pairs are generated in `.ssh/`:

```
.ssh/
├── mcm_ssh_key
├── mcm_ssh_key.pub
├── osms_ssh_key
├── osms_ssh_key.pub
├── osdc_ssh_key
└── osdc_ssh_key.pub
```

## Updating Configuration

To update your deployment configuration:

1. **Edit deployment.yml**
   ```bash
   vim environments/myenv/myenv.deployment.yml
   ```

2. **Regenerate configuration**
   ```bash
   # Inside container
   rm .first_run_complete
   exit

   # Restart container
   python3 onboarder-run.py
   # It will regenerate all config files
   ```

3. **Redeploy**
   ```bash
   # Inside container
   task deploy-mcm
   ```

**Warning**: Regenerating configuration will overwrite `inventory.yml`, `Taskfile.yml`, and `group_vars/`. Make sure you haven't manually edited these files, as those changes will be lost.

## Best Practices

### Version Control

```bash
# Only commit deployment.yml, not generated files
cd environments/myenv
git add myenv.deployment.yml
git add README.md

# Never commit these
echo "inventory.yml" >> .gitignore
echo "Taskfile.yml" >> .gitignore
echo "group_vars/" >> .gitignore
echo ".ssh/" >> .gitignore
echo ".cache/" >> .gitignore
```

### Secrets Management

- Don't commit passwords to git
- Use environment variables or external secret management
- Consider using Ansible Vault for sensitive data

### Documentation

Document your deployment configuration:

```yaml
# At the top of deployment.yml
# Deployment: Production Environment
# Purpose: Main OpenSpace platform deployment
# Owner: Infrastructure Team
# Last Updated: 2025-12-10
```

### Validation

After creating deployment.yml, validate it:

```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('environments/myenv/myenv.deployment.yml'))"

# Or use yamllint
yamllint environments/myenv/myenv.deployment.yml
```
