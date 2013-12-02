import subprocess
import os

from charmhelpers.core.hookenv import config
from charmhelpers.contrib.openstack import context

HEAT_PATH = '/var/lib/heat/'


class IdentityServiceContext(context.IdentityServiceContext):
    def __call__(self):
        ctxt = super(IdentityServiceContext, self).__call__()
        if not ctxt:
            return

        # the ec2 api needs to know the location of the keystone ec2
        # tokens endpoint, set in nova.conf
        ec2_tokens = 'http://%s:%s/v2.0/ec2tokens' % (ctxt['service_host'],
                                                      ctxt['service_port'])
        ctxt['keystone_ec2_url'] = ec2_tokens
        return ctxt


class EncryptionContext(context.OSContextGenerator):
    def __call__(self):
        ctxt = {}

        # check if we have stored encryption key
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
                cmd = 'hexdump -n 16 -v -e \'/1 "%02x"\' /dev/random'
                encryption = subprocess.check_output(cmd, shell=True).strip()
            with open(encryption_path, 'w') as enc:
                enc.write(encryption)

        ctxt['encryption_key'] = encryption
        return ctxt
