#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Cleanup previous NODE files to ensure a fresh run ---
# Note: We no longer delete host keys here automatically.
rm -f node_*.key node.ca
echo "Cleaned up old node and certificate files."
echo

# --- Step 1: Generate Host Keys (if they don't exist) ---
echo "======================================================"
echo "STEP 1: CHECKING FOR/GENERATING HOST MASTER KEYS"
echo "======================================================"
python3 generate_host_keys.py

# Check if the host private key exists after running the script
if [ ! -f "host_sk.key" ]; then
    echo "Error: Host private key file 'host_sk.key' was not found or could not be created."
    exit 1
fi
echo
echo "Host key setup complete."
echo

# --- Step 2: Generate Node Keys and CA ---
echo "=========================================================="
echo "STEP 2: GENERATING NODE KEYS AND CA (SIGNED BY HOST KEY)"
echo "=========================================================="
python3 generate_node_ca.py --host-sk-file host_sk.key
echo
echo "Node key and CA generation complete."
echo

# --- Final ---
echo "========================================="
echo "          PROCESS COMPLETE"
echo "========================================="
echo