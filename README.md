# boot2docker
Simple SDK for interacting with boot2docker from Python. 

# Motivation
Boot2Docker has a perfectly reasonable command line interface, but doesn't seem to have an up to date SDK in Python. This just uses subprocess to call the relevant commands using a somewhat 'fluent' API. It's by no means complete, but caters for (I'd imagine) the majority of cases, of setting up a Boot2Docker environment in VirtualBox, and interacting with the environment using Docker. DockerMachine in this case was installed through Chocolatey.

# Example

## Metabase Docker Image with persistent storage

Here's an example to start up the Metabase docker image with a shared folder and Symlinks:

    import boot2docker.client as b2d
    import getpass

    HOST_SHARE_FOLDER = r"C:\Users\{}\share\metabase".format(getpass.getuser())
    dm = b2d.DockerMachine("metabase", b2d.VirtualBoxDriverCommands())
    client = dm.create_local_env(HOST_SHARE_FOLDER).get_docker_client()

    client.get_image("metabase/metabase").run(volume=("/Users", "/tmp"), env=["MB_DB_FILE=/tmp/metabase.db"],
                    port_map=(3000, 3000),
                    container_name="metabase"
                    )

