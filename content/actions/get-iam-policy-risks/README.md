## Determine the granted permissions and respective least privilege violations for a role, user, or policy

Returns the policies attached to, or inlined in, a given IAM arn, along with [cloudsplaining](https://github.com/salesforce/cloudsplaining) findings. 

### Sample Input:
```json
{
  "iamArn": "arn:aws:iam::032584774331:role/dassana-DassanaEngineRole"
}
```

### Sample Output:
```json
{
   "result":{
      "PolicyFindings":{
         "ServiceWildcard":[
            "s3"
         ],
         "ServicesAffected":[
            "logs",
            "lambda"
         ],
         "PrivilegeEscalation":[
            
         ],
         "ResourceExposure":[
            
         ],
         "DataExfiltration":[
            
         ],
         "CredentialsExposure":[
            
         ],
         "InfrastructureModification":[
            "logs:PutLogEvents",
            "lambda:InvokeFunction",
            "logs:CreateLogGroup",
            "logs:CreateLogStream"
         ]
      },
      "Policies":[
         {
            "PolicyName":"DassanaEnginePolicy",
            "PolicyArn":"",
            "PolicyDocument":{
               "Version":"2012-10-17",
               "Statement":[
                  {
                     "Action":[
                        "s3:*"
                     ],
                     "Resource":[
                        "arn:aws:s3:::dassana-dassanabucket-1a22qtxca88ly/*",
                        "arn:aws:s3:::dassana-dassanabucket-1a22qtxca88ly"
                     ],
                     "Effect":"Allow"
                  },
                  {
                     "Action":[
                        "cloudformation:Describe*",
                        "cloudformation:List*",
                        "cloudformation:Get*",
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "lambda:InvokeFunction",
                        "lambda:GetFunction"
                     ],
                     "Resource":"*",
                     "Effect":"Allow"
                  },
                  {
                     "Action":[
                        "sqs:SendMessage",
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes"
                     ],
                     "Resource":[
                        "arn:aws:sqs:us-east-2:032584774331:dassana-DassanaInboundQueue",
                        "arn:aws:sqs:us-east-2:032584774331:dassana-DassanaDeadLetterQueue"
                     ],
                     "Effect":"Allow"
                  }
               ]
            },
            "PolicyFindings":{
               "ServiceWildcard":[
                  "s3"
               ],
               "ServicesAffected":[
                  "lambda",
                  "logs"
               ],
               "PrivilegeEscalation":[
                  
               ],
               "ResourceExposure":[
                  
               ],
               "DataExfiltration":[
                  
               ],
               "CredentialsExposure":[
                  
               ],
               "InfrastructureModification":[
                  "lambda:InvokeFunction",
                  "logs:CreateLogGroup",
                  "logs:CreateLogStream",
                  "logs:PutLogEvents"
               ]
            }
         }
      ]
   }
}
```
Note that returned inlined policies have a blank arn field, since they are part of the role/user and are not assigned an arn by AWS
