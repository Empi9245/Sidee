"""Regression tests for TV discovery over the local broadcast channel."""
import socket
import unittest
from unittest.mock import patch

from core import client


class DiscoverySocket:
    """Simulate Windows rejecting broadcasts unless explicitly enabled."""

    def __init__(self):
        self.broadcast_enabled = False
        self.sent = []
        self.closed = False
        self.replied = False

    def setsockopt(self, level, option, value):
        if (level, option) == (socket.SOL_SOCKET, socket.SO_BROADCAST):
            self.broadcast_enabled = bool(value)

    def bind(self, address):
        pass

    def settimeout(self, timeout):
        pass

    def sendto(self, message, address):
        if address[0].endswith(".255") and not self.broadcast_enabled:
            raise PermissionError("Broadcast not enabled")
        self.sent.append((message, address))

    def recvfrom(self, size):
        if not self.replied and any(a[0] == "192.168.1.255"
                                   for _, a in self.sent):
            self.replied = True
            return (
                b"HTTP/1.1 200 OK\r\n"
                b"LOCATION: http://192.168.1.10:18400/MediaServer/rendererdevicedesc.xml\r\n\r\n",
                ("192.168.1.10", 1900),
            )
        raise socket.timeout()

    def close(self):
        self.closed = True


class TestDiscovery(unittest.TestCase):
    def test_tv_found_when_it_only_answers_broadcast(self):
        connection = DiscoverySocket()
        tv = client.TvInfo("192.168.1.10", "Living room TV", is_vidaa=True)
        # Enough time for one reply, then end the discovery loop immediately.
        with patch.object(client.socket, "socket", return_value=connection), \
                patch.object(client, "_local_broadcasts", return_value=["192.168.1.255"]), \
                patch.object(client.time, "time", side_effect=[0, 0, 2]), \
                patch.object(client, "fetch_descriptor", return_value=tv) as fetch:
            self.assertEqual(client.discover(timeout=1), [tv])
        fetch.assert_called_once_with(
            "192.168.1.10",
            "http://192.168.1.10:18400/MediaServer/rendererdevicedesc.xml",
        )
        self.assertTrue(connection.closed)

    def test_localized_adapters_use_their_actual_subnet_masks(self):
        output = """Scheda Ethernet vEthernet:
   Indirizzo IPv4. . . : 172.19.208.1
   Subnet mask . . . . : 255.255.240.0
   Gateway . . . . . . :
Scheda Ethernet Ethernet:
   Indirizzo IPv4. . . : 192.168.1.5
   Subnet mask . . . . : 255.255.255.0
   Gateway . . . . . . : 192.168.1.1
"""
        self.assertEqual(client._broadcasts_from_ipconfig(output),
                         ["172.19.223.255", "192.168.1.255"])

    def test_invalid_masks_and_loopback_are_ignored(self):
        output = """IPv4: 192.168.1.5
Mask: 255.0.255.0
IPv4: 127.0.0.1
Mask: 255.0.0.0
IPv4: 10.0.0.1
Mask: 255.255.255.255
"""
        self.assertEqual(client._broadcasts_from_ipconfig(output), [])

    def test_search_matches_the_measured_mobile_app_request(self):
        connection = DiscoverySocket()
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client._msearch(connection, client.SSDP_BROADCAST)
        message, address = connection.sent[0]
        self.assertEqual(address, (client.SSDP_BROADCAST, 1900))
        self.assertIn(b"ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n", message)
        self.assertIn(b"CONTENT-LENGTH: 0\r\n", message)
        self.assertTrue(message.endswith(b"\r\n\r\n"))


if __name__ == "__main__":
    unittest.main()
