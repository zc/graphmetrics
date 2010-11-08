import cPickle
import datetime
import gzip
import logging
import optparse
import os
import pytz
import rrdtool
import socket
import sys
import time
import zc.graphtracelogs

# Gaaaa, pickles!
sys.modules['zc.graphtracelogs.collect'] = sys.modules[__name__]
zc.graphtracelogs.collect = sys.modules[__name__]

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)s %(levelname)s %(message)r',
                    )

hostcache = {}
def gethost(name):
    r = hostcache.get(name)
    now = time.time()
    if r and (now-r[1] < 999):
        return r[0]
    host = socket.gethostbyname(name)
    hostcache[name] = host, now
    return host

def tliter(f, lineno):
    while 1:
        line = f.readline()
        if not line:
            break
        lineno += 1
        try:
            record = line.strip().split()
            if record[3] == ':':
                # Gaaa syslog-ng 3
                record.pop(3)

            instance = '__'.join(record[:3])
            if 'T' in record[5]:
                continue
            typ, rid, date, time = record[3:7]
            args = record[7:]
            minute = date + time.rsplit(':', 1)[0]
            yield (instance, typ, rid, parsedt(date, time), minute, args,
                   lineno, line)
        except:
            logging.exception('Bad log record line %r: %r', lineno, line)

def parsedt(date, time):
    if '.' in time:
        time, ms = time.split('.')
        ms = int(ms)
    else:
        ms = 0
    return datetime.datetime(*(
        map(int, date.split('-'))
        +
        map(int, time.split(':'))
        +
        [ms]
        ))

def rrdcreate(rrd, t, name):
    f = open('.updated', 'w')
    f.write(name)
    f.close()
    rrd.create(
        rrdtool.DataSource('rpm', rrdtool.GaugeDST),
        rrdtool.DataSource('epm', rrdtool.GaugeDST),
        rrdtool.DataSource('bl',  rrdtool.GaugeDST),
        rrdtool.DataSource('spr', rrdtool.GaugeDST),
        rrdtool.DataSource('start', rrdtool.GaugeDST),
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.99,  1,   1600),
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.99,  5,   2880),
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.99, 60, 24*400),
        start=t, step=60)

dst = pytz.timezone('US/Eastern').dst

def minute2ts(minute):
    # Convert a local minute to a timetime
    args = map(int, minute[:10].split('-'))+map(int, minute[10:].split(':'))
    return int(time.mktime(
        tuple(args)+(0, 0, 0, bool(dst(datetime.datetime(*args)).seconds))))


class Instance(dict):

    def __init__(self, name, minute):
        self.name = name
        rrd_path = name+'.rrd'
        self.rrd = rrdtool.RoundRobinDatabase(rrd_path)
        if not os.path.exists(rrd_path):
            self.rrd_last = minute2ts(minute)-60
            rrdcreate(self.rrd, self.rrd_last, name)
        else:
            self.rrd_last = self.rrd.last()
        self.reset()

    last = None

    def __setstate__(self, v):
        self.__dict__.clear()
        self.__dict__.update(v)
        self.rrd_last = self.rrd.last()

    def reset(self):
        self.clear()
        self.waiting = self.requests = self.errors = 0
        self.seconds = self.secondsn = 0
        self.minute = None

    def event(self, typ, rid, dt, minute, args):
        if typ == 'E' and rid in self:
            if self[rid] == 'I':
                self.waiting -= 1
            del self[rid]
            return

        if typ not in 'ICA':
            return

        if (self.last is not None) and (dt < self.last):
            # file got reset. Whimper.
            return self.reset()
        else:
            self.last = dt

        if self.minute is None:
            self.minute = minute
        elif minute > self.minute:
            self.update(minute)
        else:
            assert minute == self.minute

        if typ == 'I':
            if rid in self:
                if self[rid] == 'I':
                    self.waiting -= 1
            self.waiting += 1
            self[rid] = 'I'
        elif rid in self:
            if typ == 'C':
                self.waiting -= 1
                self[rid] = dt
            elif typ == 'A':
                response = args[0]
                if response[0] in '5E':
                    self.errors += 1
                self.requests += 1
                if isinstance(self[rid], datetime.datetime):
                    self.seconds += dt_diff_seconds(dt, self[rid])
                    self.secondsn += 1
                self[rid] = typ
            elif typ == 'E':
                if self[rid] == 'I':
                    self.waiting -= 1
                del self[rid]

    start_template = 'start',
    def start(self, dt):
        ts = int(time.mktime((
            dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, 0, 0,
            bool(dst(dt).seconds)
            )))
        if ts > self.rrd_last:
            self.rrd.update(rrdtool.Val(1, timestamp=ts),
                            template=self.start_template)
        self.reset()

    template = 'rpm', 'epm', 'bl'
    templates = 'rpm', 'epm', 'bl', 'spr'
    def update(self, newminute):
        ts = minute2ts(self.minute)+60
        if ts > self.rrd_last:
            if self.secondsn:
                self.rrd.update(
                    rrdtool.Val(self.requests, self.errors, self.waiting,
                                self.secondsn*60/self.seconds,
                                timestamp=ts),
                    template = self.templates)
            else:
                self.rrd.update(
                    rrdtool.Val(self.requests, self.errors, self.waiting,
                                timestamp=ts),
                    template = self.template)
        self.requests = self.errors = self.secondsn = self.seconds = 0
        self.minute = newminute

    def __repr__(self):
        return repr((dict(self), self.last, self.minute,
                     self.waiting, self.requests, self.errors))

def dt_diff_seconds(d2, d1):
    d = d2-d1
    return d.days*86400+d.seconds+d.microseconds/1000000.0

def process_file(f, state, lineno=0):
    n=0
    for instance_name, typ, rid, dt, minute, args, lineno, line in tliter(
        f, lineno):
        n += 1
        try:
            requests = state[instance_name]
        except KeyError:
            requests = state[instance_name] = Instance(
                instance_name, minute)
        if typ == 'S':
            requests.start(dt)
            continue
        try:
            requests.event(typ, rid, dt, minute, args)
        except pytz.tzinfo.AmbiguousTimeError:
            # Gaaaaaa fricking DST
            requests.reset()

    return lineno, n

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    log_dir, rrd_dir = args
    log_dir_name = os.path.basename(log_dir)+'-'
    log_dir = os.path.abspath(log_dir)
    os.chdir(rrd_dir)
    logs = sorted(f for f in os.listdir(log_dir)
                  if f.endswith('-z4m.log') or f.endswith('-z4m.log.gz'))
    state = {}

    while len(logs) > 1:
        log_name = logs.pop(0)
        log_path = os.path.join(log_dir, log_name)
        endstate_name = log_dir_name+log_name
        if endstate_name.endswith('.gz'):
            endstate_name = endstate_name[:-3]
        endstate_name += '.endstate'
        if os.path.exists(endstate_name):
            state = cPickle.loads(open(endstate_name).read())
        else:
            logging.info('processing %s', log_path)
            if log_path.endswith('.gz'):
                f = gzip.GzipFile(log_path)
            else:
                f = open(log_path)
            process_file(f, state)
            open(endstate_name, 'w').write(cPickle.dumps(state))

    log_name, = logs
    while 1:
        log_path = os.path.join(log_dir, log_name)
        logging.info('processing %s', log_path)
        assert not os.path.exists(log_dir_name+log_name+'.endstate')
        log_file = open(log_path)
        lineno = 0
        while 1:
            lineno, n = process_file(log_file, state, lineno)
            later_logs = ((not n)
                          and
                          sorted(f for f in os.listdir(log_dir)
                                 if f.endswith('-z4m.log') and f > log_name)
                          )
            time.sleep(10)
            if later_logs:
                # Make sure we got the tail of the file
                lineno, n = process_file(log_file, state, lineno)
                if n:
                    continue
                open(log_dir_name+log_name+'.endstate', 'w').write(
                    cPickle.dumps(state))
                log_name = later_logs.pop()
                break

if __name__ == '__main__':
    main(sys.argv[1:])
