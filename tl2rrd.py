import datetime, os, pytz, rrdtool, sys, time

def tliter(f):
    lineno = 0
    for record in f:
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
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.5, 1, 1600),
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.5, 5, 2880),
        rrdtool.RoundRobinArchive(rrdtool.AverageCF, 0.5, 60, 60*400),
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
            rrdcreate(self.rrd, minute2ts(minute)-60)
        self.reset()

    last = None

    def reset(self):
        self.clear()
        self.waiting = self.requests = self.errors = 0
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
                self[rid] = typ
            elif typ == 'A':
                response, _ = args
                if response.startswith('5'):
                    self.errors += 1
                self.requests += 1
                self[rid] = typ
            elif typ == 'E':
                if self[rid] == 'I':
                    self.waiting -= 1
                del self[rid]

    template = 'rpm', 'epm', 'bl'
    def update(self, newminute):
        #print self.name, self.minute, self.requests, self.errors, self.waiting
        self.rrd.update(
            rrdtool.Val(self.requests, self.errors, self.waiting,
                        timestamp=minute2ts(self.minute)),
            template = self.template)
        self.requests = self.errors = 0
        self.minute = newminute

def main(args):
    fname, = args

    state = {}

    for instance_name, typ, rid, dt, minute, args, lineno in tliter(
        open(fname)):

        try:
            requests = state[instance_name]
        except KeyError:
            requests = state[instance_name] = Instance(instance_name, minute)

        if typ == 'S':
            requests.reset()
            continue

        requests.event(typ, rid, dt, minute, args)

if __name__ == '__main__':
    main(sys.argv[1:])
