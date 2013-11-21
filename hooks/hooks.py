#!/usr/bin/python

#
# Copyright 2012 Canonical Ltd.
#
# Authors:
#  Yolanda Robla <yolanda.robla@canonical.com>
#

import glob
import os
import shutil
import sys

from subprocess import check_call
from urlparse import urlparse

from charmhelpers.core.hookenv import (
    Hooks,
    UnregisteredHookError,
    config,
    charm_dir,
    log,
    ERROR,
    relation_get,
    relation_ids,
    relation_set,
    open_port,
    unit_get
)

from charmhelpers.core.host import (
    restart_on_change
)

from charmhelpers.fetch import (
    apt_install,
    apt_update
)

from charmhelpers.contrib.openstack.utils import (
    configure_installation_source,
)

from utils import (
    api_port,
    auth_token_config,
    determine_endpoints,
    determine_packages,
    determine_ports,
    keystone_ca_cert_b64,
    save_script_rc,
    register_configs,
    restart_map,
    HEAT_CONF
)

from charmhelpers.payload.execd import execd_preinstall

hooks = Hooks()
CONFIGS = register_configs()


@hooks.hook('install')
def install():
    execd_preinstall()
    configure_installation_source(config('openstack-origin'))
    apt_update()
    apt_install(determine_packages(), fatal=True)

    _files = os.path.join(charm_dir(), 'files')
    if os.path.isdir(_files):
        for f in os.listdir(_files):
            f = os.path.join(_files, f)
            log('Installing %s to /usr/bin' % f)
            shutil.copy2(f, '/usr/bin')
    [open_port(port) for port in determine_ports()]

@hooks.hook('config-changed')
@restart_on_change(restart_map())
def config_changed():
    save_script_rc()
    CONFIGS.write_all()


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
    check_call(['heat-manage', 'db_sync'])


@hooks.hook('identity-service-relation-joined')
def identity_joined(rid=None):
    base_url = canonical_url(CONFIGS)
    relation_set(relation_id=rid, **determine_endpoints(base_url))


@hooks.hook('identity-service-relation-changed')
@restart_on_change(restart_map())
def identity_changed():
    if 'identity-service' not in CONFIGS.complete_contexts():
        log('identity-service relation incomplete. Peer not ready?')
        return
    CONFIGS.write('/etc/heat/api-paste.ini')
    CONFIGS.write(HEAT_CONF)


def _auth_config():
    '''Grab all KS auth token config from api-paste.ini, or return empty {}'''
    ks_auth_host = auth_token_config('auth_host')
    if not ks_auth_host:
        # if there is no auth_host set, identity-service changed hooks
        # have not fired, yet.
        return {}
    cfg = {
        'auth_host': ks_auth_host,
        'auth_port': auth_token_config('auth_port'),
        'service_port': auth_token_config('service_port'),
        'service_username': auth_token_config('admin_user'),
        'service_password': auth_token_config('admin_password'),
        'service_tenant_name': auth_token_config('admin_tenant_name'),
        'auth_uri': auth_token_config('auth_uri')
    }
    return cfg


def keystone_compute_settings():
    ks_auth_config = _auth_config()
    rel_settings = {}

    ks_ca = keystone_ca_cert_b64()
    if ks_auth_config and ks_ca:
        rel_settings['ca_cert'] = ks_ca

    return rel_settings


@hooks.hook('amqp-relation-broken',
            'identity-service-relation-broken',
            'shared-db-relation-broken')
def relation_broken():
    CONFIGS.write_all()


@hooks.hook('upgrade-charm')
def upgrade_charm():
    for r_id in relation_ids('amqp'):
        amqp_joined(relation_id=r_id)


def main():
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))


if __name__ == '__main__':
    main()
