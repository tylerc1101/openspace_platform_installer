# Baremetal Deployment Guide

Deploy OpenSpace infrastructure to existing bare metal servers.

## What You Need

**Bare Metal Servers:**
- RHEL 9 or Rocky Linux 9 installed
- Minimum 3 servers for MCM (for HA)
- Additional servers for OSMS and OSDC
- SSH access with sudo privileges
- Network connectivity between all servers

**Your Workstation:**
- Docker or Podman installed
- Python 3.9+
- This repository cloned

**Per Server Requirements:**
- 8+ CPU cores (16+ recommended)
- 16+ GB RAM (32+ GB recommended)
- 200+ GB disk
- Static IP address
- Access to DNS and NTP servers

## Step 1: Prepare Your Servers

On each bare metal server:

```bash
# Ensure RHEL/Rocky 9 is installed
cat /etc/os-release

# Verify static IP is configured
ip addr show

# Test SSH access from your workstation
ssh rancher@<server-ip>
```

## Step 2: Create deployment.yml

Copy the example and edit for your environment:

```bash
mkdir -p environments/myenv
cp docs/examples/baremetal.deployment.yml environments/myenv/myenv.deployment.yml
vim environments/myenv/myenv.deployment.yml
```

**Example deployment.yml:**

```yaml
---
deployment:
  name: "production"
  type: "baremetal"
  onboarder_version: "3.5.0-rc7"
  osms_tooling_version: "1.8.x"

ssh:
  user: "rancher"              # SSH username for all servers
  pass: "your-password"        # Initial SSH password
  become: "rancher"            # Sudo user

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

domain:
  base: "prod.example.com"

ntp:
  server: "pool.ntp.org"
  timezone: "America/New_York"

# MCM cluster - 3 nodes for HA
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

# OSMS cluster - 3 nodes for HA
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
        - name: "srv06"
          mgmt_ip: "192.168.1.16"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]

# OSDC cluster (optional)
openspace_data_cluster:
  clusters:
    - cluster_name: "osdc"
      ssh_key: "osdc_ssh_key"
      nodes:
        - name: "srv07"
          mgmt_ip: "192.168.1.17"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]
        - name: "srv08"
          mgmt_ip: "192.168.1.18"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]
        - name: "srv09"
          mgmt_ip: "192.168.1.19"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]

# Optional: NFS storage
storage:
  nfs:
    enabled: true
    server: "192.168.1.100"
    path: "/exports/kubernetes"

# Note: No infrastructure or virtual_machines sections for baremetal
```

**Edit these values:**
- Server IP addresses (`mgmt_ip`)
- Server hostnames (`name`)
- Network interface names (`mgmt_interface`)
- SSH credentials
- DNS and NTP servers
- Domain name

## Step 3: Verify Server Access

Test SSH access to all servers:

```bash
# Test from your workstation
for ip in 192.168.1.{11..19}; do
  echo "Testing $ip..."
  ssh -o ConnectTimeout=5 rancher@$ip hostname || echo "Failed: $ip"
done
```

All servers should respond with their hostnames.

## Step 4: Launch Onboarder Container

```bash
python3 onboarder-run.py
```

Select your environment when prompted. First run automatically generates all configuration.

## Step 5: Verify Generated Configuration

Inside the container:

```bash
# Check inventory - should list all your servers
cat inventory.yml

# Verify SSH keys
ls -la .ssh/

# List available tasks
task --list
```

## Step 6: Deploy MCM

```bash
# Prepare environment
task prep

# Deploy MCM cluster
task deploy-mcm
```

**This will:**
1. Copy SSH keys to all MCM servers
2. Prepare nodes (OS configuration, install RKE2 SELinux module)
3. Deploy RKE2 cluster
4. Deploy Harbor registry
5. Deploy Rancher
6. Deploy Gitea and ArgoCD

**Duration:** 20-40 minutes

## Step 7: Deploy Downstream Clusters

```bash
# Deploy OSMS
task deploy-prod-osms

# Deploy OSDC
task deploy-prod-osdc
```

## Step 8: Get Kubeconfigs

```bash
task get-kubeconfig-mcm
task get-kubeconfig-osms
task get-kubeconfig-osdc

# Exit container
exit

# Use kubeconfigs on your workstation
export KUBECONFIG=environments/myenv/kubeconfig-mcm
kubectl get nodes
```

## Step 9: Access Services

**Rancher:**
```bash
kubectl --kubeconfig=environments/myenv/kubeconfig-mcm \
  get ingress -n cattle-system rancher -o jsonpath='{.spec.rules[0].host}'

# Get bootstrap password
kubectl --kubeconfig=environments/myenv/kubeconfig-mcm \
  get secret -n cattle-system bootstrap-secret \
  -o jsonpath='{.data.bootstrapPassword}' | base64 -d
```

## Monitoring Progress

**View logs:**
```bash
# Inside container
tail -f .cache/logs/task_*.log
```

**Check state:**
```bash
cat .cache/state.json
jq '.completed_tasks | keys' .cache/state.json
```

## If Something Fails

**Resume automatically:**
```bash
# Just re-run the task
task deploy-mcm
# Skips completed steps, continues from failure
```

**Start fresh:**
```bash
rm .cache/state.json
task deploy-mcm
```

**Common issues:**
- SSH fails → Verify IP addresses and credentials
- Node prep fails → Check server has sudo access
- RKE2 install fails → Verify network connectivity between nodes

See [Troubleshooting Guide](TROUBLESHOOTING.md).

## Production Best Practices

### High Availability

Always use 3+ nodes per cluster:
- Provides quorum for etcd
- Allows maintenance without downtime
- Survives single node failure

### Resource Planning

**MCM Cluster** (per node):
- 16+ CPU cores
- 32+ GB RAM
- 200+ GB disk (SSD recommended)

**OSMS/OSDC** (per node):
- 16+ CPU cores
- 32+ GB RAM
- 500+ GB disk (SSD recommended)

### Network

- Use bonded network interfaces for redundancy
- Separate management and data networks if possible
- Configure firewall rules appropriately

### Storage

Use external storage for production:
```yaml
storage:
  nfs:
    enabled: true
    server: "nfs-server.example.com"
    path: "/exports/kubernetes"
```

## Single-Node Testing (Not for Production)

For testing only, you can deploy to a single node:

```yaml
management_cluster:
  clusters:
    - cluster_name: "local"
      ssh_key: "mcm_ssh_key"
      nodes:
        - name: "test-server"
          mgmt_ip: "192.168.1.10"
          mgmt_interface: "eno1"
          roles: ["controlplane", "etcd", "worker"]
```

**Warning:** Single-node clusters have no redundancy and will experience downtime during maintenance.

## Scaling

To add nodes to an existing cluster, update deployment.yml and regenerate:

```bash
# Edit deployment.yml, add new nodes
vim environments/myenv/myenv.deployment.yml

# Inside container, regenerate config
rm .first_run_complete
exit

# Restart container
python3 onboarder-run.py

# Deploy to new nodes
task deploy-mcm  # Will skip existing, configure new nodes
```

## Quick Reference

```bash
# Start container
python3 onboarder-run.py

# Inside container:
task prep                    # Prepare environment
task deploy-mcm             # Deploy MCM
task deploy-prod-osms       # Deploy OSMS
task deploy-prod-osdc       # Deploy OSDC
task get-kubeconfig-mcm     # Get kubeconfigs
task get-kubeconfig-osms
task get-kubeconfig-osdc

# Reset state
rm .cache/state.json

# View logs
tail -f .cache/logs/task_*.log
```

## Next Steps

1. Configure Rancher authentication (LDAP/AD)
2. Set up monitoring (Prometheus/Grafana)
3. Configure backups (Velero)
4. Set up GitOps with ArgoCD
5. Deploy applications
6. Configure TLS certificates
7. Set up log aggregation
