---
title: FluxCD
parent: Jupyter Hub
layout: page
---

The FluxCD Configuration for [Jupyter Hub](https://jupyter.org/hub). 

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