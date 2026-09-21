import unittest

import cloudrun_alumni


class AlumniClientKeyTests(unittest.TestCase):
    def test_cloud_run_client_address_is_the_last_forwarded_value(self):
        with cloudrun_alumni.app.test_request_context(
            "/api/alumni-submissions",
            headers={"X-Forwarded-For": "198.51.100.9, 203.0.113.42"},
        ):
            self.assertEqual(cloudrun_alumni.request_client_key(), "203.0.113.42")

    def test_forged_forwarded_prefix_cannot_change_rate_limit_identity(self):
        with cloudrun_alumni.app.test_request_context(
            "/api/alumni-submissions",
            headers={"X-Forwarded-For": "forged-one, 203.0.113.42"},
        ):
            first = cloudrun_alumni.request_client_key()
        with cloudrun_alumni.app.test_request_context(
            "/api/alumni-submissions",
            headers={"X-Forwarded-For": "forged-two, 203.0.113.42"},
        ):
            second = cloudrun_alumni.request_client_key()
        self.assertEqual(first, "203.0.113.42")
        self.assertEqual(second, "203.0.113.42")

    def test_remote_address_is_used_only_without_a_proxy_header(self):
        with cloudrun_alumni.app.test_request_context("/api/alumni-submissions", environ_base={"REMOTE_ADDR": "127.0.0.9"}):
            self.assertEqual(cloudrun_alumni.request_client_key(), "127.0.0.9")
