from json import load
from typing import Dict, Any, List

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validator
from botocore.exceptions import ClientError
from iteration_utilities import deepflatten
from pydantic import BaseModel
from pydantic.json import IPv4Address
from json import loads

from dassana.common.aws_client import DassanaAwsObject
from dassana.common.cache import configure_ttl_cache

logger = Logger(service='dassana-actions')
get_cached_client = configure_ttl_cache(1024, 60)

with open('input.json', 'r') as schema:
    schema = load(schema)
    dassana_aws = DassanaAwsObject()


class Exposure(BaseModel):
    class Direct(BaseModel):
        class AllowedVia(BaseModel):
            sg: List[str]

        publicIp: IPv4Address = None
        allowedVia: AllowedVia = None
        isExposed: bool = None

    class AppLayer(BaseModel):
        type: str = None
        canReceiveUnauthenticatedTraffic: bool = False
        exceptionMatch: bool = False
        authConfig: Dict = None

    appLayer: AppLayer
    direct: Direct


@logger.inject_lambda_context
@validator(inbound_schema=schema)
def handle(event: Dict[str, Any], context: LambdaContext):
    instance_id = event.get('instanceId')
    region = event.get('region')
    event_exceptions = event.get('exceptions', [])

    ec2_client = get_cached_client(dassana_aws.create_aws_client, context=context, service='ec2',
                                   region=region)
    elb_client = get_cached_client(dassana_aws.create_aws_client, context=context, service='elbv2',
                                   region=region)
    lb_paginator = elb_client.get_paginator('describe_load_balancers')
    tg_paginator = elb_client.get_paginator('describe_target_groups')
    page_iterator = lb_paginator.paginate()

    exp = Exposure(
        appLayer={},
        direct={}
    )

    def evaluate_app_layer(resource, event_exceptions_app_layer):
        for lb_page in page_iterator:
            for lb_arn, scheme in list(map(lambda x: (x['LoadBalancerArn'], x['Scheme']),
                                           lb_page['LoadBalancers'])):
                for tg_page in tg_paginator.paginate(LoadBalancerArn=lb_arn):
                    target_groups = list(
                        filter(lambda x: x['TargetType'] == 'instance',
                               tg_page['TargetGroups']
                               )
                    )
                    targets = list(
                        deepflatten(
                            map(lambda x: {
                                'TargetArn': x['TargetGroupArn'],
                                'Targets': elb_client.describe_target_health(
                                    TargetGroupArn=x['TargetGroupArn'])['TargetHealthDescriptions']}, target_groups),
                            types=list)
                    )
                    # If any of the targets of the LB is the EC2 instance
                    ec2_targets = list(
                        filter(
                            lambda x: len(
                                list(
                                    filter(lambda y: y['Target']['Id'] == resource, x['Targets']))) > 0,
                            targets
                        ))
                    if len(ec2_targets) > 0:
                        if scheme != 'internet-facing':
                            continue
                        exp.appLayer.type = scheme
                        listeners_resp = elb_client.describe_listeners(
                            LoadBalancerArn=lb_arn
                        )
                        # Go through listeners Skip iteration if listener does not have authentication (default is
                        # False, so no auth in any listener -> False)
                        for listener_arn in map(lambda x: x['ListenerArn'], listeners_resp['Listeners']):
                            rules = elb_client.describe_rules(
                                ListenerArn=listener_arn
                            )['Rules']
                            auth_obj = next(
                                # Filter the LoadBalancer Rules and return first rule where the Action Type is either
                                # authenticate-oidc or authenticate-cognito
                                filter(
                                    lambda rule_ele: any(
                                        map(lambda x: x['Type'] == 'authenticate-oidc' or x[
                                            'Type'] == 'authenticate-cognito', rule_ele[1]['Actions'])),
                                    enumerate(rules)
                                ),
                                None
                            )

                            if auth_obj is None:
                                continue
                            auth_idx = auth_obj[0]
                            auth_obj = auth_obj[1]

                            exp.appLayer.authConfig = next(filter(
                                lambda x: x['Type'] == 'authenticate-oidc' or x[
                                    'Type'] == 'authenticate-cognito', auth_obj['Actions']), None)

                            rules_before_auth = rules[:auth_idx]
                            if len(rules_before_auth) == 0:
                                exp.appLayer.canReceiveUnauthenticatedTraffic = False
                            else:
                                # Check for rules before authentication. In any event where there are rules before
                                # auth that have the EC2 instance as a target, check if their conditions are
                                # equivalent to the exceptions from the input to the action. This is for special cases
                                # (i.e permitting HTTP(S) OPTION requests).
                                auth_check = []
                                for rule in rules_before_auth:
                                    actions = rule['Actions']
                                    target_arns = set(deepflatten(list(
                                        map(lambda x: list(
                                            map(lambda y: y['TargetGroupArn'], x['ForwardConfig']['TargetGroups'])),
                                            actions)), types=list))
                                    is_subset = target_arns.issubset(set(map(lambda x: x['TargetArn'], ec2_targets)))
                                    # If the rules before auth involve EC2 as a target
                                    if is_subset:
                                        conditions = rule['Conditions']
                                        auth_check.append(event_exceptions_app_layer != conditions)
                                if any(auth_check):
                                    exp.appLayer.canReceiveUnauthenticatedTraffic = True
                                    return
                                elif len(event_exceptions_app_layer) != 0:
                                    exp.appLayer.exceptionMatch = True

    def evaluate_direct(ec2_resource) -> bool:
        try:
            instance_resp = ec2_client.describe_instances(InstanceIds=[ec2_resource],
                                                          Filters=[
                                                              {
                                                                  'Name': 'instance-state-code',
                                                                  'Values': ['16']
                                                              }
                                                          ])
        except ClientError as e:
            logger.error(e.response)
            if e.response.get('Error').get('Code') in ['InvalidInstanceID.Malformed', 'InvalidInstanceID.NotFound']:
                return False
            else:
                raise Exception(e)
        if len(instance_resp['Reservations']) == 0:
            return False
        # Filter and deep flatten security groups attached to the EC2 instance
        groups = list(map(
            lambda x: list(map(lambda instance:
                               list(map(lambda interface: interface['Groups'],
                                        instance['NetworkInterfaces'])),
                               x['Instances'])),
            instance_resp['Reservations']))
        groups = list(deepflatten(groups, types=list))
        filters = [
            [{
                'Name': 'ip-permission.cidr',
                'Values': [
                    '0.0.0.0/0'
                ]
            }],
            [{
                'Name': 'ip-permission.ipv6-cidr',
                'Values': [
                    '::/0'
                ]
            }]
        ]

        open_groups = set(
            map(lambda sg: sg['GroupId'],
                deepflatten(list(map(lambda filter_sg: ec2_client.describe_security_groups(
                    GroupIds=list(map(lambda group: group['GroupId'], groups)),
                    Filters=filter_sg
                )['SecurityGroups'], filters)), types=list)))

        public_ip_address = instance_resp.get('Reservations')[0].get('Instances')[0].get(
            'PublicIpAddress')

        if public_ip_address is not None:
            public_ip = IPv4Address(public_ip_address)
        else:
            public_ip = ''

        exp.direct = {
            'publicIp': public_ip,
            'allowedVia': {
                'sg': open_groups
            },
            'isExposed': public_ip_address is not None and len(open_groups) > 0
        }

        return True

    if evaluate_direct(instance_id):
        evaluate_app_layer(instance_id, event_exceptions)

    # Clean up / post handler
    # If traffic going to instance is unauthenticated, we do not care about the config.
    if exp.appLayer.canReceiveUnauthenticatedTraffic and exp.appLayer.authConfig is not None:
        exp.appLayer.authConfig = None

    return loads(exp.json(exclude_none=True))
