import datetime, json, os, pytz, re, rrdtool, sys, time, tempfile
from rrdtool import *
import bobo, boboserver

inst_rrd = re.compile(r'\S+__\S+__\S+.rrd$').match

def config(config):
    global rrd_dir
    rrd_dir = config['rrd']

@bobo.query('/')
def index():
    return open(os.path.join(os.path.dirname(__file__), 'index.html')).read()

@bobo.query('/web.js', content_type="text/javascript")
def js():
    return open(os.path.join(os.path.dirname(__file__), 'web.js')).read()

@bobo.query(content_type='application/json')
def get_instances():
    return json.dumps(dict(
        instances=[f[:-4] for f in os.listdir(rrd_dir)
                   if inst_rrd(f)]
        ))

@bobo.query('/show.png', content_type='image/png')
def show(instance, start=None, end=None,
         width=900, height=200, step=None,
         log=None):
    instance += '.rrd'
    assert inst_rrd(instance)
    rrd_path = os.path.join(rrd_dir, instance)
    fd, img_path = tempfile.mkstemp('.png')
    g = RoundRobinGraph(img_path)

    options = dict(
        width=int(width),
        height=int(height),
        title='Instance %s' % instance.replace('__', ' '),
        )
    if start:
        options['start'] = parsedt(start)
    if end:
        options['end'] = parsedt(end)
        if not title.endswith('-'):
            title += ' -'
    if step:
        options['step'] = int(step)*60

    lines = [
        Def("rpm", rrd_path, data_source="rpm", cf=AverageCF),
        Def("epm", rrd_path, data_source="epm", cf=AverageCF),
        Def("bl", rrd_path, data_source="bl", cf=AverageCF),
        LINE1("rpm", rrggbb="00ff00", legend="rpm"),
        LINE1("epm", rrggbb="ff0000", legend="epm"),
        LINE1("bl", rrggbb="e082e6", legend="waiting"),
        ]

    if log == 'y':
        options['logarithmic'] = None
        lines.extend((
            Def("spr", rrd_path, data_source="spr", cf=AverageCF),
            LINE1("spr", rrggbb="93f9fb", legend="max rpm"),
            ))

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

