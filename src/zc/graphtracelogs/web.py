import datetime
import json
import os
import pool
import pytz
import re
import rrdtool
import socket
import sys
import time
import tempfile
import bobo
import boboserver

inst_rrd = re.compile(r'\S+__\S+__\S+.rrd$').match
numbered_instance = re.compile('instance(\d+)$').match

def config(config):
    global rrd_dir
    rrd_dir = config['rrd']

@bobo.query('/')
def index():
    return open(os.path.join(os.path.dirname(__file__), 'index.html')).read()

@bobo.query('/web.js', content_type="text/javascript")
def js():
    return open(os.path.join(os.path.dirname(__file__), 'web.js')).read()


port_funcs = dict(
    ghm = (lambda i: (i+8)*1000+80),
    cnhi = (lambda i: (i+8)*1000+80),
    hd = (lambda i: 11000+i*100+80),
    tbc = (lambda i: 13000+i*100+80),
    )

@bobo.query(content_type='application/json')
def get_instances():
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
        instances = [by_addr[addr] for addr in addrs
                     if addr in by_addr]
        if len(instances) > 1:
            all = ("%s-%s," % (customer, label))+(','.join(instances))
            instances = [(inst, inst)
                         for inst in sorted(instances)]
            instances.insert(0, ('all', all))
            cpools = customers.get(customer)
            if cpools is None:
                cpools = customers[customer] = {}
            cpools[label] = instances


    import pprint
    pprint.pprint(by_addr)
    pprint.pprint(customers)

    return json.dumps(dict(
        customers=sorted((customer, sorted(customers[customer].items()))
                         for customer in customers)
        ))

@bobo.query('/show.png', content_type='image/png')
def show(instance, start=None, end=None,
         width=900, height=200, step=None,
         log=None, trail=None):
    log = log == 'y'

    lines = []
    if ',' in instance:
        instances = instance.split(',')
        title = instances.pop(0).replace('-', ' ')
        n=0
        for instance in instances:
            instance += '.rrd'
            assert inst_rrd(instance)
            rrd_path = os.path.join(rrd_dir, instance)
            assert os.path.exists(rrd_path)
            lines.extend([
                rrdtool.Def("rpm%s" % n, rrd_path, data_source="rpm",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("epm%s" % n, rrd_path, data_source="epm",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("bl%s" % n, rrd_path, data_source="bl",
                            cf=rrdtool.AverageCF),
                rrdtool.Def("start%s" % n, rrd_path, data_source="start",
                            cf=rrdtool.AverageCF),
                ])
            if log:
                lines.append(
                    rrdtool.Def("spr%s" % n, rrd_path, data_source="spr",
                                cf=rrdtool.AverageCF),
                    )
            n += 1
        lines.extend([
            "CDEF:rpm=rpm0,%s" % (
                ','.join("rpm%s,+" % i for i in range(1, n))),
            "CDEF:epm=epm0,%s" % (
                ','.join("epm%s,+" % i for i in range(1, n))),
            "CDEF:bl=bl0,%s" % (
                ','.join("bl%s,+" % i for i in range(1, n))),
            "CDEF:start=%s,%s,AVG" % (
                ','.join("start%s" % i for i in range(0, n)),
                n
                ),
            ])
        if log:
            lines.append(
                "CDEF:spr=spr0,%s" % (
                    ','.join("spr%s,+" % i for i in range(1, n))),
                )
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
        width=int(width),
        height=int(height),
        title=title,
        )

    if trail:
        options['start'] = int(time.time()/60*60-int(trail)*3600)
    else:
        if start:
            options['start'] = parsedt(start)
        if end:
            options['end'] = parsedt(end)

    if step:
        options['step'] = int(step)*60

    lines.extend([
        rrdtool.LINE1("rpm", rrggbb="00ff00", legend="rpm"),
        rrdtool.LINE1("epm", rrggbb="ff0000", legend="epm"),
        rrdtool.LINE1("bl", rrggbb="e082e6", legend="waiting"),
        'TICK:start#000000aa:1:start',
        ])

    if log:
        options['logarithmic'] = None
        lines.append(
            rrdtool.LINE1("spr", rrggbb="93f9fb", legend="max rpm"),
            )

    import pprint
    pprint.pprint(map(str, lines))

    g.graph(*lines, **options)

    os.close(fd)
    return open(img_path).read()

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

if __name__ == '__main__':
    main(sys.argv[1:])

