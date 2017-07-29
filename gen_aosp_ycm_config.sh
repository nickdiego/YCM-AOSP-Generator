#!/usr/bin/env bash

set -e

scriptdir=$(cd `dirname $0`; pwd)
config_cmd=${scriptdir}/config_gen.py
aosp_root="/aosp"
ccache=${aosp_root}/prebuilts/misc/linux-x86/ccache/ccache
opts=(
	-m "packages/apps/OMA-DM"
    #-m "bionic/libc"
    -p "/home/nick/projects/oma/src/aosp-src/aosp"
    -v "${aosp_root}" )

echo "#### Loading build env.."
${ccache} -M 10G
echo "#### Loading build env.."
source ${aosp_root}/build/envsetup.sh
echo
echo "#### Configuring x86 build..."
lunch aosp_x86-eng
echo
mkdir -pv ${scriptdir}/logs
echo "#### Running '${config_cmd} ${opts[@]}' ..."
${config_cmd} "${opts[@]}"
