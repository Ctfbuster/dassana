from json import load, loads, dumps
from typing import Dict, Any

from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.validation import validator
from dassana.common.aws_client import DassanaAwsObject, parse_arn

from cloudsplaining.scan.policy_document import PolicyDocument
from cloudsplaining.shared.exclusions import Exclusions
from cloudsplaining.output.policy_finding import PolicyFinding

with open('input.json', 'r') as schema:
    schema = load(schema)
    dassana_aws = DassanaAwsObject()


@validator(inbound_schema=schema)
def handle(event: Dict[str, Any], context: LambdaContext):
    role_name = event.get('roleName')
    
    attached_policies = []
    inline_policies = []
    
    exclusions_config = {} # How can this be configured?
    
    client = dassana_aws.create_aws_client(context, 'iam', event.get('region'))
    
    response = client.list_attached_role_policies(
        RoleName=role_name,
        PathPrefix='/',
        MaxItems=100
    )
    
    for policy in response['AttachedPolicies']:
        attached_policies.append({
            'PolicyArn':policy['PolicyArn'], 
            'PolicyName':policy['PolicyName']
        })
    
    response = client.list_role_policies(
        RoleName=role_name,
        MaxItems=100
    )
    
    for policy_name in response['PolicyNames']:
        inline.policies({'PolicyName':policy_name})
    
    for policy in attached_policies:
        policy_basic = client.get_policy(
            PolicyArn=policy['PolicyArn']
        )
        
        policy_detailed = client.get_policy_version(
            PolicyArn=policy['PolicyArn'],
            VersionId=policy_basic['Policy']['DefaultVersionId']
        )
        
        policy['PolicyDocument'] = policy_detailed['PolicyVersion']['Document']
        
        policy_document = PolicyDocument(policy_detailed['PolicyVersion']['Document'])
        exclusions = Exclusions(exclusions_config)
        policy_finding = PolicyFinding(policy_document, exclusions)
        
        policy['PolicyFindings'] = policy_finding.results
    
    for policy in inline_policies:
        policy_detailed = client.get_role_policy(
            RoleName=role_name,
            PolicyName=policy['PolicyName']
        )
        
        policy['PolicyDocument'] = policy_detailed['Document']
        
        policy_document = PolicyDocument(policy_detailed['Document'])
        exclusions = Exclusions(exclusions_config)
        policy_finding = PolicyFinding(policy_document, exclusions)
        
        policy['PolicyFindings'] = policy_finding.results
    
    
    response = dumps(attached_policies, default=str)
    return {"result": loads(response)}

