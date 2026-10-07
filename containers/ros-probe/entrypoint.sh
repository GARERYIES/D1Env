#!/bin/bash
set -e
if [ "$#" -ne 1 ]; then
    echo "probe requires exactly one fixed role" >&2
    exit 2
fi
case "$1" in
    publisher|subscriber|idle) ;;
    *) echo "unsupported probe role" >&2; exit 2 ;;
esac
# Trusted, digest-locked official ROS environment; never a user-provided shell configuration.
source /opt/ros/humble/setup.bash
exec python3 /opt/d1env/probe.py "$1"
