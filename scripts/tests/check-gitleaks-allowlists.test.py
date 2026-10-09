#!/usr/bin/env python3
"""Exercise evidence exceptions with Gitleaks, including positive leak controls."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
INDEX = "docs/benchmarks/results/2026-09-20-v07-parity/evidence-index.json"
FIXTURE = "scripts/run-v07-performance.py"
BUILD = "docs/benchmarks/results/2026-09-20-v07-parity/data/reference-native-hysteria-build.txt"
DIGEST = "abcdef0123456789" * 4
PUBLIC_FIXTURE = "aGSYystUbf59_9_6LKRxD27rmSW_-2_nyd9YG_Gwbks"
ARCHIVE_INDEX = "automated-validation.json"
ARCHIVE_ALLOWLIST = "Nine verified file digests in the v0.7 automated evidence index"


class EvidenceAllowlists(unittest.TestCase):
    def test_v08_digest_exceptions_keep_path_value_and_rule_scope(self):
        # Public executable/log digests already reviewed on the v0.8 branch.
        # Keep controls independent of the configured regexes: broadening an
        # exception to a whole file, value or rule must fail this test.
        reviewed = {
            "docs/device-results/2026-10-03-iphone17-v08/manifest.json":
                "90b0c79c7487f49ba9cf8faf20bed3603" + "b3450e090602e199d12f319ae22f49b",
            "docs/benchmarks/results/2026-09-30-v08-cpu/data/verification.json":
                "fcbfcfe586d891ecf556570acd32ce516" + "0e803498e30fe072d151d0056d23b99",
            "docs/benchmarks/results/2026-10-02-v08-adaptive-relay/evidence-index.json":
                "1b7584d75dd361110e1fddb81f9242f58" + "2b02ac681e46b98bcf5ffc65210178b",
        }
        other_digest = "e79a0029cc782ff8166c708f8c911ef3" + "9de33563b71a30df2cd2ff1d63d799ab"
        for path, digest in reviewed.items():
            with self.subTest(path=path):
                self.assertEqual(self.scan({path: json.dumps({"xray": digest})}), set())
                self.assertEqual(self.scan({
                    path: json.dumps({"xray": other_digest}),
                    "unreviewed.json": json.dumps({"xray": digest}),
                }), {(name, "jfrog-identity-token") for name in (path, "unreviewed.json")})
                synthetic = "ABcdeF01234" + "GHijk56789lMno"
                self.assertEqual(self.scan({path: json.dumps({"api_key": synthetic})}),
                                 {(path, "generic-api-key")})

    def test_v08_oracle_key_exception_only_allows_the_reviewed_field(self):
        path = "tests/fixtures/v08/protocol-primitives.json"
        command_key = "d34482dca079f1e8" + "ad37ff8d08a382cf"
        oracle_line = '  "commandKey": "' + command_key + '",\n'
        self.assertEqual(self.scan({path: oracle_line}), set())
        self.assertEqual(self.scan({
            path: json.dumps({"api_key": command_key}),
            "unreviewed.json": oracle_line,
        }), {(name, "generic-api-key") for name in (path, "unreviewed.json")})

    def scan(self, files):
        binary = os.environ["GITLEAKS_BINARY"]
        with tempfile.TemporaryDirectory(prefix="xray-gitleaks-guards-") as name:
            root = Path(name)
            source = root / "source"
            source.mkdir()
            for relative, content in files.items():
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            report = root / "report.json"
            result = subprocess.run(
                [binary, "dir", ".", "--config", str(ROOT / ".gitleaks.toml"),
                 "--redact=100", "--no-banner", "--report-format", "json",
                 "--report-path", str(report)],
                cwd=source, capture_output=True, text=True, timeout=60,
            )
            self.assertIn(result.returncode, (0, 1), result.stderr)
            findings = json.loads(report.read_text())
            self.assertEqual(result.returncode, int(bool(findings)))
            return {(item["File"], item["RuleID"]) for item in findings}

    def test_reviewed_evidence_is_allowed(self):
        self.assertEqual(self.scan({
            INDEX: json.dumps({"fixture/tls.key": DIGEST}),
            FIXTURE: json.dumps({"privateKey": PUBLIC_FIXTURE}),
            BUILD: "\tdep\tgolang.org/x/oauth2\tv0.30.0\th1:"
                   "dnDm7JmhM45NNpd8FDDeLhK6FwqbOf4MLCM9zb1BOHI=\n",
        }), set())

    def test_other_credentials_in_reviewed_files_are_detected(self):
        synthetic = "ABcdeF01234" + "GHijk56789lMno"
        self.assertEqual(self.scan({
            INDEX: json.dumps({"api_key": synthetic}),
            FIXTURE: json.dumps({"privateKey": synthetic}),
            BUILD: json.dumps({"api_key": synthetic}),
        }), {(name, "generic-api-key") for name in (INDEX, FIXTURE, BUILD)})

    def test_same_values_outside_reviewed_paths_are_detected(self):
        self.assertEqual(self.scan({
            "unreviewed.json": json.dumps({"api_key": DIGEST}),
            "unreviewed.py": json.dumps({"privateKey": PUBLIC_FIXTURE}),
        }), {("unreviewed.json", "generic-api-key"),
             ("unreviewed.py", "generic-api-key")})

    def test_other_rules_still_scan_reviewed_paths(self):
        # Synthetic scanner control, assembled to avoid embedding a token literal.
        token = "ghp_" + "aB7cD9eF2gH4iJ6kL8mN0oP1qR3sT5uV7wX9"
        self.assertIn((INDEX, "github-pat"), self.scan({INDEX: token}))

    def test_exact_archive_digests_are_allowed(self):
        config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
        reviewed = [item for item in config["allowlists"]
                    if item.get("description") == ARCHIVE_ALLOWLIST]
        self.assertEqual(len(reviewed), 1)
        expressions = reviewed[0]["regexes"]
        self.assertEqual(len(expressions), 9)
        for expression in expressions:
            self.assertRegex(expression, r"^\^[0-9a-f]{64}\$$")
            digest = expression[1:-1]
            with self.subTest(digest=digest):
                self.assertEqual(self.scan({
                    ARCHIVE_INDEX: json.dumps({"fixture/private-key.pem": digest}),
                    "unreviewed.json": json.dumps({"api_key": digest}),
                }), {("unreviewed.json", "generic-api-key")})

    def test_archive_index_still_detects_unreviewed_values_and_other_rules(self):
        synthetic = "ABcdeF01234" + "GHijk56789lMno"
        for value in (DIGEST, synthetic):
            with self.subTest(value=value):
                self.assertEqual(self.scan({
                    ARCHIVE_INDEX: json.dumps({"api_key": value}),
                }), {(ARCHIVE_INDEX, "generic-api-key")})
        token = "ghp_" + "aB7cD9eF2gH4iJ6kL8mN0oP1qR3sT5uV7wX9"
        self.assertIn((ARCHIVE_INDEX, "github-pat"), self.scan({ARCHIVE_INDEX: token}))


if __name__ == "__main__":
    unittest.main()
