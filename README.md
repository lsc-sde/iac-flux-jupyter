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

## Keycloak API Documentation
At the keycloak API documentation isn't great the following is an example of the /admin/realms/{realm}/groups API:
```json
[
    {
        "id": "429c803a-a033-4e1e-8aea-73b92fd43003",
        "name": "jupyter-workspaces",
        "path": "/jupyter-workspaces",
        "subGroupCount": 2,
        "access": {
            "view": True,
            "viewMembers": True,
            "manageMembers": False,
            "manage": False,
            "manageMembership": False
        }
    },
    {
        "id": "0239d876-a497-476d-96c8-96bde8d9f718",
        "name": "some-other-group",
        "path": "/some-other-group",
        "subGroupCount": 0,
        "access": {
            "view": True,
            "viewMembers": True,
            "manageMembers": False,
            "manage": False,
            "manageMembership": False
        }
    }
]
```

once this has been queried we have to use the **id** for the relevant subgroup to query the group. This is done using the API /admin/realms/{realm}/groups/{id}:

```json

```