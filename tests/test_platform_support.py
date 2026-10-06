"""Platform and packaged-app checks without contacting a TV or user profile."""
import errno
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import client, platform_support as platform


MAC_INTERFACES = """lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
    inet 127.0.0.1 netmask 0xff000000
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet6 fe80::1%en0 prefixlen 64
    inet 192.168.88.5 netmask 0xffffff00 broadcast 192.168.88.255
    status: active
en1: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet 10.23.7.5 netmask 255.255.248.0 broadcast 10.23.7.255
    status: active
utun0: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1380
    inet 10.8.0.5 netmask 0xffffff00
en2: flags=8862<BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet 172.20.0.5 netmask 0xffff0000
en3: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet 192.168.3.5 netmask 0xffffff00
    status: inactive
"""


class TestPlatformPaths(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        env = patch.dict(os.environ, {"SIDEE_STATE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)

    def test_source_resource_root_does_not_depend_on_current_directory(self):
        source = self.folder / "Sidee" / "core" / "client.py"
        with patch.object(platform.sys, "frozen", False, create=True):
            self.assertEqual(platform.resource_root(str(source)), source.parent.parent)
            self.assertEqual(platform.resource_root(str(source.parent.parent / "sidee.py")),
                             source.parent.parent)

    def test_frozen_resources_use_bundle_data_root(self):
        bundle = self.folder / "Sidee.app" / "Contents" / "Frameworks"
        with patch.object(platform.sys, "frozen", True, create=True), \
                patch.object(platform.sys, "_MEIPASS", str(bundle), create=True):
            self.assertEqual(platform.resource_root(), bundle)
            self.assertEqual(platform.resource_root("irrelevant/core/client.py"), bundle)
        self.assertFalse(bundle.exists())

    def test_source_dashboard_state_preserves_folder_runtime(self):
        for operating_system in ("win32", "darwin", "linux"):
            with self.subTest(platform=operating_system), \
                    patch.object(platform.sys, "platform", operating_system), \
                    patch.object(platform.sys, "frozen", False, create=True):
                self.assertEqual(platform.dashboard_state_path(self.folder),
                                 self.folder / ".runtime" / "dashboard.json")

    def test_frozen_macos_state_is_outside_read_only_bundle(self):
        bundle = self.folder / "Applications" / "Sidee.app"
        home = self.folder / "home"
        with patch.object(platform.sys, "platform", "darwin"), \
                patch.object(platform.sys, "frozen", True, create=True), \
                patch.object(platform.os.path, "expanduser", return_value=str(home)):
            state = platform.dashboard_state_path(bundle)
        self.assertEqual(state, home / "Library" / "Application Support" / "Sidee"
                         / "runtime" / "dashboard.json")
        self.assertFalse(bundle.exists())
        self.assertFalse(state.exists())

    def test_explicit_state_override_isolated_from_real_pairing(self):
        home = self.folder / "home"
        legacy = home / ".vidaa-tile"
        legacy.mkdir(parents=True)
        (legacy / "session.json").write_text("user pairing", encoding="utf-8")
        isolated = self.folder / "isolated"
        with patch.dict(os.environ, {"SIDEE_STATE_DIR": str(isolated)}), \
                patch.object(platform.os.path, "expanduser", return_value=str(home)):
            self.assertEqual(platform.profile_dir(), isolated)
            self.assertEqual(Path(client.Session.path()), isolated / "session.json")
            self.assertEqual(platform.dashboard_state_path(self.folder),
                             isolated / "runtime" / "dashboard.json")
            self.assertIsNone(client.Session().load_or_none())
        self.assertEqual((legacy / "session.json").read_text(encoding="utf-8"), "user pairing")

    def test_fresh_unix_profile_directory_is_private(self):
        if os.name == "nt":
            self.skipTest("Unix permission bits are verified by the macOS CI job")
        isolated = self.folder / "isolated"
        with patch.dict(os.environ, {"SIDEE_STATE_DIR": str(isolated)}):
            platform.profile_dir()
        self.assertEqual(isolated.stat().st_mode & 0o777, 0o700)

    def test_frozen_certificate_lookup_uses_bundled_resource(self):
        bundle = self.folder / "bundle"
        (bundle / "core").mkdir(parents=True)
        certificate = bundle / "core" / "tv-client.bundle"
        certificate.write_bytes(b"encoded bundle fixture")
        with patch.object(platform.sys, "frozen", True, create=True), \
                patch.object(platform.sys, "_MEIPASS", str(bundle), create=True), \
                patch.object(client, "_cert_dir", return_value=str(self.folder / "profile")):
            self.assertEqual(Path(client._certificate_path()), certificate)
            self.assertTrue(client.has_client_certificate())

    def test_source_certificate_lookup_preserves_local_and_profile_precedence(self):
        project = self.folder / "project"
        local = project / ".sidee" / client._CERT_BUNDLE
        local.parent.mkdir(parents=True)
        local.write_bytes(b"encoded local fixture")
        profile = self.folder / "profile"
        profile.mkdir()
        with patch.object(platform.sys, "frozen", False, create=True), \
                patch.object(client, "__file__", str(project / "core" / "client.py")), \
                patch.object(client, "_cert_dir", return_value=str(profile)):
            self.assertEqual(Path(client._certificate_path()), local)
            user = profile / client._CERT_BUNDLE
            user.write_bytes(b"encoded user fixture")
            self.assertEqual(Path(client._certificate_path()), user)


class TestMacDiscovery(unittest.TestCase):
    def test_wifi_ethernet_and_hexadecimal_masks_are_used(self):
        self.assertEqual(platform.broadcasts_from_ifconfig(MAC_INTERFACES),
                         ["10.23.7.255", "192.168.88.255"])

    def test_broadcast_is_calculated_from_the_actual_mask(self):
        output = """en0: flags=8863<UP,BROADCAST,RUNNING> mtu 1500
    inet 172.19.208.1 netmask 0xfffff000 broadcast 172.19.208.255
"""
        self.assertEqual(platform.broadcasts_from_ifconfig(output), ["172.19.223.255"])

    def test_invalid_nonbroadcast_and_local_only_addresses_are_ignored(self):
        for host, mask in (("192.168.1.5", "0xff00ff00"),
                           ("192.168.1.5", "0x100000000"),
                           ("192.168.1.5", "invalid"),
                           ("192.168.1.999", "0xffffff00"),
                           ("127.0.0.1", "0xff000000"),
                           ("169.254.2.5", "0xffff0000"),
                           ("0.0.0.0", "0xffffff00"),
                           ("239.1.2.3", "0xffffff00"),
                           ("10.0.0.5", "0xffffffff"),
                           ("10.0.0.5", "0xfffffffe")):
            with self.subTest(host=host, mask=mask):
                output = f"en0: flags=3<UP,BROADCAST>\n    inet {host} netmask {mask}\n"
                self.assertEqual(platform.broadcasts_from_ifconfig(output), [])

    def test_macos_never_executes_windows_commands_or_creationflags(self):
        response = Mock(returncode=0, stdout=MAC_INTERFACES)
        with patch.object(platform.sys, "platform", "darwin"), \
                patch.object(platform.subprocess, "run", return_value=response) as run:
            self.assertEqual(client._local_broadcasts(), ["10.23.7.255", "192.168.88.255"])
        run.assert_called_once_with(["/sbin/ifconfig"], capture_output=True, text=True,
                                    errors="replace", timeout=3)

    def test_windows_interface_detection_preserves_hidden_subprocess(self):
        response = Mock(returncode=0, stdout="IPv4: 192.168.1.5\nMask: 255.255.255.0\n")
        with patch.object(platform.sys, "platform", "win32"), \
                patch.object(platform.os, "name", "nt"), \
                patch.object(platform.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
                patch.object(platform.subprocess, "run", return_value=response) as run:
            self.assertEqual(platform.local_broadcasts(), ["192.168.1.255"])
        run.assert_called_once_with(["ipconfig"], capture_output=True, text=True,
                                    errors="replace", timeout=3, creationflags=0x08000000)

    def test_interface_inspection_errors_preserve_discovery_fallback(self):
        failures = [OSError("No interface command"),
                    subprocess.TimeoutExpired("/sbin/ifconfig", 3)]
        for failure in failures:
            with self.subTest(error=type(failure).__name__), \
                    patch.object(platform.sys, "platform", "darwin"), \
                    patch.object(platform.subprocess, "run", side_effect=failure):
                self.assertEqual(platform.local_broadcasts(), [])
        with patch.object(platform.sys, "platform", "darwin"), \
                patch.object(platform.subprocess, "run", return_value=Mock(returncode=1)):
            self.assertEqual(platform.local_broadcasts(), [])


class TestSocketLifecycle(unittest.TestCase):
    def test_discovery_closes_socket_after_receive_failure(self):
        connection = Mock()
        connection.recvfrom.side_effect = OSError("Network went away")
        with patch.object(client.socket, "socket", return_value=connection), \
                patch.object(client, "_local_broadcasts", return_value=[]):
            with self.assertRaises(OSError):
                client.discover(timeout=1)
        connection.close.assert_called_once()

    def test_tv_clock_connections_are_closed_after_request_failure(self):
        connections = [Mock(), Mock(), Mock()]
        for connection in connections:
            connection.request.side_effect = OSError("TV offline")
        with patch.object(client.http.client, "HTTPConnection", side_effect=connections), \
                patch.object(client.time, "time", return_value=123):
            self.assertEqual(client.tv_timestamp("192.168.88.42"), 123)
        for connection in connections:
            connection.close.assert_called_once()

    def test_exclusive_windows_binding_keeps_existing_behavior(self):
        connection = Mock()
        with patch.object(platform.os, "name", "nt"), \
                patch.object(platform.socket, "SO_EXCLUSIVEADDRUSE", -5, create=True):
            self.assertFalse(platform.allow_reuse_address())
            platform.configure_exclusive_tcp_socket(connection)
        connection.setsockopt.assert_called_once_with(socket.SOL_SOCKET, -5, 1)

    def test_macos_binding_uses_no_windows_socket_option(self):
        connection = Mock()
        with patch.object(platform.os, "name", "posix"):
            self.assertTrue(platform.allow_reuse_address())
            platform.configure_exclusive_tcp_socket(connection)
        connection.setsockopt.assert_not_called()

    def test_only_address_conflicts_allow_a_fallback_port(self):
        self.assertTrue(platform.address_in_use(OSError(errno.EADDRINUSE, "occupied")))
        for code in (10013, 10048):
            error = OSError(errno.EACCES, "occupied")
            error.winerror = code
            self.assertTrue(platform.address_in_use(error))
        self.assertFalse(platform.address_in_use(OSError(errno.EACCES, "permission denied")))
        self.assertFalse(platform.address_in_use(OSError(errno.EIO, "setup failed")))

    def test_decoded_certificate_files_are_private_and_removed_before_mqtt_connect(self):
        context = Mock()
        loaded = []

        def load_certificate(certificate, key):
            for name in (certificate, key):
                path = Path(name)
                self.assertTrue(path.is_file())
                if os.name != "nt":
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                loaded.append(path)

        context.load_cert_chain.side_effect = load_certificate
        mqtt = Mock()
        with patch.object(client, "_load_client_pem_key", return_value=(b"cert", b"key")), \
                patch.object(client.ssl, "SSLContext", return_value=context), \
                patch.object(client.mqtt, "Client", return_value=mqtt):
            client.MqttSession("192.168.88.42", "aa:bb:cc:dd:ee:ff", 123)
        self.assertEqual(len(loaded), 2)
        self.assertTrue(all(not path.exists() for path in loaded))
        self.assertFalse(loaded[0].parent.exists())
        mqtt.connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
