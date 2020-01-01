#!/bin/bash
set -ex

export GITHUB_USERNAME=$1
export GITHUB_TOKEN=$2
export AWS_ACCESS_KEY_ID=$3
export AWS_ACCESS_KEY=$4
export REPO=$5
export BRANCH=$6
export CORE_BRANCH="master"

set +e
. /etc/profile.d/rvm.sh
set -e

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

install_common_prereqs
cd packaging/omnibus
export CLI_BRANCH="$CORE_BRANCH"

# Get Omnibus software from Chef Omnibus repo
rm -rf omnibus-software
git clone https://github.com/chef/omnibus-software.git --depth 1 -q
list_of_omnibus_softwares="gdbm cacerts config_guess gdbm libffi makedepend
    ncurses openssl pkg-config-lite setuptools
    util-macros version-manifest xproto zlib"
for omnibus_softwate in $list_of_omnibus_softwares
do
    if [[ -e omnibus-software/config/software/$omnibus_softwate.rb ]] ; then
        cp -r omnibus-software/config/software/$omnibus_softwate.rb \
        config/software/$omnibus_softwate.rb
    else
        echo "Missing software in Omnibus-Software repo"
        exit
    fi

    [[ -e omnibus-software/config/patches/$omnibus_softwate ]] &&
    cp -r omnibus-software/config/patches/$omnibus_softwate config/patches/
done

[ ! -d config/templates/ ] && mkdir config/templates/ 
cp -r omnibus-software/config/templates/* config/templates/
curl https://raw.githubusercontent.com/chef/omnibus-software/master/config/software/preparation.rb -o config/software/preparation.rb
curl https://raw.githubusercontent.com/systemizer/omnibus-software/master/config/software/pip.rb -o config/software/pip.rb

if [[ "$OSTYPE" == "darwin"* ]]; then
    grep -l '/opt' config/software/* | xargs sed -i "" 's|/opt|/usr/local/opt|g'
fi

omnibus build cloudify && result="success"
cd pkg
cat *.json || exit 1
rm -f version-manifest.json
[ $(ls | grep rpm | sed -n 2p ) ] && FILEEXT="rpm"
[ $(ls | grep deb | sed -n 2p ) ] && FILEEXT="deb"
[ $(ls | grep pkg | sed -n 2p ) ] && FILEEXT="pkg"

#remove the -1 - omnibus set the build_iteration to 1 if it null
file=$(basename $(find . -type f -name "*.$FILEEXT"))
echo "file=$file"
file_no_build=$(echo "$file" | sed 's/\(.*\)-1/\1/' | sed 's/cloudify/cloudify-cli/')
echo "file_no_build=$file_no_build"
mv $file $file_no_build

if [[ ! -z $BRANCH ]] && [[ "$BRANCH" != "master" ]] ; then
    AWS_S3_PATH="$AWS_S3_PATH/$BRANCH"
fi

[ "$result" == "success" ] && create_md5 $FILEEXT &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 $FILEEXT && upload_to_s3 "md5" &&
upload_to_s3 "json"
