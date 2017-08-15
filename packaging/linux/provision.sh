#/bin/bash -e

export GITHUB_USERNAME=$1
export GITHUB_PASSWORD=$2
AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4
CLI_BRANCH=$5
PACKAGER_BRANCH=$6
export REPO=$7
export CORE_TAG_NAME="4.2.dev1"
export CORE_BRANCH="master"

curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/common_build_env.sh -o ./common_build_env.sh &&
source common_build_env.sh &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/${CORE_BRANCH}/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh
if [ $REPO == "cloudify-versions" ];then
     curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/manager-single-tar.yaml -o ./manager-single-tar.yaml
 else
     curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/manager-single-tar-release.yaml -o ./manager-single-tar.yaml
fi
export SINGLE_TAR_URL=$(cat manager-single-tar.yaml)


install_common_prereqs &&
rm -rf cloudify-cli
git clone https://github.com/cloudify-cosmo/cloudify-cli.git
cd cloudify-cli/packaging/omnibus
gitTagExists=$(git tag -l $CORE_TAG_NAME)
if [ "$CORE_BRANCH" != "master" ]; then
    #git checkout -b ${CORE_BRANCH} origin/${CORE_BRANCH}
    git checkout -b add-osx-support origin/add-osx-support
else
    git checkout ${CORE_BRANCH}
fi

# OSX preparation
function prepare_osx () {
    which -s brew
    if [[ $? != 0 ]] ; then
        echo "Missing Brew isntaller - Make sure your system has Brew"
        echo "Install Brew with sudo and run agian"
    else
        echo "Brew already installed. Updating"
        brew update
    fi
    brew install rbenv ruby-build

    if [[ 'grep "if which rbenv" ~/.bash_profile' != 0 ]]; then
        source ~/.bash_profile
    else
        echo 'if which rbenv > /dev/null; then eval "$(rbenv init -)"; fi' >> ~/.bash_profile
        source ~/.bash_profile
    fi

    if [[ $(rbenv version | cut -d' ' -f1) != '2.2.1' ]] ; then
        echo "Installing rbenv version 2.2.1"
        rbenv install 2.2.1 -s
    else
        echo "rbenv 2.2.1 is installed"
    fi
    rbenv global 2.2.1
    if [[ $(gem list |grep bundler) != 'bundler (1.8.4)' ]] ; then
        gem install bundler -v '=1.8.4' --no-ri --no-rdoc
    fi
    which -s omnibus
    if [[ $? != 0 ]] ; then
        gem install omnibus --no-ri --no-rdoc
    fi
}

# OSX manipulation
if [[ "$OSTYPE" == "darwin"* ]]; then
    prepare_osx
    # Get Omnibus software from Chef Omnibus repo
    mkdir omnibus_source
    git clone https://github.com/chef/omnibus-software.git --depth 1
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
    cp -r omnibus-software/config/templates/* config/templates/
    curl https://raw.githubusercontent.com/chef/omnibus-software/master/config/software/preparation.rb -o config/software/preparation.rb
    curl https://raw.githubusercontent.com/systemizer/omnibus-software/master/config/software/pip.rb -o config/software/pip.rb
    grep -l '/opt' config/software/* | xargs sed -i "" 's|/opt|/usr/local/opt|g'
fi


omnibus build cloudify && result="success"
cd pkg
cat *.json || exit 1
rm -f version-manifest.json
[ $(ls | grep rpm | sed -n 2p ) ] && FILEEXT="rpm"
[ $(ls | grep deb | sed -n 2p ) ] && FILEEXT="deb"

#remove the -1 - omnibus set the build_iteration to 1 if it null
file=$(basename $(find . -type f -name "*.$FILEEXT"))
echo "file=$file"
file_no_build=$(echo "$file" | sed 's/\(.*\)-1/\1/')
echo "file_no_build=$file_no_build"
mv $file $file_no_build

[ "$result" == "success" ] && create_md5 $FILEEXT &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 $FILEEXT && upload_to_s3 "md5" &&
upload_to_s3 "json"
