from json import loads
from typing import Dict, List

from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic.main import BaseModel

from dassana.common.aws_client import parse_arn
from dassana.common.models import NormalizedOutput

class PrismaResourceData(BaseModel):
    arn: str = None
    tagSets: Dict[str, str] = {}
    tags: List[Dict[str, str]] = []


class PrismaResource(BaseModel):
    rrn: str
    id: str
    cloudType: str
    accountId: str
    region: str
    regionId: str
    resourceType: str = None
    data: PrismaResourceData


class PrismaAlert(BaseModel):
    alertId: str
    alertStatus: str
    policyId: str
    policyType: str
    resource: PrismaResource


@event_parser(model=PrismaAlert)
def handle(event: PrismaAlert, context: LambdaContext):
    arn_obj = parse_arn(event.resource.data.arn) if event.resource.data.arn else None
    if len(event.resource.data.tagSets) > 0:
        tags = [{'name': k, 'value': v} for k, v in event.resource.data.tagSets.items()]
    elif len(event.resource.data.tags) > 0:
        tags = list(map(lambda x: {
            "value": x.get('value'),
            "name": x.get('key')
        }, event.resource.data.tags))
    else:
        tags = []

    return loads(NormalizedOutput(
        vendorId='prisma-cloud',
        alertId=event.alertId,
        canonicalId=event.resource.data.arn,
        vendorPolicy=event.policyId,
        csp=event.resource.cloudType,
        resourceContainer=event.resource.accountId,
        region=event.resource.regionId,
        service=arn_obj.service if arn_obj is not None else None,
        resourceType=arn_obj.resource_type if arn_obj is not None else None,
        resourceId=arn_obj.resource if arn_obj is not None else event.resource.id,
        tags=tags
    ).json())
