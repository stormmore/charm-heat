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

BASE_RESOURCE_MAP = OrderedDict([
    (HEAT_CONF, {
        'services': BASE_SERVICES,
        'contexts': [context.AMQPContext(),
                     context.SharedDBContext(relation_prefix='nova'),
                     context.OSConfigFlagContext(),
                     heat_context.IdentityServiceContext()]
    }),
    (HEAT_API_PASTE, {
        'services': [s for s in BASE_SERVICES if 'api' in s],
        'contexts': [heat_context.IdentityServiceContext()],
    })
])

CA_CERT_PATH = '/usr/local/share/ca-certificates/keystone_juju_ca_cert.crt'

def resource_map():
    '''
    Dynamically generate a map of resources that will be managed for a single
    hook execution.
    '''
    resource_map = deepcopy(BASE_RESOURCE_MAP)

    return resource_map


def register_configs():
    release = os_release('heat-engine')
    configs = templating.OSConfigRenderer(templates_dir=TEMPLATES,
                                          openstack_release=release)
    for cfg, rscs in resource_map().iteritems():
        configs.register(cfg, rscs['contexts'])
    return configs


def restart_map():
    return OrderedDict([(cfg, v['services'])
                        for cfg, v in resource_map().iteritems()
                        if v['services']])


def determine_ports():
    '''Assemble a list of API ports for services we are managing'''
    ports = []
    for cfg, services in restart_map().iteritems():
        for service in services:
            try:
                ports.append(API_PORTS[service])
            except KeyError:
                pass
    return list(set(ports))


def api_port(service):
    return API_PORTS[service]


def determine_packages():
    # currently all packages match service names
    packages = [] + BASE_PACKAGES
    for k, v in resource_map().iteritems():
        packages.extend(v['services'])
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


def keystone_ca_cert_b64():
    '''Returns the local Keystone-provided CA cert if it exists, or None.'''
    if not os.path.isfile(CA_CERT_PATH):
        return None
    with open(CA_CERT_PATH) as _in:
        return b64encode(_in.read())


def determine_endpoints(url):
    '''Generates a dictionary containing all relevant endpoints to be
    passed to keystone as relation settings.'''
    region = config('region')

    heat_url = ('%s:%s/$(tenant_id)s' %
                (url, api_port('heat-api-cfn')))

    # the base endpoints
    endpoints = {
        'heat_service': 'heat',
    }

    return endpoints
