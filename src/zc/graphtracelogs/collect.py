import cPickle, datetime, logging, os, pytz, rrdtool, sys, time

logging.basicConfig(level=logging.INFO)

def tliter(f, lineno=0):
    while 1:
        record = f.readline()
        if not record:
            break
        lineno += 1
        record = record.strip().split()
        instance = '__'.join(record[:3])
        if 'T' in record[5]:
            continue
        typ, rid, date, time = record[3:7]
        args = record[7:]
        minute = date + time.rsplit(':', 1)[0]
        yield instance, typ, rid, parsedt(date, time), minute, args, lineno

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

def rrdcreate(rrd, t):
    rrd.create(
        rrdtool.DataSource('rpm', rrdtool.GaugeDST),
        rrdtool.DataSource('epm', rrdtool.GaugeDST),
        rrdtool.DataSource('bl',  rrdtool.GaugeDST),
        rrdtool.DataSource('spr', rrdtool.GaugeDST),
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.5,  1,   1600),
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.5,  5,   2880),
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.5, 60, 24*400),
        start=t, step=60)

dst = pytz.timezone('US/Eastern').dst

def minute2ts(minute):
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
            rrdcreate(self.rrd, self.rrd_last)
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
        if typ not in 'ICAE':
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
                response, _ = args
                if response.startswith('5'):
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

    template = 'rpm', 'epm', 'bl'
    templates = 'rpm', 'epm', 'bl', 'spr'
    def update(self, newminute):
        ts = minute2ts(self.minute)
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
    for instance_name, typ, rid, dt, minute, args, lineno in tliter(f, lineno):
        n += 1
        try:
            requests = state[instance_name]
        except KeyError:
            requests = state[instance_name] = Instance(
                instance_name, minute)
        if typ == 'S':
            requests.reset()
            continue
        requests.event(typ, rid, dt, minute, args)
    return lineno, n

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    log_dir, rrd_dir = args
    log_dir = os.path.abspath(log_dir)
    os.chdir(rrd_dir)
    logs = sorted(f for f in os.listdir(log_dir) if f.endswith('-z4m.log'))
    state = {}
    while len(logs) > 1:
        log_name = logs.pop(0)
        log_path = os.path.join(log_dir, log_name)
        if os.path.exists(log_name+'.endstate'):
            state = cPickle.loads(open(log_name+'.endstate').read())
        else:
            logging.info('processing %s', log_path)
            process_file(open(log_path), state)
            open(log_name+'.endstate', 'w').write(cPickle.dumps(state))

    log_name, = logs
    while 1:
        log_path = os.path.join(log_dir, log_name)
        logging.info('processing %s', log_path)
        assert not os.path.exists(log_name+'.endstate')
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
                open(log_name+'.endstate', 'w').write(cPickle.dumps(state))
                log_name = later_logs.pop()
                break

if __name__ == '__main__':
    main(sys.argv[1:])
