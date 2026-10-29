import hashlib
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import build_windows_release as windows
from tools import public_release_guard as guard

FIXTURE_TOKEN = b"private_test_fixture_only"
FIXTURE_POLICY = frozenset((hashlib.sha256(FIXTURE_TOKEN).hexdigest(),))


class ReleaseGuardTests(unittest.TestCase):
    def test_bundled_scripts_are_checked_for_private_terms(self):
        with patch.object(guard, "TOKEN_FINGERPRINTS", FIXTURE_POLICY):
            with self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_content("core/tv-client.bundle", FIXTURE_TOKEN)

    def test_credentials_are_blocked_without_echoing_values(self):
        samples = [b"sb_secret_" + b"synthetic_fixture_123456789",
                   b"eyJsyntheticHeader." + b"syntheticPayload." + b"syntheticSignature"]
        for value in samples:
            with self.subTest(kind=value[:3]), self.assertRaises(guard.ReleaseBoundaryError) as error:
                guard.check_content("core/client.py", value)
            self.assertNotIn(value.decode(), str(error.exception))

    def test_private_state_directories_are_blocked(self):
        for name in (".audit/a.json", ".secrets/keys.json", "core/__pycache__/x.pyc"):
            with self.subTest(name=name), self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_name(name)

    def test_plain_base64_update_private_key_is_blocked_but_public_key_is_allowed(self):
        private_der = b"\x30\x81\x90\x02\x01\x00\x30" + b"synthetic" * 24
        with self.assertRaises(guard.ReleaseBoundaryError):
            guard.check_content("core/client.py", base64.b64encode(private_der))
        public_der = b"\x30\x81\x90\x30" + b"synthetic" * 24
        guard.check_content("core/client.py", base64.b64encode(public_der))

    def test_public_sources_pass_current_policy(self):
        guard.check_public_source(windows.ROOT)

    def test_local_paths_and_noncanonical_names_are_rejected(self):
        for name in (".env", ".env.local", ".dev.vars", "core/presets_local.py",
                     ".opencode/chat.json", "sidee-native-core/src/a.ts", "a.js.map",
                     "../x.py", "/root/x.py", "core\\x.py", "a//b.py", "a/./b.py", "x.py:stream", "a\n.py"):
            with self.subTest(name=name), self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_name(name)

    def test_source_match_does_not_print_private_token(self):
        with patch.object(guard, "TOKEN_FINGERPRINTS", FIXTURE_POLICY):
            with self.assertRaises(guard.ReleaseBoundaryError) as error:
                guard.check_content("core/client.py", FIXTURE_TOKEN)
        self.assertNotIn(FIXTURE_TOKEN.decode(), str(error.exception))

    def test_policy_matches_whole_tokens_case_insensitively(self):
        with patch.object(guard, "TOKEN_FINGERPRINTS", FIXTURE_POLICY):
            guard.check_content("core/client.py", b"prefix_" + FIXTURE_TOKEN)
            with self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_content("core/client.py", FIXTURE_TOKEN.upper())

    def test_ports_and_key_placeholders_do_not_trigger(self):
        guard.check_content("README.md", b"https://example.test:12470 SN-XXXX-XXXX-XXXX")

    def test_activation_key_like_values_are_blocked(self):
        value = b"SN-" + b"-".join((b"ABCD", b"EFGH", b"JKMN"))
        with self.assertRaises(guard.ReleaseBoundaryError):
            guard.check_content("README.md", value)

    def test_private_pem_and_oversize_source_are_blocked(self):
        for value in (b"-----BEGIN " + b"PRIVATE KEY-----\n" + b"A" * 64, b"x" * (guard.MAX_TEXT_BYTES + 1)):
            with self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_content("core/client.py", value)

    def test_placeholder_pem_without_key_material_is_not_a_secret(self):
        guard.check_content("tests/fixture.py", b"-----BEGIN " + b"PRIVATE KEY-----\nXYZ\n")

    def test_zip_content_verified_after_assembly(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = windows.build(Path(tmp) / "good.zip")
            self.assertEqual(guard.check_zip(good), len(guard.PUBLIC_FILES))
            bad = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(good) as original, zipfile.ZipFile(bad, "w") as modified:
                for entry in original.infolist():
                    content = original.read(entry)
                    if entry.filename == "Sidee/core/client.py":
                        content += b"\n" + FIXTURE_TOKEN
                    modified.writestr(entry, content)
            with patch.object(guard, "TOKEN_FINGERPRINTS", FIXTURE_POLICY), self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_zip(bad)

    def test_zip_extra_member_and_missing_required_files_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = windows.build(Path(tmp) / "extra.zip")
            with zipfile.ZipFile(p, "a") as archive:
                archive.writestr("Sidee/core/unreviewed.py", "pass")
            with self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_zip(p)
            with zipfile.ZipFile(p, "w") as archive:
                archive.writestr("Sidee/README.md", "missing other files")
            with self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_zip(p)

    def test_failed_build_preserves_existing_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "release.zip"
            p.write_bytes(b"existing artifact")
            with patch.object(windows, "check_zip", side_effect=guard.ReleaseBoundaryError("synthetic failure")):
                with self.assertRaises(guard.ReleaseBoundaryError):
                    windows.build(p)
            self.assertEqual(p.read_bytes(), b"existing artifact")
            self.assertEqual(list(Path(tmp).glob(".sidee-release-*")), [])

    def test_unreviewed_core_module_is_blocked_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "core").mkdir()
            (root / "core" / "unreviewed.py").write_text("pass", encoding="utf-8")
            with self.assertRaisesRegex(guard.ReleaseBoundaryError, "Unreviewed"):
                guard.check_public_source(root)

    def test_git_checks_commit_objects_not_just_working_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
            def git(*args):
                return subprocess.check_output(["git", "-c", "user.name=Local test", "-c", "user.email=local@example.invalid",
                    "-c", "commit.gpgSign=false", "-c", "core.hooksPath=" + str(root / "no-hooks"), *args], cwd=root, env=env, stderr=subprocess.DEVNULL)
            git("init", "-q")
            file = root / "README.md"
            file.write_bytes(FIXTURE_TOKEN)
            git("add", "README.md")
            git("commit", "-qm", "synthetic fixture")
            file.write_text("clean working tree", encoding="utf-8")
            with patch.object(guard, "TOKEN_FINGERPRINTS", FIXTURE_POLICY), self.assertRaises(guard.ReleaseBoundaryError):
                guard.check_commit(root, "HEAD")
            file.write_text("clean commit", encoding="utf-8")
            git("add", "README.md")
            git("commit", "-qm", "clean synthetic fixture")
            guard.check_commit(root, "HEAD")

    def test_installed_hook_rejects_private_history_without_network(self):
        hook = windows.ROOT / ".git" / "hooks" / "pre-push"
        checker = hook.with_name("public-release-guard.py")
        shell = Path("C:/Program Files/Git/bin/bash.exe") if os.name == "nt" else Path("/bin/sh")
        if not shell.is_file() or not checker.is_file() or not hook.is_file():
            self.skipTest("Local installed-hook check requires the local guard and shell")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "SIDEE_GUARD_PYTHON": sys.executable.replace("\\", "/")}
            def git(*args):
                return subprocess.check_output(["git", "-c", "user.name=Local test", "-c", "user.email=local@example.invalid",
                    "-c", "commit.gpgSign=false", "-c", "core.hooksPath=" + str(root / "no-hooks"), *args], cwd=root, env=env, stderr=subprocess.DEVNULL)
            def invoke():
                oid = git("rev-parse", "HEAD").decode().strip()
                line = f"refs/heads/main {oid} refs/heads/main {'0' * 40}\n"
                return subprocess.run([str(shell), ".git/hooks/pre-push", "origin", "unused"], cwd=root,
                    env=env, input=line, text=True, capture_output=True, timeout=15)
            git("init", "-q")
            (root / "README.md").write_text("synthetic public fixture", encoding="utf-8")
            git("add", "README.md")
            git("commit", "-qm", "public synthetic fixture")
            shutil.copyfile(hook, root / ".git/hooks/pre-push")
            shutil.copyfile(checker, root / ".git/hooks/public-release-guard.py")
            self.assertEqual(invoke().returncode, 0)
            private = root / "sidee-native-core" / "fixture.ts"
            private.parent.mkdir()
            private.write_text("synthetic private fixture", encoding="utf-8")
            git("add", "sidee-native-core/fixture.ts")
            git("commit", "-qm", "private synthetic fixture")
            self.assertNotEqual(invoke().returncode, 0)
            private.unlink()
            git("add", "sidee-native-core/fixture.ts")
            git("commit", "-qm", "remove fixture from current tree")
            self.assertNotEqual(invoke().returncode, 0)


if __name__ == "__main__":
    unittest.main()
