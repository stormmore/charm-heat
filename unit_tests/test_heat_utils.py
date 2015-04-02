from collections import OrderedDict
from mock import patch, MagicMock
from test_utils import CharmTestCase

from charmhelpers.core import hookenv

_conf = hookenv.config
hookenv.config = MagicMock()

import heat_utils as utils

hookenv.config = _conf

TO_PATCH = [
    'config',
    'log',
    'os_release',
    'get_os_codename_install_source',
    'configure_installation_source',
    'apt_install',
    'apt_update'
]


# Restart map should be constructed such that API services restart
# before frontends (haproxy/apaceh) to avoid port conflicts.
RESTART_MAP = OrderedDict([
    ('/etc/heat/heat.conf', ['heat-api', 'heat-api-cfn', 'heat-engine']),
    ('/etc/heat/api-paste.ini', ['heat-api', 'heat-api-cfn']),
    ('/etc/haproxy/haproxy.cfg', ['haproxy']),
    ('/etc/apache2/sites-available/openstack_https_frontend', ['apache2']),
    ('/etc/apache2/sites-available/openstack_https_frontend.conf',
     ['apache2']),
])


class HeatUtilsTests(CharmTestCase):

    def setUp(self):
        super(HeatUtilsTests, self).setUp(utils, TO_PATCH)
        self.config.side_effect = self.test_config.get

    @patch('charmhelpers.contrib.openstack.context.SubordinateConfigContext')
    def test_determine_packages(self, subcontext):
        self.os_release.return_value = 'havana'
        pkgs = utils.determine_packages()
        ex = list(set(utils.BASE_PACKAGES + utils.BASE_SERVICES))
        self.assertEquals(ex, pkgs)

    def test_restart_map(self):
        self.assertEquals(RESTART_MAP, utils.restart_map())

    def test_openstack_upgrade(self):
        self.config.side_effect = None
        self.config.return_value = 'cloud:precise-havana'
        self.get_os_codename_install_source.return_value = 'havana'
        configs = MagicMock()
        utils.do_openstack_upgrade(configs)
        self.assertTrue(configs.write_all.called)
        configs.set_release.assert_called_with(openstack_release='havana')

    def test_api_ports(self):
        cfn = utils.api_port('heat-api-cfn')
        self.assertEquals(cfn, 8000)
        cfn = utils.api_port('heat-api')
        self.assertEquals(cfn, 8004)
