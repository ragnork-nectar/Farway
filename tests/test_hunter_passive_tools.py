import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import sunday_hunter as hunter


class PassiveHunterToolTests(unittest.TestCase):
    def test_security_headers_check_reports_missing_headers(self):
        response = SimpleNamespace(
            headers={
                "Strict-Transport-Security": "max-age=31536000",
                "X-Content-Type-Options": "nosniff",
            },
            status_code=200,
            url="https://example.com/",
        )
        requests_stub = SimpleNamespace(get=Mock(return_value=response))

        with (
            patch.object(hunter, "_safety_check", return_value=(True, "OK")),
            patch.object(hunter, "REQUESTS_OK", True),
            patch.object(hunter, "requests", requests_stub, create=True),
            patch.object(hunter, "audit_log"),
        ):
            result = hunter.security_headers_check("example.com")

        self.assertIn("Missing/review:", result)
        self.assertIn("Content-Security-Policy", result)
        self.assertIn("Strict-Transport-Security", result)
        self.assertNotIn("Strict-Transport-Security", result.split("Missing/review: ", 1)[1].split(". Present:", 1)[0])
        requests_stub.get.assert_called_once_with(
            "https://example.com",
            timeout=8,
            allow_redirects=False,
        )

    def test_security_headers_check_blocks_out_of_scope_before_request(self):
        requests_stub = SimpleNamespace(get=Mock())

        with (
            patch.object(hunter, "_safety_check", return_value=(False, "REFUSED: out of scope")),
            patch.object(hunter, "REQUESTS_OK", True),
            patch.object(hunter, "requests", requests_stub, create=True),
            patch.object(hunter, "audit_log"),
        ):
            result = hunter.security_headers_check("example.com")

        self.assertEqual(result, "REFUSED: out of scope")
        requests_stub.get.assert_not_called()

    def test_email_dns_check_reports_spf_and_dmarc_policy(self):
        resolver = SimpleNamespace(
            resolve=Mock(
                side_effect=[
                    ['"v=spf1 include:_spf.example.net -all"'],
                    ['"v=DMARC1; p=reject; rua=mailto:dmarc@example.com"'],
                ]
            ),
            NoAnswer=type("NoAnswer", (Exception,), {}),
            NXDOMAIN=type("NXDOMAIN", (Exception,), {}),
        )
        dns_stub = SimpleNamespace(resolver=resolver)

        with (
            patch.object(hunter, "_safety_check", return_value=(True, "OK")),
            patch.object(hunter, "DNS_OK", True),
            patch.object(hunter, "dns", dns_stub, create=True),
            patch.object(hunter, "audit_log"),
        ):
            result = hunter.email_dns_check("example.com")

        self.assertIn("SPF: v=spf1", result)
        self.assertIn("DMARC policy: reject", result)
        self.assertEqual(resolver.resolve.call_count, 2)

    def test_email_dns_check_does_not_report_lookup_failure_as_missing_record(self):
        resolver = SimpleNamespace(
            resolve=Mock(side_effect=RuntimeError("resolver timeout")),
            NoAnswer=type("NoAnswer", (Exception,), {}),
            NXDOMAIN=type("NXDOMAIN", (Exception,), {}),
        )
        dns_stub = SimpleNamespace(resolver=resolver)

        with (
            patch.object(hunter, "_safety_check", return_value=(True, "OK")),
            patch.object(hunter, "DNS_OK", True),
            patch.object(hunter, "dns", dns_stub, create=True),
            patch.object(hunter, "audit_log"),
        ):
            result = hunter.email_dns_check("example.com")

        self.assertIn("Email DNS lookup failed", result)
        self.assertNotIn("no SPF record found", result)

    def test_hunter_commands_route_to_new_tools(self):
        with (
            patch.object(hunter, "security_headers_check", return_value="headers") as headers,
            patch.object(hunter, "email_dns_check", return_value="email DNS") as email_dns,
        ):
            self.assertEqual(
                hunter.handle_hunter_command("security headers example.com"),
                ("headers", True),
            )
            self.assertEqual(
                hunter.handle_hunter_command("email dns example.com"),
                ("email DNS", True),
            )

        headers.assert_called_once_with("example.com")
        email_dns.assert_called_once_with("example.com")


if __name__ == "__main__":
    unittest.main()
