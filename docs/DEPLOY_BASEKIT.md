# Basekit Deployment Guide

Deploy complete OpenSpace infrastructure including VMs on a management KVM host.

## What You Need

**Management KVM Host:**
- RHEL 9 or Rocky Linux 9
- Hardware virtualization enabled (Intel VT-x or AMD-V)
- 32+ CPU cores, 128+ GB RAM, 1+ TB disk
- 2+ network interfaces (WAN + management)
- SSH access with sudo privileges

**Your Workstation:**
- Docker or Podman installed
- Python 3.9+
- This repository cloned

**Network Information:**
- IP addresses for: management KVM host, OPNsense, cluster nodes
- Gateway and DNS servers
- Network CIDR ranges

## Step 1: Create deployment.yml

Copy the example and edit for your environment:

```bash
mkdir -p environments/myenv
cp docs/examples/basekit.deployment.yml environments/myenv/myenv.deployment.yml
vim environments/myenv/myenv.deployment.yml
```

**Example deployment.yml:**

```yaml
---
deployment:
  name: "my-lab"
  type: "basekit"
  onboarder_version: "3.5.0-rc7"
  osms_tooling_version: "1.8.x"

ssh:
  user: "rancher"              # SSH username for all hosts
  pass: "your-password"        # Initial SSH password
  become: "rancher"            # Sudo user

networks:
  customer:                    # External/WAN network
    gateway: "10.10.10.1"
    cidr: "/24"
    dns_servers:
      - "8.8.8.8"
      - "8.8.4.4"
  management:                  # Internal cluster network
    network: "192.168.1"       # Network prefix
    cidr: "/24"
    dns_servers:
      - "8.8.8.8"
      - "8.8.4.4"

domain:
  base: "lab.example.com"      # Base domain for services

ntp:
  server: "pool.ntp.org"
  timezone: "Etc/UTC"

infrastructure:
  mgmt_kvm:                    # Management KVM hypervisor
    wan_ip: "10.10.10.10"
    wan_interface: "eno1"
    mgmt_ip: "192.168.1.1"
    mgmt_interface: "eno2"
  opnsense:                    # OPNsense firewall VM
    wan_ip: "10.10.10.254"
    mgmt_ip: "192.168.1.254"

management_cluster:            # MCM cluster nodes (will be VMs)
  clusters:
    - cluster_name: "local"
      ssh_key: "mcm_ssh_key"
      nodes:
        - name: "mcm1"
          mgmt_ip: "192.168.1.10"
          mgmt_interface: "enp1s0"
          roles: ["controlplane", "etcd", "worker"]

openspace_management_system:   # OSMS cluster nodes (will be VMs)
  clusters:
    - cluster_name: "osms"
      ssh_key: "osms_ssh_key"
      nodes:
        - name: "osms1"
          mgmt_ip: "192.168.1.20"
          mgmt_interface: "enp1s0"
          roles: ["controlplane", "etcd", "worker"]

# VM specifications
virtual_machines:
  mcm:
    memory: 16384              # MB
    vcpus: 8
    disk_size: 100             # GB
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"
    os_variant: "rhel9.5"
    network_bridge: "br-mgmt"
  osms:
    memory: 32768
    vcpus: 16
    disk_size: 100
    backing_store: "/var/lib/libvirt/images/rocky9.qcow2"
    os_variant: "rhel9.5"
    network_bridge: "br-mgmt"

storage:
  nfs:
    enabled: false
```

**Edit these values:**
- IP addresses to match your network
- `ssh.user` and `ssh.pass` for your environment
- `backing_store` path to your Rocky/RHEL 9 qcow2 image on the KVM host
- Add more cluster nodes for HA (recommended: 3 nodes per cluster)

## Step 2: Prepare KVM Host

On your management KVM host, ensure you have a base VM image:

```bash
# On KVM host, verify base image exists
ls -lh /var/lib/libvirt/images/rocky9.qcow2

# If you need to download Rocky 9:
# wget https://download.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2
# mv Rocky-9-GenericCloud-Base.latest.x86_64.qcow2 /var/lib/libvirt/images/rocky9.qcow2
```

## Step 3: Launch Onboarder Container

From your workstation, in the repository directory:

```bash
python3 onboarder-run.py
```

**What happens:**
1. Detects Podman/Docker
2. Shows menu of environments (finds your myenv.deployment.yml)
3. Select your environment
4. First run: automatically generates all config files
5. Drops you into container shell at `/docker-workspace/install`

## Step 4: Verify Generated Configuration

Inside the container:

```bash
# Check generated inventory
cat inventory.yml

# Check generated Taskfile
cat Taskfile.yml

# Check SSH keys were generated
ls -la .ssh/

# View available tasks
task --list
```

## Step 5: Deploy Infrastructure

Run the deployment:

```bash
# Prepare environment
task prep

# Deploy MCM (this will create VMs and deploy everything)
task deploy-mcm
```

**This will:**
1. Copy SSH keys to management KVM host
2. Bootstrap KVM host (install libvirt, configure networking)
3. Configure OPNsense firewall
4. Deploy OPNsense VM
5. Deploy cluster VMs (mcm1, osms1)
6. Configure VM partitions
7. Copy SSH keys to VMs
8. Prepare nodes (OS configuration, SELinux)
9. Deploy RKE2 on MCM
10. Deploy Harbor registry
11. Deploy Rancher
12. Deploy Gitea and ArgoCD

**Duration:** 30-60 minutes depending on your infrastructure

## Step 6: Deploy Downstream Clusters

After MCM is running:

```bash
# Deploy OSMS
task deploy-prod-osms

# Deploy OSDC (if you configured it)
task deploy-prod-osdc
```

## Step 7: Get Kubeconfigs

```bash
# Retrieve kubeconfigs
task get-kubeconfig-mcm
task get-kubeconfig-osms

# Exit container
exit

# On your workstation, use kubeconfigs
export KUBECONFIG=environments/myenv/kubeconfig-mcm
kubectl get nodes
```

## Step 8: Access Services

**Rancher:**
```bash
# Get Rancher URL (on MCM cluster)
kubectl --kubeconfig=environments/myenv/kubeconfig-mcm \
  get ingress -n cattle-system rancher -o jsonpath='{.spec.rules[0].host}'

# Get bootstrap password
kubectl --kubeconfig=environments/myenv/kubeconfig-mcm \
  get secret -n cattle-system bootstrap-secret \
  -o jsonpath='{.data.bootstrapPassword}' | base64 -d
```

Access Rancher at `https://<rancher-hostname>` and login with the bootstrap password.

## Monitoring Progress

**Real-time output:**
Tasks show live output as they run.

**Check logs:**
```bash
# Inside container
ls -lh .cache/logs/
tail -f .cache/logs/task_bootstrap-mgmt-kvm.log
```

**Check state:**
```bash
cat .cache/state.json
```

## If Something Fails

**The installer automatically resumes:**
```bash
# Just re-run the same command
task deploy-mcm
# It will skip completed tasks and continue from where it failed
```

**Start completely fresh:**
```bash
rm .cache/state.json
task deploy-mcm
```

**Common issues:**
- SSH connection fails → Check IP addresses in deployment.yml
- VM creation fails → Check backing_store path on KVM host
- Insufficient resources → Reduce VM memory/vcpus in deployment.yml

See [Troubleshooting Guide](TROUBLESHOOTING.md) for more help.

## Production Recommendations

For production deployments:

**High Availability:**
```yaml
management_cluster:
  clusters:
    - cluster_name: "local"
      nodes:
        - name: "mcm1"
          mgmt_ip: "192.168.1.10"
          roles: ["controlplane", "etcd", "worker"]
        - name: "mcm2"
          mgmt_ip: "192.168.1.11"
          roles: ["controlplane", "etcd", "worker"]
        - name: "mcm3"
          mgmt_ip: "192.168.1.12"
          roles: ["controlplane", "etcd", "worker"]
```

**Increase Resources:**
```yaml
virtual_machines:
  mcm:
    memory: 32768     # 32 GB
    vcpus: 16
    disk_size: 200    # 200 GB
```

**Add Storage:**
```yaml
storage:
  nfs:
    enabled: true
    server: "192.168.1.100"
    path: "/exports/kubernetes"
```

## Next Steps

1. Configure Rancher authentication
2. Set up GitOps with ArgoCD
3. Deploy applications to OSMS/OSDC
4. Set up monitoring and alerting
5. Configure backups

## Quick Reference

```bash
# Start container
python3 onboarder-run.py

# Inside container:
task prep                    # Prepare environment
task deploy-mcm             # Deploy MCM (creates VMs)
task deploy-prod-osms       # Deploy OSMS
task deploy-prod-osdc       # Deploy OSDC
task get-kubeconfig-mcm     # Get MCM kubeconfig
task get-kubeconfig-osms    # Get OSMS kubeconfig

# Reset state
rm .cache/state.json

# View logs
ls .cache/logs/
tail -f .cache/logs/task_*.log
```
