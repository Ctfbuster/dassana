---
slug: prisma-cloud
title: Dassana 💙 Prisma Cloud
author: Parth Shah
author_title: Co-Founder & Head of Product and Engineering
author_url: https://github.com/parth-dassana
author_image_url: https://avatars.githubusercontent.com/u/68707443?v=4
tags: [aws, contextualization, prisma-cloud, splunk]
no_comments: false
---

![Dassana 💙 Prisma Cloud](/img/blog/prisma-cloud/dassanaLovesPrismaCloud.jpg)

<!--truncate-->

We are excited to announce Prisma Cloud support! Prisma Cloud is one of the undisputed juggernauts in the cloud security space. Prisma Cloud is amongst the most comprehensive cloud security platforms encompassing cloud security posture management, workload protection, network security, and data security.

Prisma Cloud has always held a special place in my heart. Both Gaurav (my co-founder and CEO) and I were part of the RedLock founding team (which was acquired by Palo Alto Networks and incorporated into Prisma Cloud). As a startup, set out to solve the visibility problem in the Cloud Security Posture Management (CSPM) space. We wanted to ensure that there was a simple way for customers to discover hygiene issues in the cloud. To accomplish that, we built a flexible query language to ask any question about an environment. Furthermore, we wanted this to be easily translated across a multitude of compliance standards across any public cloud. While we solved that problem, we ended up creating another one: alert fatigue.

Let's be clear about one thing. Most security alerts are not false positives; they are merely noisy. By applying the appropriate context, alerts start to become relevant (or irrelevant).

Prisma Cloud does a phenomenal job of providing coverage across just about any misconfiguration in your cloud environment. All of the security policies are very objective. The thing with context, though, is that it is very subjective. What's important for one team may not be a priority for another. For instance, a SecOps team may want to prioritize vulnerabilities exposed to the internet or those that are remotely exploitable whereas a compliance team may care about open security groups or unencrypted EBS volumes in a PCI environment even though the resources may not be exploitable or reachable from the internet. This is why Dassana has taken a context-based approach to prioritize cloud security alerts.

The combination of Prisma Cloud and Dassana is quite an explosive one. Let's dive deeper.

![Integration](/img/blog/prisma-cloud/integration.jpg)

Here's how the integration works:

1. When you [deploy Dassana](/docs/getting-started/installation) (which is absolutely free!), it creates an inbound queue and an outbound queue with the magic happening in the middle. [Learn more](/docs/how-it-works/high-level).
2. Using Prisma Cloud [alert rules](https://docs.paloaltonetworks.com/prisma/prisma-cloud/prisma-cloud-admin/configure-external-integrations-on-prisma-cloud/integrate-prisma-cloud-with-amazon-sqs.html), you can forward alerts to Dassana's inbound queue.
3. Once Dassana has finished processing an alert, it makes its way into the outbound queue.
4. In [Splunk](https://docs.splunk.com/Documentation/AddOns/released/AWS/SQS), we use the AWS add-on to dequeue alerts from the Dassana outbound queue. When alerts show up in Splunk, you get the original alert along with a `dassana` object added to your alert:

    ```yaml
    {
      ...,
        "dassana": {
    	    "policy-context": {},
    	    "normalize": {},
    	    "general-context": {},
    	    "resource-context": {}
      },
    	...
    }
    ```

For this demo, I created a new AWS account and have no resources whatsoever. As soon as I wired it up to Prisma Cloud, I got this many alerts!

![Total alerts](/img/blog/prisma-cloud/totalAlerts.png)

Now let me show you how I cut through the noise. Before we jump into the how, let's do a quick refresher on how Dassana works:

As soon as an alert is received in the inbound queue, Dassana normalizes the alert so that we can add context regardless of the vendor. Normalization is our way of thinking about security from first principles. Here is sample output from our normalizer:

```yaml
{
    'csp': 'aws',
    'resourceId': 'xxxxx',
    'alertClassification':
        {
            'class': 'risk',
            'subclass': 'config',
            'category': 'storage',
            'subcategory': 'encryption'
        },
    'service': 'ec2',
    'vendorPolicy': 'some-uuid',
    'vendorId': 'prisma-cloud',
    'alertId': 'P-42',
    'resourceContainer': 'xxxxxxxxxxxx', # AWS account ID
    'region': 'us-east-1',
    'resourceType': 'snapshot',
    'tags': [{ 'name': 'env', 'value': 'prod' }]
}
```

The output of normalization is fed to the following three workflow types and each workflow provides a risk value (critical, high, medium, low, unknown):

1. General context - Environment (dev/prod etc) or category-based (IAM, Auth, Encryption etc) based alert prioritization happens here. Most likely, you will be using `region`, `tags` and `alertClassification` from the normalizer output shown above.
2. Resource context - Resource type (ec2/s3 etc) based alert prioritization happens here. You will likely use `resourceType` and `service` from normalizer output here. Refer to an example [here](https://github.com/dassana-io/dassana/blob/main/content/workflows/csp/aws/service/ec2/resources/instance/resource-context/instance-context.yaml).
3. Policy context - Anything related to the policy which generated the alert goes here.

These workflows run in parallel. Think of them as "dimensions" of risk. Like a 3D movie, think of Dassana making your alerts feel more alive ([click here](https://docs.dassana.io/docs/how-it-works/low-level/) to learn more). For this demo, I'm only going to use the general context workflow.

First and foremost, I only use one region in the cloud account I have. And so, right off the bat, I don't care about any other regions. Here's what my general-context workflow looks like right now:

:::info
We use [JQ](https://stedolan.github.io/jq/) to write rule conditions.
:::

```yaml
schema: 1
type: general-context

id: general-context-aws
name: This workflow sets the "general" risk of resources.
csp: aws

filters:
    - match-type: all
      rules:
          - .csp=="aws"

risk-config:
    default-risk: ''
    rules:
        - name: My team uses us-east-1 exclusively
          condition: .region != "us-east-1"
          risk: low
```

This one rule alone helped me get rid of most of my noise (~90%).

![Alerts in my region](/img/blog/prisma-cloud/regionAlerts.png)

To be frank, filtering out a region is something you can easily do using Prisma Cloud filters or even Splunk queries. However, consider two things:

1. Most customers use multiple security solutions. Are you going to add a region filter across all of your vendors or all of your Splunk queries? Wouldn't it be nice if everything was normalized and the alert prioritization was vendor-agnostic?
2. As a continuation of the previous point, we don't want tribal knowledge to exist in different places. We want all the "context" in a single place. We want to help teams avoid information silos using declarative alert-processing-as-code.

Another neat thing we have done at Dassana is create a categorization system for risk-based alerts. For incidents, we use the MITRE ATT&CK framework. However, nothing of that sort existed for risks, and so we went and created our own. [Learn more](https://github.com/dassana-io/dassana/blob/main/content/schemas/policy-classification/policy-classification.yaml).

Moving on, I decided to analyze the remaining alerts by category.

![Categorized alerts](/img/blog/prisma-cloud/categorizedAlerts.png)

I had 16 alerts across four categories: IAM, visibility, storage, and networking. Personally, I only care about IAM and networking alerts from a prioritization standpoint, so I went ahead and added another rule to filter out visibility and storage alerts.

```yaml
schema: 1
type: general-context

id: general-context-aws
name: This workflow sets the "general" risk of resources.
csp: aws

filters:
    - match-type: all
      rules:
          - .csp=="aws"

risk-config:
    default-risk: ''
    rules:
        - name: My team uses us-east-1 exclusively
          condition: .region != "us-east-1"
          risk: low

        - name: Visibility and storage are lower priority for my team
          condition: .alertClassification.category == "storage" or .alertClassification.category == "visibility"
          risk: low
```

Just with two rules, I have reduced 157 alerts down by 93%.

![Final alerts](/img/blog/prisma-cloud/finalAlerts.png)

I can further extend this to do things like

-   assign risk based on a keyword inside a resource name
-   assign general risk based on tags

```yaml
# Risk based on keywords
- name: If the word PCI is in the name, then it's a big deal for me
  condition: .resourceId | contains("pci")
  risk: critical

# Risk based on tags
- name: dev environment risk is low
  condition: .tags | any( select(.name | test("env" ; "ix")) | select(.value | test("dev" ; "ix")))
  risk: low

- name: prod environment risk is high
  condition: .tags | any( select(.name | test("env" ; "ix")) | select(.value | test("prod" ; "ix")))
  risk: high
```

Just for context (pun intended 😉), here is the entire Splunk dashboard.

![Splunk dashboard](/img/blog/prisma-cloud/splunkDashboard.png)

To summarize, while most alert-producing and alert-consuming tools give you the filters you need, it's challenging to put subjective context in the right places. We need to eliminate tribal knowledge and information silos. Context is subjective. Dassana's general-context workflow is a great place to add simple declarative rules to prioritize alerts regardless of vendor.

Here are the key benefits of using Dassana with Prisma Cloud:

1. It’s FREE!. [Deploy now](/docs/getting-started/installation)!
2. Elimate tribal knowledge by creating a centralized alert management system providing consistency across any security alert source or cloud service provider.
3. Improve your cloud security posture by as much as 90% in minutes.
4. Forward only relevant cloud alerts to your SIEM tool and save big on licensing and storage costs.
5. Reduce Mean Time to Identify (MTTI) exposure from months to hours.

That's it for today. If you are already using Prisma Cloud, try [deploying Dassana](/docs/getting-started/installation/)! If you like Dassana please tweet [@DassanaSecurity](https://twitter.com/DassanaSecurity). If you have questions, feedback, or even want to contribute, head on over to our [open source GitHub repo](https://github.com/dassana-io/dassana). Lets beat alert fatigue together, as a [community](https://join.slack.com/t/dassanacommunity/shared_invite/zt-teo6d5ed-xkWDNSaH4m6pC8PAJnrD8g).
