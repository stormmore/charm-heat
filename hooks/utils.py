#
# Copyright 2012 Canonical Ltd.
#
# Authors:
#  Yolanda Robla <yolanda.robla@canonical.com>
#

import os
import subprocess
import ConfigParser

from base64 import b64encode
from collections import OrderedDict
from copy import deepcopy

from charmhelpers.contrib.openstack import context, templating

from charmhelpers.contrib.openstack.utils import (
    configure_installation_source,
    get_host_ip,
    get_hostname,
    get_os_codename_install_source,
    is_ip,
    os_release,
    save_script_rc as _save_script_rc)

from charmhelpers.fetch import (
    apt_install,
    apt_update,
)

from charmhelpers.core.hookenv import (
    config,
    log,
    relation_get,
    relation_ids,
    remote_unit,
    INFO,
    ERROR,
)

import heat_context

TEMPLATES = 'templates/'

BASE_PACKAGES = [
    'python-keystoneclient',
    'uuid',
]

BASE_SERVICES = [
    'heat-api',
    'heat-api-cfn',
    'heat-engine'
]

API_PORTS = {
    'heat-api-cfn': 8000,
    'heat-api': 8004
}

HEAT_CONF = '/etc/heat/heat.conf'
HEAT_API_PASTE = '/etc/heat/api-paste.ini'

CONFIG_FILES = OrderedDict([
    (HEAT_CONF, {
        'services': BASE_SERVICES,
        'contexts': [context.AMQPContext(),
                     context.SharedDBContext(relation_prefix='heat'),
                     context.OSConfigFlagContext(),
                     context.IdentityServiceContext()]
    }),
    (HEAT_API_PASTE, {
        'services': [s for s in BASE_SERVICES if 'api' in s],
        'contexts': [context.IdentityServiceContext()],
    })
])

CA_CERT_PATH = '/usr/local/share/ca-certificates/keystone_juju_ca_cert.crt'


def register_configs():
    release = os_release('heat-engine')
    configs = templating.OSConfigRenderer(templates_dir=TEMPLATES,
                                          openstack_release=release)

    confs = [HEAT_CONF, HEAT_API_PASTE]
    for conf in confs:
        configs.register(conf, CONFIG_FILES[conf]['contexts'])

    return configs


def api_port(service):
    return API_PORTS[service]


def determine_packages():
    # currently all packages match service names
    packages = BASE_PACKAGES + BASE_SERVICES
    return list(set(packages))


def save_script_rc():
    env_vars = {
        'OPENSTACK_SERVICE_API': 'heat-api',
        'OPENSTACK_SERVICE_API_CFN': 'heat-api-cfn',
        'OPENSTACK_SERVICE_ENGINE': 'heat-engine'
    }
    _save_script_rc(**env_vars)


def auth_token_config(setting):
    '''
    Returns currently configured value for setting in api-paste.ini's
    authtoken section, or None.
    '''
    config = ConfigParser.RawConfigParser()
    config.read('/etc/heat/api-paste.ini')
    try:
        value = config.get('filter:authtoken', setting)
    except:
        return None
    if value.startswith('%'):
        return None
    return value
