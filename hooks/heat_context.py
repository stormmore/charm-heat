import os

from charmhelpers.contrib.openstack import context
from charmhelpers.core.hookenv import config, leader_get
from charmhelpers.core.host import pwgen
from charmhelpers.contrib.hahelpers.cluster import (
    determine_apache_port,
    determine_api_port,
)

HEAT_PATH = '/var/lib/heat/'
API_PORTS = {
    'heat-api-cfn': 8000,
    'heat-api': 8004
}


def generate_ec2_tokens(protocol, host, port):
    ec2_tokens = '%s://%s:%s/v2.0/ec2tokens' % (protocol, host, port)
    return ec2_tokens


class HeatIdentityServiceContext(context.IdentityServiceContext):
    def __call__(self):
        ctxt = super(HeatIdentityServiceContext, self).__call__()
        if not ctxt:
            return

        # the ec2 api needs to know the location of the keystone ec2
        # tokens endpoint, set in nova.conf
        ec2_tokens = generate_ec2_tokens(ctxt['service_protocol'] or 'http',
                                         ctxt['service_host'],
                                         ctxt['service_port'])
        ctxt['keystone_ec2_url'] = ec2_tokens
        ctxt['region'] = config('region')
        return ctxt


def get_encryption_key():
    encryption_path = os.path.join(HEAT_PATH, 'encryption-key')
    if os.path.isfile(encryption_path):
        with open(encryption_path, 'r') as enc:
            encryption = enc.read()
    else:
        # create encryption key and store it
        if not os.path.isdir(HEAT_PATH):
            os.makedirs(HEAT_PATH)
        encryption = config("encryption-key")
        if not encryption:
            # generate random key
            encryption = pwgen(16)
        with open(encryption_path, 'w') as enc:
            enc.write(encryption)
    return encryption


class HeatSecurityContext(context.OSContextGenerator):

    def __call__(self):
        ctxt = {}
        # check if we have stored encryption key
        encryption = get_encryption_key()
        ctxt['encryption_key'] = encryption
        ctxt['heat_domain_admin_passwd'] = leader_get('heat-domain-admin-passwd')
        return ctxt


class HeatHAProxyContext(context.OSContextGenerator):
    interfaces = ['heat-haproxy']

    def __call__(self):
        """Extends the main charmhelpers HAProxyContext with a port mapping
        specific to this charm.
        Also used to extend cinder.conf context with correct api_listening_port
        """
        haproxy_port = API_PORTS['heat-api']
        api_port = determine_api_port(haproxy_port, singlenode_mode=True)
        apache_port = determine_apache_port(haproxy_port, singlenode_mode=True)

        haproxy_cfn_port = API_PORTS['heat-api-cfn']
        api_cfn_port = determine_api_port(haproxy_cfn_port,
                                          singlenode_mode=True)
        apache_cfn_port = determine_apache_port(haproxy_cfn_port,
                                                singlenode_mode=True)

        ctxt = {
            'service_ports': {'heat_api': [haproxy_port, apache_port],
                              'heat_cfn_api': [haproxy_cfn_port,
                                               apache_cfn_port]},
            'api_listen_port': api_port,
            'api_cfn_listen_port': api_cfn_port,
        }
        return ctxt


class HeatApacheSSLContext(context.ApacheSSLContext):

    external_ports = API_PORTS.values()
    service_namespace = 'heat'


class InstanceUserContext(context.OSContextGenerator):

    def __call__(self):
        ctxt = {}

        instance_user = ''
        if config('instance-user'):
            instance_user = config('instance-user')
        ctxt['instance_user'] = instance_user
        return ctxt
