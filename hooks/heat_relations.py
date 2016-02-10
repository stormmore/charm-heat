#!/usr/bin/python

#
# Copyright 2012 Canonical Ltd.
#
# Authors:
#  Yolanda Robla <yolanda.robla@canonical.com>
#

import os
import shutil
import subprocess
import sys

from charmhelpers.core.hookenv import (
    Hooks,
    UnregisteredHookError,
    config,
    charm_dir,
    log,
    relation_ids,
    relation_set,
    open_port,
    unit_get,
    status_set,
    leader_get,
    leader_set,
    is_leader,
)

from charmhelpers.core.host import (
    restart_on_change,
    service_reload,
    pwgen,
)

from charmhelpers.fetch import (
    apt_install,
    apt_update
)

from charmhelpers.contrib.openstack.utils import (
    configure_installation_source,
    openstack_upgrade_available,
    set_os_workload_status,
    sync_db_with_multi_ipv6_addresses,
)

from charmhelpers.contrib.openstack.ip import (
    canonical_url,
    ADMIN,
    INTERNAL,
    PUBLIC,
)

from heat_utils import (
    do_openstack_upgrade,
    restart_map,
    determine_packages,
    migrate_database,
    register_configs,
    HEAT_CONF,
    REQUIRED_INTERFACES,
    setup_ipv6,
)

from heat_context import (
    API_PORTS,
)

from charmhelpers.payload.execd import execd_preinstall

hooks = Hooks()
CONFIGS = register_configs()


@hooks.hook('install.real')
def install():
    status_set('maintenance', 'Executing pre-install')
    execd_preinstall()
    configure_installation_source(config('openstack-origin'))
    status_set('maintenance', 'Installing apt packages')
    apt_update()
    apt_install(determine_packages(), fatal=True)

    _files = os.path.join(charm_dir(), 'files')
    if os.path.isdir(_files):
        for f in os.listdir(_files):
            f = os.path.join(_files, f)
            log('Installing %s to /usr/bin' % f)
            shutil.copy2(f, '/usr/bin')

    for port in API_PORTS.values():
        open_port(port)


@hooks.hook('config-changed')
@restart_on_change(restart_map())
def config_changed():
    if not config('action-managed-upgrade'):
        if openstack_upgrade_available('heat-common'):
            status_set('maintenance', 'Running openstack upgrade')
            do_openstack_upgrade(CONFIGS)

    if config('prefer-ipv6'):
        status_set('maintenance', 'configuring ipv6')
        setup_ipv6()
        sync_db_with_multi_ipv6_addresses(config('database'),
                                          config('database-user'),
                                          relation_prefix='heat')

    CONFIGS.write_all()
    configure_https()


@hooks.hook('upgrade-charm')
def upgrade_charm():
    leader_elected()


@hooks.hook('amqp-relation-joined')
def amqp_joined(relation_id=None):
    relation_set(relation_id=relation_id,
                 username=config('rabbit-user'), vhost=config('rabbit-vhost'))


@hooks.hook('amqp-relation-changed')
@restart_on_change(restart_map())
def amqp_changed():
    if 'amqp' not in CONFIGS.complete_contexts():
        log('amqp relation incomplete. Peer not ready?')
        return
    CONFIGS.write(HEAT_CONF)


@hooks.hook('shared-db-relation-joined')
def db_joined():
    if config('prefer-ipv6'):
        sync_db_with_multi_ipv6_addresses(config('database'),
                                          config('database-user'),
                                          relation_prefix='heat')
    else:
        relation_set(heat_database=config('database'),
                     heat_username=config('database-user'),
                     heat_hostname=unit_get('private-address'))


@hooks.hook('shared-db-relation-changed')
@restart_on_change(restart_map())
def db_changed():
    if 'shared-db' not in CONFIGS.complete_contexts():
        log('shared-db relation incomplete. Peer not ready?')
        return
    CONFIGS.write(HEAT_CONF)
    migrate_database()


def configure_https():
    """Enables SSL API Apache config if appropriate."""
    # need to write all to ensure changes to the entire request pipeline
    # propagate (c-api, haprxy, apache)
    CONFIGS.write_all()
    if 'https' in CONFIGS.complete_contexts():
        cmd = ['a2ensite', 'openstack_https_frontend']
        subprocess.check_call(cmd)
    else:
        cmd = ['a2dissite', 'openstack_https_frontend']
        subprocess.check_call(cmd)

    # TODO: improve this by checking if local CN certs are available
    # first then checking reload status (see LP #1433114).
    service_reload('apache2', restart_on_failure=True)

    for rid in relation_ids('identity-service'):
        identity_joined(rid=rid)


@hooks.hook('identity-service-relation-joined')
def identity_joined(rid=None):
    public_url_base = canonical_url(CONFIGS, PUBLIC)
    internal_url_base = canonical_url(CONFIGS, INTERNAL)
    admin_url_base = canonical_url(CONFIGS, ADMIN)

    api_url_template = '%s:8004/v1/$(tenant_id)s'
    public_api_endpoint = (api_url_template % public_url_base)
    internal_api_endpoint = (api_url_template % internal_url_base)
    admin_api_endpoint = (api_url_template % admin_url_base)

    cfn_url_template = '%s:8000/v1'
    public_cfn_endpoint = (cfn_url_template % public_url_base)
    internal_cfn_endpoint = (cfn_url_template % internal_url_base)
    admin_cfn_endpoint = (cfn_url_template % admin_url_base)

    relation_data = {
        'heat_service': 'heat',
        'heat_region': config('region'),
        'heat_public_url': public_api_endpoint,
        'heat_admin_url': admin_api_endpoint,
        'heat_internal_url': internal_api_endpoint,
        'heat-cfn_service': 'heat-cfn',
        'heat-cfn_region': config('region'),
        'heat-cfn_public_url': public_cfn_endpoint,
        'heat-cfn_admin_url': admin_cfn_endpoint,
        'heat-cfn_internal_url': internal_cfn_endpoint,
    }

    relation_set(relation_id=rid, **relation_data)


@hooks.hook('identity-service-relation-changed')
@restart_on_change(restart_map())
def identity_changed():
    if 'identity-service' not in CONFIGS.complete_contexts():
        log('identity-service relation incomplete. Peer not ready?')
        return

    CONFIGS.write_all()
    configure_https()


@hooks.hook('amqp-relation-broken',
            'identity-service-relation-broken',
            'shared-db-relation-broken')
def relation_broken():
    CONFIGS.write_all()


@hooks.hook('leader-elected')
def leader_elected():
    if is_leader() and not leader_get('heat-domain-admin-passwd'):
        leader_set({'heat-domain-admin-passwd': pwgen(32)})


def main():
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))
    set_os_workload_status(CONFIGS, REQUIRED_INTERFACES)


if __name__ == '__main__':
    main()
