#!/bin/bash
set -e

# Check the number of input parameters.
if [ $# -ne 1 ]; then
    echo "usage: $0 [config_path]"
    exit 1
fi
# Get the config path.
config_path=$1
# Check if config path exists.
if [ ! -d "$config_path" ]; then
    echo "$config_path does not exist"
    exit 1
fi

# Remove the old version.
rm -rf "$config_path/custom_components/xiaomi_home"
# Get the script path.
script_path=$(dirname "$0")
# Change to the script path.
cd "$script_path"
# Copy the new version.
cp -r custom_components/xiaomi_home/  "$config_path/custom_components/"

# Done.
echo "Xiaomi Home installation is completed. Please restart Home Assistant."
exit 0
