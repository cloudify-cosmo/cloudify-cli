#!/bin/bash

echo $CI_PULL_REQUEST
if [ -n "$CI_PULL_REQUEST" ]; then
	git clone --depth=50 --branch=$CIRCLE_BRANCH  https://github.com/cloudify-cosmo/$CIRCLE_PROJECT_REPONAME.git cloudify-cosmo/$CIRCLE_PROJECT_REPONAME
        cd cloudify-cosmo/$CIRCLE_PROJECT_REPONAME
        git fetch origin +refs/pull/254/merge:
	git checkout -qf FETCH_HEAD
 	tox -e docs
        tox -e flake8
        tox -e py27
fi

