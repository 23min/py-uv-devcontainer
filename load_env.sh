#!/bin/bash

# Temporary file to store the merged environment variables
temp_env_file="/workspace/.env/.env.combined"

# Clear the temporary file if it exists
> "$temp_env_file"

# Append variables from each .env file
cat /workspace/.env/.env.common >> "$temp_env_file"
cat /workspace/.env/.env.dev >> "$temp_env_file"
cat /workspace/.env/.env.sensors-fake >> "$temp_env_file"

echo "Combined .env files written to $temp_env_file"
