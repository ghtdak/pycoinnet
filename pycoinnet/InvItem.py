from pycoin.serialize import b2h_rev
from pycoin.serialize.bitcoin_streamer import parse_struct, stream_struct


class InvItem(object):

    def __init__(self, item_type, data):
        self.item_type = item_type
        self.data = data

    def __str__(self):
        INV_TYPES = [None, "Tx", "Block"]
        return "%s [%s]" % (INV_TYPES[self.item_type], b2h_rev(self.data))

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash(self.data)

    def stream(self, f):
        stream_struct("L#", f, self.item_type, self.data)

    @classmethod
    def parse(self, f):
        return self(*parse_struct("L#", f))
