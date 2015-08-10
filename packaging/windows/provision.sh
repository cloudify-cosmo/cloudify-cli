export CORE_TAG_NAME="master"
export PLUGINS_TAG_NAME="master"
# export VERSION=`cat packaging/VERSION  | grep version | sed 's/"version": "//g' | sed 's/"//g' | sed 's/,//g' | sed 's/ //g'`
export VERSION="3.3.0-m4"
# echo "VERSION=$VERSION"

pip install wheel

pip wheel --wheel-dir packaging/source/wheels https://github.com/cloudify-cosmo/cloudify-cli/archive/$CORE_TAG_NAME.zip#egg=cloudify-cli \
https://github.com/cloudify-cosmo/cloudify-rest-client/archive/$CORE_TAG_NAME.zip#egg=cloudify-rest-client \
https://github.com/cloudify-cosmo/cloudify-dsl-parser/archive/$CORE_TAG_NAME.zip#egg=cloudify-dsl-parser \
https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/$CORE_TAG_NAME.zip#egg=cloudify-plugins-common \
https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-script-plugin

pushd packaging/source/pip
curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/get-pip.py
curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/pip-6.1.1-py2.py3-none-any.whl
curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/setuptools-15.2-py2.py3-none-any.whl
popd
pushd packaging/source/python
curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/python/python.msi
popd
pushd packaging/source/virtualenv
curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/virtualenv/virtualenv-12.1.1-py2.py3-none-any.whl
popd


# export VERSION_FILE=$(cat packaging/VERSION)

# python packaging/update_wheel.py --path packaging/source/wheels/cloudify-*.whl --name cloudify_cli/VERSION --data "$VERSION_FILE"
# mv packaging/source/wheels/cloudify-*.whl-new packaging/source/wheels/cloudify-*.whl

iscc packaging/create_install_wizard.iss
