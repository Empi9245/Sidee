"""Brand-aware credentials: the TV declares its brand in the UPnP
descriptor (brand=his on Hisense, brand=tos on Toshiba-licensed firmware)
and the official app's native library takes it as an input.

Offline verification: credential structure per brand, descriptor parsing,
session persistence, and brand propagation to the pairing connections.
Whether Toshiba firmware accepts these credentials requires the real TV.
"""
import os
import unittest
from unittest.mock import patch

from core import client, protocol


TS = 1791900000
UUID = "16:1e:d5:d4:61:0d"

TOSHIBA_DESCRIPTOR = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <friendlyName>Living Room TV</friendlyName>
    <manufacturer>SmartTV</manufacturer>
    <modelDescription>#CAP#
mac=001122334455
ip=192.168.18.138
transport_protocol=3290
brand=tos
vidaa_support=1
</modelDescription>
    <modelName>Renderer</modelName>
    <UDN>uuid:test-udn</UDN>
  </device>
</root>
"""

HISENSE_DESCRIPTOR = TOSHIBA_DESCRIPTOR.replace("brand=tos", "brand=his")
TESLA_DESCRIPTOR = TOSHIBA_DESCRIPTOR.replace("brand=tos", "brand=tes")
TESLA_UPPER_DESCRIPTOR = TOSHIBA_DESCRIPTOR.replace("brand=tos", "Brand=TES")


class TestCredentialBrand(unittest.TestCase):
    def test_brand_changes_client_id_and_username(self):
        his = protocol.session_credentials(UUID, TS, auth_profile="modern",
                                           brand="his")
        tos = protocol.session_credentials(UUID, TS, auth_profile="modern",
                                           brand="tos")
        self.assertTrue(his[0].startswith(UUID + "$his$"))
        self.assertTrue(tos[0].startswith(UUID + "$tos$"))
        self.assertTrue(his[1].startswith("his$"))
        self.assertTrue(tos[1].startswith("tos$"))
        self.assertNotEqual(his[0], tos[0])
        self.assertNotEqual(his[1], tos[1])
        self.assertNotEqual(his[2], tos[2], "password must depend on brand")

    def test_suffix_constants_unchanged_by_brand(self):
        # the value suffixes are firmware constants (3-slot table in the
        # native library): the brand is a separate input, the salt is not
        # rebuilt per brand.
        before = protocol.VALUE_SUFFIX
        protocol.session_credentials(UUID, TS, auth_profile="modern",
                                     brand="tos")
        self.assertEqual(protocol.VALUE_SUFFIX, before)

    def test_brand_deterministic(self):
        a = protocol.session_credentials(UUID, TS, auth_profile="modern",
                                         brand="tos")
        b = protocol.session_credentials(UUID, TS, auth_profile="modern",
                                         brand="tos")
        self.assertEqual(a, b)

    def test_token_mode_keeps_brand_identity(self):
        cid, user, pwd = protocol.session_credentials(
            UUID, TS, token="tok", auth_profile="modern", brand="tos")
        self.assertTrue(cid.startswith(UUID + "$tos$"))
        self.assertTrue(user.startswith("tos$"))
        self.assertEqual(pwd, "tok")

    def test_default_brand_is_his(self):
        explicit = protocol.session_credentials(UUID, TS, auth_profile="modern",
                                                brand="his")
        implicit = protocol.session_credentials(UUID, TS, auth_profile="modern")
        self.assertEqual(explicit, implicit)


class TestDescriptorBrand(unittest.TestCase):
    def test_toshiba_descriptor_yields_tos(self):
        self.assertEqual(client._descriptor_brand(TOSHIBA_DESCRIPTOR), "tos")

    def test_hisense_descriptor_yields_his(self):
        self.assertEqual(client._descriptor_brand(HISENSE_DESCRIPTOR), "his")

    def test_missing_or_invalid_brand_falls_back(self):
        self.assertEqual(client._descriptor_brand("no brand line"), "his")
        self.assertEqual(client._descriptor_brand("brand=TOSHIBA!!"), "his")

    def test_any_brand_running_vidaa_is_used_as_declared(self):
        # The badge is not a gate: whatever the TV declares is the input to the
        # credential algorithm. `tes` is only a synthetic example for a
        # Tesla-branded VIDAA set; the real descriptor is authoritative.
        self.assertEqual(client._descriptor_brand(TESLA_DESCRIPTOR), "tes")
        self.assertEqual(client._descriptor_brand(TESLA_UPPER_DESCRIPTOR), "tes")
        cid, user, pwd = protocol.session_credentials(
            UUID, TS, auth_profile="modern", brand="tes")
        self.assertTrue(cid.startswith(UUID + "$tes$"))
        self.assertTrue(user.startswith("tes$"))
        self.assertNotEqual(pwd, protocol.session_credentials(
            UUID, TS, auth_profile="modern", brand="his")[2])

    def test_session_brand_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "session.json")
            with patch.object(client.Session, "path", classmethod(
                    lambda cls: path)):
                s = client.Session(host="192.168.18.138",
                                   device_uuid=UUID,
                                   client_id=f"{UUID}$tos$ABC123_vidaacommon_001",
                                   username="tos$123",
                                   access_token="A", refresh_token="R",
                                   access_time=TS, access_days=2,
                                   brand="tos")
                s.save()
                loaded = client.Session.load()
                self.assertEqual(loaded.brand, "tos")
                # a legacy session without brand stays Hisense-compatible
                import json
                with open(path, encoding="utf-8") as stream:
                    data = json.load(stream)
                del data["brand"]
                with open(path, "w", encoding="utf-8") as stream:
                    json.dump(data, stream)
                legacy = client.Session.load()
                self.assertEqual(legacy.brand, "his")


class TestPairingUsesDescriptorBrand(unittest.TestCase):
    def test_pairing_connection_receives_declared_brand(self):
        seen = []

        class FakeSess:
            def __init__(self, host, uuid, ts, auth_profile="modern",
                         brand="his", **kw):
                seen.append(brand)
                self.topics = protocol.tv_topics("x")
                self.messages = []
            def start(self):
                return 5
            def stop(self):
                pass

        descriptor = client.TvInfo("192.168.18.138", brand="tos",
                                   raw_description=TOSHIBA_DESCRIPTOR)
        with patch.object(client, "MqttSession", FakeSess), \
                patch.object(client, "fetch_descriptor", return_value=descriptor), \
                patch.object(client, "log"):
            with self.assertRaises(ConnectionError):
                client._pairing_connection("192.168.18.138", UUID, TS,
                                           preferred="modern", brand="tos")
        self.assertTrue(seen and all(b == "tos" for b in seen))


if __name__ == "__main__":
    unittest.main()
