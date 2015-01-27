#!/bin/sh
set -x
set -e

cf_org="mendix-rnd.com"
cf_space="continuous-integration"
cf_app="buildpack-testing"
cf_buildpack="https://github.com/mendix/cf-mendix-buildpack.git"
cf_db="${cf_app}-db"
mx_admin_password="c+onT5bWvGBM34A5eUP5Dobk6uk"
cf_mda="app.mda"

which cf || (echo "Cloudfoundry CLI not installed, please install it first"; exit 1)
cf target -o $cf_org || (echo "Unable to select correct org, expecting: ${cf_org}"; exit 1)
cf target -s $cf_space || (echo "Unable to select correct space, expecting: ${cf_space}"; exit 1)

cd ./tests/app
cf app ${cf_app} &>/dev/null && cf delete -f ${cf_app}
cf service ${cf_db} &>/dev/null && cf delete-service -f ${cf_db}

cf push ${cf_app} -b ${cf_buildpack} -p ${cf_mda} --no-start
cf create-service elephantsql turtle ${cf_db}

