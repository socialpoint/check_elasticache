#check_elasticache.py

##Overview

This Nagios plugin allows you to check the status of an ElastiCache instance.

Instead of connecting directly to the instance, it will query AWS CloudWatch for some metrics.

##Setup

Install it in your Nagios plugins directory, create a [Nagios command](http://nagios.sourceforge.net/docs/3_0/objectdefinitions.html#command) and start adding your service checks.

###Setup requirements

This script requires the Boto library and the following IAM permissions:
- elasticache:DescribeCacheClusters
- cloudwatch:GetMetricStatistics

##Usage

Some usage examples:


List all available ElastiCache clusters in us-east-1:
```
check_elasticache.py --region us-east-1 -l
```

Print all available information about the ElastiCache cluster 'cluster1'
```
check_elasticache.py --region us-east-1 -i cluster1 -p
```

Check the current status of 'cluster1'. Returns CRITICAL if status is not 'available'
```
check_elasticache.py --region us-east-1 -i cluster1 -m status
```

Check the current cpu of 'cluster1'. Will return WARNING or CRITICAL if the result is over the specified thresholds.
```
check_elasticache.py --region us-east-1 -i cluster1 -m cpu -w 90,85,80 -c 98,95,90
```

Check the current cpu of 'cluster1' but do not calculate the real thresholds when using redis
```
check_elasticache.py --region us-east-1 -i cluster1 -m cpu -w 90,85,80 -c 98,95,90 --no-threshold-calc
```

Check the current memory usage of 'cluster1'. Will return WARNING or CRITICAL if the result is over the specified thresholds.
```
check_elasticache.py --region us-east-1 -i cluster1 -m memory -w 10 -c 5
```
