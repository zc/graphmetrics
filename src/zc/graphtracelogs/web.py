import BTrees.OOBTree
import bobo
import datetime
import json
import os
import persistent.mapping
import pool
import pprint
import pytz
import re
import rrdtool
import socket
import sys
import tempfile
import time

inst_rrd = re.compile(r'\S+__\S+__\S+.rrd$').match
numbered_instance = re.compile('instance(\d+)$').match

def config(config):
    global rrd_dir
    rrd_dir = config['rrd']


port_funcs = dict(
    ghm = (lambda i: (i+8)*1000+80),
    cnhi = (lambda i: (i+8)*1000+80),
    hd = (lambda i: 11000+i*100+80),
    tbc = (lambda i: 13000+i*100+80),
    )

hex2 = lambda v: ('0'+hex(v)[2:])[-2:]

colors = []
for i in 0, 127, 255:
    for j in 0, 127, 255:
        for k in 0, 127, 255:
            colors.append(hex2(i)+hex2(j)+hex2(k))
ncolors = len(colors)-1

def who(request):
    if 'HTTP_AUTHORIZATION' in request.environ:
        return request.environ['HTTP_AUTHORIZATION'
                               ].split()[1].decode('base64').split(':')[0]
    return 'anon'

@bobo.resource('/')
def home(request):
    return bobo.redirect('%s/default/' % who(request))

@bobo.subroute('/:user/:name', scan=True)
class App:

    def __init__(self, request, user, name):
        self.request = request
        self.user = user
        self.name = name

        root = request.environ['zodb.connection']

    @bobo.query('')
    def base(self):
        return bobo.redirect(self.request.url+'/')

    @bobo.query('/')
    def index(self):
        return open(os.path.join(os.path.dirname(__file__), 'index.html')
                    ).read()

    @bobo.query('/web.js', content_type="text/javascript")
    def js(self):
        return open(os.path.join(os.path.dirname(__file__), 'web.js')).read()

    @property
    def definitions(self):
        root = self.request.environ['zodb.connection'].root()
        try:
            definitions = root['definitions']
        except KeyError:
            definitions = root['definitions'] = BTrees.OOBTree.BTree()
        try:
            return definitions[self.user]
        except KeyError:
            definitions[self.user] = r = BTrees.OOBTree.BTree()
            return r

    @bobo.query(content_type='application/json')
    def load(self):
        defs = self.definitions.get(self.name)
        if defs is None:
            result = dict(charts=[])
        else:
            result = dict(
                charts=[i[1]
                        for i in sorted(defs['charts'].iteritems())
                        ]
                )
        return json.dumps(result)

    @bobo.query(content_type='application/json')
    def get_instances(self):
        customers = {}
        by_addr = {}
        pools = {}
        for inst in sorted(f[:-4] for f in os.listdir(rrd_dir)
                           if inst_rrd(f)):
            host, customer, inst_name = inst.split('__')
            addr = socket.gethostbyname(host)
            m = numbered_instance(inst_name)
            if m:
                port_func = port_funcs.get(customer)
                if port_func is not None:
                    port = port_func(int(m.group(1)))
                    by_addr["%s:%s" % (addr, port)] = inst
            elif inst_name == 'media-instance':
                port = 17080
                by_addr["%s:%s" % (addr, port)] = inst
            hosts = customers.get(customer)
            if hosts is None:
                hosts = customers[customer] = {}

            instances = hosts.get(host)
            if instances is None:
                instances = hosts[host] = []
            instances.append((inst_name, inst))

        for info, addrs in pool.get_pools():
            customer = info['customer'].lower()
            label = "%(pooltype)s-%(desc)s" % info
            instances = sorted([by_addr[addr] for addr in addrs
                                if addr in by_addr])
            if len(instances) > 1:
                all = ("%s-%s," % (customer, label)) + (','.join(instances))
                compare_rpm = (
                    (',rpm,%s-%s-rpm,' % (customer, label))
                    + (','.join(instances)))
                compare_max_rpm = (
                    (',spr,%s-%s-max-rpm,' % (customer, label))
                    + (','.join(instances)))
                instances = [(inst, inst)
                             for inst in sorted(instances)]
                instances[0:0] = [
                    ('all', all),
                    ('compare rpm', compare_rpm),
                    ('compare max rpm', compare_max_rpm),
                    ]
                cpools = customers.get(customer)
                if cpools is None:
                    cpools = customers[customer] = {}
                cpools[label] = instances

        return json.dumps(dict(
            customers=sorted((customer, sorted(customers[customer].items()))
                             for customer in customers)
            ))

    @bobo.query('/show.png', content_type='image/png')
    def show(self, imgid, instance, start=None, end=None,
             width=900, height=None, step=None,
             log=None, trail=None, upper_limit=None, lower_limit=None,
             ):
        params = dict(i for i in dict(
            instance = instance,
            start = start,
            end = end,
            height = height,
            step = step,
            log = log,
            trail=trail,
            upper_limit = upper_limit,
            lower_limit = lower_limit,
            ).iteritems() if i[1])

        log = log == 'y'

        lines = []
        compare = False
        if ',' in instance:
            instances = instance.split(',')
            if not instances[0]:
                instances.pop(0)
                compare = instances.pop(0)
            title = instances.pop(0).replace('-', ' ')
            ninstances = len(instances)
            n=0
            for instance in instances:
                instance += '.rrd'
                assert inst_rrd(instance)
                rrd_path = os.path.join(rrd_dir, instance)
                assert os.path.exists(rrd_path)
                if compare:
                    lines.extend([
                        rrdtool.Def("v%s" % n, rrd_path, data_source=compare,
                                    cf=rrdtool.AverageCF),
                        "LINE1:v%s#%s:%s" % (
                            n, colors[(n*ncolors/ninstances) % len(colors)],
                            instance[:-4]),
                        ])
                else:
                    lines.extend([
                        rrdtool.Def("rpm%s" % n, rrd_path, data_source="rpm",
                                    cf=rrdtool.AverageCF),
                        rrdtool.Def("epm%s" % n, rrd_path, data_source="epm",
                                    cf=rrdtool.AverageCF),
                        rrdtool.Def("bl%s" % n, rrd_path, data_source="bl",
                                    cf=rrdtool.AverageCF),
                        ])
                    if log:
                        lines.append(
                            rrdtool.Def("spr%s" % n, rrd_path,
                                        data_source="spr",
                                        cf=rrdtool.AverageCF),
                            )
                lines.append(
                    rrdtool.Def("start%s" % n, rrd_path,
                                data_source="start",
                                cf=rrdtool.AverageCF)
                    )
                n += 1
            if not compare:
                lines.extend([
                    "CDEF:rpm=rpm0,%s" % (
                        ','.join("rpm%s,+" % i for i in range(1, n))),
                    "CDEF:epm=epm0,%s" % (
                        ','.join("epm%s,+" % i for i in range(1, n))),
                    "CDEF:bl=bl0,%s" % (
                        ','.join("bl%s,+" % i for i in range(1, n))),
                    ])
                if log:
                    lines.append(
                        "CDEF:spr=spr0,%s" % (
                            ','.join("spr%s,+" % i for i in range(1, n))),
                        )
            lines.append("CDEF:start=%s,%s,AVG" % (
                ','.join("start%s" % i for i in range(0, n)),
                n))
        else:
            title = instance.replace('__', ' ')
            instance += '.rrd'
            assert inst_rrd(instance)
            rrd_path = os.path.join(rrd_dir, instance)
            assert os.path.exists(rrd_path)
            lines.extend([
                rrdtool.Def("rpm", rrd_path, data_source="rpm",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("epm", rrd_path, data_source="epm",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("bl", rrd_path, data_source="bl",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("start", rrd_path, data_source="start",
                            cf=rrdtool.AverageCF),
                ])
            if log:
                lines.append(
                    rrdtool.Def("spr", rrd_path, data_source="spr",
                                cf=rrdtool.AverageCF),
                    )

        rrd_path = os.path.join(rrd_dir, instance)
        fd, img_path = tempfile.mkstemp('.png')
        g = rrdtool.RoundRobinGraph(img_path)

        options = dict(
            width=int(width)-70,
            height=height and int(height) or 200,
            title=title,
            )
        if upper_limit:
            options['upper_limit'] = int(upper_limit)
            options['rigid'] = None
        if lower_limit:
            options['lower_limit'] = int(lower_limit)
            options['rigid'] = None

        if trail:
            options['start'] = int(time.time()/60*60-int(trail)*3600)
        else:
            if start:
                options['start'] = parsedt(start)
            if end:
                options['end'] = parsedt(end)

        if step:
            options['step'] = int(step)*60

        if not compare:
            lines.extend([
                rrdtool.LINE1("rpm", rrggbb="00ff00", legend="rpm"),
                rrdtool.LINE1("epm", rrggbb="ff0000", legend="epm"),
                rrdtool.LINE1("bl", rrggbb="e082e6", legend="waiting"),
                ])

            if log:
                options['logarithmic'] = None
                lines.append(
                    rrdtool.LINE1("spr", rrggbb="93f9fb", legend="max rpm"),
                    )
        else:
            if log:
                options['logarithmic'] = None
        lines.append('TICK:start#00000055:1:start')

        g.graph(*lines, **options)

        if self.user == who(self.request):
            defs = self.definitions.get(self.name)
            if defs is None:
                defs = persistent.mapping.PersistentMapping(
                    charts=persistent.mapping.PersistentMapping())
                self.definitions[self.name] = defs
            if params != defs['charts'].get(imgid):
                defs['charts'][imgid] = params

        os.close(fd)
        return open(img_path).read()

    @bobo.query('/destroy')
    def destroy(self, imgid):
        if self.user == who(self.request):
            defs = self.definitions.get(self.name)
            if defs is None:
                return
            if imgid in defs['charts']:
                del defs['charts'][imgid]
        return ''

dst = pytz.timezone('US/Eastern').dst

def parsedt(s):
    if 'T' in s:
        d, t = s.split('T')
        t = d.split('-')+t.split(':')
    else:
        t = s.split('-')
    t = map(int, t)

    t.extend([0]*(8-len(t)))
    t.append(bool(dst(datetime.datetime(*t[:6])).seconds))
    return int(time.mktime(t))
