from mock import patch
import heat_context
from test_utils import CharmTestCase

TO_PATCH = [
    'get_encryption_key'
]


class TestHeatContext(CharmTestCase):

    def setUp(self):
        super(TestHeatContext, self).setUp(heat_context, TO_PATCH)

    def test_encryption_configuration(self):
        self.get_encryption_key.return_value = 'key'
        self.assertEquals(
            heat_context.EncryptionContext()(),
            {'encryption_key': 'key'})
