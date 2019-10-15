# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import mock
import requests_mock

from designate import exceptions
from designate import objects
from designate.backend import impl_pdns4
from designate.mdns import rpcapi as mdns_rpcapi
import designate.tests
from designate.tests import fixtures


class PDNS4BackendTestCase(designate.tests.TestCase):
    def setUp(self):
        super(PDNS4BackendTestCase, self).setUp()
        self.stdlog = fixtures.StandardLogging()
        self.useFixture(self.stdlog)

        self.base_address = 'http://localhost:8081/api/v1/servers'
        self.context = self.get_context()
        self.zone = objects.Zone(
            id='e2bed4dc-9d01-11e4-89d3-123b93f75cba',
            name='example.com.',
            email='example@example.com',
        )

        self.target = {
            'id': '4588652b-50e7-46b9-b688-a9bad40a873e',
            'type': 'pdns4',
            'masters': [
                {'host': '192.0.2.1', 'port': 53},
                {'host': '192.0.2.2', 'port': 35},
            ],
            'options': [
                {'key': 'api_endpoint', 'value': 'http://localhost:8081'},
                {'key': 'api_token', 'value': 'api_key'},
            ],
        }

        self.backend = impl_pdns4.PDNS4Backend(
            objects.PoolTarget.from_dict(self.target)
        )

    @requests_mock.mock()
    @mock.patch.object(mdns_rpcapi.MdnsAPI, 'notify_zone_changed')
    def test_create_zone_success(self, req_mock, mock_notify_zone_changed):
        req_mock.post(
            '%s/localhost/zones' % self.base_address,
        )
        req_mock.get(
            '%s/localhost/zones/%s' % (self.base_address, self.zone.name),
            status_code=404,
        )

        self.backend.create_zone(self.context, self.zone)

        self.assertEqual(
            req_mock.last_request.json(),
            {
                'kind': u'slave',
                'masters': ['192.0.2.1:53', '192.0.2.2:35'],
                'name': u'example.com.',
            }
        )

        self.assertEqual(
            req_mock.last_request.headers.get('X-API-Key'), 'api_key'
        )

        mock_notify_zone_changed.assert_called_with(
            self.context, self.zone, '127.0.0.1', 53, 30, 15, 10, 5)

    @requests_mock.mock()
    @mock.patch.object(mdns_rpcapi.MdnsAPI, 'notify_zone_changed')
    def test_create_zone_ipv6(self, req_mock, mock_notify_zone_changed):
        self.target['masters'] = [
            {'host': '2001:db8::9abc', 'port': 53},
        ]

        self.backend = impl_pdns4.PDNS4Backend(
            objects.PoolTarget.from_dict(self.target)
        )

        req_mock.post(
            '%s/localhost/zones' % self.base_address,
        )
        req_mock.get(
            '%s/localhost/zones/%s' % (self.base_address, self.zone.name),
            status_code=404,
        )

        self.backend.create_zone(self.context, self.zone)

        self.assertEqual(
            req_mock.last_request.json(),
            {
                'kind': u'slave',
                'masters': ['[2001:db8::9abc]:53'],
                'name': u'example.com.',
            }
        )

        self.assertEqual(
            req_mock.last_request.headers.get('X-API-Key'), 'api_key'
        )

        mock_notify_zone_changed.assert_called_with(
            self.context, self.zone, '127.0.0.1', 53, 30, 15, 10, 5)

    @requests_mock.mock()
    def test_create_zone_already_exists(self, req_mock):
        req_mock.post(
            '%s/localhost/zones' % self.base_address,
        )
        req_mock.get(
            '%s/localhost/zones/%s' % (self.base_address, self.zone.name),
            status_code=200,
        )
        req_mock.delete(
            '%s/localhost/zones/example.com.' % self.base_address,
        )

        self.backend.create_zone(self.context, self.zone)

        self.assertEqual(
            req_mock.last_request.json(),
            {
                'kind': u'slave',
                'masters': ['192.0.2.1:53', '192.0.2.2:35'],
                'name': u'example.com.',
            }
        )

        self.assertEqual(
            req_mock.last_request.headers.get('X-API-Key'), 'api_key'
        )

    @requests_mock.mock()
    def test_create_zone_already_exists_and_fails_to_delete(self, req_mock):
        req_mock.post(
            '%s/localhost/zones' % self.base_address,
            status_code=500,
        )
        req_mock.get(
            '%s/localhost/zones/%s' % (self.base_address, self.zone.name),
            status_code=200,
        )
        req_mock.delete(
            '%s/localhost/zones/example.com.' % self.base_address,
            status_code=500,
        )

        self.assertRaisesRegexp(
            exceptions.Backend,
            '500 Server Error: None for url: '
            '%s/localhost/zones' % self.base_address,
            self.backend.create_zone, self.context, self.zone
        )

        self.assertIn(
            "Could not delete pre-existing zone "
            "<Zone id:'e2bed4dc-9d01-11e4-89d3-123b93f75cba' "
            "type:'None' name:'example.com.' pool_id:'None' serial:'None' "
            "action:'None' status:'None'>",
            self.stdlog.logger.output
        )

        self.assertIn(
            "<Zone id:'e2bed4dc-9d01-11e4-89d3-123b93f75cba' type:'None' "
            "name:'example.com.' pool_id:'None' serial:'None' action:'None' "
            "status:'None'> exists on the server. "
            "Deleting zone before creation",
            self.stdlog.logger.output
        )

    @requests_mock.mock()
    def test_create_zone_with_tsigkey(self, req_mock):
        req_mock.post(
            '%s/localhost/zones' % self.base_address,
        )
        req_mock.get(
            '%s/localhost/zones/%s' % (self.base_address, self.zone.name),
            status_code=404,
        )

        target = dict(self.target)
        target['options'].append(
            {'key': 'tsigkey_name', 'value': 'tsig_key'}
        )
        backend = impl_pdns4.PDNS4Backend(
            objects.PoolTarget.from_dict(target)
        )

        backend.create_zone(self.context, self.zone)

        self.assertEqual(
            req_mock.last_request.json(),
            {
                'kind': u'slave',
                'masters': ['192.0.2.1:53', '192.0.2.2:35'],
                'name': u'example.com.',
                'slave_tsig_key_ids': ['tsig_key'],
            }
        )

        self.assertEqual(
            req_mock.last_request.headers.get('X-API-Key'), 'api_key'
        )

    @requests_mock.mock()
    def test_create_zone_fail(self, req_mock):
        req_mock.post(
            '%s/localhost/zones' % self.base_address,
            status_code=500,
        )
        req_mock.get(
            '%s/localhost/zones/%s' % (self.base_address, self.zone.name),
            status_code=404,
        )

        self.assertRaisesRegexp(
            exceptions.Backend,
            '500 Server Error: None for url: '
            '%s/localhost/zones' % self.base_address,
            self.backend.create_zone, self.context, self.zone
        )

        self.assertEqual(
            req_mock.last_request.headers.get('X-API-Key'), 'api_key'
        )

    @requests_mock.mock()
    def test_create_zone_fail_with_failed_delete(self, req_mock):
        req_mock.post(
            '%s/localhost/zones' % self.base_address,
            status_code=500,
        )
        req_mock.get(
            '%s/localhost/zones/%s' % (self.base_address, self.zone.name),
            [{'status_code': 404}, {'status_code': 200}],
        )
        req_mock.delete(
            '%s/localhost/zones/example.com.' % self.base_address,
            status_code=500,
        )

        self.assertRaisesRegexp(
            exceptions.Backend,
            '500 Server Error: None for url: '
            '%s/localhost/zones' % self.base_address,
            self.backend.create_zone, self.context, self.zone
        )

        self.assertEqual(
            req_mock.last_request.headers.get('X-API-Key'), 'api_key'
        )

        self.assertIn(
            "<Zone id:'e2bed4dc-9d01-11e4-89d3-123b93f75cba' type:'None' "
            "name:'example.com.' pool_id:'None' serial:'None' action:'None' "
            "status:'None'> was created with an error. Deleting zone",
            self.stdlog.logger.output
        )

        self.assertIn(
            "Could not delete errored zone "
            "<Zone id:'e2bed4dc-9d01-11e4-89d3-123b93f75cba' type:'None' "
            "name:'example.com.' pool_id:'None' serial:'None' action:'None' "
            "status:'None'>",
            self.stdlog.logger.output
        )

    @requests_mock.mock()
    def test_delete_zone_success(self, req_mock):
        req_mock.delete(
            '%s/localhost/zones/example.com.' % self.base_address,
        )

        self.backend.delete_zone(self.context, self.zone)

        self.assertEqual(
            req_mock.last_request.headers.get('X-API-Key'), 'api_key'
        )

    @requests_mock.mock()
    def test_delete_zone_fail(self, req_mock):
        req_mock.delete(
            '%s/localhost/zones/example.com.' % self.base_address,
            status_code=500,
        )

        self.assertRaisesRegexp(
            exceptions.Backend,
            '500 Server Error: None for url: '
            '%s/localhost/zones' % self.base_address,
            self.backend.delete_zone, self.context, self.zone
        )

        self.assertEqual(
            req_mock.last_request.headers.get('X-API-Key'), 'api_key'
        )