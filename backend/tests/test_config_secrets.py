from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import config


class LoadEnvFileTests(unittest.TestCase):
    def write_env(self, text: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_fills_missing_vars_and_strips_quotes(self) -> None:
        path = self.write_env('CONVERSE_TEST_A="alpha"\n# comment\nCONVERSE_TEST_B=beta\n\nnot a pair\n')
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONVERSE_TEST_A", None)
            os.environ.pop("CONVERSE_TEST_B", None)
            config.load_env_file(path)
            self.assertEqual(os.environ["CONVERSE_TEST_A"], "alpha")
            self.assertEqual(os.environ["CONVERSE_TEST_B"], "beta")

    def test_process_env_wins_over_file(self) -> None:
        path = self.write_env("CONVERSE_TEST_C=from-file\n")
        with mock.patch.dict(os.environ, {"CONVERSE_TEST_C": "from-env"}, clear=False):
            config.load_env_file(path)
            self.assertEqual(os.environ["CONVERSE_TEST_C"], "from-env")

    def test_missing_file_is_a_no_op(self) -> None:
        config.load_env_file(Path("/nonexistent/converse/.env"))

    def test_accepts_shell_export_lines(self) -> None:
        path = self.write_env('export CONVERSE_TEST_D="delta"\nexport CONVERSE_TEST_E=echo\n')
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONVERSE_TEST_D", None)
            os.environ.pop("CONVERSE_TEST_E", None)
            config.load_env_file(path)
            self.assertEqual(os.environ["CONVERSE_TEST_D"], "delta")
            self.assertEqual(os.environ["CONVERSE_TEST_E"], "echo")

    def test_skips_shell_substitution_values(self) -> None:
        path = self.write_env('export CONVERSE_TEST_F="$(security find-generic-password)"\nCONVERSE_TEST_G=$HOME/x\n')
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONVERSE_TEST_F", None)
            os.environ.pop("CONVERSE_TEST_G", None)
            config.load_env_file(path)
            self.assertNotIn("CONVERSE_TEST_F", os.environ)
            self.assertNotIn("CONVERSE_TEST_G", os.environ)


class SecretPrecedenceTests(unittest.TestCase):
    def test_env_wins_over_keychain(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env"}, clear=False):
            with mock.patch.object(config, "keychain_secret") as keychain:
                self.assertEqual(config.secret("OPENAI_API_KEY"), "sk-env")
                keychain.assert_not_called()

    def test_falls_back_to_keychain_service(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with mock.patch.object(config, "keychain_secret", return_value="sk-keychain") as keychain:
                self.assertEqual(config.secret("ANTHROPIC_API_KEY"), "sk-keychain")
                keychain.assert_called_once_with("convo-maker-anthropic-api-key")

    def test_no_keychain_service_for_unknown_names(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SOME_OTHER_KEY", None)
            with mock.patch.object(config, "keychain_secret") as keychain:
                self.assertIsNone(config.secret("SOME_OTHER_KEY"))
                keychain.assert_not_called()


class KeychainSecretTests(unittest.TestCase):
    def completed(self, returncode: int, stdout: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")

    def test_returns_trimmed_secret_on_success(self) -> None:
        with mock.patch.object(config.sys, "platform", "darwin"):
            with mock.patch.object(config.subprocess, "run", return_value=self.completed(0, "sk-abc\n")):
                self.assertEqual(config.keychain_secret("svc"), "sk-abc")

    def test_returns_none_on_lookup_failure(self) -> None:
        with mock.patch.object(config.sys, "platform", "darwin"):
            with mock.patch.object(config.subprocess, "run", return_value=self.completed(44, "")):
                self.assertIsNone(config.keychain_secret("svc"))

    def test_returns_none_off_macos(self) -> None:
        with mock.patch.object(config.sys, "platform", "linux"):
            self.assertIsNone(config.keychain_secret("svc"))


if __name__ == "__main__":
    unittest.main()
