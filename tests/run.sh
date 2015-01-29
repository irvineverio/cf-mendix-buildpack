#!/bin/bash
set -e

cf_org="mendix-rnd.com"
cf_space="continuous-integration"
cf_app_prefix="buildpack-testing"
cf_app="${cf_app_prefix}-${BUILD_NUMBER}"
cf_endpoint=api.run.pivotal.io
cf_buildpack="https://github.com/mendix/cf-mendix-buildpack.git#testing"
cf_db="${cf_app}-db"
mx_admin_password="$(openssl rand -hex 10)@AA"
cf_mda="tests/app/app.mda"
cf_app_domain="cfapps.io"
cf_app_url="https://${cf_app}.${cf_app_domain}/xas/"
cf_memory="512M"
cf_cli_url="https://cli.run.pivotal.io/stable?release=linux64-binary&version=6.9.0&source=github-rel"
cf_failed_builds_to_keep=1

tests_init() {
    if [ ! -x ./cf ] ; then
        wget -O - "${cf_cli_url}" | tar zxf -
    fi

    export CF_HOME="$WORKSPACE"
    export MX_ADMIN_PASSWORD="${mx_admin_password}"
    export MX_APP_URL="${cf_app_url}"

    if [ -z "$CF_HOME" ] ; then
        echo "WORKSPACE environment variable has to be set!"
        exit 1
    fi

    if [ ! -d "lib/mxplient" ] ; then
        git clone gitlab@gitlab.srv.hq.mendix.net:rnd/mxplient.git lib/mxplient
    else
        cd lib/mxplient
        git pull
        cd -
    fi

    [ -d "venv" ] && rm -rf "venv"
    virtualenv venv
    source venv/bin/activate
    pip install -r requirements.txt
}

cf_init() {
    ./cf api ${cf_endpoint}
    ./cf auth "$CF_USERNAME" "$CF_PASSWORD" || (echo "Authentication failed!"; exit 1)
    ./cf target -o $cf_org || (echo "Unable to select correct org, expecting: ${cf_org}"; exit 1)
    ./cf target -s $cf_space || (echo "Unable to select correct space, expecting: ${cf_space}"; exit 1)
}

clean_old_builds() {
    old_apps=$(./cf apps | grep "^$cf_app_prefix" | awk '{print $1}' | sort -n -t - -k 3 | head -n -${cf_failed_builds_to_keep})
    if [ ! -z "$old_apps" ] ; then
        for app in "$old_apps" ; do
            app_db=${app}-db
            ./cf delete $app -f
            ./cf delete-service $app_db -f &> /dev/null || echo "Cannot find service" $app_db
            ./cf delete-route $cf_app_domain -n $app -f &> /dev/null || echo "Cannot find route" $app
        done
    fi
}

cf_push_mda() {
    ./cf push ${cf_app} -m ${cf_memory} -b ${cf_buildpack} -p ${cf_mda} --no-start
    ./cf create-service elephantsql turtle ${cf_db}
    ./cf bind-service ${cf_app} ${cf_db}
    ./cf set-env ${cf_app} ADMIN_PASSWORD "${mx_admin_password}"
    ./cf push ${cf_app} -m ${cf_memory} -b ${cf_buildpack} -p ${cf_mda}
}


clean() {
    ./cf delete $cf_app -f
    ./cf delete-route $cf_app_domain -n $cf_app -f
    ./cf delete-service $cf_db -f
}

set -x

tests_init
cf_init

clean_old_builds
cf_push_mda

python venv/bin/nosetests -vv --with-xunit tests/usecases

clean
