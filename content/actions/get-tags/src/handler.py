from json import load
from typing import Dict, Any, Optional

from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validator
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

from dassana.common.aws_client import DassanaAwsObject, parse_arn
from dassana.common.cache import configure_ttl_cache

with open('input.json', 'r') as schema:
    schema = load(schema)
    dassana_aws = DassanaAwsObject()

logger = Logger(service='dassana-actions')


def tag_mapping(tags):
    return [{'name': tag['Key'], 'value': tag['Value']} for tag in tags]


get_cached_client = configure_ttl_cache(1024, 60)


@logger.inject_lambda_context
@validator(inbound_schema=schema)
def handle(event: Dict[str, Optional[Any]], context: LambdaContext):
    arn = event.get('arn')
    arn_component = parse_arn(arn)
    service = arn_component.service
    region = arn_component.region
    if region is None and event.get('region') is None:
        raise Exception(
            'Arn: %s is missing region and the region is missing from the input. Please supply a region for the '
            'resource')
    else:
        region = event.get('region')

    if service == 'iam':
        client = get_cached_client(dassana_aws.create_aws_client, context=context, service='iam', region=region)
        resource_type = arn_component.resource_type
        resource = arn_component.resource
        try:
            if resource_type == 'user':
                resp = client.list_user_tags(UserName=resource)
                tag_set = resp.get('Tags')
            elif resource_type == 'role':
                resp = client.list_role_tags(RoleName=resource)
                tag_set = resp.get('Tags')
            elif resource_type == 'policy':
                resp = client.list_policy_tags(PolicyArn=arn)
                tag_set = resp.get('Tags')
            else:
                return []
            return tag_mapping(tag_set)
        except ClientError as e:
            if e.response.get('Error').get('Code') in ['NoSuchEntity']:
                return []
            else:
                raise e
    else:
        client = get_cached_client(dassana_aws.create_aws_client, context=context, service='resourcegroupstaggingapi',
                                  region=region)
        try:
            resp = client.get_resources(ResourceARNList=[
                arn
            ])
            tag_set = resp.get('ResourceTagMappingList')
            if len(tag_set) > 0:
                tag_set = tag_set[0].get('Tags')
                return tag_mapping(tag_set)
            else:
                return []
        except ClientError as e:
            logger.error(e.response)
            raise e
