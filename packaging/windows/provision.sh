#!/bin/bash -e

function install_requirements() {
    pip install wheel==0.24.0
}

function download_wheels() {
    GITHUB_USERNAME=$1
    GITHUB_TOKEN=$2

    mkdir -p packaging/source/wheels
    curl -LO https://pypi.python.org/packages/2.7/l/lxml/lxml-3.5.0.win32-py2.7.exe
    wheel convert lxml-3.5.0.win32-py2.7.exe --dest-dir packaging/source/wheels

    PATCH_URL="https://raw.githubusercontent.com/cloudify-cosmo/cloudify-cli/${CLI_BRANCH}/packaging/omnibus/config/patches/cloudify-cli/cloudify_cli.patch"
    curl -sLO https://github.com/cloudify-cosmo/cloudify-cli/archive/${CLI_BRANCH}.zip
    unzip -q -o ${CLI_BRANCH}.zip
    [[ -f ${CLI_BRANCH}.zip ]] && rm -f ${CLI_BRANCH}.zip
    curl -sL "${PATCH_URL}" -o cloudify-cli-${CLI_BRANCH}/cloudify_cli.patch
    patch -p1 -d cloudify-cli-${CLI_BRANCH} < cloudify-cli-${CLI_BRANCH}/cloudify_cli.patch
    rm -f cloudify-cli-${CLI_BRANCH}/cloudify_cli.patch
    zip -q -r cloudify-cli-${CLI_BRANCH}.zip cloudify-cli-${CLI_BRANCH}
    [[ $? -eq 0 ]] && rm -rf cloudify-cli-${CLI_BRANCH}

    pip wheel --wheel-dir packaging/source/wheels --find-links packaging/source/wheels C:/Cygwin/home/Administrator/cloudify-cli-${CLI_BRANCH}.zip \
    https://github.com/cloudify-cosmo/cloudify-common/archive/${CORE_BRANCH}.zip#egg=cloudify-common \
    https://github.com/cloudify-cosmo/cloudify-fabric-plugin/archive/1.5.2.zip#egg=cloudify-fabric-plugin

    # Rename "Bad" wheels
    pushd packaging/source/wheels
        for file in *cp27m*; do
            a="$(echo $file | sed s/-cp27m-/-none-/)"
            mv -v "$file" "$a"
        done
    popd

}

function download_resources() {

    GITHUB_USERNAME=$1
    GITHUB_TOKEN=$2

    mkdir -p packaging/source/{python,types,scripts,plugins}
    pushd packaging/source/python
        curl -L https://cloudify-release-eu.s3.amazonaws.com/cloudify/components/Python279_x32.tar.gz -o /tmp/Python279_x32.tar.gz
        tar -zxvf /tmp/Python279_x32.tar.gz --strip-components=1
    popd

    # Downloading types.yaml
    pushd packaging/source/types
        curl -LO http://cloudify.co/spec/cloudify/${CORE_TAG_NAME}/types.yaml
    popd

}

function update_remote_to_local_links() {
    sed -i -e 's/https:\/\/raw\.githubusercontent\.com\/cloudify-cosmo\/cloudify-manager\/.*\/resources\/rest-service\/cloudify\/.*\//file:\/cfy\/cloudify\/scripts\//g' packaging/source/types/types.yaml
}

# VERSION/PRERELEASE/BUILD/CORE_BRANCH/PLUGINS_TAG_NAME must be exported as they are being read as an env var by the install wizard

export GITHUB_USERNAME=$1
export GITHUB_TOKEN=$2
export AWS_ACCESS_KEY_ID=$3
export AWS_ACCESS_KEY=$4
export REPO=$5
export BRANCH=$6
export CORE_TAG_NAME="5.0.5"
export CORE_BRANCH="master"

set +x
export current_branch=$CORE_BRANCH && curl -u $GITHUB_USERNAME:$GITHUB_TOKEN -fO "https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/common_build_env.sh" || \
              export current_branch=master && curl -u $GITHUB_USERNAME:$GITHUB_TOKEN -fO "https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/master/packages-urls/common_build_env.sh"

echo Gotten Environment Variables from here: https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${current_branch}/packages-urls/common_build_env.sh
. $PWD/common_build_env.sh &&


export current_branch=$CORE_BRANCH && curl -fO "https://raw.githubusercontent.com/cloudify-cosmo/cloudify-common/${CORE_BRANCH}/packaging/common/provision.sh" || \
              export current_branch=master && curl -u $GITHUB_USERNAME:$GITHUB_TOKEN -fO "https://raw.githubusercontent.com/cloudify-cosmo/cloudify-common/master/packaging/common/provision.sh"

echo Gotten provision script from here: https://raw.githubusercontent.com/cloudify-cosmo/cloudify-common/${current_branch}/packaging/common/provision.sh
. $PWD/provision.sh &&
set -x

export CLI_BRANCH="$CORE_BRANCH"
if [ "$CORE_BRANCH" != "master" ] && [ "$REPO" == "cloudify-versions" ]; then
    source packaging/source_branch
fi
if [[ ! -z $BRANCH ]] && [[ "$BRANCH" != "master" ]];then
    pushd /tmp
        curl -sLO https://github.com/cloudify-cosmo/cloudify-cli/archive/${BRANCH}.zip
        if zip -T $BRANCH.zip > /dev/null; then
            export CLI_BRANCH="$BRANCH"
            AWS_S3_PATH="$AWS_S3_PATH/$BRANCH"
        fi
    popd
fi
install_common_prereqs &&
#install_requirements && # moved to cloudify-common
download_wheels $GITHUB_USERNAME $GITHUB_TOKEN &&
download_resources $GITHUB_USERNAME $GITHUB_TOKEN &&
update_remote_to_local_links &&
iscc packaging/create_install_wizard.iss &&
cd /home/Administrator/packaging/output/ && create_md5 "exe"  &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "exe" && upload_to_s3 "md5"
