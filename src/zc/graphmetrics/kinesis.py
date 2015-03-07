"""Collect metrics from a kinesis stream into rrd files
"""
import argparse
import boto.kinesis
import datetime
import json
import logging
import os
import pytz
import rrdtool
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('stream', help='Kinesis stream name')
parser.add_argument('dest', help='Destination rrd directory')
parser.add_argument('-z', '--local-time-zone', default='US/Eastern',
                    help='Time-zone to record data under')

def main(args=None):
    if args is None:
        args = sys.argv[1:]

    args = parser.parse_args(args)

    stream = args.stream
    local_timezone = args.local_time_zone
    rrd_dir = os.path.abspath(args.dest)

    sequence_path = os.path.join(rrd_dir, 'sequence-number')
    rrds = {}

    local = pytz.timezone(local_timezone)
    conn = boto.kinesis.connect_to_region('us-east-1')
    [shard] = conn.describe_stream(stream)['StreamDescription']['Shards']

    if os.path.exists(sequence_path):
        # Pick up where we left off
        with open(sequence_path) as f:
            sequence_number = f.read()
        try:
            it = conn.get_shard_iterator(
                stream, shard['ShardId'],
                'AFTER_SEQUENCE_NUMBER', sequence_number)
        except TypeError:
            logger.error("Bad sequence number %r", sequence_number)
            it = conn.get_shard_iterator(
                stream, shard['ShardId'], 'TRIM_HORIZON')
    else:
        it = conn.get_shard_iterator(stream, shard['ShardId'], 'TRIM_HORIZON')

    it = it['ShardIterator']
    sequence_number = None
    while 1:
        data = conn.get_records(it)
        it = data['NextShardIterator']
        records = data['Records']
        if records:
            #print 'got records', len(records), records[0]['Data']
            for record in records:
                sequence_number = record[u'SequenceNumber']
                record = json.loads(record['Data'])
                d, t = record['timestamp'].split('T')
                l = datetime.datetime(
                    *(map(int, d.split('-')) +
                      map(int, t.split('.')[0].split(':'))
                      ),
                    tzinfo=pytz.utc).astimezone(local)
                l = l.year, l.month, l.day, l.hour, l.minute, l.second
                ts = int(time.mktime(
                    l+(0, 0)+(bool(local.dst(datetime.datetime(*l))),)))
                elem = record['name'][2:].replace(':','..').replace('#', '/')
                host = elem.split('/', 1)[0]
                path = (os.path.join(rrd_dir, elem)+'.rrd').encode('utf8')
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
                    # Repeated data because lost sequence number save
                    continue
                if ts == rrd.rrd_last:
                    ts += 1
                rrd.update(rrdtool.Val(float(record['value']), timestamp=ts))
                rrd.rrd_last = ts
            with open(sequence_path, 'w') as f:
                f.write(sequence_number)
        else:
            #print 'sleeping'
            time.sleep(10)
