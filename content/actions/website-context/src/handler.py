from functools import partial
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

make_cached_call = configure_ttl_cache(1024, 60)


@logger.inject_lambda_context
@validator(inbound_schema=schema)
def handle(event: Dict[str, Optional[Any]], context: LambdaContext):
    bucket_name = event.get('bucketName')
    region = event.get('region')

    client = make_cached_call(partial(dassana_aws.create_aws_client, context=context), service='s3', region=region)

    try:
        bucket_website = client.get_bucket_website(Bucket=bucket_name)
        return {"bucketWebsiteUrl": "%s.s3-website-%s.amazonaws.com" % (bucket_name, region)}
    except ClientError as e:
        logger.error(e.response)
        if e.response.get('Error').get('Code') in ['NoSuchBucket', 'NoSuchWebsiteConfiguration']:
            return {"bucketWebsiteUrl": ""}
        else:
            raise Exception(e)
