---
title: FluxCD
parent: Jupyter Hub
layout: page
---

The FluxCD Configuration for [Jupyter Hub](https://jupyter.org/hub). This configuration deploys and configures the jupyter hub helm chart from the [jupyter hub repository](https://jupyterhub.github.io/helm-chart/). The implementation is configured to use a [customized jupyter image](../../../../docker/jupyterhub/docs/image.md). It disables the default ingress inside of the helm chart and deploys it's own to match the configuration needed in the SDE.

In addition to the helm chart deployment and configuration, the solution also deploys role binding that allows jupyter hub to query the kubernetes API for AWMS custom resources such as AnalyticsWorkspaces and AnalyticsWorkspaceBindings.

Finally, the solution adds the storage class called jupyter-default. This is then used by the custom jupyter image when creating PVC's for each of the workspaces.


## Network Policies

```mermaid
flowchart LR
    all([all services]) -->|Ingress ALL| svc[JupyterHub] 
    svc -->|Egress HTTPS|all
    svc -->|Egress HTTPS| kubernetes[[Kubernetes API]]
    svc -->|Egress DNS| coredns
```

| Direction | Ports/Type | Description |
| --- | --- | --- |
| Ingress | All | Allows all traffic inbound. TODO: This needs to be refined |
| Egress | All | Allows all traffic to egress. TODO: This needs to be refined |
| Egress | TCP/UDP 53 | Allows traffic for DNS ports |
| Egress | HTTPS | Allows access to the kubernetes service to allow Kubernetes API Access |