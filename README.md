# OpenSpace Platform Installer

Automated deployment system for OpenSpace infrastructure. Define your infrastructure in a single YAML file and deploy complete Kubernetes clusters with all platform components.

## What Can It Do?

- Deploy complete OpenSpace infrastructure from a single configuration file
- Supports multiple deployment types: basekit (VMs), baremetal servers, AWS
- Automatically sets up MCM (Management Cluster) with Harbor, Rancher, Gitea, ArgoCD
- Deploys OSMS and OSDC clusters
- Handles networking, VMs, SSH keys, and all configuration automatically

## Quick Start - Choose Your Deployment Type

### [Basekit Deployment](docs/DEPLOY_BASEKIT.md) ⭐
Deploy full infrastructure including VMs on a management KVM host. Perfect for lab environments.

**Quick example:**
```bash
cp docs/examples/basekit.deployment.yml environments/myenv/myenv.deployment.yml
vim environments/myenv/myenv.deployment.yml  # Edit IPs and settings
python3 onboarder-run.py  # Start container
task prep && task deploy-mcm  # Deploy!
```

### [Baremetal Deployment](docs/DEPLOY_BAREMETAL.md)
Deploy to existing bare metal servers. For production environments.

**Quick example:**
```bash
cp docs/examples/baremetal.deployment.yml environments/myenv/myenv.deployment.yml
vim environments/myenv/myenv.deployment.yml  # Edit IPs and settings
python3 onboarder-run.py
task prep && task deploy-mcm
```

### [AWS Deployment](docs/DEPLOY_AWS.md)
Cloud-based deployment (coming soon).

## Requirements

- Linux host (RHEL 9 or Rocky Linux 9)
- Docker or Podman installed
- Python 3.9+
- SSH access to target infrastructure
- See deployment-specific guides for detailed requirements

## Help & Troubleshooting

- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Fix common issues
- **[How It Works](docs/HOW_IT_WORKS.md)** - Technical details and architecture

## What Gets Deployed

**MCM (Management Cluster):**
- RKE2 Kubernetes
- Harbor container registry
- Rancher multi-cluster management
- Gitea source control
- ArgoCD for GitOps

**OSMS & OSDC:**
- Downstream Kubernetes clusters
- Managed via Rancher

---

**Ready to deploy?** Pick your deployment type above and follow the guide!
