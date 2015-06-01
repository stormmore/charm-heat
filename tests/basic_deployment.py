#!/usr/bin/python

"""
Basic heat functional test.

test_* methods are called in lexical sort order.

Convention to ensure desired test order:
    1xx service and endpoint checks
    2xx relation checks
    3xx config checks
    4xx functional checks
    9xx restarts and other final checks

Common relation definitions:
    - [ heat, mysql ]
    - [ heat, keystone ]
    - [ heat, rabbitmq-server ]

Resultant relations of heat service:
    relations:
      amqp:
      - rabbitmq-server
      identity-service:
      - keystone
      shared-db:
      - mysql
"""
import amulet
import os
import time
from heatclient.openstack.common.py3kcompat import urlutils
from heatclient.common import template_utils

from charmhelpers.contrib.openstack.amulet.deployment import (
    OpenStackAmuletDeployment
)

from charmhelpers.contrib.openstack.amulet.utils import (
    OpenStackAmuletUtils,
    DEBUG,
    #ERROR
)

# Use DEBUG to turn on debug logging
u = OpenStackAmuletUtils(DEBUG)

# Resource and name constants
IMAGE_NAME = 'cirros-image-1'
KEYPAIR_NAME = 'testkey'
STACK_NAME = 'hello_world'
RESOURCE_TYPE = 'server'
TEMPLATE_REL_PATH = 'tests/files/hot_hello_world.yaml'


class HeatBasicDeployment(OpenStackAmuletDeployment):
    """Amulet tests on a basic heat deployment."""

    def __init__(self, series=None, openstack=None, source=None, git=False,
                 stable=False):
        """Deploy the entire test environment."""
        super(HeatBasicDeployment, self).__init__(series, openstack,
                                                  source, stable)
        self.git = git
        self._add_services()
        self._add_relations()
        self._configure_services()
        self._deploy()
        self._initialize_tests()

    def _add_services(self):
        """Add services

           Add the services that we're testing, where heat is local,
           and the rest of the service are from lp branches that are
           compatible with the local charm (e.g. stable or next).
           """
        this_service = {'name': 'heat'}
        other_services = [{'name': 'keystone'},
                          {'name': 'rabbitmq-server'},
                          {'name': 'mysql'},
                          {'name': 'glance'},
                          {'name': 'nova-cloud-controller'},
                          {'name': 'nova-compute'}]
        super(HeatBasicDeployment, self)._add_services(this_service,
                                                       other_services)

    def _add_relations(self):
        """Add all of the relations for the services."""

        relations = {
            'heat:amqp': 'rabbitmq-server:amqp',
            'heat:identity-service': 'keystone:identity-service',
            'heat:shared-db': 'mysql:shared-db',
            'nova-compute:image-service': 'glance:image-service',
            'nova-compute:shared-db': 'mysql:shared-db',
            'nova-compute:amqp': 'rabbitmq-server:amqp',
            'nova-cloud-controller:shared-db': 'mysql:shared-db',
            'nova-cloud-controller:identity-service':
            'keystone:identity-service',
            'nova-cloud-controller:amqp': 'rabbitmq-server:amqp',
            'nova-cloud-controller:cloud-compute':
            'nova-compute:cloud-compute',
            'nova-cloud-controller:image-service': 'glance:image-service',
            'keystone:shared-db': 'mysql:shared-db',
            'glance:identity-service': 'keystone:identity-service',
            'glance:shared-db': 'mysql:shared-db',
            'glance:amqp': 'rabbitmq-server:amqp'
        }
        super(HeatBasicDeployment, self)._add_relations(relations)

    def _configure_services(self):
        """Configure all of the services."""
        nova_config = {'config-flags': 'auto_assign_floating_ip=False',
                       'enable-live-migration': 'False'}
        keystone_config = {'admin-password': 'openstack',
                           'admin-token': 'ubuntutesting'}
        configs = {'nova-compute': nova_config, 'keystone': keystone_config}
        super(HeatBasicDeployment, self)._configure_services(configs)

    def _initialize_tests(self):
        """Perform final initialization before tests get run."""
        # Access the sentries for inspecting service units
        self.heat_sentry = self.d.sentry.unit['heat/0']
        self.mysql_sentry = self.d.sentry.unit['mysql/0']
        self.keystone_sentry = self.d.sentry.unit['keystone/0']
        self.rabbitmq_sentry = self.d.sentry.unit['rabbitmq-server/0']
        self.nova_compute_sentry = self.d.sentry.unit['nova-compute/0']
        self.glance_sentry = self.d.sentry.unit['glance/0']

        u.log.debug('openstack release val: {}'.format(
            self._get_openstack_release()))
        u.log.debug('openstack release str: {}'.format(
            self._get_openstack_release_string()))

        # Let things settle a bit before moving forward
        time.sleep(30)

        # Authenticate admin with keystone
        self.keystone = u.authenticate_keystone_admin(self.keystone_sentry,
                                                      user='admin',
                                                      password='openstack',
                                                      tenant='admin')

        # Authenticate admin with glance endpoint
        self.glance = u.authenticate_glance_admin(self.keystone)

        # Authenticate admin with nova endpoint
        self.nova = u.authenticate_nova_user(self.keystone,
                                             user='admin',
                                             password='openstack',
                                             tenant='admin')

        # Authenticate admin with heat endpoint
        self.heat = u.authenticate_heat_admin(self.keystone)

    def file_url(self, file_rel_path):
        """Return file:// url for a file expressed as a relative path."""
        file_abs_path = os.path.abspath(file_rel_path)
        file_url = urlutils.urljoin('file:',
                                    urlutils.pathname2url(file_abs_path))
        return file_url

    def create_or_get_keypair(self, keypair_name="testkey"):
        """Create a new keypair, or return pointer if it already exists."""
        try:
            _keypair = self.nova.keypairs.get(keypair_name)
            u.log.debug('Keypair ({}) already exists, '
                        'using it.'.format(keypair_name))
            return _keypair
        except:
            u.log.debug('Keypair ({}) does not exist, '
                        'creating it.'.format(keypair_name))

        _keypair = self.nova.keypairs.create(name=keypair_name)
        return _keypair

    def test_100_services(self):
        """Verify the expected services are running on the corresponding
           service units."""
        commands = {
            self.heat_sentry: ['status heat-api',
                               'status heat-api-cfn',
                               'status heat-engine'],
            self.mysql_sentry: ['status mysql'],
            self.rabbitmq_sentry: ['sudo service rabbitmq-server status'],
            self.nova_compute_sentry: ['status nova-compute',
                                       'status nova-network',
                                       'status nova-api'],
            self.keystone_sentry: ['status keystone'],
            self.glance_sentry: ['status glance-registry', 'status glance-api']
        }

        ret = u.validate_services(commands)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

    def test_110_service_catalog(self):
        """Verify that the service catalog endpoint data is valid."""
        u.log.debug('Checking service catalog endpoint data...')
        endpoint_vol = {'adminURL': u.valid_url,
                        'region': 'RegionOne',
                        'publicURL': u.valid_url,
                        'internalURL': u.valid_url}
        endpoint_id = {'adminURL': u.valid_url,
                       'region': 'RegionOne',
                       'publicURL': u.valid_url,
                       'internalURL': u.valid_url}
        if self._get_openstack_release() >= self.precise_folsom:
            endpoint_vol['id'] = u.not_null
            endpoint_id['id'] = u.not_null
        expected = {'s3': [endpoint_vol], 'compute': [endpoint_vol],
                    'ec2': [endpoint_vol], 'identity': [endpoint_id]}
        actual = self.keystone.service_catalog.get_endpoints()

        ret = u.validate_svc_catalog_endpoint_data(expected, actual)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

    def test_120_heat_endpoint(self):
        """Verify the heat api endpoint data."""
        u.log.debug('Checking api endpoint data...')
        endpoints = self.keystone.endpoints.list()
        admin_port = internal_port = public_port = '3333'
        expected = {'id': u.not_null,
                    'region': 'RegionOne',
                    'adminurl': u.valid_url,
                    'internalurl': u.valid_url,
                    'publicurl': u.valid_url,
                    'service_id': u.not_null}

        ret = u.validate_endpoint_data(endpoints, admin_port, internal_port,
                                       public_port, expected)
        if ret:
            message = 'heat endpoint: {}'.format(ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_200_heat_mysql_shared_db_relation(self):
        """Verify the heat:mysql shared-db relation data"""
        u.log.debug('Checking heat:mysql shared-db relation data...')
        unit = self.heat_sentry
        relation = ['shared-db', 'mysql:shared-db']
        expected = {
            'private-address': u.valid_ip,
            'heat_database': 'heat',
            'heat_username': 'heat',
            'heat_hostname': u.valid_ip
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('heat:mysql shared-db', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_202_heat_keystone_identity_relation(self):
        """Verify the heat:keystone identity-service relation data"""
        u.log.debug('Checking heat:keystone identity-service relation data...')
        unit = self.heat_sentry
        relation = ['identity-service', 'keystone:identity-service']
        expected = {
            'heat_service': 'heat',
            'heat_region': 'RegionOne',
            'heat_public_url': u.valid_url,
            'heat_admin_url': u.valid_url,
            'heat_internal_url': u.valid_url,
            'heat-cfn_service': 'heat-cfn',
            'heat-cfn_region': 'RegionOne',
            'heat-cfn_public_url': u.valid_url,
            'heat-cfn_admin_url': u.valid_url,
            'heat-cfn_internal_url': u.valid_url
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('heat:keystone identity-service', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_204_heat_rmq_amqp_relation(self):
        """Verify the heat:rabbitmq-server amqp relation data"""
        u.log.debug('Checking heat:rabbitmq-server amqp relation data...')
        unit = self.heat_sentry
        relation = ['amqp', 'rabbitmq-server:amqp']
        expected = {
            'username': u.not_null,
            'private-address': u.valid_ip,
            'vhost': 'openstack'
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('heat:rabbitmq-server amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_300_heat_config(self):
        """Verify the data in the heat config file."""
        u.log.debug('Checking heat config file data...')
        unit = self.heat_sentry
        conf = '/etc/heat/heat.conf'

        ks_rel = self.keystone_sentry.relation('identity-service',
                                               'heat:identity-service')
        rmq_rel = self.rabbitmq_sentry.relation('amqp',
                                                'heat:amqp')
        mysql_rel = self.mysql_sentry.relation('shared-db',
                                               'heat:shared-db')

        u.log.debug('keystone:heat relation: {}'.format(ks_rel))
        u.log.debug('rabbitmq:heat relation: {}'.format(rmq_rel))
        u.log.debug('mysql:heat relation: {}'.format(mysql_rel))

        db_uri = "mysql://{}:{}@{}/{}".format('heat',
                                              mysql_rel['heat_password'],
                                              mysql_rel['db_host'],
                                              'heat')

        auth_uri = '{}://{}:{}/v2.0'.format(ks_rel['service_protocol'],
                                            ks_rel['service_host'],
                                            ks_rel['service_port'])

        expected = {
            'DEFAULT': {
                'use_syslog': 'False',
                'debug': 'False',
                'verbose': 'False',
                'log_dir': '/var/log/heat',
                'instance_driver': 'heat.engine.nova',
                'plugin_dirs': '/usr/lib64/heat,/usr/lib/heat',
                'environment_dir': '/etc/heat/environment.d',
                'deferred_auth_method': 'password',
                'host': 'heat',
            },
            'keystone_authtoken': {
                'auth_uri': auth_uri,
                'auth_host': ks_rel['service_host'],
                'auth_port': ks_rel['auth_port'],
                'auth_protocol': ks_rel['auth_protocol'],
                'admin_tenant_name': 'services',
                'admin_user': 'heat-cfn_heat',
                'admin_password': ks_rel['service_password'],
                'signing_dir': '/var/cache/heat'
            },
            'database': {
                'connection': db_uri
            },
            'heat_api': {
                'bind_port': '7994'
            },
            'heat_api_cfn': {
                'bind_port': '7990'
            },
            'paste_deploy': {
                'api_paste_config': '/etc/heat/api-paste.ini'
            },
        }

        if self._get_openstack_release() >= self.trusty_kilo:
            # Kilo or later
            expected.update(
                {
                    'oslo_messaging_rabbit': {
                        'rabbit_userid': 'heat',
                        'rabbit_virtual_host': 'openstack',
                        'rabbit_password': rmq_rel['password'],
                        'rabbit_host': rmq_rel['hostname']
                    }
                }
            )
        else:
            # Juno or earlier
            expected['DEFAULT'].update(
                {
                    'rabbit_userid': 'heat',
                    'rabbit_virtual_host': 'openstack',
                    'rabbit_password': rmq_rel['password'],
                    'rabbit_host': rmq_rel['hostname']
                }
            )

        for section, pairs in expected.iteritems():
            ret = u.validate_config_data(unit, conf, section, pairs)
            if ret:
                message = "heat config error: {}".format(ret)
                amulet.raise_status(amulet.FAIL, msg=message)

    def test_400_heat_resource_types_list(self):
        """Check default heat resource list functionality."""
        u.log.debug('Checking default heat resouce list...')
        try:
            types = list(self.heat.resource_types.list())
            if type(types) is list:
                u.log.debug('Resource type list check is ok.')
            else:
                msg = 'Resource type list is not a list!'
                u.log.error('{}'.format(msg))
                raise
            if len(types) > 0:
                u.log.debug('Resource type list length is non-zero '
                            '({}, ok).'.format(len(types)))
            else:
                msg = 'Resource type list length is zero!'
                u.log.error(msg)
                raise
        except:
            msg = 'Resource type list failed.'
            u.log.error(msg)
            raise

    def test_402_heat_stack_list(self):
        """Check default heat stack list functionality."""
        u.log.debug('Checking default heat stack list...')
        try:
            stacks = list(self.heat.stacks.list())
            if type(stacks) is list:
                u.log.debug("Stack list check is ok.")
            else:
                msg = 'Stack list returned something other than a list.'
                u.log.error(msg)
                raise
        except:
            msg = 'Heat stack list failed.'
            u.log.error(msg)
            raise

    def test_410_image_create(self):
        """Create an image to be used by the heat template, verify it exists"""
        u.log.debug('Creating glance image ({})...'.format(IMAGE_NAME))

        # Create a new image
        image_new = u.create_cirros_image(self.glance, IMAGE_NAME)

        # Confirm image is created and has status of 'active'
        if not image_new:
            message = 'glance image create failed'
            amulet.raise_status(amulet.FAIL, msg=message)

        # Verify new image name
        images_list = list(self.glance.images.list())
        if images_list[0].name != IMAGE_NAME:
            message = ('glance image create failed or unexpected '
                       'image name {}'.format(images_list[0].name))
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_411_nova_keypair_create(self):
        """Create a keypair to be used by the heat template,
           or get a keypair if it exists."""
        self.keypair = self.create_or_get_keypair(keypair_name=KEYPAIR_NAME)
        if not self.keypair:
            msg = 'Failed to create or get keypair.'
            amulet.raise_status(amulet.FAIL, msg=msg)
        u.log.debug("Keypair: {} {}".format(self.keypair.id,
                                            self.keypair.fingerprint))

    def test_412_heat_stack_create(self):
        """Create a heat stack from a basic heat template, verify its status"""
        u.log.debug('Creating heat stack...')

        t_url = self.file_url(TEMPLATE_REL_PATH)
        r_req = self.heat.http_client.raw_request
        u.log.debug('template url: {}'.format(t_url))

        t_files, template = template_utils.get_template_contents(t_url, r_req)
        env_files, env = template_utils.process_environment_and_files(
            env_path=None)

        fields = {
            'stack_name': STACK_NAME,
            'timeout_mins': '15',
            'disable_rollback': False,
            'parameters': {
                'admin_pass': 'Ubuntu',
                'key_name': KEYPAIR_NAME,
                'image': IMAGE_NAME
            },
            'template': template,
            'files': dict(list(t_files.items()) + list(env_files.items())),
            'environment': env
        }

        # Create the stack.
        try:
            _stack = self.heat.stacks.create(**fields)
            u.log.debug('Stack data: {}'.format(_stack))
            _stack_id = _stack['stack']['id']
            u.log.debug('Creating new stack, ID: {}'.format(_stack_id))
        except Exception as e:
            # Generally, an api or cloud config error if this is hit.
            msg = 'Failed to create heat stack: {}'.format(e)
            amulet.raise_status(amulet.FAIL, msg=msg)

        # Confirm stack reaches COMPLETE status.
        # /!\ Heat stacks reach a COMPLETE status even when nova cannot
        # find resources (a valid hypervisor) to fit the instance, in
        # which case the heat stack self-deletes!  Confirm anyway...
        ret = u.thing_reaches_status(self.heat.stacks, _stack_id,
                                     expected_stat="COMPLETE",
                                     msg="Stack status wait")
        _stacks = list(self.heat.stacks.list())
        u.log.debug('All stacks: {}'.format(_stacks))
        if not ret:
            msg = 'Heat stack failed to reach expected state.'
            amulet.raise_status(amulet.FAIL, msg=msg)

        # Confirm stack still exists.
        try:
            _stack = self.heat.stacks.get(STACK_NAME)
        except Exception as e:
            # Generally, a resource availability issue if this is hit.
            msg = 'Failed to get heat stack: {}'.format(e)
            amulet.raise_status(amulet.FAIL, msg=msg)

        # Confirm stack name.
        u.log.debug('Expected, actual stack name: {}, '
                    '{}'.format(STACK_NAME, _stack.stack_name))
        if STACK_NAME != _stack.stack_name:
            msg = 'Stack name mismatch, {} != {}'.format(STACK_NAME,
                                                         _stack.stack_name)
            amulet.raise_status(amulet.FAIL, msg=msg)

    def test_413_heat_stack_resource_compute(self):
        """Confirm that the stack has created a subsequent nova
           compute resource, and confirm its status."""
        u.log.debug('Confirming heat stack resource status...')

        # Confirm existence of a heat-generated nova compute resource.
        _resource = self.heat.resources.get(STACK_NAME, RESOURCE_TYPE)
        _server_id = _resource.physical_resource_id
        if _server_id:
            u.log.debug('Heat template spawned nova instance, '
                        'ID: {}'.format(_server_id))
        else:
            msg = 'Stack failed to spawn a nova compute resource (instance).'
            amulet.raise_status(amulet.FAIL, msg=msg)

        # Confirm nova instance reaches ACTIVE status.
        ret = u.thing_reaches_status(self.nova.servers, _server_id,
                                     expected_stat="ACTIVE",
                                     msg="nova instance")
        if not ret:
            msg = 'Nova compute instance failed to reach expected state.'
            amulet.raise_status(amulet.FAIL, msg=msg)

    def test_490_heat_stack_delete(self):
        """Delete a heat stack, verify."""
        u.log.debug('Deleting heat stack...')
        u.delete_thing(self.heat.stacks, STACK_NAME, msg="heat stack")

    def test_491_image_delete(self):
        """Delete that image."""
        u.log.debug('Deleting glance image...')
        image = self.nova.images.find(name=IMAGE_NAME)
        u.delete_thing(self.nova.images, image, msg="glance image")

    def test_492_keypair_delete(self):
        """Delete that keypair."""
        u.log.debug('Deleting keypair...')
        u.delete_thing(self.nova.keypairs, KEYPAIR_NAME, msg="nova keypair")

    def test_900_heat_restart_on_config_change(self):
        """Verify that the specified services are restarted when the config
           is changed."""
        sentry = self.heat_sentry
        juju_service = 'heat'

        # Expected default and alternate values
        set_default = {'use-syslog': 'False'}
        set_alternate = {'use-syslog': 'True'}

        # Config file affected by juju set config change
        conf_file = '/etc/heat/heat.conf'

        # Services which are expected to restart upon config change
        services = ['heat-api',
                    'heat-api-cfn',
                    'heat-engine']

        # Make config change, check for service restarts
        u.log.debug('Making config change on {}...'.format(juju_service))
        self.d.configure(juju_service, set_alternate)

        sleep_time = 30
        for s in services:
            u.log.debug("Checking that service restarted: {}".format(s))
            if not u.service_restarted(sentry, s,
                                       conf_file, sleep_time=sleep_time):
                self.d.configure(juju_service, set_default)
                msg = "service {} didn't restart after config change".format(s)
                amulet.raise_status(amulet.FAIL, msg=msg)
            sleep_time = 0

        self.d.configure(juju_service, set_default)
