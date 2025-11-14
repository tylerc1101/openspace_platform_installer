#!/usr/bin/env python3
"""
Deploy OPNsense VM and Configuration
"""
import os
import subprocess
import sys
from pathlib import Path

def log(msg):
    """Print log message"""
    print(f"[deploy-opnsense] {msg}", flush=True)

def run_command(cmd, check=True):
    """Run a shell command"""
    log(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr)
    
    if check and result.returncode != 0:
        log(f"❌ Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    
    return result

def check_config_exists(env_name):
    """Check if config.xml was generated"""
    config_path = Path(f"/docker-workspace/config/{env_name}/files/opnsense/config.xml")
    
    if not config_path.exists():
        log("❌ config.xml not found!")
        log(f"Expected at: {config_path}")
        log("Make sure the generate_opnsense_config step completed successfully")
        sys.exit(1)
    
    log(f"✓ Found config.xml at: {config_path}")
    return config_path

def copy_config_to_mgmt_kvm(config_path):
    """Copy config.xml to management KVM server"""
    log("Copying config.xml to management KVM server...")
    
    # Create destination directory on mgmt-kvm
    run_command([
        "ansible", "mgmt_kvm",
        "-m", "file",
        "-a", "path=/var/lib/libvirt/config/opnsense state=directory mode=0755",
        "-b"
    ])
    
    # Copy config.xml
    run_command([
        "ansible", "mgmt_kvm",
        "-m", "copy",
        "-a", f"src={config_path} dest=/var/lib/libvirt/config/opnsense/config.xml mode=0644",
        "-b"
    ])
    
    log("✓ Config copied successfully")

def deploy_opnsense_vm():
    """Deploy OPNsense VM using the install script"""
    log("Deploying OPNsense VM...")
    
    # Check if install script exists
    install_script = Path("/docker-workspace/images/base-kit-1.0.1/scripts/install_opnsense.sh")
    
    if not install_script.exists():
        log(f"⚠️  Install script not found at: {install_script}")
        log("Attempting alternate deployment method...")
        
        # Try direct virt-install or other method
        # This is a placeholder - implement your OPNsense deployment method
        log("Please ensure install_opnsense.sh is available")
        return False
    
    # Run the install script
    result = run_command(
        ["sudo", str(install_script)],
        check=False
    )
    
    if result.returncode == 0:
        log("✓ OPNsense VM deployed successfully")
        return True
    else:
        log(f"❌ OPNsense deployment failed with exit code {result.returncode}")
        return False

def main():
    """Main execution"""
    log("=" * 60)
    log("OPNsense Deployment")
    log("=" * 60)
    
    # Get environment name from environment variable or default
    env_name = os.getenv("ENV_NAME", "unknown")
    log(f"Environment: {env_name}")
    
    # Step 1: Check if config.xml exists
    config_path = check_config_exists(env_name)
    
    # Step 2: Copy config to management KVM
    copy_config_to_mgmt_kvm(config_path)
    
    # Step 3: Deploy OPNsense VM
    success = deploy_opnsense_vm()
    
    if success:
        log("=" * 60)
        log("✅ OPNsense deployment completed successfully")
        log("=" * 60)
        log("")
        log("Next steps:")
        log("  1. Access OPNsense web interface")
        log("  2. Verify network connectivity")
        log("  3. Test port forwards and firewall rules")
        sys.exit(0)
    else:
        log("=" * 60)
        log("❌ OPNsense deployment encountered errors")
        log("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n❌ Deployment interrupted by user")
        sys.exit(130)
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
