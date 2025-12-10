# OpenSpace Platform Installer

Automated deployment system for OpenSpace infrastructure. Define your infrastructure in a single YAML file and deploy complete Kubernetes clusters with all platform components.

## What Can It Do?

- Deploy complete OpenSpace infrastructure from a single configuration file  
- Supports multiple deployment types: basekit (VMs), bare metal, AWS  
- Automatically provisions the MCM (Management Cluster) with Harbor, Rancher, Gitea, and ArgoCD  
- Deploys OSMS and OSDC downstream clusters  
- Handles networking, VMs, SSH keys, and configuration automatically  

## Quick Start — Choose Your Deployment Type

### [Basekit Deployment](docs/DEPLOY_BASEKIT.md)
Deploys full infrastructure, including VMs on a management KVM host. Ideal for lab or demo environments.

Full guide located at `docs/DEPLOY_BASEKIT.md`.

#### Example workflow

**Copy and edit the deployment YAML:**
```bash
cp docs/examples/basekit.deployment.yml ./myenv.deployment.yml
vi ./myenv.deployment.yml  # Edit IPs and settings
```

**Load the Basekit image tarball:**
```bash
tar -xvf images/basekit-1.0.1.tar -C /
```

**Start the deployment:**
```bash
python3 onboarder-run.py  # Start container
task deploy-all           # Deploy!
```

---

### [Bare Metal Deployment](docs/DEPLOY_BAREMETAL.md)
Deploy to existing bare metal servers. Recommended for production environments.  
*(Coming soon)*

---

### [AWS Deployment](docs/DEPLOY_AWS.md)
Cloud-based deployment.  
*(Coming soon)*

---

## Requirements

- Linux host (RHEL 9 or Rocky Linux 9)  
- Docker or Podman installed  
- Python 3.9+  
- SSH access to target infrastructure  
- See deployment-specific guides for detailed requirements  

---

## Help & Troubleshooting

- **[Troubleshooting Guide](docs/TROUBLESHOOTLING.md)** — Fix common issues  
- **[How It Works](docs/HOW_IT_WORKS.md)** — Technical details and architecture  

---

## What Gets Deployed

### MCM (Management Cluster)

- RKE2 Kubernetes  
- Harbor container registry  
- Rancher multi-cluster management  
- Gitea source control  
- ArgoCD for GitOps  

### OSMS & OSDC

- Downstream RKE2 Kubernetes clusters  
- Fully managed through Rancher  

---

**Ready to deploy?** Choose your deployment type above and follow the guide!
