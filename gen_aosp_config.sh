#!/usr/bin/env bash

set -e

scriptdir=$(cd `dirname $0`; pwd)
config_cmd=${scriptdir}/config_gen.py
aosp_root="/aosp"
ccache=${aosp_root}/prebuilts/misc/linux-x86/ccache/ccache
aosp_root_host=${1:-/home/nick/projects/oma/src/aosp-src/aosp}
opts=(
    '--forma=all'
    '--module=packages/apps/OMA-DM'
    "--include-prefix=${aosp_root_host}"
    --verbose "${aosp_root}" )

echo "# Loading build env"
source ${aosp_root}/build/envsetup.sh >/dev/null

echo "# Configuring x86 build"
lunch aosp_x86-eng >/dev/null
unset -v USE_CCACHE
mkdir -p ${scriptdir}/logs

echo "# Generating YCM/ColorCoded files..."
echo "# cmd: ${config_cmd} ${opts[@]}"
python ${config_cmd} "${opts[@]}"
