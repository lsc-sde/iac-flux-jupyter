from datetime import datetime, timedelta
from secrets import token_hex

from kubernetes_asyncio import client
from kubernetes_asyncio.client.models import (
    V1ObjectMeta,
    V1Pod,
    V1Volume,
    V1VolumeMount,
)
from kubespawner.spawner import KubeSpawner
from kubespawner.utils import get_k8s_model

import z2jh
import requests
import urllib.parse

def query_keycloak(spawner: KubeSpawner, url):
    spawner.log.info( f"Querying Keycloak at: {url}" )
    access_token = spawner.access_token
    keycloak_headers = {"Authorization": f"Bearer {access_token}" } 
    keycloak_response = requests.get(url, headers=keycloak_headers, verify="/etc/ssl/certs/ca-certificates.crt")
    response_json = keycloak_response.json()
    spawner.log.info( f"Keycloak returned the following response: {response_json}" )
    return response_json

def get_keycloak_groups(spawner: KubeSpawner):
    base_url = z2jh.get_config("hub.config.GenericOAuthenticator.keycloak_api_base_url")
    api_url = f"{base_url}/groups?populateHierarchy=true"
    return query_keycloak(spawner, api_url)
    
def get_keycloak_group_children(spawner: KubeSpawner, groupId):
    base_url = z2jh.get_config("hub.config.GenericOAuthenticator.keycloak_api_base_url")
    api_url = f"{base_url}/groups/{groupId}/children"
    return query_keycloak(spawner, api_url)
    
def get_keycloak_group(spawner: KubeSpawner, groupId):
    base_url = z2jh.get_config("hub.config.GenericOAuthenticator.keycloak_api_base_url")
    api_url = f"{base_url}/groups/{groupId}"
    return query_keycloak(spawner, api_url)
    
def get_keycloak_group_by_name(spawner: KubeSpawner, name):
    base_url = z2jh.get_config("hub.config.GenericOAuthenticator.keycloak_api_base_url")
    api_url = f"{base_url}/groups"
    results = query_keycloak(spawner, api_url)
    return [g for g in results if g['name'] == name][0]

def get_workspaces(spawner: KubeSpawner):
    user = spawner.user.name
    userdata = spawner.oauth_user
    groups = userdata["realm_groups"]
    permitted_workspaces = []
    
    keycloak_workspace_children = []
    try:
        # Get the workspace group details so we can use the id in the next phase
        jupyter_workspace_group = get_keycloak_group_by_name(spawner, "jupyter-workspaces")
        spawner.log.info(f"jupyter_workspace_group = {jupyter_workspace_group}")
        keycloak_workspace_children = get_keycloak_group_children(spawner, jupyter_workspace_group["id"])

    except Exception as error:
        spawner.log.error(
            f"Keycloak returned: {error}"
        )

    for group_name in groups:
        spawner.log.info(
            f"User {user} is member of {group_name}, checking for any workspaces associated with"
        )
        if not group_name.startswith("/jupyter-workspaces/"):
            spawner.log.info(f"Group {group_name} is not part of jupyter-workspaces, ignoring.")
            continue
        #try:
        #    keycloak_workspace_group = get_keycloak_group_by_path(spawner, group_name)
        #except Exception as e:
        #    spawner.log.info(f"Exception getting keycloak group: {e}.")

        group_configuration = [g for g in keycloak_workspace_children if g['path'].casefold() == group_name.casefold()][0]
        group_attributes = group_configuration.get("attributes", {})
        
        ws = dict()
        display_name = group_name.split("/")[-1]
        ws["display_name"] = display_name
        
        spawner.log.info(f"Group {group_name} does represent a workspace.")

        # get the kubespawner_override
        environment_name = group_attributes.get("workspace.xlscsde.nhs.uk/environment", [ "jupyter_default" ])[0]
        kubespawner_override = z2jh.get_config("custom.environments").get(environment_name)
        
        workspace_name = display_name.lower().replace(" ", "-")
        kubespawner_override["extra_labels"] = {"workspace": workspace_name}
        ws["kubespawner_override"] = kubespawner_override

        # Check if workspace itself has expired
        ws_end_date = group_attributes.get("workspace.xlscsde.nhs.uk/endDate", [ "1900-01-01" ])[0]
        ws_end_date = datetime.strptime(ws_end_date, "%Y-%m-%d")
        ws_days_left: timedelta = ws_end_date - datetime.today()
        ws_days_left = ws_days_left.days

        if ws_days_left < 0:
            spawner.log.info(
                f"Workspace {group_name} expired on {ws_end_date.strftime( '%Y-%m-%d')}. Consider removing it from config."
            )
            continue

        # Check if user access to workspace has expired
        # user_ws_end_date = ws_values.get("end_date", "1900-01-01")
        # user_ws_end_date = datetime.strptime(user_ws_end_date, "%Y-%m-%d")
        # user_ws_days_left: timedelta = user_ws_end_date - datetime.today()
        # user_ws_days_left = user_ws_days_left.days

        #if user_ws_days_left < 0:
        #    spawner.log.info(
        #        f"User {user}'s access to workspace {group_name}({ws.get('display_name','' )}) has expired."
        #    )
        #    continue

        ws["slug"] = workspace_name
        
        ws["description"] = group_attributes.get("workspace.xlscsde.nhs.uk/description", [ "No description provided" ])[0] 
        ws["start_date"] = group_attributes.get("workspace.xlscsde.nhs.uk/startDate", [ "1900-01-01" ])[0]
        ws["end_date"] = ws_end_date
        ws["ws_days_left"] = ws_days_left
        #ws["user_ws_days_left"] = user_ws_days_left
        
        spawner.log.info(f"Group {group_name} has a workspace config of {ws}.")

        permitted_workspaces.append(ws)

    permitted_workspaces = sorted(
        permitted_workspaces, key=lambda x: x.get("slug", "99_Z")
    )

    # Raise an unhandled exception if no user workspaces found.
    # This is avoided by adding default workspace to all users.
    # This currently raises a 500 status code. Find a better way of doing this.
    # https://github.com/jupyterhub/jupyterhub/issues/2291
    if len(permitted_workspaces) == 0:
        raise Exception(f"User {user} does not have any workspaces assigned!")

    return permitted_workspaces


def modify_pod_hook(spawner: KubeSpawner, pod: V1Pod):
    # Add additional storage based on workspace label on pod
    # This ensures that the correct storage is mounted into the correct workspace
    try:
        metadata: V1ObjectMeta = pod.metadata

        workspace = metadata.labels.get("workspace", "")

        storage = z2jh.get_config(f"custom.workspaces.{workspace}.storage")

        spawner.log.info(f"Attempting to mount {str(storage)}...")

        if storage:
            # Remove other user storage if workspace has dedicated storage specified
            # This prevents user from moving data between workspaces using their personal
            # storage that appears in all workpaces.
            # Unless the user is an admin user, in which case leave their storage in place

            admin_users = z2jh.get_config(
                "hub.config.AzureAdOAuthenticator.admin_users", []
            )

            if spawner.user.name not in admin_users:
                spawner.log.info(
                    f"Workspace {workspace} has dedicated storage. Removing all user storage from container."
                )
                pod.spec.volumes = []
                pod.spec.containers[0].volume_mounts = []

            volumes = storage["volumes"]
            volume_mounts = storage["volume_mounts"]
            for v, vm in zip(volumes, volume_mounts):
                pod.spec.volumes.append(get_k8s_model(V1Volume, v))
                pod.spec.containers[0].volume_mounts.append(
                    get_k8s_model(V1VolumeMount, vm)
                )

            spawner.log.info(f"Successfully mounted {v['name']} to {vm['mountPath']}.")
        else:
            spawner.log.info(
                f"No additional volumes to mount for '{workspace}' workspace."
            )

    except Exception as e:
        spawner.log.error(f"Error mounting workspace storage! Error msg {str(e)}")

    # Mount read-only shared folder at the end.
    try:
        common_storage = {
            "volume": {
                "name": "landerhub-common",
                "persistentVolumeClaim": {"claimName": "pvc-landerhub-common"},
            },
            "volume_mount": {
                "name": "landerhub-common",
                "mountPath": "/home/jovyan/shared_readonly",
                "readOnly": True,
            },
        }

        # get both volume and volume_mount before adding to exsiting lists.
        # Error here will skip assigning just the volume and not the mount
        volume = common_storage["volume"]
        volume_mount = common_storage["volume_mount"]

        pod.spec.volumes.append(get_k8s_model(V1Volume, volume))
        pod.spec.containers[0].volume_mounts.append(
            get_k8s_model(V1VolumeMount, volume_mount)
        )

        spawner.log.info(
            f"Successfully mounted {volume['name']} to {volume_mount['mountPath']}."
        )

    except Exception as e:
        spawner.log.error(f"Error mounting common shared folders. Error msg: {str(e)}")

    return pod

def userdata_hook(spawner, auth_state):
    spawner.oauth_user = auth_state["oauth_user"]
    spawner.access_token = auth_state["access_token"]

c.KubeSpawner.start_timeout = 900
c.JupyterHub.authenticator_class = 'oauthenticator.generic.GenericOAuthenticator'
c.GenericOAuthenticator.enable_auth_state = True
os.environ['JUPYTERHUB_CRYPT_KEY'] = token_hex(32)


c.Spawner.auth_state_hook = userdata_hook
# c.KubeSpawner.modify_pod_hook = modify_pod_hook
c.KubeSpawner.profile_list = get_workspaces
c.KubeSpawner.profile_form_template = """
        <style>
        /* The profile description should not be bold, even though it is inside the <label> tag */
        #kubespawner-profiles-list label p {
            font-weight: normal;
        }
        </style>
        <div class='form-group' id='kubespawner-profiles-list'>
        {% for profile in profile_list %}
        <label for='profile-item-{{ profile.slug }}' class='form-control input-group'>
            <div class='col-md-1'>
                <input type='radio' name='profile' id='profile-item-{{ profile.slug }}' value='{{ profile.slug }}' {% if profile.default %}checked{% endif %} />
            </div>
            <div class='col-md-11'>
                <strong>{{ profile.display_name }}</strong>
                {% if profile.description %}
                    <p>{{ profile.description }}
                {% endif %}
                {% if profile.kubespawner_override.image %}
                    <br><em>Image: {{ profile.kubespawner_override.image.split('/')[-1] }}</em>
                {% endif %}
                <br><em>Your access expires in : {{profile.user_ws_days_left }} days.</em>
                </p>
            </div>
        </label>
        {% endfor %}
        </div>
        """
