import heat_context
from mock import patch
from test_utils import CharmTestCase

TO_PATCH = [
    'get_encryption_key',
    'generate_ec2_tokens',
    'config',
    'leader_get',
]


class TestHeatContext(CharmTestCase):

    def setUp(self):
        super(TestHeatContext, self).setUp(heat_context, TO_PATCH)

    def test_encryption_configuration(self):
        self.get_encryption_key.return_value = 'key'
        self.leader_get.return_value = 'password'
        self.assertEquals(
            heat_context.HeatSecurityContext()(),
            {'encryption_key': 'key',
             'heat_domain_admin_passwd': 'password'})
        self.leader_get.assert_called_with('heat-domain-admin-passwd')

    def test_instance_user_empty_configuration(self):
        self.config.return_value = None
        self.assertEquals(
            heat_context.InstanceUserContext()(),
            {'instance_user': ''})

    @patch('charmhelpers.contrib.openstack.'
           'context.IdentityServiceContext.__call__')
    def test_identity_configuration(self, __call__):
        __call__.return_value = {
            'service_port': 'port',
            'service_host': 'host',
            'auth_host': 'host',
            'auth_port': 'port',
            'admin_tenant_name': 'tenant',
            'admin_user': 'user',
            'admin_password': 'pass',
            'service_protocol': 'http',
            'auth_protocol': 'http'}
        self.generate_ec2_tokens.return_value = \
            'http://host:port/v2.0/ec2tokens'

        final_result = __call__.return_value
        final_result['keystone_ec2_url'] = \
            self.generate_ec2_tokens.return_value

        self.assertEquals(
            heat_context.HeatIdentityServiceContext()(), final_result)
