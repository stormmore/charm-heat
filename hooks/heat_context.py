from charmhelpers.core.hookenv import (
    config, relation_ids, relation_set, log, ERROR)

from charmhelpers.fetch import apt_install, filter_installed_packages
from charmhelpers.contrib.openstack import context, neutron, utils

from charmhelpers.contrib.hahelpers.cluster import (
    determine_api_port, determine_haproxy_port)


class IdentityServiceContext(context.IdentityServiceContext):
    def __call__(self):
        ctxt = super(IdentityServiceContext, self).__call__()
        if not ctxt:
            return

        # the ec2 api needs to know the location of the keystone ec2
        # tokens endpoint, set in heat.conf
        ec2_tokens = 'http://%s:%s/v2.0/ec2tokens' % (ctxt['service_host'],
                                                      ctxt['service_port'])
        ctxt['keystone_ec2_url'] = ec2_tokens
        return ctxt
