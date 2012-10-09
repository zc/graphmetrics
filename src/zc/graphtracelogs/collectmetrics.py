import datetime
import logging
import os
import pytz
import rrdtool
import sys
import time
import threading
import zc.ngi.adapters
import zc.ngi.async
import zc.ngi.generator

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)s %(levelname)s %(message)r',
                    )

logger = logging.getLogger(__name__)

eastern = pytz.timezone('US/Eastern')

class Collector:

    def __init__(self, connector, addr, rrd_dir):
        assert os.path.isdir(rrd_dir), rrd_dir
        self.rrd_dir = os.path.abspath(rrd_dir)
        self.rrds = {} # path -> rrd
        self.connector = connector
        self.addr = addr
        connector(addr, self)

    @zc.ngi.generator.handler(connection_adapter=zc.ngi.adapters.Lines)
    def connected(self, connection):
        connection.write('subscribe metrics\n')
        rrd_dir = self.rrd_dir
        rrds = self.rrds
        badhosts = set()

        while 1:
            try:
                line = (yield)
                if not line.startswith('METRIC:\t'):
                    continue
                date, time_, elem, units, value = line.split()[1:]
                l = datetime.datetime(*(tuple(map(int, date.split('-')))+
                                        tuple(map(int, time_.split(':')))),
                                      tzinfo=pytz.utc).astimezone(eastern)
                l = l.year, l.month, l.day, l.hour, l.minute, l.second
                ts = int(time.mktime(
                    l+(0, 0)+(bool(eastern.dst(datetime.datetime(*l))),)))
                assert elem.startswith('element://')
                elem = elem[10:].replace(':','..')
                host = elem.split('/', 1)[0]
                if '.' not in host:
                    if host not in badhosts:
                        badhosts.add(host)
                        logger.error('Bad host in %r', line)
                    continue
                path = os.path.join(rrd_dir, elem)+'.rrd'
                assert path.startswith(rrd_dir+'/'), path
                rrd = rrds.get(path)
                if rrd is None:
                    rrd = rrds[path] = rrdtool.RoundRobinDatabase(path)
                    if not os.path.exists(path):
                        d = os.path.dirname(path)
                        if not os.path.exists(d):
                            os.makedirs(d)
                        else:
                            assert os.path.isdir(d)
                        rrd.create(
                            rrdtool.DataSource('data', rrdtool.GaugeDST, 500),
                            rrdtool.RoundRobinArchive(
                                rrdtool.AverageCF, 0.99,  1,   2880),
                            rrdtool.RoundRobinArchive(
                                rrdtool.AverageCF, 0.99, 12, 24*400),
                            start=(ts-60)//300*300, step=300)
                        f = open(os.path.join(rrd_dir, '.updated'), 'w')
                        f.write(path)
                        f.close()
                    rrd.rrd_last = rrd.last()
                if ts < rrd.rrd_last:
                    # logger.error('ts out of order %s %s %s %s',
                    #              line, path, ts, rrd.rrd_last)
                    continue
                if ts == rrd.rrd_last:
                    ts += 1
                rrd.update(rrdtool.Val(float(value), timestamp=ts))
                rrd.rrd_last = ts
            except GeneratorExit:       # Disconnected
                logger.info('disconnected')
                self.connector(self.addr, self)
                break
            except:                     # Unexpected error
                logger.exception('failure in input handler')
                connection.close()
                self.connector(self.addr, self)
                break

    def failed_connect(self, reason):
        # We can sleep here because we essentially own the thread.
        logger.warning('failed connect')
        time.sleep(10)
        self.connector(self.addr, self)

def main(args=None):
    if args is None:
        args = sys.argv[1:]

    rrd_dir, addr = args
    addr = addr.split(':')
    Collector(zc.ngi.async.connect, (addr[0], int(addr[1])), rrd_dir)
    threading.Event().wait() # forever
