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

This should in turn deploy all of the resulting resources on your local cluster. Once done you'll need to download the CA certificate for this so that you can install it onto your local machine:

```bash
kubectl get secrets/jupyterhub.lsc-sde.local-tls -n jupyterhub -o=jsonpath="{.data.ca\.crt}" | base64 --decode > ca.crt
```

this will create a ca.crt file in the directory, you will then need to install it into your trusted root authorities.

You will also need to adjust your machines hosts file to include the line:

```
127.0.0.1 jupyterhub.lsc-sde.local
```