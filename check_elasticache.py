#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2014 Carles Amigó <carles.amigo@socialpoint.es>
#
# Distributed under terms of the MIT license.

"""
Nagios plugin for Amazon ElastiCache monitoring

Somehow inspired from the pmp-check-aws-rds.py script from the Percona
Monitoring Toolkit
"""

import boto.elasticache
import optparse
import sys
import pprint
import datetime


def get_instance_info(region, indentifier=None):
    """Function for fetching ElastiCache details"""
    elasticache = boto.elasticache.connect_to_region(region)
    try:
        if indentifier:
            info = elasticache.describe_cache_clusters(indentifier)[
                'DescribeCacheClustersResponse'][
                'DescribeCacheClustersResult'][
                'CacheClusters'][0]
        else:
            info = [str(v['CacheClusterId'])
                    for v in elasticache.describe_cache_clusters()[
                        'DescribeCacheClustersResponse'][
                        'DescribeCacheClustersResult'][
                        'CacheClusters']]
    except boto.exception.BotoServerError:
        info = None
    return info


def get_instance_stats(step, start_time, end_time, metric, indentifier):
    """Function for fetching ElastiCache statistics from CloudWatch"""
    cw = boto.connect_cloudwatch()
    result = cw.get_metric_statistics(step,
                                      start_time,
                                      end_time,
                                      metric,
                                      'AWS/ElastiCache',
                                      'Average',
                                      dimensions={'CacheClusterId':
                                                  [indentifier]}
                                      )
    if result:
        if len(result) > 1:
            # Get the last point
            result = sorted(result, key=lambda k: k['Timestamp'])
            result.reverse()
        result = float('%.2f' % result[0]['Average'])
    return result


def main():
    """Main function"""

    # Nagios status codes
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3
    short_status = {OK: 'OK',
                    WARNING: 'WARN',
                    CRITICAL: 'CRIT',
                    UNKNOWN: 'UNK'}

    # Cache instance classes as listed on
    # http://aws.amazon.com/elasticache/pricing/
    elasticache_classes = {'cache.t2.micro': 0.555,
                           'cache.t2.small': 1.55,
                           'cache.t2.medium': 3.22,
                           'cache.m3.medium': 2.78,
                           'cache.m3.large': 6.05,
                           'cache.m3.xlarge': 13.3,
                           'cache.m3.2xlarge': 27.9,
                           'cache.r3.large': 13.5,
                           'cache.r3.xlarge': 28.4,
                           'cache.r3.2xlarge': 58.2,
                           'cache.r3.4xlarge': 118,
                           'cache.r3.8xlarge': 237,
                           'cache.m1.small': 1.3,
                           'cache.m1.medium': 3.35,
                           'cache.m1.large': 7.1,
                           'cache.m1.xlarge': 14.6,
                           'cache.m2.xlarge': 16.7,
                           'cache.m2.2xlarge': 33.8,
                           'cache.m2.4xlarge': 68,
                           'cache.c1.xlarge': 6.6,
                           'cache.t1.micro': 0.213}

    # ElastiCache metrics as listed on
    # http://docs.aws.amazon.com/AmazonCloudWatch/latest/DeveloperGuide/elasticache-metricscollected.html # noqa
    metrics = {'status': 'ElastiCache availability',
               'load': 'CPUUtilization',
               'memory': 'FreeableMemory'}

    units = ('percent', 'GB')

    # Parse options
    parser = optparse.OptionParser()
    parser.add_option('-r', '--region', help='AWS region')
    parser.add_option('-l', '--list', help='list of all ElastiCache instances',
                      action='store_true', default=False, dest='instance_list')
    parser.add_option('-i', '--ident', help='ElastiCache instance identifier')
    parser.add_option('-p', '--print', help='print status and other details ' +
                      'for a given ElastiCache instance',
                      action='store_true', default=False, dest='info')
    parser.add_option('-m', '--metric', help='metric to check: [%s]' %
                      ', '.join(metrics.keys()))
    parser.add_option('-w', '--warn', help='warning threshold')
    parser.add_option('-c', '--crit', help='critical threshold')
    parser.add_option('-u', '--unit', help='unit of thresholds for "memory" '
                      'metrics: [%s]. Default: percent' % ', '.join(units),
                      default='percent')
    options, args = parser.parse_args()

    # Check args
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()
    elif not options.region:
        parser.print_help()
        parser.error('AWS region is not set.')
    elif options.instance_list:
        info = get_instance_info(options.region)
        pprint.pprint(info)
        sys.exit()
    elif not options.ident:
        parser.print_help()
        parser.error('ElastiCache identifier is not set.')
    elif options.info:
        info = get_instance_info(options.region, options.ident)
        if info:
            pprint.pprint(info)
        else:
            print 'No ElastiCache instance "%s" found on your AWS account.' % \
                  options.ident
        sys.exit()
    elif not options.metric or options.metric not in metrics.keys():
        parser.print_help()
        parser.error('Metric is not set or not valid.')
    elif not options.warn and options.metric != 'status':
        parser.print_help()
        parser.error('Warning threshold is not set.')
    elif not options.crit and options.metric != 'status':
        parser.print_help()
        parser.error('Critical threshold is not set.')

    tm = datetime.datetime.utcnow()
    status = None
    note = ''
    perf_data = None

    # ElastiCache Status
    if options.metric == 'status':
        info = get_instance_info(options.region, options.ident)
        if not info:
            status = UNKNOWN
            note = 'Unable to get ElastiCache instance'
        else:
            if info['CacheClusterStatus'] == 'available':
                status = OK
            else:
                status = CRITICAL
            note = '%s %s. Status: %s' % (info['Engine'],
                   info['EngineVersion'], info['CacheClusterStatus'])

    # ElastiCache Load Average
    elif options.metric == 'load':
        # Check thresholds
        try:
            warns = [float(x) for x in options.warn.split(',')]
            crits = [float(x) for x in options.crit.split(',')]
            fail = len(warns) + len(crits)
        except:
            fail = 0
        if fail != 6:
            parser.error('Warning and critical thresholds should be 3 comma ' +
                         'separated numbers, e.g. 20,15,10')

        loads = []
        fail = False
        j = 0
        perf_data = []
        for i in [1, 5, 15]:
            if i == 1:
                # Some stats are delaying to update on CloudWatch.
                # Let's pick a few points for 1-min load avg and get the last
                # point.
                n = 5
            else:
                n = i
            load = get_instance_stats(i * 60, tm - datetime.timedelta(
                                      seconds=n * 60),
                                      tm, metrics[options.metric],
                                      options.ident)
            if not load:
                status = UNKNOWN
                note = 'Unable to get RDS statistics'
                perf_data = None
                break
            loads.append(str(load))
            perf_data.append('load%s=%s;%s;%s;0;100' % (i, load, warns[j],
                             crits[j]))

            # Compare thresholds
            if not fail:
                if warns[j] > crits[j]:
                    parser.error('Parameter inconsistency: warning threshold' +
                                 ' is greater than critical.')
                elif load >= crits[j]:
                    status = CRITICAL
                    fail = True
                elif load >= warns[j]:
                    status = WARNING
            j = j + 1

        if status != UNKNOWN:
            if status is None:
                status = OK
            note = 'Load average: %s%%' % '%, '.join(loads)
            perf_data = ' '.join(perf_data)

    # RDS Free Storage
    # RDS Free Memory
    elif options.metric in ['memory']:
        # Check thresholds
        try:
            warn = float(options.warn)
            crit = float(options.crit)
        except:
            parser.error('Warning and critical thresholds should be integers.')
        if crit > warn:
            parser.error('Parameter inconsistency: critical threshold is ' +
                         'greater than warning.')
        if options.unit not in units:
            parser.print_help()
            parser.error('Unit is not valid.')

        info = get_instance_info(options.region, options.ident)
        free = get_instance_stats(60, tm - datetime.timedelta(seconds=60), tm,
                                  metrics[options.metric], options.ident)
        if not info or not free:
            status = UNKNOWN
            note = 'Unable to get ElastiCache details and statistics'
        else:
            if options.metric == 'memory':
                try:
                    storage = elasticache_classes[info['CacheNodeType']]
                except:
                    print 'Unknown ElastiCache instance class "%s"' % \
                          info.instance_class
                    sys.exit(UNKNOWN)
            free = '%.2f' % (free / 1024 ** 3)
            free_pct = '%.2f' % (float(free) / storage * 100)
            if options.unit == 'percent':
                val = float(free_pct)
                val_max = 100
            elif options.unit == 'GB':
                val = float(free)
                val_max = storage

            # Compare thresholds
            if val <= crit:
                status = CRITICAL
            elif val <= warn:
                status = WARNING

            if status is None:
                status = OK
            note = 'Free %s: %s GB (%.0f%%) of %s GB' % (options.metric,
                                                         free,
                                                         float(free_pct),
                                                         storage)
            perf_data = 'free_%s=%s;%s;%s;0;%s' % (options.metric,
                                                   val,
                                                   warn,
                                                   crit,
                                                   val_max)

    # Final output
    if status != UNKNOWN and perf_data:
        print '%s %s | %s' % (short_status[status], note, perf_data)
    else:
        print '%s %s' % (short_status[status], note)
    sys.exit(status)


if __name__ == '__main__':
    main()
