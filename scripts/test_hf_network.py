"""Exercise real SDK requests against mocked HTTP, including paginated 429s."""
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import httpx
from huggingface_hub import set_client_factory
from huggingface_hub.utils._http import default_client_factory

import hf_network as network


class RetryTests(unittest.TestCase):
    def test_anonymous_transport_retry_is_bounded_and_preserves_permanent_errors(self):
        with patch.object(network.time, 'sleep'), redirect_stdout(io.StringIO()):
            operation = unittest.mock.Mock(side_effect=[URLError('TLS EOF'), b'complete'])
            self.assertEqual(network.retry_read(operation, 'anonymous download'), b'complete')
            self.assertEqual(operation.call_count, 2)
            operation = unittest.mock.Mock(side_effect=URLError('TLS EOF'))
            with self.assertRaises(URLError):
                network.retry_read(operation, 'anonymous download', max_retries=2)
            self.assertEqual(operation.call_count, 3)
            operation = unittest.mock.Mock(side_effect=HTTPError('https://example.invalid', 403, 'denied', {}, None))
            with self.assertRaises(HTTPError):
                network.retry_read(operation, 'anonymous download')
            self.assertEqual(operation.call_count, 1)

    def test_server_delay_takes_precedence_and_fallback_grows(self):
        self.assertEqual(network.retry_delay({'Retry-After': '350'}, 0), 351)
        self.assertEqual(network.retry_delay({'RateLimit': '"api";r=0;t=70'}, 0), 71)
        self.assertEqual(network.retry_delay({'Retry-After': '5', 'RateLimit': '"api";r=0;t=70'}, 0), 71)
        with patch.object(network.time, 'time', return_value=0):
            self.assertEqual(network.retry_delay({'Retry-After': 'Thu, 01 Jan 1970 00:02:00 GMT'}, 0), 121)
        self.assertEqual([network.retry_delay({}, i) for i in range(4)], [60, 120, 240, 300])
        for invalid in ['invalid', 'nan', 'inf']:
            self.assertEqual(network.retry_delay({'Retry-After': invalid}, 0), 60)

    def test_anonymous_urllib_download_retries_without_logging_url_or_credentials(self):
        calls = []
        stream = io.BytesIO()
        def download():
            calls.append(True)
            if len(calls) == 1:
                raise HTTPError('https://example.invalid/?private=value', 429, 'limited', {'Retry-After': '61'}, stream)
            return b'public data'
        output = io.StringIO()
        with patch.object(network.time, 'sleep') as sleep, redirect_stdout(output):
            self.assertEqual(network.retry_429(download, 'anonymous public download'), b'public data')
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [60, 2])
        self.assertTrue(stream.closed)
        self.assertNotIn('private=value', output.getvalue())
        self.assertIn('retry 1/6', output.getvalue())

    def test_retries_are_bounded_and_other_errors_are_not_replayed(self):
        for status in [401, 403, 409, 500, 429]:
            calls = []
            def fail():
                calls.append(status)
                raise HTTPError('https://example.invalid', status, 'failure', {}, None)
            with self.subTest(status=status), patch.object(network.time, 'sleep'), redirect_stdout(io.StringIO()):
                with self.assertRaises(HTTPError):
                    network.retry_429(fail, 'test', max_retries=2)
                self.assertEqual(len(calls), 3 if status == 429 else 1)


class SDKReadTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(set_client_factory, default_client_factory)
        # The SDK may fetch an agent registry while constructing User-Agent.
        # Keep that unrelated telemetry request out of the mocked Hub protocol.
        telemetry = patch('huggingface_hub.constants.HF_HUB_DISABLE_TELEMETRY', True)
        telemetry.start()
        self.addCleanup(telemetry.stop)
        sleeper = patch.object(network.time, 'sleep')
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)
        token = patch.dict(os.environ, {'HF_TOKEN': 'fixture-token'})
        token.start()
        self.addCleanup(token.stop)

    def api(self, handler):
        original_factory = network.http_client
        with patch.object(network, 'http_client', lambda: original_factory(transport=httpx.MockTransport(handler))):
            return network.authenticated_api()

    def test_repo_info_uses_login_even_with_implicit_auth_disabled(self):
        requests = []
        def handler(request):
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(429, headers={'Retry-After': '0'})
            return httpx.Response(200, json={'id': 'search-swe/trajectories', 'sha': 'a' * 40,
                                              'private': False, 'gated': False})
        api = self.api(handler)
        with patch('huggingface_hub.constants.HF_HUB_DISABLE_IMPLICIT_TOKEN', True):
            info = api.repo_info('search-swe/trajectories', repo_type='dataset', revision='main', expand=['sha', 'private', 'gated'])
        self.assertEqual(info.sha, 'a' * 40)
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(r.headers['authorization'] == 'Bearer fixture-token' for r in requests))

    def test_pagination_retries_only_the_page_that_was_limited(self):
        calls = []
        endpoint = 'https://huggingface.co/api/datasets/search-swe/trajectories/tree/' + 'a' * 40
        def handler(request):
            page = 'second' if request.url.params.get('cursor') else 'first'
            calls.append(page)
            if calls.count(page) == 1:
                return httpx.Response(429, headers={'RateLimit': '"api";r=0;t=0'})
            headers = {'Link': f'<{endpoint}?cursor=two>; rel="next"'} if page == 'first' else {}
            return httpx.Response(200, headers=headers, json=[{'type': 'file', 'oid': 'b' * 40, 'size': 3, 'path': page}])
        files = list(self.api(handler).list_repo_tree('search-swe/trajectories', revision='a' * 40, repo_type='dataset', recursive=True))
        self.assertEqual([f.path for f in files], ['first', 'second'])
        self.assertEqual(calls, ['first', 'first', 'second', 'second'])

    def test_readonly_paths_info_post_retries(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(429, headers={'Retry-After': '0'}) if len(requests) == 1 else httpx.Response(200, json=[])
        self.assertEqual(self.api(handler).get_paths_info('search-swe/trajectories', ['README.md'], repo_type='dataset'), [])
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].content, requests[1].content)

    def test_readonly_transport_and_server_failures_are_retried(self):
        calls = []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                raise httpx.ConnectError('TLS connection interrupted', request=request)
            if len(calls) == 2:
                return httpx.Response(503)
            return httpx.Response(200, json=[])
        self.assertEqual(self.api(handler).get_paths_info('search-swe/trajectories', ['README.md'], repo_type='dataset'), [])
        self.assertEqual(len(calls), 3)

    def test_transient_mutation_failures_are_not_replayed(self):
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ConnectError('Connection interrupted', request=request)
        with network.http_client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(httpx.ConnectError):
                client.post('https://huggingface.co/api/datasets/test/commit/main', content=b'commit')
        self.assertEqual(len(calls), 1)
        self.sleep.assert_not_called()

    def test_mutating_requests_are_not_automatically_replayed_by_the_http_client(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429)
        with network.http_client(transport=httpx.MockTransport(handler)) as client:
            response = client.post('https://huggingface.co/api/datasets/test/commit/main', content=b'commit')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(calls), 1)
        self.sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
