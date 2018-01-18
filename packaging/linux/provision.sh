#/bin/bash -e -x

export GITHUB_USERNAME=$1
export GITHUB_PASSWORD=$2
AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4
PACKAGER_BRANCH=$5
export REPO=$6
export CORE_TAG_NAME="4.3.dev1"
export CORE_BRANCH="18.1.25-build"


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

# Linux Preperation
function prepare_linux () {
    sudo chmod 777 /opt
    if  which yum >> /dev/null; then
        sudo yum install -y http://opensource.wandisco.com/centos/6/git/x86_64/wandisco-git-release-6-1.noarch.rpm
        sudo yum install -y git fakeroot python-devel rpm-build
        sudo curl -sSL https://rvm.io/mpapis.asc | gpg2 --import -
    else
        sudo apt-get install -y git curl fakeroot python-dev
        sudo curl -sSL https://rvm.io/mpapis.asc | gpg --import -
    fi
    
    sudo curl -L get.rvm.io | bash -s stable
    
    if  which yum >> /dev/null; then
        source /etc/profile.d/rvm.sh
    else
        source /home/admin/.rvm/scripts/rvm
    fi
    rvm install 2.2.1 && rvm use 2.2.1
    gem install bundler -v '=1.8.4' --no-ri --no-rdoc
    gem install omnibus --no-ri --no-rdoc
}

if [[ "$OSTYPE" == "darwin"* ]]; then
    prepare_osx
else
    prepare_linux
fi
echo "curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/common_build_env.sh -o ./common_build_env.sh"
echo "curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/${CORE_BRANCH}/common/provision.sh -o ./common-provision.sh"

echo "CORE_BRANCH=${CORE_BRANCH}"
curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/common_build_env.sh -o ./common_build_env.sh &&
source common_build_env.sh &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/${CORE_BRANCH}/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

install_common_prereqs &&
rm -rf cloudify-cli
git clone https://github.com/cloudify-cosmo/cloudify-cli.git
cd ~/cloudify-cli/packaging/omnibus
if [ "$CORE_BRANCH" != "master" ]; then
    echo "in if ###"
    export CLI_BRANCH="$CORE_BRANCH"
    echo "CLI_BRANCH=${CLI_BRANCH}"
    echo "REPO=${REPO}"
    if [ "${REPO}" == "cloudify-versions" ]; then
        source ~/cloudify-cli/packaging/source_branch
        echo "CORE_BRANCH=${CORE_BRANCH}"
    fi
    git checkout -b ${CLI_BRANCH} origin/${CLI_BRANCH}
else
    git checkout ${CLI_BRANCH}
fi

# Get Omnibus software from Chef Omnibus repo
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

[ "$result" == "success" ] && create_md5 $FILEEXT &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 $FILEEXT && upload_to_s3 "md5" &&
upload_to_s3 "json"
