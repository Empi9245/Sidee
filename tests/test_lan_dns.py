import socket
import socketserver
import struct
import threading
import unittest

from lan_dns import LanDNS, exchange, healthy, question, receive_exact, reply, servers


def query(name, qtype=1):
    labels = b''.join(bytes([len(label)]) + label.encode() for label in name.split('.')) + b'\0'
    return struct.pack('!6H', 123, 0x100, 1, 0, 0, 0) + labels + struct.pack('!2H', qtype, 1)


class Upstream(socketserver.BaseRequestHandler):
    def handle(self):
        packet, sock = self.request
        sock.sendto(reply(packet, question(packet), record=socket.inet_aton('192.0.2.10')), self.client_address)


class UpstreamTCP(socketserver.BaseRequestHandler):
    def handle(self):
        size = struct.unpack('!H', receive_exact(self.request, 2))[0]
        packet = receive_exact(self.request, size)
        result = reply(packet, question(packet), record=socket.inet_aton('192.0.2.10'))
        self.request.sendall(struct.pack('!H', len(result)) + result)


class LanDNSTest(unittest.TestCase):
    def test_actual_udp_tcp_route_nodata_and_forwarding(self):
        upstream = socketserver.ThreadingUDPServer(('127.0.0.2', 0), Upstream)
        upstream_tcp = socketserver.ThreadingTCPServer(upstream.server_address, UpstreamTCP)
        upstream_workers = [threading.Thread(target=server.serve_forever, daemon=True) for server in (upstream, upstream_tcp)]
        for worker in upstream_workers:
            worker.start()
        dns = LanDNS('127.0.0.1', '127.0.0.0/8', ['127.0.0.2'], upstream_port=upstream.server_address[1])
        udp, tcp = servers(dns, 0)
        workers = [threading.Thread(target=server.serve_forever, daemon=True) for server in (udp, tcp)]
        for worker in workers:
            worker.start()
        try:
            for use_tcp in (False, True):
                a = exchange(query('vidaahub.com'), '127.0.0.1', udp.server_address[1], tcp=use_tcp)
                self.assertEqual(struct.unpack('!6H', a[:12])[3], 1)
                self.assertEqual(a[-4:], socket.inet_aton('127.0.0.1'))
                for qtype in (28, 65):
                    empty = exchange(query('vidaahub.com', qtype), '127.0.0.1', udp.server_address[1], tcp=use_tcp)
                    header = struct.unpack('!6H', empty[:12])
                    self.assertEqual(header[1] & 15, 0)
                    self.assertEqual(header[3], 0)
                forwarded = exchange(query('ordinary.invalid'), '127.0.0.1', udp.server_address[1], tcp=use_tcp)
                self.assertEqual(forwarded[-4:], socket.inet_aton('192.0.2.10'))
            self.assertTrue(healthy(dns, udp.server_address[1]))
            dns.marker += b'-different-build'
            self.assertTrue(healthy(dns, udp.server_address[1]))
            other = LanDNS('127.0.0.1', '127.0.0.0/8', ['127.0.0.2'])
            self.assertFalse(healthy(other, udp.server_address[1]))
            denied = dns.answer(query('vidaahub.com'), '192.168.1.7')
            self.assertEqual(struct.unpack('!6H', denied[:12])[1] & 15, 5)
            self.assertEqual(dns.answer(b'xx', '127.0.0.1')[3] & 15, 1)
            with self.assertRaises(OSError):
                servers(dns, udp.server_address[1])
            self.assertEqual(exchange(query('vidaahub.com'), '127.0.0.1', udp.server_address[1])[-4:], socket.inet_aton('127.0.0.1'))
        finally:
            for server in (udp, tcp, upstream, upstream_tcp):
                server.shutdown()
                server.server_close()
            for worker in workers + upstream_workers:
                worker.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
