# iac-flux-jupyter
Flux configuration for JupyterHub

## Developer Guide
This flux configuration will be created by the [Core LSCSDE Helm Chart](../../helm/lscsde-flux/), which in turn is called by the [Core LSCSDE Flux configuration](../lscsde/)

When the main branch of this repository is created it will trigger a github action which will:
* Calculate a semver version number
* Create a release branch with the semver version
* Update the submodules on the main repository
* Update the jupyter_branch value on the core [lscsde flux configuration](../lscsde)

This will in turn trigger github actions that will propagate those changes up the chain

## Keycloak API Documentation
There are two roles within keycloak needed for jupyter to function correctly:

* jupyter-users
* jupyter-admins

These two roles should be associated so that jupyter-admins are automatically part of jupyter-users.

Jupyter users should also be associated with the following client roles:
* realm-management - query groups
* account - view groups
* realm-management - view users

The following is an example of the /admin/realms/{realm}/groups API:
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

once this has been queried we have to use the **id** for the relevant subgroup to query the group. This is done using the API /admin/realms/{realm}/groups/{id}/children:

```json
[
    {
        "id": "79cdf13c-a6bc-46cd-8a5d-1281b0fe8e53",
        "name": "Colorectal Cancer Research Group Workspace",
        "path": "/jupyter-workspaces/Colorectal Cancer Research Group Workspace",
        "parentId": "429c803a-a033-4e1e-8aea-73b92fd43003",
        "subGroupCount": 0,
        "attributes": {
            "workspace.xlscsde.nhs.uk/environment": [
                "jupyter_advanced"
            ],
            "workspace.xlscsde.nhs.uk/startDate": [
                "2022-01-01"
            ],
            "workspace.xlscsde.nhs.uk/endDate": [
                "2030-01-01"
            ],
            "workspace.xlscsde.nhs.uk/description": [
                "An example workspace for the testing of using keycloak groups"
            ]
        },
        "access": {
            "view": True,
            "viewMembers": True,
            "manageMembers": False,
            "manage": False,
            "manageMembership": False
        }
    },
    {
        "id": "a6fdb60b-f11d-4c59-bdf3-e03fac24b6ab",
        "name": "Default Generic Workspace",
        "path": "/jupyter-workspaces/Default Generic Workspace",
        "parentId": "429c803a-a033-4e1e-8aea-73b92fd43003",
        "subGroupCount": 0,
        "attributes": {
            "workspace.xlscsde.nhs.uk/startDate": [
                "2022-01-01"
            ],
            "workspace.xlscsde.nhs.uk/environment": [
                "jupyter_default"
            ],
            "workspace.xlscsde.nhs.uk/endDate": [
                "2030-01-01"
            ],
            "workspace.xlscsde.nhs.uk/description": [
                "Basic environment for testing with Python R and Julia."
            ]
        },
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