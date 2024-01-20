
# https://github.com/jupyterhub/zero-to-jupyterhub-k8s/issues/1580#issuecomment-707776237
# https://zero-to-jupyterhub.readthedocs.io/en/latest/resources/reference.html#hub-extrafiles
# https://discourse.jupyter.org/t/tailoring-spawn-options-and-server-configuration-to-certain-users/8449
# https://discourse.jupyter.org/t/shared-folder-for-users-with-r-o-access-for-some-and-r-w-access-for-some-in-jupyterhub/4220/8

from datetime import datetime, timedelta

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


def get_workspaces(spawner: KubeSpawner):
    user = spawner.user.name
    # ToDo: Find a better way of dealing with new users.
    try:
        # accessing user workspaces using email id in dot notation does not work
        # user_workspaces:dict = z2jh.get_config(f"custom.users.{user}.workspaces", dict())
        user_workspaces: dict = (
            z2jh.get_config("custom.users").get(user).get("workspaces")
        )
    except:
        user_workspaces = {"00_ws_default": {"end_date": "2023-12-31"}}

    # Add the default workspace to all users.
    # Otherwise, the code at the end of this function will raise an unhandled error
    # Will have to reimplement/rethink whether a new user should get access to an analytical environment by default.
    # Good practice would be for no one to have access unless explicitly set.

    permitted_workspaces = []

    for ws_key, ws_values in user_workspaces.items():
        ws = z2jh.get_config(f"custom.workspaces.{ws_key}", None)
        if ws is None:
            spawner.log.error(f"Workspace {ws_key} not found for user {user}.")
            continue

        # Check if workspace itself has expired
        ws_end_date = ws.get("end_date", "1900-01-01")
        ws_end_date = datetime.strptime(ws_end_date, "%Y-%m-%d")
        ws_days_left: timedelta = ws_end_date - datetime.today()
        ws_days_left = ws_days_left.days

        if ws_days_left < 0:
            spawner.log.info(
                f"Workspace {ws_key} expired on {ws_end_date.strftime( '%Y-%m-%d')}. Consider removing it from config."
            )
            continue

        # Check if user access to workspace has expired
        user_ws_end_date = ws_values.get("end_date", "1900-01-01")
        user_ws_end_date = datetime.strptime(user_ws_end_date, "%Y-%m-%d")
        user_ws_days_left: timedelta = user_ws_end_date - datetime.today()
        user_ws_days_left = user_ws_days_left.days

        if user_ws_days_left < 0:
            spawner.log.info(
                f"User {user}'s access to workspace {ws_key}({ws.get('display_name','' )}) has expired."
            )
            continue

        ws["kubespawner_override"]["extra_labels"] = {"workspace": ws_key}
        ws["slug"] = ws_key

        ws["ws_days_left"] = ws_days_left
        ws["user_ws_days_left"] = user_ws_days_left

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


c.KubeSpawner.start_timeout = 900
c.KubeSpawner.modify_pod_hook = modify_pod_hook
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
