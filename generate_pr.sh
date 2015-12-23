#!/bin/bash

echo $CI_PULL_REQUEST
if [ -n "$CI_PULL_REQUEST" ]; then
	PR_ID=${CI_PULL_REQUES%\*}
	git clone --depth=50 --branch=$CIRCLE_BRANCH  https://github.com/cloudify-cosmo/$CIRCLE_PROJECT_REPONAME.git cloudify-cosmo/$CIRCLE_PROJECT_REPONAME
        cd cloudify-cosmo/$CIRCLE_PROJECT_REPONAME
        git fetch origin +refs/pull/$PR_ID/merge:
	git checkout -qf FETCH_HEAD
 	tox -e docs
        tox -e flake8
        tox -e py27
fi

