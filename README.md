# iac-flux-jupyter
Flux configuration for JupyterHub

## Developer Guide
To test the changes, ensure that you are on your developer machine and that the context is set correctly to your local instance please amend the following script to use the target branch:

```bash
kubectl config use-context docker-desktop
kubectl create namespace jupyterhub
flux create source git jupyterhub --url="https://github.com/lsc-sde/iac-flux-jupyter" --branch=main --namespace=jupyterhub
flux create kustomization jupyterhub-cluster-config --source="GitRepository/jupyterhub" --namespace=jupyterhub --path="./cluster/local" --interval=1m --prune=true --health-check-timeout=10m --wait=false
flux create kustomization jupyterhub-config --source="GitRepository/jupyterhub" --namespace=jupyterhub --path="./sources/config" --interval=1m --prune=true --health-check-timeout=10m --wait=false
flux create kustomization jupyterhub-package --source="GitRepository/jupyterhub" --namespace=jupyterhub --path="./sources/package" --interval=1m --prune=true --health-check-timeout=10m --wait=false
```

This should in turn deploy all of the resulting resources on your local cluster.