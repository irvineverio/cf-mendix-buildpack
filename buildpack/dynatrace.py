import logging
import os
import shutil
import json

from buildpack import util

default_env = {
    "DT_TENANTTOKEN": None,  # optional, default to one found in manifest.json
    "DT_APPLICATIONID": None,  # optional, default not set
    "DT_TENANT": None,  # required, environment ID (uuid format)
    # "DT_PAAS_TOKEN": None,  # required
    # "DT_SAAS_URL": None,  # required
    "DT_LOGS_LEVEL": None, # optional, accepted values: CRITICAL, ERROR, WARNING, INFO, DEBUG, TRACE
    "DT_LOGS_PATH": "/tmp/app.logs", # optional, path to app logs. Must be writable by app process
    "DT_LOGSTREAM": "stdout",
    "DT_NETWORK_ZONE": None,  # optional, not sure what this means :D
    "DT_CUSTOM_PROP": None,  # optional metadata e.g. Department=Acceptance Stage=Sprint
    "DT_TAGS": None,  # optional tags e.g. MikesStuff easyTravel=Mike
}


def stage(buildpack_path, build_path):
    if is_enabled():
        agent_url = "{url}/e/{environment}/api/v1/deployment/installer/agent/unix/paas/latest?include=java&bitness=64&Api-Token={token}".format(
            url=os.environ.get("DT_SAAS_URL"),
            environment=os.environ.get("DT_TENANT"),
            token=os.environ.get("DT_PAAS_TOKEN"),
        )

        try:
            util.download_and_unpack(
                agent_url,
                buildpack_path,  # DOT_LOCAL_LOCATION,
                cache_dir=build_path,  # CACHE_DIR,
                unpack=True,
            )
        except Exception as e:
            logging.warning(
                "Dynatrace agent download and unpack failed", exc_info=True
            )


def update_config(m2ee, app_name):
    if not is_enabled():
        logging.debug(
            "Skipping Dynatrace setup, no DT_TENANTTOKEN found in environment"
        )
        return
    logging.info("Enabling Dynatrace")
    try:
        manifest = get_manifest()
    except Exception as e:
        logging.warning(
            "Failed to parse Dynatrace manifest file", exc_info=True
        )
        return

    # dynamic default
    default_env.update({"DT_TENANTTOKEN": manifest.get("tenantToken")})

    m2ee_section = m2ee.config._conf["m2ee"]
    if "custom_environment" not in m2ee_section:
        m2ee_section["custom_environment"] = {}

    for key, dv in default_env.items():
        value = os.environ.get(key, dv)
        if value:
            m2ee_section["custom_environment"][key] = value
    m2ee_section["custom_environment"][
        "DT_CONNECTION_POINT"
    ] = get_connection_endpoint()

    agent_path = os.path.join(".local", get_agent_path())
    if not os.path.exists(agent_path):
        raise Exception(
            "Dynatrace Agent not found: {agent_path}".format(agent_path)
        )

    m2ee.config._conf["m2ee"]["javaopts"].append(
        "-agentpath:{path}".format(path=os.path.abspath(agent_path))
    )
    m2ee.config._conf["m2ee"]["javaopts"].append("-Xshare:off")

    # logs shipping
    logs_level = get_logs_level()
    if logs_level:
        log_path = os.environ.get("DT_LOGS_PATH", "/tmp/out.log")
        util.lazy_remove_file(log_path)
        #os.mkfifo(log_path)
        m2ee.config._conf["logging"].append(
            {
                "type": "file",
                "name": "dynatracesubscriber",
                "autosubscribe": logs_level,
                "filename": log_path,
                "max_size": 1125899906842624,
                "max_rotation": 1,
            }
        )


def get_manifest():
    with open(".local/manifest.json", "r") as f:
        return json.load(f)


def get_connection_endpoint():
    manifest = get_manifest()
    endpoints = manifest.get("communicationEndpoints", [])
    # prepend the DT_SAAS_URL because the communication endpoints might not be correct
    endpoints.insert(
        0, "{url}/communication".format(url=os.environ.get("DT_SAAS_URL"))
    )
    return ";".join(endpoints)


def get_agent_path():
    manifest = get_manifest()
    technologies = manifest.get("technologies")
    java_binaries = technologies.get("java").get("linux-x86-64")
    for f in java_binaries:
        binary_type = f.get("binarytype")
        if binary_type == "loader":
            return f.get("path")


def is_enabled():
    return "DT_PAAS_TOKEN" in os.environ.keys()

def get_logs_level():
    return os.environ.get("DT_LOGS_LEVEL", None)