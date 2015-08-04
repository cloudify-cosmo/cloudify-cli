function install_prereqs
{
    if which apt-get; then
        # ubuntu
        sudo apt-get -y update &&
        # precise
        sudo apt-get install -y python-software-properties
        # # trusty
        # sudo apt-get install -y software-properties-common
        # sudo add-apt-repository -y ppa:git-core/ppa &&
        sudo apt-get install -y curl python-dev git make gcc libyaml-dev zlib1g-dev g++ rpm
    elif which yum; then
        echo "UPDATING LOCAL REPO"
        sudo yum -y --exclude=kernel\* update &&
        sudo yum install -y yum-downloadonly wget mlocate yum-utils s3cmd
        sudo yum install -y python-devel libyaml-devel ruby rubygems ruby-devel make gcc g++ git rpm-build libxml2-devel libxslt-devel
    else
        echo 'unsupported package manager, exiting'
        exit 1
    fi
}

function install_ruby
{
    wget http://mirrors.ibiblio.org/ruby/1.9/ruby-1.9.3-rc1.tar.gz --no-check-certificate
    tar -xzvf ruby-1.9.3-rc1.tar.gz
    cd ruby-1.9.3-rc1
    ./configure --disable-install-doc
    make
    sudo make install
    cd ~
}

function install_fpm
{
    sudo gem install fpm -v 1.3.3 --no-ri --no-rdoc
    sudo which fpm
    RESULT=$?
    if [ $RESULT -ne 0 ]; then
        FPM_PATH="$(which fpm)"
        sudo ln -s $FPM_PATH /bin/fpm
        # sudo ln -s /usr/local/bin/fpm /bin/fpm
    fi
    # if we want to downlod gems as a part of the packman run, this should be enabled
    # echo -e 'gem: --no-ri --no-rdoc\ninstall: --no-rdoc --no-ri\nupdate:  --no-rdoc --no-ri' >> ~/.gemrc
}

function install_pip
{
    if ! which pip >> /dev/null; then
        if which apt-get; then
            curl --silent --show-error --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python
        else
            curl --silent --show-error --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python2.7
        fi
    fi
}

function install_module
{

    module=$1
    venv=${2:-""}
    tag=${3:-""}
    if [[ ! -z "$tag" ]]; then
        org=${4:-cloudify-cosmo}
        url=https://github.com/${org}/${module}.git
        echo cloning ${url}
        git clone ${url}
        pushd ${module}
            git checkout -b tmp_branch ${tag}
            git log -1
            sudo ${venv}/bin/pip install .
        popd
    else
        if [[ ! -z "$venv" ]]; then
            # if [[ ! -z "$tag" ]]; then
            #   pip install git+git://github.com/${org}/${module}.git@${tag}#egg=${module}
            # else
            sudo ${venv}/bin/pip install ${module}
            # fi
        else
            sudo pip install ${module}
        fi
    fi
}

function install_py27
{
    # install python and additions
    # http://bicofino.io/blog/2014/01/16/installing-python-2-dot-7-6-on-centos-6-dot-5/
    sudo yum groupinstall -y 'development tools'
    sudo yum install -y zlib-devel bzip2-devel openssl-devel xz-libs
    sudo mkdir /py27
    cd /py27
    sudo wget http://www.python.org/ftp/python/2.7.6/Python-2.7.6.tar.xz
    sudo xz -d Python-2.7.6.tar.xz
    sudo tar -xvf Python-2.7.6.tar
    cd Python-2.7.6
    sudo ./configure --prefix=/usr
    sudo make
    sudo make altinstall
    if which python2.7; then
        alias python=python2.7
    fi
}

function copy_version_file
{
    pushd /cfy/wheelhouse/
      sudo mkdir -p cloudify_cli
      sudo cp -f /cloudify-cli/VERSION cloudify_cli
      cloudify_cli=$(basename `find . -name cloudify-*.whl`)
      sudo zip $cloudify_cli cloudify_cli/VERSION
      sudo rm -f cloudify_cli
    popd
}

function get_wheels
{
    echo "Retrieving Wheels"
    sudo pip wheel virtualenv==12.0.7 &&
    # when the cli is built for py2.6, unless argparse is put within `install_requires`, we'll have to enable this:
    # if which yum; then
    #   pip wheel argparse==#SOME_VERSION#
    # fi
    sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-rest-client@${CORE_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-dsl-parser@${CORE_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-plugins-common@${CORE_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-script-plugin@${PLUGINS_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-fabric-plugin@${PLUGINS_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-openstack-plugin@${PLUGINS_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-aws-plugin@${PLUGINS_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://${GITHUB_USERNAME}:${GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-vsphere-plugin@${PLUGINS_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://${GITHUB_USERNAME}:${GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-softlayer-plugin@${PLUGINS_TAG_NAME} --find-links=wheelhouse &&
    sudo pip wheel git+https://github.com/cloudify-cosmo/cloudify-cli@${CORE_TAG_NAME} --find-links=wheelhouse
    copy_version_file
}

function get_manager_blueprints
{
    sudo curl -O http://cloudify-public-repositories.s3.amazonaws.com/cloudify-manager-blueprints/${CORE_TAG_NAME}/cloudify-manager-blueprints.tar.gz &&
    sudo tar -zxvf cloudify-manager-blueprints.tar.gz &&
    sudo rm cloudify-manager-blueprints.tar.gz &&
    echo "Retrieving Manager Blueprints"
}

function get_license
{
    # copy license to virtualenv
	lic_dir="cloudify-license"
	sudo mkdir -p ${lic_dir}
    sudo cp -f /cloudify-cli/docker/cloudify-ui/LICENSE ${lic_dir}
}

CORE_TAG_NAME="master"
PLUGINS_TAG_NAME="master"
GITHUB_USERNAME=$1
GITHUB_PASSWORD=$2
AWS_ACCESS_KEY=$3
AWS_SECRET_KEY=$4
AWS_S3_BUCKET=$5
AWS_S3_BUCKET_PREFIX=$6

install_prereqs &&
# if which apt-get; then
#     install_ruby
# fi
if which yum; then
    if ! which python2.7 >> /dev/null; then
        install_py27
    else
        alias python=python2.7
    fi
fi
# install_fpm &&
# install_pip &&
# install_module "packman==0.5.0" &&
# install_module "wheel==0.24.0" &&

sudo mkdir -p /cfy && cd /cfy &&

echo '# GET PROCESS'
get_license &&
get_wheels &&
get_manager_blueprints &&

cd /cloudify-cli/ && sudo pkm pack -c cloudify-linux-cli -v

if [ ! -z ${AWS_ACCESS_KEY} ]; then
    s3cmd -d --access_key=${AWS_ACCESS_KEY_ID} --secret_key=${AWS_SECRET_KEY} --progress -H -p --check-md5 --continue-put put /cloudify/* s3://${AWS_S3_BUCKET}/${AWS_S3_BUCKET_PREFIX}
fi