#!/bin/bash
# Automatic partition expansion script
# Runs once after system hardening completes

set -e

DISK_DEVICE="/dev/vda"
PARTITION_NUMBER=3
VG_NAME="vg_root"
LOCKFILE="/var/lib/partition-expansion.done"

# Exit if already run
if [ -f "$LOCKFILE" ]; then
    echo "Partition expansion already completed"
    exit 0
fi

echo "=== Starting partition expansion ==="

# Check if partition needs expansion
DISK_END=$(parted $DISK_DEVICE unit s print free 2>/dev/null | grep "Disk $DISK_DEVICE" | awk '{print $3}' | sed 's/s//')
PART_END=$(parted $DISK_DEVICE unit s print 2>/dev/null | grep "^ $PARTITION_NUMBER" | awk '{print $3}' | sed 's/s//')
PART_START=$(parted $DISK_DEVICE unit s print 2>/dev/null | grep "^ $PARTITION_NUMBER" | awk '{print $2}')

if [ "$PART_END" -ge "$((DISK_END - 2048))" ]; then
    echo "Partition already at maximum size"
else
    echo "Expanding partition..."
    parted $DISK_DEVICE --script -- rm $PARTITION_NUMBER 2>&1 || true
    parted $DISK_DEVICE --script -- mkpart primary $PART_START 100% 2>&1 || true
    parted $DISK_DEVICE --script -- set $PARTITION_NUMBER lvm on 2>&1 || true
    
    partprobe $DISK_DEVICE || true
    partx -u $DISK_DEVICE || true
    blockdev --rereadpt $DISK_DEVICE || true
    sleep 3
fi

# Resize PV
echo "Resizing physical volume..."
pvresize ${DISK_DEVICE}${PARTITION_NUMBER}

# Check available space
VG_FREE=$(vgs --noheadings -o vg_free_count $VG_NAME | tr -d ' ')

if [ "$VG_FREE" -gt 0 ]; then
    echo "Extending logical volumes..."
    
    # Extend in order (ignore errors if LV already at size)
    lvextend -l +4%FREE /dev/$VG_NAME/lv_log 2>&1 || echo "lv_log: already at target size"
    xfs_growfs /var/log
    
    lvextend -l +4%FREE /dev/$VG_NAME/lv_vmp 2>&1 || echo "lv_vmp: already at target size"
    xfs_growfs /var/tmp
    
    lvextend -l +4%FREE /dev/$VG_NAME/lv_audit 2>&1 || echo "lv_audit: already at target size"
    xfs_growfs /var/log/audit
    
    lvextend -l +5%FREE /dev/$VG_NAME/lv_tmp 2>&1 || echo "lv_tmp: already at target size"
    xfs_growfs /tmp
    
    lvextend -l +25%FREE /dev/$VG_NAME/lv_home 2>&1 || echo "lv_home: already at target size"
    xfs_growfs /home
    
    lvextend -l +50%FREE /dev/$VG_NAME/lv_var 2>&1 || echo "lv_var: already at target size"
    xfs_growfs /var
    
    lvextend -l +100%FREE /dev/$VG_NAME/lv_root 2>&1 || echo "lv_root: already at target size"
    xfs_growfs /
    
    echo "Logical volumes extended successfully"
else
    echo "No free space available"
fi

# Mark as complete
touch $LOCKFILE
echo "=== Partition expansion complete ==="
df -h
