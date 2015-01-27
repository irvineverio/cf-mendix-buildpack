#!/bin/bash
set -e

cf_org="mendix-rnd.com"
cf_space="continuous-integration"
cf_app="buildpack-testing-${RANDOM}"
cf_buildpack="https://github.com/mendix/cf-mendix-buildpack.git"
cf_db="$cf_app-db"
mx_admin_password="c+onT5bWvGBM34A5eUP5Dobk6uk"
cf_mda="tests/app/app.mda"
cf_app_domain="cfapps.io"
cf_app_url="https://${cf_app}.${cf_app_domain}/xas/"
cf_memory="512M"
cf_push_cmd="push ${cf_app} -m ${cf_memory} -b ${cf_buildpack} -p ${cf_mda}"

set -x

wget -O - "https://cli.run.pivotal.io/stable?release=linux64-binary&version=6.9.0&source=github-rel" | tar zxf -
./cf target -o $cf_org || (echo "Unable to select correct org, expecting: ${cf_org}"; exit 1)
./cf target -s $cf_space || (echo "Unable to select correct space, expecting: ${cf_space}"; exit 1)

./cf app ${cf_app} &>/dev/null && cf delete -f ${cf_app}
./cf service ${cf_db} &>/dev/null && cf delete-service -f ${cf_db}

./cf push ${cf_app} -m ${cf_memory} -b ${cf_buildpack} -p ${cf_mda} --no-start
./cf create-service elephantsql turtle ${cf_db}
./cf bind-service ${cf_app} ${cf_db}
./cf set-env ${cf_app} ADMIN_PASSWORD $(pwgen -y 20 1)
./cf push ${cf_app} -m ${cf_memory} -b ${cf_buildpack} -p ${cf_mda}

# insert tests here
http_code=$(curl -s -o /dev/null -w "%{http_code}" ${cf_app_url})

return_code=0
expected_code=401
if [[ $http_code -ne $expected_code ]] ; then
    return_code=$http_code
    echo "Wrong http code $http_code, expected $expected_code"
fi

./cf delete $cf_app -f
./cf delete-route $cf_app_domain -n $cf_app -f
./cf delete-service $cf_db -f
exit $return_code
