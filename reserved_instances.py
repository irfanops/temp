import boto3
from datadog import initialize,  api

REGIONS=[ 'us-west-2', 'us-east-1', 'eu-west-1', 'ap-southeast-1', 'ap-northeast-1' ]

dd_auth = { 'api_key': "$API_KEY",
            'app_key': "$APP_KEY" 
          }
initialize(**dd_auth)

def enumerate_reserved_instances(reserved_response):
    reserved_classic = {}
    reserved_vpc     = {}
    for i, v in enumerate(reserved_response['ReservedInstances']):
        instance_type  =  reserved_response['ReservedInstances'][i]['InstanceType']
        instance_count = reserved_response['ReservedInstances'][i]['InstanceCount']
        az             = reserved_response['ReservedInstances'][i]['AvailabilityZone']
        description    = reserved_response['ReservedInstances'][i]['ProductDescription']
        if description == 'Linux/UNIX (Amazon VPC)':
            reserved_vpc[(instance_type, az)]     = reserved_vpc.get((instance_type, az), 0) + instance_count
        elif description == 'Linux/UNIX':
            reserved_classic[(instance_type, az)] = reserved_classic.get((instance_type, az), 0) + instance_count
        else:
            exit('Not sure whats going on')
    return(reserved_classic, reserved_vpc)


def enumerate_active_instances(active_response):
    active_classic = {}  
    active_vpc     = {}  
    for i, v in enumerate(active_response['Reservations']):
        for ii, vv in enumerate(active_response['Reservations'][i]['Instances']):
            az            = active_response['Reservations'][i]['Instances'][ii]['Placement']['AvailabilityZone']
            instance_type = active_response['Reservations'][i]['Instances'][ii]['InstanceType']

            if 'VpcId' in active_response['Reservations'][i]['Instances'][ii]:
                active_vpc[(instance_type, az)] = active_vpc.get((instance_type, az), 0) + 1
            else:
                active_classic[(instance_type, az)] = active_classic.get((instance_type, az), 0) + 1


    return(active_classic, active_vpc)


def compare_active_to_reserved(ec2_type, region, reserved_instances, running_instances):
    metrics_for_dd = []
    instance_diff = dict([(x, reserved_instances[x] - running_instances.get(x, 0 )) for x in reserved_instances])
    for placement_key in running_instances:
	    if not placement_key in reserved_instances:
		    instance_diff[placement_key] = -running_instances[placement_key]

    unused_reservations = dict((key,value) for key, value in instance_diff.iteritems() if value > 0)
    if unused_reservations == {}:
        print "No unused reservations"
    else:
	    for unused_reservation in unused_reservations:
		    print "UNUSED RESERVATION!\t(%s)\t%s\t%s" % ( unused_reservations[unused_reservation], unused_reservation[0], unused_reservation[1] )
		    metrics_for_dd.append({ 'metric': ec2_type + '_unused_reservations', 
		    	                    'points': unused_reservations[unused_reservation], 
		    	                    'tags':[ 'instance_type:' + unused_reservation[0], 
		    	                             'az:' + unused_reservation[1],
                                             'ec2_region:' + region ]})

    print ""

    unreserved_instances = dict((key,-value) for key, value in instance_diff.iteritems() if value < 0)
    if unreserved_instances == {}:
        print "No unreserved instances"
    else:
	    for unreserved_instance in unreserved_instances:
		    print "Instance not reserved:\t(%s)\t%s\t%s" % ( unreserved_instances[unreserved_instance], unreserved_instance[0], unreserved_instance[1] )
		    metrics_for_dd.append({ 'metric': ec2_type + '_unreserved_instance', 
		    	                    'points': unreserved_instances[unreserved_instance], 
		    	                    'tags': ['instance_type:' + unreserved_instance[0], 
		    	                             'az:' + unreserved_instance[1],
                                             'ec2_region:' + region ]})
    if metrics_for_dd:
        api.Metric.send(metrics_for_dd)
    if running_instances:
        qty_running_instances = reduce( lambda x, y: x+y, running_instances.values() )
    else:
    	qty_running_instances = 0
    if reserved_instances:
        qty_reserved_instances = reduce( lambda x, y: x+y, reserved_instances.values() )
    else:
    	qty_reserved_instances = 0

    print "\n(%s) running on-demand instances\n(%s) reservations\n" % ( qty_running_instances, qty_reserved_instances )

for region in REGIONS:
    print "Processing " + region
    client = boto3.client('ec2', region)
    active_classic, active_vpc = enumerate_active_instances(client.describe_instances(Filters=[ {'Name': 'instance-state-name', 'Values': [ 'running', ] } , ], ))
    reserved_classic, reserved_vpc = enumerate_reserved_instances(client.describe_reserved_instances(Filters=[ {'Name': 'state', 'Values': [ 'active', ] } , ], ))

    print "VPC"
    compare_active_to_reserved('vpc', region, reserved_vpc, active_vpc)
    
    print "EC2_CLASSIC"
    compare_active_to_reserved('ec2_classic', region, reserved_classic, active_classic)