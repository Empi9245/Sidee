import json
import pathlib
import socket
import socketserver
import struct
import threading
import tempfile
import unittest
from unittest.mock import patch

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
    def test_rapid_target_events_keep_both_clients_and_send_failures(self):
        with tempfile.TemporaryDirectory(prefix='sidee-dns-status-') as directory:
            path = pathlib.Path(directory) / 'status.json'
            dns = LanDNS('192.168.1.5', '192.168.1.0/24', ['192.168.1.1'], path)
            a = query('vidaahub.com')
            result = dns.answer(a, '192.168.1.10')
            dns.note_reply(a, result, '192.168.1.10')
            dns.answer(a, '192.168.1.5')
            empty = query('vidaahub.com', 28)
            result = dns.answer(empty, '192.168.1.10', tcp=True)
            dns.note_reply(empty, result, '192.168.1.10', tcp=True, submitted=False)
            saved = json.loads(path.read_text())
            self.assertEqual(saved['targetQueries'], 3)
            self.assertEqual(saved['clients']['192.168.1.5']['queries'], 1)
            tv = saved['clients']['192.168.1.10']
            self.assertEqual((tv['queries'], tv['repliesSubmitted'], tv['replyErrors']), (2, 1, 1))
            self.assertEqual((tv['lastReplyType'], tv['lastReplyCode'], tv['lastReplyAnswers']), (28, 0, 0))
            self.assertEqual(tv['lastReplyTransport'], 'TCP')
            self.assertFalse(tv['lastReplySubmitted'])
            # No other-name source or event is saved by this diagnostic.
            other = query('ordinary.invalid')
            dns.note_reply(other, reply(other, question(other)), '192.168.1.10')
            self.assertEqual(json.loads(path.read_text()), saved)
            self.assertNotIn('ordinary.invalid', path.read_text())

    def test_unwritable_diagnostics_do_not_break_actual_udp_or_tcp(self):
        with tempfile.TemporaryDirectory(prefix='sidee-dns-write-failure-') as directory:
            dns = LanDNS('127.0.0.1', '127.0.0.0/8', ['127.0.0.2'], pathlib.Path(directory) / 'status.json')
            udp, tcp = servers(dns, 0)
            workers = [threading.Thread(target=server.serve_forever, daemon=True) for server in (udp, tcp)]
            for worker in workers:
                worker.start()
            submitted = threading.Event()
            note_reply = dns.note_reply

            def observed_reply(*args, **kwargs):
                note_reply(*args, **kwargs)
                submitted.set()

            try:
                with patch.object(pathlib.Path, 'replace', side_effect=PermissionError('fixture file locked')):
                    with patch.object(dns, 'note_reply', side_effect=observed_reply):
                        for use_tcp in (False, True):
                            submitted.clear()
                            result = exchange(query('vidaahub.com'), '127.0.0.1', udp.server_address[1], tcp=use_tcp)
                            self.assertEqual(result[-4:], socket.inet_aton('127.0.0.1'))
                            self.assertTrue(submitted.wait(timeout=3))
                saved = dns.snapshot()
                self.assertEqual(saved['statusWriteErrors'], 4)
                client = saved['clients']['127.0.0.1']
                self.assertEqual((client['queries'], client['repliesSubmitted'], client['replyErrors']), (2, 2, 0))
                self.assertEqual((client['lastReplyCode'], client['lastReplyAnswers']), (0, 1))
            finally:
                for server in (udp, tcp):
                    server.shutdown()
                    server.server_close()
                for worker in workers:
                    worker.join(timeout=3)

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
