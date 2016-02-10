#
# Copyright 2012 Canonical Ltd.
#
# Authors:
#  Yolanda Robla <yolanda.robla@canonical.com>
#
import os

from collections import OrderedDict
from subprocess import check_call

from charmhelpers.contrib.openstack import context, templating

from charmhelpers.contrib.openstack.utils import (
    configure_installation_source,
    get_os_codename_install_source,
    os_release)

from charmhelpers.fetch import (
    add_source,
    apt_install,
    apt_update,
    apt_upgrade,
)

from charmhelpers.core.hookenv import (
    log,
    config,
)

from charmhelpers.core.host import (
    lsb_release,
    service_start,
    service_stop,
)

from heat_context import (
    API_PORTS,
    HeatIdentityServiceContext,
    HeatSecurityContext,
    InstanceUserContext,
    HeatApacheSSLContext,
    HeatHAProxyContext,
)

TEMPLATES = 'templates/'

# The interface is said to be satisfied if anyone of the interfaces in
# the list has a complete context.
REQUIRED_INTERFACES = {
    'database': ['shared-db'],
    'messaging': ['amqp'],
    'identity': ['identity-service'],
}

BASE_PACKAGES = [
    'python-keystoneclient',
    'python-swiftclient',  # work-around missing epoch in juno heat package
    'python-six',
    'uuid',
    'apache2',
    'haproxy',
]

BASE_SERVICES = [
    'heat-api',
    'heat-api-cfn',
    'heat-engine'
]

SVC = 'heat'
HEAT_DIR = '/etc/heat'
HEAT_CONF = '/etc/heat/heat.conf'
HEAT_API_PASTE = '/etc/heat/api-paste.ini'
HAPROXY_CONF = '/etc/haproxy/haproxy.cfg'
HTTPS_APACHE_CONF = '/etc/apache2/sites-available/openstack_https_frontend'
HTTPS_APACHE_24_CONF = os.path.join('/etc/apache2/sites-available',
                                    'openstack_https_frontend.conf')

CONFIG_FILES = OrderedDict([
    (HEAT_CONF, {
        'services': BASE_SERVICES,
        'contexts': [context.AMQPContext(ssl_dir=HEAT_DIR),
                     context.SharedDBContext(relation_prefix='heat',
                                             ssl_dir=HEAT_DIR),
                     context.OSConfigFlagContext(),
                     HeatIdentityServiceContext(service=SVC, service_user=SVC),
                     HeatHAProxyContext(),
                     HeatSecurityContext(),
                     InstanceUserContext(),
                     context.SyslogContext(),
                     context.LogLevelContext(),
                     context.BindHostContext()]
    }),
    (HEAT_API_PASTE, {
        'services': [s for s in BASE_SERVICES if 'api' in s],
        'contexts': [HeatIdentityServiceContext()],
    }),
    (HAPROXY_CONF, {
        'contexts': [context.HAProxyContext(singlenode_mode=True),
                     HeatHAProxyContext()],
        'services': ['haproxy'],
    }),
    (HTTPS_APACHE_CONF, {
        'contexts': [HeatApacheSSLContext()],
        'services': ['apache2'],
    }),
    (HTTPS_APACHE_24_CONF, {
        'contexts': [HeatApacheSSLContext()],
        'services': ['apache2'],
    })
])


def register_configs():
    release = os_release('heat-common')
    configs = templating.OSConfigRenderer(templates_dir=TEMPLATES,
                                          openstack_release=release)

    confs = [HEAT_CONF, HEAT_API_PASTE, HAPROXY_CONF]
    for conf in confs:
        configs.register(conf, CONFIG_FILES[conf]['contexts'])

    if os.path.exists('/etc/apache2/conf-available'):
        configs.register(HTTPS_APACHE_24_CONF,
                         CONFIG_FILES[HTTPS_APACHE_24_CONF]['contexts'])
    else:
        configs.register(HTTPS_APACHE_CONF,
                         CONFIG_FILES[HTTPS_APACHE_CONF]['contexts'])

    return configs


def api_port(service):
    return API_PORTS[service]


def determine_packages():
    # currently all packages match service names
    packages = BASE_PACKAGES + BASE_SERVICES
    return list(set(packages))


def do_openstack_upgrade(configs):
    """Perform an uprade of heat.

    Takes care of upgrading packages,
    rewriting configs and potentially any other post-upgrade
    actions.

    :param configs: The charms main OSConfigRenderer object.

    """
    new_src = config('openstack-origin')
    new_os_rel = get_os_codename_install_source(new_src)

    log('Performing OpenStack upgrade to %s.' % (new_os_rel))

    configure_installation_source(new_src)
    dpkg_opts = [
        '--option', 'Dpkg::Options::=--force-confnew',
        '--option', 'Dpkg::Options::=--force-confdef',
    ]
    apt_update()
    apt_upgrade(options=dpkg_opts, fatal=True, dist=True)
    packages = BASE_PACKAGES + BASE_SERVICES
    apt_install(packages=packages, options=dpkg_opts, fatal=True)

    # set CONFIGS to load templates from new release and regenerate config
    configs.set_release(openstack_release=new_os_rel)
    configs.write_all()

    migrate_database()


def restart_map():
    """Restarts on config change.

    Determine the correct resource map to be passed to
    charmhelpers.core.restart_on_change() based on the services configured.

    :returns: dict: A dictionary mapping config file to lists of services
    that should be restarted when file changes.
    """
    _map = []
    for f, ctxt in CONFIG_FILES.iteritems():
        svcs = []
        for svc in ctxt['services']:
            svcs.append(svc)
        if svcs:
            _map.append((f, svcs))
    return OrderedDict(_map)


def services():
    """Returns a list of services associate with this charm"""
    _services = []
    for v in restart_map().values():
        _services = _services + v
    return list(set(_services))


def migrate_database():
    """Runs heat-manage to initialize a new database or migrate existing"""
    log('Migrating the heat database.')
    [service_stop(s) for s in services()]
    check_call(['heat-manage', 'db_sync'])
    [service_start(s) for s in services()]


def setup_ipv6():
    ubuntu_rel = lsb_release()['DISTRIB_CODENAME'].lower()
    if ubuntu_rel < "trusty":
        raise Exception("IPv6 is not supported in the charms for Ubuntu "
                        "versions less than Trusty 14.04")

    # Need haproxy >= 1.5.3 for ipv6 so for Trusty if we are <= Kilo we need to
    # use trusty-backports otherwise we can use the UCA.
    if ubuntu_rel == 'trusty' and os_release('heat-common') < 'liberty':
        add_source('deb http://archive.ubuntu.com/ubuntu trusty-backports '
                   'main')
        apt_update()
        apt_install('haproxy/trusty-backports', fatal=True)
