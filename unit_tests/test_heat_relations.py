from mock import call, patch, MagicMock

from test_utils import CharmTestCase

import heat_utils as utils

_reg = utils.register_configs
_map = utils.restart_map

utils.register_configs = MagicMock()
utils.restart_map = MagicMock()

import heat_relations as relations

utils.register_configs = _reg
utils.restart_map = _map

TO_PATCH = [
    # charmhelpers.core.hookenv
    'Hooks',
    'config',
    'open_port',
    'relation_set',
    'unit_get',
    # charmhelpers.core.host
    'apt_install',
    'apt_update',
    'restart_on_change',
    # charmhelpers.contrib.openstack.utils
    'configure_installation_source',
    'openstack_upgrade_available',
    'determine_packages',
    'charm_dir',
    # charmhelpers.contrib.hahelpers.cluster_utils
    # heat_utils
    'restart_map',
    'register_configs',
    'do_openstack_upgrade',
    # other
    'execd_preinstall',
    'log',
    'migrate_database',
]


class HeatRelationTests(CharmTestCase):

    def setUp(self):
        super(HeatRelationTests, self).setUp(relations, TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.charm_dir.return_value = '/var/lib/juju/charms/heat/charm'

    def test_install_hook(self):
        repo = 'cloud:precise-havana'
        self.determine_packages.return_value = [
            'python-keystoneclient', 'uuid', 'heat-api',
            'heat-api-cfn', 'heat-engine']
        self.test_config.set('openstack-origin', repo)
        relations.install()
        self.configure_installation_source.assert_called_with(repo)
        self.assertTrue(self.apt_update.called)
        self.apt_install.assert_called_with(['python-keystoneclient',
                                             'uuid', 'heat-api',
                                             'heat-api-cfn',
                                             'heat-engine'], fatal=True)
        self.assertTrue(self.execd_preinstall.called)

    @patch.object(relations, 'configure_https')
    def test_config_changed_no_upgrade(self, mock_configure_https):
        self.openstack_upgrade_available.return_value = False
        relations.config_changed()

    @patch.object(relations, 'configure_https')
    def test_config_changed_with_upgrade(self, mock_configure_https):
        self.openstack_upgrade_available.return_value = True
        relations.config_changed()
        self.assertTrue(self.do_openstack_upgrade.called)

    @patch.object(relations, 'configure_https')
    def test_config_changed_with_openstack_upgrade_action(
            self,
            mock_configure_https):
        self.openstack_upgrade_available.return_value = True
        self.test_config.set('action-managed-upgrade', True)

        relations.config_changed()

        self.assertFalse(self.do_openstack_upgrade.called)

    def test_db_joined(self):
        self.unit_get.return_value = 'heat.foohost.com'
        relations.db_joined()
        self.relation_set.assert_called_with(heat_database='heat',
                                             heat_username='heat',
                                             heat_hostname='heat.foohost.com')
        self.unit_get.assert_called_with('private-address')

    def _shared_db_test(self, configs):
        configs.complete_contexts = MagicMock()
        configs.complete_contexts.return_value = ['shared-db']
        configs.write = MagicMock()
        relations.db_changed()
        self.assertTrue(self.migrate_database.called)

    @patch.object(relations, 'CONFIGS')
    def test_db_changed(self, configs):
        self._shared_db_test(configs)
        self.assertEquals([call('/etc/heat/heat.conf')],
                          configs.write.call_args_list)

    @patch.object(relations, 'CONFIGS')
    def test_db_changed_missing_relation_data(self, configs):
        configs.complete_contexts = MagicMock()
        configs.complete_contexts.return_value = []
        relations.db_changed()
        self.log.assert_called_with(
            'shared-db relation incomplete. Peer not ready?'
        )

    def test_amqp_joined(self):
        relations.amqp_joined()
        self.relation_set.assert_called_with(
            username='heat',
            vhost='openstack',
            relation_id=None)

    def test_amqp_joined_passes_relation_id(self):
        "Ensures relation_id correct passed to relation_set"
        relations.amqp_joined(relation_id='heat:1')
        self.relation_set.assert_called_with(username='heat',
                                             vhost='openstack',
                                             relation_id='heat:1')

    @patch.object(relations, 'CONFIGS')
    def test_amqp_changed_relation_data(self, configs):
        configs.complete_contexts = MagicMock()
        configs.complete_contexts.return_value = ['amqp']
        configs.write = MagicMock()
        relations.amqp_changed()
        self.assertEquals([call('/etc/heat/heat.conf')],
                          configs.write.call_args_list)

    @patch.object(relations, 'CONFIGS')
    def test_amqp_changed_missing_relation_data(self, configs):
        configs.complete_contexts = MagicMock()
        configs.complete_contexts.return_value = []
        relations.amqp_changed()
        self.assertTrue(self.log.called)

    @patch.object(relations, 'CONFIGS')
    def test_relation_broken(self, configs):
        relations.relation_broken()
        self.assertTrue(configs.write_all.called)

    @patch.object(relations, 'canonical_url')
    def test_identity_service_joined(self, _canonical_url):
        "It properly requests unclustered endpoint via identity-service"
        self.unit_get.return_value = 'heatnode1'
        _canonical_url.return_value = 'http://heatnode1'
        relations.identity_joined()
        expected = {
            'heat_service': 'heat',
            'heat_region': 'RegionOne',
            'heat_public_url': 'http://heatnode1:8004/v1/$(tenant_id)s',
            'heat_admin_url': 'http://heatnode1:8004/v1/$(tenant_id)s',
            'heat_internal_url': 'http://heatnode1:8004/v1/$(tenant_id)s',
            'heat-cfn_service': 'heat-cfn',
            'heat-cfn_region': 'RegionOne',
            'heat-cfn_public_url': 'http://heatnode1:8000/v1',
            'heat-cfn_admin_url': 'http://heatnode1:8000/v1',
            'heat-cfn_internal_url': 'http://heatnode1:8000/v1',
            'relation_id': None,
        }
        self.relation_set.assert_called_with(**expected)

    @patch.object(relations, 'canonical_url')
    def test_identity_service_joined_with_relation_id(self, _canonical_url):
        _canonical_url.return_value = 'http://heatnode1'
        relations.identity_joined(rid='identity-service:0')
        ex = {
            'heat_service': 'heat',
            'heat_region': 'RegionOne',
            'heat_public_url': 'http://heatnode1:8004/v1/$(tenant_id)s',
            'heat_admin_url': 'http://heatnode1:8004/v1/$(tenant_id)s',
            'heat_internal_url': 'http://heatnode1:8004/v1/$(tenant_id)s',
            'heat-cfn_service': 'heat-cfn',
            'heat-cfn_region': 'RegionOne',
            'heat-cfn_public_url': 'http://heatnode1:8000/v1',
            'heat-cfn_admin_url': 'http://heatnode1:8000/v1',
            'heat-cfn_internal_url': 'http://heatnode1:8000/v1',
            'relation_id': 'identity-service:0',
        }
        self.relation_set.assert_called_with(**ex)

    @patch('charmhelpers.contrib.openstack.ip.unit_get',
           lambda *args: 'heatnode1')
    @patch('charmhelpers.contrib.openstack.ip.is_clustered',
           lambda *args: False)
    @patch('charmhelpers.contrib.openstack.ip.service_name')
    @patch('charmhelpers.contrib.openstack.ip.config')
    def test_identity_service_public_address_override(self, ip_config,
                                                      _service_name):
        ip_config.side_effect = self.test_config.get
        _service_name.return_value = 'heat'
        self.test_config.set('os-public-hostname', 'heat.example.org')
        relations.identity_joined(rid='identity-service:0')
        exp = {
            'heat_service': 'heat',
            'heat_region': 'RegionOne',
            'heat_public_url': 'http://heat.example.org:8004/v1/$(tenant_id)s',
            'heat_admin_url': 'http://heatnode1:8004/v1/$(tenant_id)s',
            'heat_internal_url': 'http://heatnode1:8004/v1/$(tenant_id)s',
            'heat-cfn_service': 'heat-cfn',
            'heat-cfn_region': 'RegionOne',
            'heat-cfn_public_url': 'http://heat.example.org:8000/v1',
            'heat-cfn_admin_url': 'http://heatnode1:8000/v1',
            'heat-cfn_internal_url': 'http://heatnode1:8000/v1',
            'relation_id': 'identity-service:0',
        }
        self.relation_set.assert_called_with(**exp)

    @patch.object(relations, 'configure_https')
    @patch.object(relations, 'CONFIGS')
    def test_identity_changed(self, configs, mock_configure_https):
        configs.complete_contexts.return_value = ['identity-service']
        relations.identity_changed()
        self.assertTrue(configs.write_all.called)

    @patch.object(relations, 'CONFIGS')
    def test_identity_changed_incomplete(self, configs):
        configs.complete_contexts.return_value = []
        relations.identity_changed()
        self.assertTrue(self.log.called)
        self.assertFalse(configs.write.called)
