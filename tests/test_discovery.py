"""Regression tests for TV discovery over the local broadcast channel."""
import socket
import unittest
from unittest.mock import Mock, patch

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


class NotifySocket:
    """SSDP multicast listener that delivers queued announcements once."""

    def __init__(self, announcements=()):
        self.queue = list(announcements)
        self.closed = False

    def setsockopt(self, level, option, value):
        pass

    def bind(self, address):
        pass

    def setblocking(self, flag):
        pass

    def recvfrom(self, size):
        if self.queue:
            return self.queue.pop(0)
        raise BlockingIOError()

    def close(self):
        self.closed = True


class TestDiscovery(unittest.TestCase):
    def test_tv_found_when_it_only_answers_broadcast(self):
        connection = DiscoverySocket()
        tv = client.TvInfo("192.168.1.10", "Living room TV", is_vidaa=True)
        # Enough time for one reply, then end the discovery loop immediately.
        with patch.object(client.socket, "socket",
                          side_effect=[connection, NotifySocket()]), \
                patch.object(client, "_local_broadcasts", return_value=["192.168.1.255"]), \
                patch.object(client.time, "time", side_effect=[0, 0, 2]), \
                patch.object(client, "fetch_descriptor", return_value=tv) as fetch:
            self.assertEqual(client.discover(timeout=1), [tv])
        fetch.assert_called_once_with(
            "192.168.1.10",
            "http://192.168.1.10:18400/MediaServer/rendererdevicedesc.xml",
        )
        self.assertTrue(connection.closed)

    def test_tv_found_when_it_only_sends_notify_announcements(self):
        connection = DiscoverySocket()
        connection.recvfrom = Mock(side_effect=socket.timeout())  # no direct reply
        notify = NotifySocket([
            # A TV leaving the network is ignored.
            (b"NOTIFY * HTTP/1.1\r\nNT: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
             b"NTS: ssdp:byebye\r\nLocation: http://192.168.1.99:18400/gone.xml\r\n\r\n",
             ("192.168.1.99", 1900)),
            # Other UPnP devices (here a router) are ignored without a descriptor fetch.
            (b"NOTIFY * HTTP/1.1\r\nNT: urn:schemas-upnp-org:device:InternetGatewayDevice:2\r\n"
             b"NTS: ssdp:alive\r\nLocation: http://192.168.1.1:5000/rootDesc.xml\r\n\r\n",
             ("192.168.1.1", 1900)),
            (b"NOTIFY * HTTP/1.1\r\nServer: Platform 1.0 His/1.0 UPnP/1.0\r\n"
             b"Location: http://192.168.1.10:18400/MediaServer/rendererdevicedesc.xml\r\n"
             b"NT: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
             b"NTS: ssdp:alive\r\n\r\n",
             ("192.168.1.10", 1900)),
        ])
        tv = client.TvInfo("192.168.1.10", "Living room TV", is_vidaa=True)
        with patch.object(client.socket, "socket", side_effect=[connection, notify]), \
                patch.object(client, "_local_broadcasts", return_value=["192.168.1.255"]), \
                patch.object(client.time, "time", side_effect=[0, 0, 2]), \
                patch.object(client, "fetch_descriptor", return_value=tv) as fetch:
            self.assertEqual(client.discover(timeout=1), [tv])
        fetch.assert_called_once_with(
            "192.168.1.10",
            "http://192.168.1.10:18400/MediaServer/rendererdevicedesc.xml",
        )
        self.assertTrue(connection.closed)
        self.assertTrue(notify.closed)

    def test_discovery_continues_when_ssdp_port_is_unavailable(self):
        connection = DiscoverySocket()
        busy = Mock()
        busy.bind.side_effect = OSError("Address already in use")
        tv = client.TvInfo("192.168.1.10", "Living room TV", is_vidaa=True)
        with patch.object(client.socket, "socket", side_effect=[connection, busy]), \
                patch.object(client, "_local_broadcasts", return_value=["192.168.1.255"]), \
                patch.object(client.time, "time", side_effect=[0, 0, 2]), \
                patch.object(client, "fetch_descriptor", return_value=tv):
            self.assertEqual(client.discover(timeout=1), [tv])
        busy.close.assert_called_once()

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
