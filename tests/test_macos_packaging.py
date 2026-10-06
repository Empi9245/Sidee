"""Reject incomplete or incorrectly targeted macOS distribution bundles."""
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import build_macos_release as packaging


class TestMacBundleValidation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = Path(temporary.name) / "Sidee.app"
        contents = self.app / "Contents"
        self.executable = contents / "MacOS" / "Sidee"
        self.executable.parent.mkdir(parents=True)
        self.executable.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
        self.executable.chmod(0o755)
        with (contents / "Info.plist").open("wb") as stream:
            plistlib.dump({"CFBundleExecutable": "Sidee",
                          "NSLocalNetworkUsageDescription": "Find the TV."}, stream)
        for relative in packaging.RESOURCES + ("_tcl_data/init.tcl", "_tk_data/tk.tcl"):
            destination = contents / "Resources" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("fixture", encoding="utf-8")

    def test_complete_native_app_is_verified_without_running_a_tv_operation(self):
        command = Mock(return_value=Mock(stdout="arm64\n"))
        with patch.object(packaging, "run", command):
            self.assertEqual(packaging.verify_app(self.app, "arm64"), self.executable)
        command.assert_any_call("lipo", "-archs", self.executable,
                                capture_output=True, text=True)
        command.assert_any_call("codesign", "--verify", "--deep", "--strict", self.app)

    def test_wrong_native_slice_is_rejected(self):
        with patch.object(packaging, "run", return_value=Mock(stdout="x86_64\n")):
            with self.assertRaisesRegex(RuntimeError, "Unexpected architecture"):
                packaging.verify_app(self.app, "arm64")

    def test_missing_connection_identity_is_rejected(self):
        (self.app / "Contents" / "Resources" / "core" / "tv-client.bundle").unlink()
        with self.assertRaisesRegex(RuntimeError, "tv-client.bundle"):
            packaging.verify_app(self.app, "arm64")

    def test_missing_tk_runtime_is_rejected(self):
        (self.app / "Contents" / "Resources" / "_tk_data" / "tk.tcl").unlink()
        with self.assertRaisesRegex(RuntimeError, "Tk runtime"):
            packaging.verify_app(self.app, "arm64")

    def test_external_resource_links_are_rejected(self):
        link = self.app / "Contents" / "Resources" / "external"
        try:
            link.symlink_to(self.app.parent)
        except OSError as error:
            self.skipTest(f"Creating symlinks is unavailable: {error}")
        with self.assertRaisesRegex(RuntimeError, "external file"):
            packaging.verify_app(self.app, "arm64")


class TestNativeMacBuild(unittest.TestCase):
    def test_cross_compilation_is_rejected(self):
        with patch.object(packaging.sys, "platform", "win32"):
            with self.assertRaisesRegex(RuntimeError, "must be built on macOS"):
                packaging.build("arm64")

    def test_python_architecture_must_match_runner_target(self):
        with patch.object(packaging.sys, "platform", "darwin"), \
                patch.object(packaging.platform, "machine", return_value="x86_64"):
            with self.assertRaisesRegex(RuntimeError, "native runner"):
                packaging.build("arm64")

    def test_versions_follow_existing_release_tag_format(self):
        self.assertEqual(packaging.validate_version("v0.1.1"), "0.1.1")
        for value in ("v1", "v1.2.3-preview", "1.2.3/../other", "1.2.3\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                packaging.validate_version(value)


if __name__ == "__main__":
    unittest.main()
