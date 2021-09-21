# Introduction

**How can Dassana help me?**

Dassana is on a mission to solve the alert fatigue problem. Now, more than ever before, it is easy to "scan" your environment for security issues and deploy threat detection tools. But as soon as you deploy these tools, you will find that they start generating too many alerts. Although most of the alerts are accurate, they still lack the necessary context to be of great help. For example, if you get an alert that an s3 bucket has been found public in your environment, you might drop everything and start investigating it. But what if you find that there is a website associated with the bucket? What if the bucket has the word public or static in it? Wouldn't it be great if the alert already had this context to begin with? That's what Dassana does. Dassana adds context to security alerts.

PS: Check out [this](https://docs.dassana.io/blog/static-s3-bucket) blog to get a flavor of what we are talking about.

**How is it different?**

Current approaches to the alert fatigue problem involve prioritizing alerts based on the severity of the alert generated. The original severity provided by the vendor does not consider your runtime context. This means that a low or medium severity alert could be more important than a high severity alert. Dassana takes a different approach. Dassana believes in contextual risk; this means that the risk values provided by Dassana are specific to your environment.

Furthermore, Dassana normalizes all alerts it receives, which means all contextualization happens on a normalized alert. This means that you gain vendor independence, you can use any cloud security tool, and the contextualization will continue to work in a vendor-agnostic manner.

:::info
Much like snort was created to inspect network traffic declaratively, and ModSecurity was designed to inspect HTTP traffic, Dassana was created to process security alerts declaratively.
:::

**Can I contextualize any alert?**

Yes. Out-of-the-box, we are supporting GuardDuty and AWS Config alerts ingested by SecurityHub. We also provide a free and open-source [editor](https://editor.dassana.io/) that you can use to contextualize any alert.

**Is it free and open source?**

Yes. And the core product will always remain open source available under Apache license.

**How do I deploy it?**

CloudFormation template. Dassana only uses serverless components, so you don't have to manage anything! It is the best of both worlds - you get a SaaS-like experience, and all the data resides in your environment.

**How does it work?**

The Dassana Engine processes alerts by running them through a set of workflows. These workflows are responsible for the normalization and contextualization of alerts. You can edit an existing workflow or author a new one using [Dassana Editor](https://editor.dassana.io/). For more information, check out [this](https://docs.dassana.io/docs/how-it-works/high-level) documentation.

**What's next?**

Give it a try and let us know what you think. We would love to support any use case solving the alert fatigue problem, so please give us feedback.
