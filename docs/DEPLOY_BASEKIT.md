# Basekit Deployment Guide

Deploy complete OpenSpace infrastructure including VMs on a management KVM host.

## What You Need

**Management KVM Host:**
- RHEL 9 or Rocky Linux 9
- Hardware virtualization enabled (Intel VT-x or AMD-V)
- 32+ CPU cores, 128+ GB RAM, 1+ TB disk
- 2+ network interfaces (WAN + management)
- SSH access with sudo privileges
- Docker or Podman installed
- Python 3.9+

**Network Information:**
- IP addresses for: management KVM host, OPNsense, cluster nodes
- Gateway and DNS servers
- Network CIDR ranges

## Step 1: Create deployment.yml

Copy the example and edit for your environment:

```bash
cp docs/examples/basekit.deployment.yml ./myenv.deployment.yml
vi ./myenv.deployment.yml  # Edit IPs and settings
```

**Edit these values:**
- IP addresses to match your network
- `ssh.user` and `ssh.pass` for your environment
- Add more cluster nodes for HA (recommended: 3 nodes per cluster)

## Step 2: Prepare KVM Host

On your management KVM host:

```bash
tar -xvf images/basekit-1.0.1.tar -C /
```

## Step 3: Launch Onboarder Container

On your management KVM host, in the repository directory:

```bash
python3 onboarder-run.py
```

**What happens:**
1. Detects Podman/Docker
2. Loads/Runs onboarder container
3. First run: automatically generates all config files needed inside container
4. Drops you into container shell at `/docker-workspace/config/install`

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

Run the task:

```bash
# Deploy basekit infrastructure
task deploy-infra
```

**This will:**
1. Copy SSH keys to management KVM host
2. Bootstrap KVM host (install libvirt, configure networking)
3. Configure OPNsense firewall
4. Deploy OPNsense VM
5. Deploy cluster VMs (mcm1, osms1)
6. Configure VM partitions

**Duration:** 30-60 minutes depending on your infrastructure

## Step 6: Deploy MCM

Run the task:

```bash
task deploy-mcm
```

**This will:**
1. Copy SSH keys
2. Prepare node (OS configuration, SELinux)
3. Deploy RKE2 on MCM
4. Deploy Harbor registry
5. Deploy Rancher
6. Deploy Gitea and ArgoCD

## Step 7: Deploy Downstream Clusters

After MCM is running:

```bash
# Deploy OSMS
task deploy-osms

# Deploy OSDC (if you configured it)
task deploy-osdc
```

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
