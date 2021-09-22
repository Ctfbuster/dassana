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
    
    policies = []
    all_findings = {}
    exclusions_config = {}
    
    iam_arn = event.get('iamArn')
    client = dassana_aws.create_aws_client(context, 'iam', event.get('region'))
    
    prefix, name = iam_arn.split("/")
    prefix = prefix.split(":")
    
    if prefix[-1] == 'role':
        paginator = client.get_paginator('list_attached_role_policies')
        
        page_iterator = paginator.paginate(
            RoleName=name,
            PathPrefix='/'
        )
        
        try:
            for page in page_iterator:
                for policy in page['AttachedPolicies']:
                    policies.append({
                        'PolicyArn':policy['PolicyArn'], 
                        'PolicyName':policy['PolicyName']
                    })
        except Exception:
            pass
            
        paginator = client.get_paginator('list_role_policies')
        
        page_iterator = paginator.paginate(
            RoleName=name
        )
        
        try:
            for page in page_iterator:
                for policy_name in page['PolicyNames']:
                    policies.append({
                        'PolicyName':policy_name,
                        'PolicyArn':''
                    })
        except Exception:
            pass
    elif prefix[-1] == 'user':
        paginator = client.get_paginator('list_attached_user_policies')
        
        page_iterator = paginator.paginate(
            UserName=name,
            PathPrefix='/'
        )
        try: 
            for page in page_iterator:
                for policy in page['AttachedPolicies']:
                    policies.append({
                        'PolicyArn':policy['PolicyArn'], 
                        'PolicyName':policy['PolicyName']
                    })
        except Exception:
            pass
        
        paginator = client.get_paginator('list_user_policies')
        
        page_iterator = paginator.paginate(
            UserName=name
        )
        try:
            for page in page_iterator:
                for policy_name in page['PolicyNames']:
                    policies.append({
                        'PolicyName':policy_name,
                        'PolicyArn':''
                    })
        except Exception:
            pass
    elif prefix[-1] == 'policy':
        policies.append({
            'PolicyArn':iam_arn, 
            'PolicyName':name
        })
    
    for policy in policies:
        if policy['PolicyArn'] != '':
            policy_basic = client.get_policy(
                PolicyArn=policy['PolicyArn']
            )
            
            policy_detailed = client.get_policy_version(
                PolicyArn=policy['PolicyArn'],
                VersionId=policy_basic['Policy']['DefaultVersionId']
            )
            policy_document = policy_detailed['PolicyVersion']['Document']
        else:
            policy_detailed = client.get_role_policy(
                RoleName=name,
                PolicyName=policy['PolicyName']
            )
            policy_document = policy_detailed['PolicyDocument']
            
        policy['PolicyDocument'] = policy_document
        
        policy_document = PolicyDocument(policy_document)
        exclusions = Exclusions(exclusions_config)
        policy_finding = PolicyFinding(policy_document, exclusions)
        
        policy['PolicyFindings'] = policy_finding.results
        
        for finding_category in policy_finding.results.keys():
            if finding_category in all_findings:
                for finding in policy_finding.results[finding_category]:
                    if finding_category != 'PrivilegeEscalation':
                        all_findings[finding_category].add(finding)
                    else:
                        for perm in finding['actions']:
                            all_findings[finding_category].add(perm) 
            else:
                if finding_category != 'PrivilegeEscalation':
                    all_findings[finding_category] = set(policy_finding.results[finding_category])
                else:
                    all_findings[finding_category] = set([perm for type in policy_finding.results[finding_category] for perm in type['actions']])
    
    all_findings = {category: list(findings) for category, findings in all_findings.items()}
    
    response = dumps({
        'PolicyFindings': all_findings,
        'Policies': policies
    }, default=str)
    
    return {"result": loads(response)}
