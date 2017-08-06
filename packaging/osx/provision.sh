#/bin/bash -e

export GITHUB_USERNAME=$1
export GITHUB_PASSWORD=$2
AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4
CLI_BRANCH=$5
PACKAGER_BRANCH=$6
export REPO=$7
export CORE_TAG_NAME="4.2.dev1"
export VERSION="4.2.dev1"
export PRERELEASE="4.2.dev1"
export CORE_BRANCH="master"

curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/common_build_env.sh -o ./common_build_env.sh &&
source common_build_env.sh &&
curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/manager-single-tar.yaml -o ./manager-single-tar.yaml &&
export SINGLE_TAR_URL=$(cat manager-single-tar.yaml)

curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/${PACKAGER_BRANCH}/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh


install_common_prereqs &&
rm -rf cloudify-cli
git clone -b add-osx-support https://github.com/cloudify-cosmo/cloudify-cli.git

# OSX manipulation
ditto cloudify-cli/packaging/osx/osx-resources/patches/ cloudify-cli/packaging/omnibus/config/patches/
ditto cloudify-cli/packaging/osx/osx-resources/software/ cloudify-cli/packaging/omnibus/config/software/
ditto cloudify-cli/packaging/osx/osx-resources/templates/ cloudify-cli/packaging/omnibus/config/templates/
grep -l '/opt' cloudify-cli/packaging/omnibus/config/software/* | xargs sed -i "" 's|/opt|/usr/local/opt|g'

cd cloudify-cli/packaging/omnibus
gitTagExists=$(git tag -l $CORE_TAG_NAME)
if [ "$CORE_BRANCH" != "master" ]; then
    git checkout -b ${CORE_BRANCH} origin/${CORE_BRANCH}
else
    git checkout ${CORE_BRANCH}
fi
export tag=4.2.dev1

omnibus build cloudify && result="success"
cd pkg
cat *.json || exit 1
rm -f version-manifest.json
[ $(ls | grep pkg | sed -n 2p ) ] && FILEEXT="pkg"

#remove the -1 - omnibus set the build_iteration to 1 if it null
file=$(basename $(find . -type f -name "*.$FILEEXT"))
echo "file=$file"
file_no_build=$(echo "$file" | sed 's/\(.*\)-1/\1/')
echo "file_no_build=$file_no_build"
mv $file $file_no_build

[ "$result" == "success" ] && create_md5 $FILEEXT &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 $FILEEXT && upload_to_s3 "md5"
upload_to_s3 "json"