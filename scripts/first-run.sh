#!/bin/bash
#
# OpenSpace Onboarder - First Run Setup Script
# =============================================
# This script runs on the first container startup to:
#   1. Create the install directory
#   2. Copy deployment configuration
#   3. Generate all config files from deployment.yml
#   4. Run container preparation playbook
#   5. Mark environment as initialized
#
# Environment variables (passed by onboarder-run.py):
#   - DEPLOYMENT_TYPE: Deployment type (e.g., basekit, aws)
#   - ONBOARDER_VERSION: Onboarder version (e.g., 3.5.0-rc7)
#   - CONTAINER_WORKSPACE: Container workspace path (e.g., /docker-workspace)
#   - CONTAINER_INSTALL_DIR: Install directory path
#   - FIRST_RUN_MARKER: Path to marker file

set -e

# Validate required environment variables
: "${DEPLOYMENT_TYPE:?Environment variable DEPLOYMENT_TYPE is required}"
: "${ONBOARDER_VERSION:?Environment variable ONBOARDER_VERSION is required}"
: "${CONTAINER_WORKSPACE:?Environment variable CONTAINER_WORKSPACE is required}"
: "${CONTAINER_DATA_DIR:?Environment variable CONTAINER_DATA_DIR is required}"
: "${CONTAINER_INSTALL_DIR:?Environment variable CONTAINER_INSTALL_DIR is required}"
: "${FIRST_RUN_MARKER:?Environment variable FIRST_RUN_MARKER is required}"

# Configuration
INSTALL_DIR="${CONTAINER_INSTALL_DIR}"
DATA_DIR="${CONTAINER_DATA_DIR}"
ONBOARDER_DIR="${DATA_DIR}/onboarders/${ONBOARDER_VERSION}"
MARKER_FILE="${FIRST_RUN_MARKER}"
DEPLOYMENT_FILE="/tmp/deployment.yml"
CONFIG_DIR="${CONTAINER_WORKSPACE}/config"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     OpenSpace Onboarder - First Run Configuration              ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if already initialized
if [ -f "$MARKER_FILE" ]; then
    echo -e "${GREEN}✓ Environment already initialized${NC}"
    echo ""
    cd "$INSTALL_DIR"
    exit 0
fi

echo -e "${BLUE}→ Setting up environment: $ENV_NAME${NC}"
echo -e "  Deployment Type:    $DEPLOYMENT_TYPE"
echo -e "  Onboarder Version:  $ONBOARDER_VERSION"
echo ""

# Step 1: Create install directory
echo -e "${BLUE}[1/5] Creating install directory...${NC}"
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}  ✓ Created $INSTALL_DIR${NC}"

# Step 2: Copy deployment.yml
echo -e "${BLUE}[2/5] Copying deployment configuration...${NC}"
if [ ! -f "$DEPLOYMENT_FILE" ]; then
    echo -e "${RED}  ✗ Deployment file not found: $DEPLOYMENT_FILE${NC}"
    exit 1
fi
cp "$DEPLOYMENT_FILE" "$INSTALL_DIR/deployment.yml"
echo -e "${GREEN}  ✓ Copied deployment.yml${NC}"

# Step 3: Run config generation
echo -e "${BLUE}[3/5] Generating configuration files...${NC}"

GENERATOR_PLAYBOOK="${ONBOARDER_DIR}/tasks/generate_config.yml"

if [ -f "$GENERATOR_PLAYBOOK" ]; then
    cd "$INSTALL_DIR"

    # Run the generator playbook
    ansible-playbook "$GENERATOR_PLAYBOOK" \
        -e "install_dir=$INSTALL_DIR" \
        -e "deployment_config=$INSTALL_DIR/deployment.yml" \
        -e "templates_dir=$ONBOARDER_DIR/templates" \
        -c local \
        -i localhost,

    echo -e "${GREEN}  ✓ Configuration files generated${NC}"
else
    echo -e "${RED}  ✗ Generator playbook not found: $GENERATOR_PLAYBOOK${NC}"
    echo -e "${RED}    Cannot continue without generate_config.yml${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Run Onboarder Preparation Playbook                         ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 4: Run prep_onboarder_container.yml
echo -e "${BLUE}[4/5] Preparing onboarder container...${NC}"

PREP_PLAYBOOK="${ONBOARDER_DIR}/tasks/prep_onboarder_container.yml"

if [ -f "$PREP_PLAYBOOK" ]; then
    cd "$INSTALL_DIR"

    # Run the prep playbook
    ansible-playbook "$PREP_PLAYBOOK" \
        -i "$INSTALL_DIR/inventory.yml" \
        -e "target_hosts=localhost"

    echo -e "${GREEN}  ✓ Onboarder container prepared${NC}"
else
    echo -e "${YELLOW}  ⚠ Prep playbook not found: $PREP_PLAYBOOK${NC}"
    echo -e "${YELLOW}    Skipping container preparation${NC}"
fi

# Step 5: Create marker file
echo -e "${BLUE}[5/5] Finalizing setup...${NC}"
cat > "$MARKER_FILE" << EOF
initialized=$(date -Iseconds)
env_name=$ENV_NAME
deployment_type=$DEPLOYMENT_TYPE
onboarder_version=$ONBOARDER_VERSION
EOF
echo -e "${GREEN}  ✓ Setup complete${NC}"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Environment Ready!                                         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${YELLOW}Generated files:${NC}"
ls -la "$INSTALL_DIR" 2>/dev/null | grep -v "^total" | grep -v "^\." | head -15 | while read line; do
    echo "    $line"
done
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo "    task --list           # See available tasks"
echo "    task prep             # Prepare environment"
echo "    task deploy-mcm       # Deploy MCM"
echo ""

cd "$INSTALL_DIR"
