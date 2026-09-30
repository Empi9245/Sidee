"""LAN-only DNS route to the owner's passive collector; no TV/SDK commands."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import pathlib
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent
TARGET = 'vidaahub.com'
HEALTH = '_sidee-dns.vidaahub.com'
MAX_PACKET = 4096


def question(packet):
    if len(packet) < 12:
        raise ValueError('Short DNS header')
    identifier, flags, count, _, _, _ = struct.unpack('!6H', packet[:12])
    if flags & 0xF800 or count != 1:
        raise ValueError('Only a single ordinary query is accepted')
    offset, labels = 12, []
    while True:
        if offset >= len(packet):
            raise ValueError('Short DNS name')
        length = packet[offset]
        offset += 1
        if not length:
            break
        if length > 63 or offset + length > len(packet):
            raise ValueError('Invalid/compressed question name')
        labels.append(packet[offset:offset + length].decode('ascii'))
        offset += length
        if offset > 267:
            raise ValueError('Long DNS name')
    if offset + 4 > len(packet):
        raise ValueError('Short DNS question')
    qtype, qclass = struct.unpack('!2H', packet[offset:offset + 4])
    return identifier, flags, '.'.join(labels).lower(), qtype, qclass, offset + 4


def reply(packet, parsed, code=0, record=None):
    identifier, flags, _, qtype, _, end = parsed
    response_flags = 0x8480 | (flags & 0x0100) | code
    header = struct.pack('!6H', identifier, response_flags, 1, int(record is not None), 0, 0)
    answer = b'' if record is None else b'\xc0\x0c' + struct.pack('!2HIH', qtype, 1, 30, len(record)) + record
    return header + packet[12:end] + answer


def receive_exact(sock, size):
    result = bytearray()
    while len(result) < size:
        chunk = sock.recv(size - len(result))
        if not chunk:
            raise OSError('Short DNS TCP frame')
        result.extend(chunk)
    return bytes(result)


def exchange(packet, address, port=53, tcp=False):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM) as sock:
        sock.settimeout(2)
        sock.connect((address, port))
        if tcp:
            sock.sendall(struct.pack('!H', len(packet)) + packet)
            result = receive_exact(sock, struct.unpack('!H', receive_exact(sock, 2))[0])
        else:
            sock.send(packet)
            result = sock.recv(MAX_PACKET)
        if len(result) < 12 or result[:2] != packet[:2] or not result[2] & 0x80:
            raise OSError('Unmatched DNS answer')
        # TC on UDP is an ordinary request to retry the same query over TCP.
        if not tcp and result[2] & 2:
            return exchange(packet, address, port, tcp=True)
        return result


class LanDNS:
    def __init__(self, bind, network, upstreams, status_path=None, upstream_port=53):
        self.bind = str(ipaddress.IPv4Address(bind))
        self.network = ipaddress.IPv4Network(network, strict=False)
        if not ipaddress.ip_address(bind).is_private or ipaddress.ip_address(bind) not in self.network:
            raise ValueError('Private local bind/network required')
        self.upstreams = [str(ipaddress.IPv4Address(value)) for value in upstreams]
        if not self.upstreams or self.bind in self.upstreams:
            raise ValueError('Independent upstream required')
        self.upstream_port = upstream_port
        self.status_path = status_path
        self.hash = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
        self.marker = f'sidee-lan-dns-v1|{self.bind}|{self.hash}'.encode('ascii')
        self.lock = threading.Lock()
        self.queries = 0
        self.clients = {}
        self.status_errors = 0
        self.last_target = {}

    def _status_locked(self):
        return {'mode': 'isolated-lan-dns', 'pid': os.getpid(), 'bind': self.bind,
                'target': TARGET, 'targetAddress': self.bind, 'sourceSha256': self.hash,
                'targetQueries': self.queries, **self.last_target,
                'clients': {client: dict(item) for client, item in self.clients.items()},
                'statusWriteErrors': self.status_errors, 'checkedAtUnix': time.time(),
                'scope': 'target DNS only; submitted means socket send, not TV receipt; no capture, other-query logging, SDK or native API'}

    def snapshot(self):
        with self.lock:
            return self._status_locked()

    def _write_status_locked(self):
        if self.status_path is None:
            return
        try:
            self.status_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.status_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self._status_locked(), indent=2) + '\n', encoding='utf-8')
            temporary.replace(self.status_path)
        except OSError:
            # A locked/unwritable diagnostic file must never prevent a DNS reply.
            self.status_errors += 1

    def _client_locked(self, client):
        if client not in self.clients and len(self.clients) >= 32:
            return None
        return self.clients.setdefault(client, {'queries': 0, 'repliesSubmitted': 0, 'replyErrors': 0})

    def note_target(self, client, qtype, tcp=False):
        with self.lock:
            self.queries += 1
            now = time.time()
            self.last_target = {'lastTargetClient': client, 'lastTargetType': qtype,
                                'lastTargetAtUnix': now}
            item = self._client_locked(client)
            if item is not None:
                item['queries'] += 1
                item.update(lastQueryType=qtype, lastQueryTransport='TCP' if tcp else 'UDP', lastQueryAtUnix=now)
            # Persist each target event: the old one-second throttle lost the
            # last query of a burst and could hide the TV behind a PC probe.
            self._write_status_locked()

    def note_reply(self, packet, result, client, tcp=False, submitted=True):
        try:
            _, _, name, qtype, qclass, _ = question(packet)
        except (ValueError, UnicodeError):
            return
        if name != TARGET or qclass != 1 or ipaddress.ip_address(client) not in self.network:
            return
        with self.lock:
            item = self._client_locked(client)
            if item is None:
                return
            item['repliesSubmitted' if submitted else 'replyErrors'] += 1
            _, flags, _, answers, _, _ = struct.unpack('!6H', result[:12])
            item.update(lastReplyType=qtype, lastReplyCode=flags & 15, lastReplyAnswers=answers,
                        lastReplyTransport='TCP' if tcp else 'UDP', lastReplyAtUnix=time.time(),
                        lastReplySubmitted=submitted)
            self._write_status_locked()

    def answer(self, packet, client, tcp=False):
        try:
            parsed = question(packet)
        except (ValueError, UnicodeError):
            return packet[:2] + struct.pack('!5H', 0x8001, 0, 0, 0, 0) if len(packet) >= 2 else None
        _, _, name, qtype, qclass, _ = parsed
        if ipaddress.ip_address(client) not in self.network or qclass != 1:
            return reply(packet, parsed, code=5)
        if name == TARGET:
            self.note_target(client, qtype, tcp)
            # AAAA/HTTPS and other types get NOERROR/NODATA, never NXDOMAIN.
            return reply(packet, parsed, record=socket.inet_aton(self.bind) if qtype == 1 else None)
        if name == HEALTH and qtype == 16:
            return reply(packet, parsed, record=bytes([len(self.marker)]) + self.marker)
        for upstream in self.upstreams:
            try:
                return exchange(packet, upstream, self.upstream_port, tcp=tcp)
            except OSError:
                pass
        return reply(packet, parsed, code=2)


class BoundedServer:
    daemon_threads = True
    allow_reuse_address = False

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def process_request(self, request, client_address):
        if not self.workers.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.workers.release()


class UDPServer(BoundedServer, socketserver.ThreadingUDPServer):
    pass


class TCPServer(BoundedServer, socketserver.ThreadingTCPServer):
    pass


class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        packet, sock = self.request
        result = self.server.dns.answer(packet, self.client_address[0])
        if result:
            try:
                sent = sock.sendto(result, self.client_address)
            except OSError:
                self.server.dns.note_reply(packet, result, self.client_address[0], submitted=False)
                return
            self.server.dns.note_reply(packet, result, self.client_address[0], submitted=sent == len(result))


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(3)
        try:
            size = struct.unpack('!H', receive_exact(self.request, 2))[0]
            if not 12 <= size <= MAX_PACKET:
                return
            packet = receive_exact(self.request, size)
            result = self.server.dns.answer(packet, self.client_address[0], tcp=True)
            if result:
                try:
                    self.request.sendall(struct.pack('!H', len(result)) + result)
                except OSError:
                    self.server.dns.note_reply(packet, result, self.client_address[0], tcp=True, submitted=False)
                    return
                self.server.dns.note_reply(packet, result, self.client_address[0], tcp=True)
        except OSError:
            return


def servers(dns, port):
    udp = UDPServer((dns.bind, port), UDPHandler)
    try:
        tcp = TCPServer((dns.bind, udp.server_address[1]), TCPHandler)
    except BaseException:
        udp.server_close()
        raise
    workers = threading.BoundedSemaphore(16)
    for server in (udp, tcp):
        server.dns, server.workers = dns, workers
    return udp, tcp


def health_query():
    name = b''.join(bytes([len(label)]) + label.encode() for label in HEALTH.split('.')) + b'\0'
    return struct.pack('!6H', 0x5344, 0x100, 1, 0, 0, 0) + name + struct.pack('!2H', 16, 1)


def healthy(dns, port):
    packet = health_query()
    parsed = question(packet)
    expected = reply(packet, parsed, record=bytes([len(dns.marker)]) + dns.marker)
    try:
        return all(exchange(packet, dns.bind, port, tcp=tcp) == expected for tcp in (False, True))
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True)
    parser.add_argument('--network', required=True)
    parser.add_argument('--upstream', action='append', required=True)
    parser.add_argument('--port', type=int, default=53)
    parser.add_argument('--background', action='store_true')
    args = parser.parse_args()
    dns = LanDNS(args.bind, args.network, args.upstream, ROOT / 'reports/bridge-domain-dns-status.json')
    if args.background:
        if healthy(dns, args.port):
            print('[LAN-DNS] DNS LAN gia attivo e verificato.', flush=True)
            return
        arguments = [value for value in sys.argv[1:] if value != '--background']
        log_path = ROOT / 'reports/bridge-domain-dns.stdout.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('ab') as log:
            process = subprocess.Popen([sys.executable, str(pathlib.Path(__file__).resolve()), *arguments],
                                       cwd=ROOT, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if healthy(dns, args.port):
                print('[LAN-DNS] DNS LAN avviato e verificato UDP/TCP.', flush=True)
                return
            if process.poll() is not None:
                break
            time.sleep(0.1)
        print('[LAN-DNS] Avvio non verificato; controllare il log locale. Nessun altro servizio fermato.', flush=True)
        raise SystemExit(1)
    try:
        udp, tcp = servers(dns, args.port)
    except OSError:
        if healthy(dns, args.port):
            print('[LAN-DNS] DNS conforme gia attivo; nessun processo fermato.', flush=True)
            return
        print('[LAN-DNS] Porta occupata o non disponibile. Nessun servizio fermato.', flush=True)
        raise SystemExit(1)
    print(f'[LAN-DNS] UDP/TCP {dns.bind}:{args.port}; {TARGET} -> {dns.bind}', flush=True)
    print('[LAN-DNS] Solo LAN. Nessun probe TV, capture, SDK o Git worker.', flush=True)
    thread = threading.Thread(target=tcp.serve_forever, daemon=True)
    thread.start()
    try:
        udp.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        tcp.shutdown()
        udp.server_close()
        tcp.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    main()
