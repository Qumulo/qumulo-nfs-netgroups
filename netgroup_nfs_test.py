import os
import unittest

from unittest.mock import patch, MagicMock

from netgroup_nfs import *

class NetgroupNFSTest(unittest.TestCase):

    def test_get_ips_localhost(self):
        with patch('socket.gethostbyname_ex') as socket_mock:
            socket_mock.return_value = ('localhost', [], ['127.0.0.1'])
            ips = get_ips('localhost')
        self.assertEqual(ips,['127.0.0.1'])

    def test_get_ips_bad_hostname(self):
        ips = get_ips('notarealname1111')
        self.assertEqual(ips, [])

    @patch('nis.cat')
    def test_parse_net_group(self, nis_cat_mock):
        nis_cat_mock.return_value = {
            'n1': 'n2 (h1,user1,domain1) (h2,u2,d2) (h3,u3,d3)',
            'n2': 'n3 (h4,u4,d4)',
            'n3': '(h5,u5,d5)'
        }
        hosts = parse_net_group('n1')
        self.assertEqual(set(hosts), set(['h1', 'h2', 'h3', 'h4', 'h5']))

    @patch('nis.cat')
    def test_parse_net_group_no_map(self, nis_cat_mock):
        nis_cat_mock.return_value = {}
        hosts = parse_net_group('missing_map')
        self.assertEqual(hosts, [])

    @patch('nis.cat')
    def test_parse_net_group_raise_exception(self, nis_cat_mock):
        def nis_error(netgroup):
            raise Exception('error error!')
        nis_cat_mock.side_effect = nis_error

        with self.assertRaisesRegex(Exception, 'error error!'):
            parse_net_group('missing_map')

    def test_enumerate_hosts(self):
        with patch('netgroup_nfs.parse_net_group') as parse_net_group_mock, patch('netgroup_nfs.get_ips') as get_ips_mock:
            def get_ips(hostname):
                if hostname == 'linux-1':
                    return ['1.2.3.4']
                else:
                    return ['1.2.3.4', '9.8.7.6']
            get_ips_mock.side_effect = get_ips

            allowed_hosts = { 'hosts': ['linux-1', 'linux-2'], 'netgroups': ['workstation'] }
            ips = enumerate_hosts(allowed_hosts)

        self.assertEqual(set(ips), set(['1.2.3.4', '9.8.7.6']))

    def test_parse_config(self):
        config = parse_config('netgroup_nfs.json.sample')
        self.assertEqual(config['username'], 'admin')

    @patch('netgroup_nfs.log.error')
    def test_bad_parse_config(self, mock_logger):
        with self.assertRaisesRegex(Exception, 'No such file or directory'):
            config = parse_config('bad.json.sample')

        self.assertIn('FAILED to open', mock_logger.call_args[0][0])

    def setup_mocks(self, rest_mock, nis_mock, socket_mock):
        rest_client_mock = MagicMock()
        rest_mock.return_value = rest_client_mock

        def get_export(export_path):
            return { 'id': 1, 'restrictions': [{'host_restrictions': []}] }
        rest_client_mock.nfs.nfs_get_export.side_effect = get_export

        nis_mock.return_value = { 'workstations': '123', 'servers': '123' }
        socket_mock.return_value = '1.2.3.4'

        return rest_client_mock

    def test_main_no_commit(self):
        with patch('qumulo.rest_client.RestClient') as rest_mock, patch('nis.cat') as nis_mock, patch('socket.gethostbyname_ex') as socket_mock:
            rest_client_mock = self.setup_mocks(rest_mock, nis_mock, socket_mock)
            main(['--config', 'netgroup_nfs.json.sample'])

        self.assertEqual(rest_mock.call_args[0][0], 'qumulo_cluster.eng.qumulo.com')
        self.assertEqual(rest_mock.call_args[0][1], 8000)
        self.assertEqual(
            len(rest_client_mock.nfs.nfs_modify_export.call_args_list), 0
        )

    def test_main_commit(self):
        with patch('qumulo.rest_client.RestClient') as rest_mock, patch('nis.cat') as nis_mock, patch('socket.gethostbyname_ex') as socket_mock:
            rest_client_mock = self.setup_mocks(rest_mock, nis_mock, socket_mock)
            main(['--config', 'netgroup_nfs.json.sample', '--commit'])

        self.assertEqual(rest_mock.call_args[0][0], 'qumulo_cluster.eng.qumulo.com')
        self.assertEqual(rest_mock.call_args[0][1], 8000)
        self.assertEqual(
            len(rest_client_mock.nfs.nfs_modify_export.call_args_list), 2
        )



if __name__ == '__main__':
    unittest.main()

