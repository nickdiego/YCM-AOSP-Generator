#!/usr/bin/env bash

scriptdir=$(cd `dirname $0`; pwd)
aosp_root="/aosp"
ccache=${aosp_root}/prebuilts/misc/linux-x86/ccache/ccache
aosp_root_host=${1:-/home/nick/projects/oma/src/aosp-src/aosp}

echo "# Loading build env"
${ccache} -M 10G >/dev/null
source ${aosp_root}/build/envsetup.sh >/dev/null

echo "# Configuring x86 build"
lunch aosp_x86-eng >/dev/null

echo "# Preparing build.."
outdir=${aosp_root}/out
clean_before=0

# for now do not clear before
# run build
if (( $clean_before )); then
    make -C $aosp_root clean >/dev/null
fi

echo -n "# Generating compilation database files..."
build_with_dependencies=1
#B=bear

if (( $build_with_dependencies )); then
    build_cmd=(make -j6 -nk -C "${aosp_root}" -f 'build/core/main.mk'
        all_modules 'BUILD_MODULES_IN_PATHS=packages/apps/OMA-DM')
else
    export ONE_SHOT_MAKEFILE=packages/apps/OMA-DM/Android.mk
    build_cmd=(make -j6 -C "${aosp_root}" -f 'build/core/main.mk' all_modules)
fi

$B "${build_cmd[@]}" 2>&1 1>build_log.txt && echo "Done." || echo "Failed!"
