#!/usr/bin/env bash
set -euo pipefail

# -------- paths --------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${ROOT_DIR}/data"
USR_HOME_DIR="${ROOT_DIR}/usr_home"

die() { echo "ERROR: $*" >&2; exit 1; }
usage() {
  cat <<EOF
Usage: ./onboarder-run.sh [OPTIONS]

Options:
  --env=<name>        Environment name (or select interactively)
  --validate-only     Only validate configuration, don't run
  --resume            Resume from last successful step
  --verbose           Enable verbose logging
  -h, --help          Show this help

Behavior:
  - Auto-detect runtime (podman/docker)
  - Read profile from usr_home/<env>/.profile
  - Read onboarder image from group_vars
  - Run container and execute main.py
EOF
}

# -------- parse options --------
ENV_NAME=""
VALIDATE_ONLY=""
RESUME=""
VERBOSE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env=*)
      ENV_NAME="${1#*=}"
      shift
      ;;
    --validate-only)
      VALIDATE_ONLY="--validate-only"
      shift
      ;;
    --resume)
      RESUME="--resume"
      shift
      ;;
    --verbose|-v)
      VERBOSE="--verbose"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

# -------- pick ENV from usr_home via menu if not specified --------
if [[ -z "${ENV_NAME}" ]]; then
  mapfile -t ENV_DIRS < <(
    find "${USR_HOME_DIR}" -mindepth 1 -maxdepth 1 -type d \
      ! -name '.*' \
      ! -name 'sample_aws' \
      ! -name 'sample_baremetal' \
      ! -name 'sample_basekit' \
      -printf "%f\n" | sort
  )

  [[ ${#ENV_DIRS[@]} -ge 1 ]] || die "No environment directories found in ${USR_HOME_DIR}"

  if [[ -t 0 ]]; then
    echo "Select environment:"
    select ENV_NAME in "${ENV_DIRS[@]}"; do
      if [[ -n "${ENV_NAME:-}" ]]; then
        break
      else
        echo "Invalid selection. Try again."
      fi
    done
  else
    die "No environment specified. Use --env=<name> or run interactively"
  fi
fi

ENV_DIR="${USR_HOME_DIR}/${ENV_NAME}"
[[ -d "${ENV_DIR}" ]] || die "Environment dir not found: ${ENV_DIR}"

echo "Selected environment: ${ENV_NAME}"

# -------- Read profile from group_vars --------
# We need to peek into group_vars to find profile_kind
GROUPVARS_DIR="${ENV_DIR}/group_vars"
[[ -d "${GROUPVARS_DIR}" ]] || die "Missing group_vars directory in ${ENV_DIR}"

# Try to find which group_vars file exists (basekit.yml, baremetal.yml, aws.yml)
PROFILE_KIND=""
for kind in basekit baremetal aws; do
  if [[ -f "${GROUPVARS_DIR}/${kind}.yml" ]]; then
    # Verify it has profile_kind set
    DECLARED_KIND="$(grep -E '^[[:space:]]*profile_kind:' "${GROUPVARS_DIR}/${kind}.yml" | head -1 | awk -F':' '{print $2}' | tr -d " \"'")"
    if [[ "${DECLARED_KIND}" == "${kind}" ]]; then
      PROFILE_KIND="${kind}"
      break
    fi
  fi
done

[[ -n "${PROFILE_KIND}" ]] || die "Could not determine profile kind from ${GROUPVARS_DIR}

Expected one of:
  - group_vars/basekit.yml with 'profile_kind: basekit'
  - group_vars/baremetal.yml with 'profile_kind: baremetal'
  - group_vars/aws.yml with 'profile_kind: aws'"

echo "Profile kind: ${PROFILE_KIND}"

GROUPVARS_FILE="${GROUPVARS_DIR}/${PROFILE_KIND}.yml"

# -------- runtime detection --------
if command -v podman >/dev/null 2>&1; then
  RUNTIME="podman"
  SE_OPT="rw,Z"
elif command -v docker >/dev/null 2>&1; then
  RUNTIME="docker"
  SE_OPT="rw"
else
  die "Neither podman nor docker found in PATH"
fi
echo "Using runtime: ${RUNTIME}"

# -------- resolve onboarder image tar --------
ONBOARDER_TAR="$(grep -E '^[[:space:]]*onboarder:' "${GROUPVARS_FILE}" | head -1 | awk -F':' '{print $2}' | tr -d " \"'")"
[[ -n "${ONBOARDER_TAR}" ]] || die "'onboarder' not set in ${GROUPVARS_FILE}"

IMAGE_ARCHIVE="${DATA_DIR}/images/onboarder/${ONBOARDER_TAR}"
[[ -f "${IMAGE_ARCHIVE}" ]] || die "Onboarder image archive not found: ${IMAGE_ARCHIVE}"

# -------- load image --------
echo "Loading image: ${IMAGE_ARCHIVE}"

# Check if image is already loaded
IMAGE_REF="$(${RUNTIME} images --format '{{.Repository}}:{{.Tag}}' | grep -i 'onboarder' | head -1 || true)"

if [[ -z "${IMAGE_REF}" ]]; then
  echo "Loading container image..."
  ${RUNTIME} load -i "${IMAGE_ARCHIVE}"
  IMAGE_REF="$(${RUNTIME} images --format '{{.Repository}}:{{.Tag}}' | grep -i 'onboarder' | head -1 || true)"
  [[ -n "${IMAGE_REF}" ]] || die "Failed to load image from ${IMAGE_ARCHIVE}"
else
  echo "Image already loaded: ${IMAGE_REF}"
fi

# -------- container name --------
CONTAINER_NAME="onboarder"
if ${RUNTIME} ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "Removing existing container ${CONTAINER_NAME} ..."
  ${RUNTIME} rm -f "${CONTAINER_NAME}" >/dev/null
fi

# -------- logs under env --------
LOG_DIR="${ENV_DIR}/logs"
mkdir -p "${LOG_DIR}"

# -------- run container --------
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# Build the command
CMD_ARGS=(
  "python3" "/install/data/main.py"
  "--env" "${ENV_NAME}"
  "--profile" "${PROFILE_KIND}"
)

[[ -n "${VALIDATE_ONLY}" ]] && CMD_ARGS+=("${VALIDATE_ONLY}")
[[ -n "${RESUME}" ]] && CMD_ARGS+=("${RESUME}")
[[ -n "${VERBOSE}" ]] && CMD_ARGS+=("${VERBOSE}")

echo ""
echo "========================================"
echo "Running Onboarder"
echo "========================================"
echo "Environment: ${ENV_NAME}"
echo "Profile: ${PROFILE_KIND}"
[[ -n "${VALIDATE_ONLY}" ]] && echo "Mode: VALIDATE ONLY"
[[ -n "${RESUME}" ]] && echo "Resume: Yes"
[[ -n "${VERBOSE}" ]] && echo "Verbose: Yes"
echo "Logs: ${LOG_DIR}"
echo "========================================"
echo ""

set -x
${RUNTIME} run \
  --name "${CONTAINER_NAME}" \
  -u "${HOST_UID}:${HOST_GID}" \
  -v "${DATA_DIR}:/install/data:${SE_OPT}" \
  -v "${ENV_DIR}:/install/usr_home/${ENV_NAME}:${SE_OPT}" \
  -v "${LOG_DIR}:/install/logs:${SE_OPT}" \
  -w /install \
  "${IMAGE_REF}" \
  "${CMD_ARGS[@]}"
set +x

EXIT_CODE=$?

echo ""
if [[ ${EXIT_CODE} -eq 0 ]]; then
  echo "✅ Onboarder completed successfully"
else
  echo "❌ Onboarder failed with exit code: ${EXIT_CODE}"
  echo "Check logs in: ${LOG_DIR}"
fi

exit ${EXIT_CODE}