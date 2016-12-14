#/bin/bash -e

export GITHUB_USERNAME=$1
export GITHUB_PASSWORD=$2
AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4
CLI_BRANCH=$5
PACKAGER_BRANCH=$6
export PREMIUM=$7

CORE_TAG_NAME="4.0m10"

curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/$CORE_TAG_NAME/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

if [ "$PREMIUM" == "true" ]; then
    export AWS_S3_PATH=$AWS_S3_PATH"/"$PREMIUM_FOLDER
fi
echo "AWS_S3_PATH=$AWS_S3_PATH"

install_common_prereqs &&
rm -rf cloudify-cli
git clone https://github.com/cloudify-cosmo/cloudify-cli.git
cd cloudify-cli/packaging/omnibus
git checkout ${CLI_BRANCH-$CORE_TAG_NAME}
git tag -d $CORE_TAG_NAME
NEW_TAG_NAME="${VERSION}.${PRERELEASE}"
git -d tag $NEW_TAG_NAME
git tag $NEW_TAG_NAME
omnibus build cloudify && result="success"
cd pkg
cat *.json || exit 1
rm -f version-manifest.json
[ $(ls | grep rpm | sed -n 2p ) ] && FILEEXT="rpm"
[ $(ls | grep deb | sed -n 2p ) ] && FILEEXT="deb"

#remove the -1 - omnibus set the build_iteration to 1 if it null
file=$(basename $(find . -type f -name "*.$FILEEXT"))
file_no_build=$(echo "$file" | sed 's/\-1//')
mv $file $file_no_build

[ "$result" == "success" ] && create_md5 $FILEEXT &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 $FILEEXT && upload_to_s3 "md5" &&
upload_to_s3 "json"
