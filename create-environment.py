#!/usr/bin/env python3
"""
Environment Creation Wizard
---------------------------
Interactive tool to create new deployment environments.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
import yaml


SCRIPT_DIR = Path(__file__).parent.resolve()
USR_HOME_DIR = SCRIPT_DIR / "usr_home"
DATA_DIR = SCRIPT_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"


def print_header(text):
    """Print a nice header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_success(text):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text):
    """Print error message."""
    print(f"❌ {text}", file=sys.stderr)


def print_info(text):
    """Print info message."""
    print(f"ℹ️  {text}")


def get_available_profiles():
    """Get list of available profile types."""
    if not PROFILES_DIR.exists():
        return []
    
    profiles = []
    for profile_dir in PROFILES_DIR.iterdir():
        if profile_dir.is_dir() and not profile_dir.name.startswith('.'):
            profiles.append(profile_dir.name)
    
    return sorted(profiles)


def get_profile_variants(profile_kind):
    """Get list of profile variants for a given profile kind."""
    profile_dir = PROFILES_DIR / profile_kind
    if not profile_dir.exists():
        return []
    
    variants = []
    for profile_file in profile_dir.glob("*.yml"):
        if not profile_file.name.startswith('.'):
            variants.append(profile_file.stem)
    
    return sorted(variants)


def prompt_choice(question, choices, allow_back=False):
    """Present a menu of choices and return selected option."""
    print(f"\n{question}")
    for idx, choice in enumerate(choices, 1):
        print(f"  {idx}) {choice}")
    
    if allow_back:
        print(f"  {len(choices) + 1}) ← Go back")
    
    while True:
        try:
            choice_input = input(f"Selection [1-{len(choices) + (1 if allow_back else 0)}]: ").strip()
            choice_idx = int(choice_input) - 1
            
            if allow_back and choice_idx == len(choices):
                return None  # Go back
            
            if 0 <= choice_idx < len(choices):
                return choices[choice_idx]
            else:
                print_error(f"Please choose 1-{len(choices) + (1 if allow_back else 0)}")
        except (ValueError, KeyboardInterrupt):
            print()
            if input("Cancel? (y/n): ").lower() == 'y':
                sys.exit(0)


def prompt_text(question, default=None, validator=None):
    """Prompt for text input with optional validation."""
    while True:
        if default:
            user_input = input(f"{question} [{default}]: ").strip()
            if not user_input:
                user_input = default
        else:
            user_input = input(f"{question}: ").strip()
        
        if not user_input:
            print_error("Input cannot be empty")
            continue
        
        if validator:
            valid, message = validator(user_input)
            if not valid:
                print_error(message)
                continue
        
        return user_input


def validate_env_name(name):
    """Validate environment name."""
    if not name:
        return False, "Name cannot be empty"
    
    if not name.replace('_', '').replace('-', '').isalnum():
        return False, "Name can only contain letters, numbers, underscores, and hyphens"
    
    env_path = USR_HOME_DIR / name
    if env_path.exists():
        return False, f"Environment '{name}' already exists"
    
    if name.startswith('sample_'):
        return False, "Environment name cannot start with 'sample_'"
    
    return True, ""


def create_environment_structure(env_name, profile_kind):
    """Create the directory structure for new environment."""
    env_dir = USR_HOME_DIR / env_name
    
    print_info(f"Creating environment directory: {env_dir}")
    env_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (env_dir / "group_vars").mkdir(exist_ok=True)
    (env_dir / ".ssh").mkdir(mode=0o700, exist_ok=True)
    (env_dir / "logs").mkdir(exist_ok=True)
    
    print_success(f"Created directory structure")
    
    return env_dir


def copy_sample_configs(env_dir, profile_kind):
    """Copy sample configuration files."""
    sample_dir = USR_HOME_DIR / f"sample_{profile_kind}"
    
    if not sample_dir.exists():
        print_error(f"Sample directory not found: {sample_dir}")
        return False
    
    print_info("Copying sample configuration files...")
    
    # Copy config.yml
    if (sample_dir / "config.yml").exists():
        shutil.copy2(sample_dir / "config.yml", env_dir / "config.yml")
        print_success("Copied config.yml")
    
    # Copy group_vars
    sample_group_vars = sample_dir / "group_vars"
    if sample_group_vars.exists():
        for gv_file in sample_group_vars.glob("*.yml"):
            shutil.copy2(gv_file, env_dir / "group_vars" / gv_file.name)
            print_success(f"Copied group_vars/{gv_file.name}")
    
    return True


def generate_ssh_keys(env_dir):
    """Generate SSH keys for the environment."""
    ssh_dir = env_dir / ".ssh"
    
    print_info("Generating SSH keys...")
    
    key_names = [
        "onboarder_ssh_key",
        "rancher_ssh_key",
        "osdc_ssh_key",
        "osms_ssh_key"
    ]
    
    for key_name in key_names:
        key_path = ssh_dir / key_name
        if key_path.exists():
            print_info(f"  {key_name} already exists, skipping")
            continue
        
        try:
            subprocess.run(
                ["ssh-keygen", "-t", "rsa", "-b", "4096", 
                 "-f", str(key_path), "-N", "", "-C", f"{key_name}@environment"],
                check=True,
                capture_output=True
            )
            key_path.chmod(0o600)
            print_success(f"Generated {key_name}")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to generate {key_name}: {e}")
            return False
    
    return True


def open_editor(file_path):
    """Open file in user's preferred editor."""
    editor = os.getenv('EDITOR', 'vim')  # Default to vim
    
    # Try common editors
    for try_editor in [editor, 'vim', 'vi', 'nano', 'emacs']:
        if shutil.which(try_editor):
            try:
                subprocess.run([try_editor, str(file_path)], check=True)
                return True
            except subprocess.CalledProcessError:
                continue
    
    print_error("Could not find a text editor")
    print_info(f"Please manually edit: {file_path}")
    return False


def prompt_edit_config(config_file):
    """Ask user if they want to edit the config file."""
    print(f"\n📝 Configuration file: {config_file}")
    print("\nWhat would you like to do?")
    print("  1) Edit now")
    print("  2) Edit later (manual)")
    print("  3) Use defaults (not recommended)")
    
    choice = input("Selection [1-3]: ").strip()
    
    if choice == '1':
        print_info(f"Opening {config_file.name} in editor...")
        return open_editor(config_file)
    elif choice == '2':
        print_info(f"You can edit later: {config_file}")
        return True
    else:
        print_info("Using default configuration")
        return True


def update_group_vars(env_dir, profile_kind, profile_name):
    """Update group_vars with selected profile."""
    group_vars_file = env_dir / "group_vars" / f"{profile_kind}.yml"
    
    if not group_vars_file.exists():
        print_error(f"group_vars file not found: {group_vars_file}")
        return False
    
    try:
        with open(group_vars_file, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        data['profile_kind'] = profile_kind
        data['profile_name'] = profile_name
        
        with open(group_vars_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        print_success(f"Updated profile configuration in group_vars/{profile_kind}.yml")
        return True
    
    except Exception as e:
        print_error(f"Failed to update group_vars: {e}")
        return False


def show_summary(env_name, profile_kind, profile_name, env_dir):
    """Show summary of created environment."""
    print_header("Environment Created Successfully!")
    
    print(f"""
📦 Environment: {env_name}
📋 Profile: {profile_kind}/{profile_name}
📁 Location: {env_dir}

📝 Configuration Files:
   • config.yml - Ansible inventory (hosts, IPs, credentials)
   • group_vars/{profile_kind}.yml - Profile settings
   • .ssh/ - SSH keys for authentication

⚠️  IMPORTANT NEXT STEPS:
   1. Edit config.yml with your actual hosts and credentials
   2. Review group_vars/{profile_kind}.yml for image versions
   3. Ensure required images are in images/ directory
   4. Validate configuration before deploying
""")


def confirm_deploy(env_name):
    """Ask if user wants to deploy now."""
    print("\n" + "=" * 70)
    response = input("Would you like to validate and deploy now? (y/n): ").strip().lower()
    
    if response == 'y':
        print_info("Starting validation...")
        print()
        return True
    else:
        print_info("You can deploy later with:")
        print(f"  python3 onboarder-run.py --env={env_name}")
        return False


def main():
    """Main wizard flow."""
    print_header("🚀 OpenSpace Environment Creation Wizard")
    
    print("""
This wizard will help you create a new deployment environment.
You'll be guided through:
  1. Choosing an environment name
  2. Selecting a profile type
  3. Configuring your deployment
  4. Optionally deploying immediately
""")
    
    input("Press Enter to continue...")
    
    # Step 1: Get environment name
    print_header("Step 1: Environment Name")
    print("\nChoose a descriptive name for your environment.")
    print("Examples: production, staging, dev, customer_name_site")
    
    env_name = prompt_text(
        "\nEnvironment name",
        validator=validate_env_name
    )
    
    # Step 2: Select profile kind
    print_header("Step 2: Select Profile Type")
    
    available_profiles = get_available_profiles()
    if not available_profiles:
        print_error("No profiles found in data/profiles/")
        sys.exit(1)
    
    print("\nAvailable deployment profiles:")
    for profile in available_profiles:
        profile_dir = PROFILES_DIR / profile
        # Try to get description from a profile
        desc = f"Deploy using {profile} profile"
        for yml_file in profile_dir.glob("*.yml"):
            try:
                with open(yml_file) as f:
                    data = yaml.safe_load(f)
                    if data and 'metadata' in data:
                        desc = data['metadata'].get('description', desc)
                        break
            except:
                pass
        print(f"  • {profile}: {desc}")
    
    profile_kind = prompt_choice(
        "\nSelect profile type:",
        available_profiles
    )
    
    # Step 3: Select profile variant
    print_header("Step 3: Select Profile Variant")
    
    variants = get_profile_variants(profile_kind)
    if not variants:
        print_error(f"No profile variants found for {profile_kind}")
        sys.exit(1)
    
    if len(variants) == 1:
        profile_name = variants[0]
        print_info(f"Using profile: {profile_name}")
    else:
        profile_name = prompt_choice(
            f"\nSelect {profile_kind} profile variant:",
            variants
        )
    
    # Step 4: Create environment
    print_header("Step 4: Creating Environment")
    
    env_dir = create_environment_structure(env_name, profile_kind)
    
    if not copy_sample_configs(env_dir, profile_kind):
        print_error("Failed to copy sample configurations")
        sys.exit(1)
    
    if not update_group_vars(env_dir, profile_kind, profile_name):
        print_error("Failed to update group_vars")
        sys.exit(1)
    
    if not generate_ssh_keys(env_dir):
        print_error("Failed to generate SSH keys")
        sys.exit(1)
    
    # Step 5: Edit configuration
    print_header("Step 5: Configure Environment")
    
    print("\nYou need to customize the configuration for your environment.")
    print("This includes:")
    print("  • Host IP addresses")
    print("  • SSH credentials")
    print("  • Network settings")
    print("  • Domain names")
    
    config_file = env_dir / "config.yml"
    prompt_edit_config(config_file)
    
    print("\nDo you want to review/edit the profile settings?")
    print("(Image versions, additional configuration)")
    response = input("Edit group_vars? (y/n): ").strip().lower()
    if response == 'y':
        group_vars_file = env_dir / "group_vars" / f"{profile_kind}.yml"
        open_editor(group_vars_file)
    
    # Step 6: Summary and deploy
    show_summary(env_name, profile_kind, profile_name, env_dir)
    
    if confirm_deploy(env_name):
        # Run validation
        import onboarder_run
        sys.argv = ['onboarder-run.py', f'--env={env_name}', '--validate-only']
        try:
            result = onboarder_run.main()
            if result == 0:
                print_success("Validation passed!")
                response = input("\nDeploy now? (y/n): ").strip().lower()
                if response == 'y':
                    sys.argv = ['onboarder-run.py', f'--env={env_name}']
                    onboarder_run.main()
            else:
                print_error("Validation failed. Please fix issues and try again.")
        except Exception as e:
            print_error(f"Error during validation: {e}")
            print_info(f"You can manually run: python3 onboarder-run.py --env={env_name}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)