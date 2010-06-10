import datetime, os, pytz, rrdtool, sys, time, tempfile
from rrdtool import *
import bobo

@bobo.query('/show.png', content_type='image/png')
def show(instance, start=None, end=None,
         width=900, height=200, step=None,
         log=None):
    rrd_path = 'app2.ghm.zope.net__GHM__instance%s.rrd' % str(instance)
    fd, img_path = tempfile.mkstemp('.png')
    g = RoundRobinGraph(img_path)

    title = 'Instance %s' % instance

    options = {}
    if start:
        options['start'] = parsedt(start)
        title += ' %s-' % start
    if end:
        options['end'] = parsedt(end)
        if not title.endswith('-'):
            title += ' -'
        title += end
    if step:
        options['step'] = int(step)*60
    if log is not None:
        options['logarithmic'] = None


    print 'wtf', rrd_path

    g.graph(
        # 3-level key
        Def("rpm", rrd_path, data_source="rpm", cf=AverageCF),
        Def("epm", rrd_path, data_source="epm", cf=AverageCF),
        Def("bl", rrd_path, data_source="bl", cf=AverageCF),
        LINE1("rpm", rrggbb="ff0000", legend="rpm"),
        LINE1("epm", rrggbb="00ff00", legend="epm"),
        LINE1("bl", rrggbb="0000ff", legend="waiting"),
        #alt_y_mrtg=None,
        width=int(width),
        height=int(height),
        #x="HOUR:1:HOUR:2:HOUR:4:0:%H",
        title=title,
        zoom=2,
        **options)

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

