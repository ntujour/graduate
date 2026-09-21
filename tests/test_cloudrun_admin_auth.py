import unittest
from unittest.mock import patch

import cloudrun_admin


class CloudRunAdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.admins = {"owner@example.com", "student-admin@example.com"}
        self.audience = "/projects/123/locations/asia-east1/services/graduate-course-admin"

    def test_empty_admin_list_denies_every_request(self):
        with (
            patch.object(cloudrun_admin, "ADMIN_EMAILS", set()),
            patch.object(cloudrun_admin, "IAP_JWT_AUDIENCE", self.audience),
            cloudrun_admin.app.test_request_context(
                "/api/admin-state",
                headers={"X-Goog-Authenticated-User-Email": "accounts.google.com:owner@example.com"},
            ),
        ):
            response, status = cloudrun_admin.require_admin()
            self.assertEqual(status, 403)
            self.assertEqual(response.get_json(), {"error": "Forbidden"})

    def test_unsigned_email_header_cannot_grant_access(self):
        with (
            patch.object(cloudrun_admin, "ADMIN_EMAILS", self.admins),
            patch.object(cloudrun_admin, "IAP_JWT_AUDIENCE", self.audience),
            cloudrun_admin.app.test_request_context(
                "/api/admin-state",
                headers={"X-Goog-Authenticated-User-Email": "accounts.google.com:owner@example.com"},
            ),
        ):
            response, status = cloudrun_admin.require_admin()
            self.assertEqual(status, 403)
            self.assertEqual(response.get_json(), {"error": "Forbidden"})

    def test_valid_iap_assertion_uses_signed_email_not_unsigned_header(self):
        claims = {
            "iss": "https://cloud.google.com/iap",
            "sub": "signed-subject",
            "email": "student-admin@example.com",
        }
        with (
            patch.object(cloudrun_admin, "ADMIN_EMAILS", self.admins),
            patch.object(cloudrun_admin, "IAP_JWT_AUDIENCE", self.audience),
            patch.object(cloudrun_admin.id_token, "verify_token", return_value=claims),
            cloudrun_admin.app.test_request_context(
                "/api/admin-state",
                headers={
                    "X-Goog-IAP-JWT-Assertion": "signed-assertion",
                    "X-Goog-Authenticated-User-Email": "accounts.google.com:attacker@example.com",
                },
            ),
        ):
            self.assertIsNone(cloudrun_admin.require_admin())

    def test_assertion_with_unexpected_issuer_is_denied(self):
        claims = {"iss": "https://attacker.example", "sub": "subject", "email": "owner@example.com"}
        with (
            patch.object(cloudrun_admin, "ADMIN_EMAILS", self.admins),
            patch.object(cloudrun_admin, "IAP_JWT_AUDIENCE", self.audience),
            patch.object(cloudrun_admin.id_token, "verify_token", return_value=claims),
            cloudrun_admin.app.test_request_context(
                "/api/admin-state", headers={"X-Goog-IAP-JWT-Assertion": "invalid-issuer"}
            ),
        ):
            response, status = cloudrun_admin.require_admin()
            self.assertEqual(status, 403)
            self.assertEqual(response.get_json(), {"error": "Forbidden"})
