import os

from charmhelpers.contrib.openstack import context
from charmhelpers.core.hookenv import config
from charmhelpers.core.host import pwgen


HEAT_PATH = '/var/lib/heat/'


def generate_ec2_tokens(host, port):
    ec2_tokens = 'http://%s:%s/v2.0/ec2tokens' % (host, port)
    return ec2_tokens


class HeatIdentityServiceContext(context.IdentityServiceContext):
    def __call__(self):
        ctxt = super(HeatIdentityServiceContext, self).__call__()
        if not ctxt:
            return

        # the ec2 api needs to know the location of the keystone ec2
        # tokens endpoint, set in nova.conf
        ec2_tokens = generate_ec2_tokens(ctxt['service_host'],
                                         ctxt['service_port'])
        ctxt['keystone_ec2_url'] = ec2_tokens
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


class EncryptionContext(context.OSContextGenerator):

    def __call__(self):
        ctxt = {}

        # check if we have stored encryption key
        encryption = get_encryption_key()
        ctxt['encryption_key'] = encryption
        return ctxt


class HeatContext(context.OSContextGenerator):
    def __call__(self):
        ctxt = {
            'use_syslog': config('use-syslog')
        }
        return ctxt
