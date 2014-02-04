#!/usr/bin/env python
"""
This bitcoin client does little more than try to keep an up-to-date
list of available clients in a text file "addresses".
"""

import asyncio
import binascii
import logging
import random
import time

from pycoinnet.peer.BitcoinPeerProtocol import BitcoinPeerProtocol


class AddressDB(object):

    def __init__(self, path):
        self.path = path
        self.addresses = self.load_addresses()
        self.shuffled = []

    def load_addresses(self):
        """
        Return an array of (host, port, timestamp) triples.
        """
        addresses = {}
        try:
            with open(self.path) as f:
                for l in f:
                    timestamp, host, port = l[:-1].split("/")
                    timestamp = int(timestamp)
                    port = int(port)
                    addresses[(host, port)] = timestamp
        except Exception:
            logging.error("can't open %s, using default", self.path)
            for h in [
                    "bitseed.xf2.org", "dnsseed.bluematt.me",
                    "seed.bitcoin.sipa.be", "dnsseed.bitcoin.dashjr.org"
            ]:
                addresses[(h, 8333)] = 1
        return addresses

    def next_address(self):
        if len(self.shuffled) == 0:
            self.shuffled = list(self.addresses.keys())
            random.shuffle(self.shuffled)
        return self.shuffled.pop()

    def remove_address(self, host, port):
        key = (host, port)
        del self.addresses[key]

    def add_address(self, host, port, timestamp):
        key = (host, port)
        old_timestamp = self.addresses.get(key) or timestamp
        self.addresses[key] = max(timestamp, old_timestamp)

    def add_addresses(self, addresses):
        for timestamp, host, port in addresses:
            self.add_address(host, port, timestamp)

    def save(self):
        if len(self.addresses) < 2:
            logging.error("too few addresses: not overwriting")
            return
        with open(self.path, "w") as f:
            for host, port in self.addresses:
                f.write("%d/%s/%d\n" %
                        (self.addresses[(host, port)], host, port))


class AddressKeeper:

    def __init__(self, peer, address_db):
        self.address_db = address_db
        peer.register_delegate(self)
        self.address_db = address_db

    def handle_msg_addr(self, peer, date_address_tuples):
        self.address_db.add_addresses(
            (timestamp, address.ip_address.exploded, address.port)
            for timestamp, address in date_address_tuples)
        self.address_db.save()
        # we got addresses from this client. Exit loop and disconnect
        peer.stop()


@asyncio.coroutine
def connect_to_remote(event_loop, magic_header, address_db, connections):
    host, port = address_db.next_address()
    logging.info("connecting to %s port %d", host, port)
    try:
        transport, peer = yield from event_loop.create_connection(
            lambda: BitcoinPeerProtocol(magic_header),
            host=host,
            port=port)
    except Exception:
        logging.exception("failed to connect to %s:%d", host, port)
        address_db.remove_address(host, port)
        address_db.save()
        return

    try:
        logging.info("connected to %s:%d", host, port)
        AddressKeeper(peer, address_db)
        address_db.add_address(host, port, int(time.time()))
        connections.add(transport)
        peer.run()
    except Exception:
        logging.exception("exception talking to %s:%d", host, port)
    logging.info("done talking to %s:%d", host, port)
    connections.remove(transport)


def keep_minimum_connections(event_loop, min_connection_count=4):
    connections = set()
    address_db = AddressDB("addresses.txt")
    magic_header = binascii.unhexlify('F9BEB4D9')  # use 0B110907 for testnet3
    while 1:
        logging.debug("connection count is %d", len(connections))
        difference = min_connection_count - len(connections)
        for i in range(difference * 2):
            asyncio.Task(connect_to_remote(event_loop, magic_header, address_db,
                                           connections))
        yield from asyncio.sleep(10)


def main():
    logging.basicConfig(level=logging.INFO,
                        format=('%(asctime)s [%(process)d] [%(levelname)s] '
                                '%(filename)s:%(lineno)d %(message)s'))
    event_loop = asyncio.get_event_loop()
    asyncio.Task(keep_minimum_connections(event_loop))
    event_loop.run_forever()


main()
