import cPickle
import logging
import pprint
import re
import string
import time
import zc.ngi
import zc.ngi.adapters
import zc.ngi.blocking
import zc.ngi.async
import zc.ngi.generator

errors = logging.getLogger('errors')

import __main__
class PoolInformation:
    pass
__main__.PoolInformation = PoolInformation
class Server(object):
    pass
__main__.VServer = __main__.RServer = Server

extra_desc = re.compile(r"\{([a-z]+)\}").search

class Sized(zc.ngi.adapters.Sized):

    def set_handler(self, handler):
        self.handler = handler
        self.input = []
        self.want = 9
        self.got = 0
        self.getting_size = True
        self.connection.setHandler(self)

    def handle_input(self, connection, data):
        self.got += len(data)
        self.input.append(data)
        while self.got >= self.want:
            extra = self.got - self.want
            if extra == 0:
                collected = ''.join(self.input)
                self.input = []
            else:
                input = self.input
                self.input = [data[-extra:]]
                input[-1] = input[-1][:-extra]
                collected = ''.join(input)

            self.got = extra

            if self.getting_size:
                # we were recieving the message size
                assert self.want == 9
                self.want = int(collected)
                self.getting_size = False
            else:
                self.want = 9
                self.getting_size = True
                self.handler.handle_input(self, cPickle.loads(collected))

    def write(self, message):
        self.connection.write(message+'\n')

def hex2ip(strng):
    """ Convert a hex IP address to a dotted quad notation string """
    if len(strng) != 8:
        raise IllegalIP, "hex2ip: hex %s is not a valid hex IP" % strng
    l = []
    for i in range(0,8,2):
        l.append(strng[i:i+2])
    l = map(string.atoi, l, (16,16,16,16))
    l = map(str, l)
    return ".".join(l)

def hex2addr(strng):
    """ Convert a hex service address to a dotted-quad:port string """
    ip, port = strng.split(':')
    ip = hex2ip(ip)
    port = string.atoi(port, 16)
    return "%s:%s" % (ip, port)

def get_pools(addr=('lb-prod.att.zope.net', 33333)):

    result = []

    @zc.ngi.generator.handler(connection_adapter=Sized)
    def f(connection):
        connection.write("get metadata")
        data = (yield)
        for addr, v in data.items():
            component = dict((k.replace('_', ''), v)
                             for (k, v) in v.__dict__.items())
            connection.write('get pools %s' % addr)
            pools = (yield)
            for pool in pools:
                vaddr = "%s:%s" % (
                    hex2ip(pool._vip), string.atoi(pool._vport, 16))
                assert vaddr == addr
                raddrs = map(hex2addr, pool._real_servers)
                result.append((component, raddrs))

    _ = zc.ngi.blocking.request(zc.ngi.async.connect, addr, f)
    return result
