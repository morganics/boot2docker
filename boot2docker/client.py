import subprocess
import os
from typing import Dict
from typing import Tuple
import getpass

# this is the shared folder that is by default installed on a VirtualBox.
SHARED_FOLDER = "/Users"

class VirtualBoxDriverCommands:

    def __init__(self, path:str=r"c:\program files\oracle\virtualbox"):
        self._vbox_path = path

    def vboxmanage_path(self):
        return os.path.join(self._vbox_path, "vboxmanage")

    def sharedfolder_remove(self, vm_name, folder_name='Users'):
        return "\"{}\" sharedfolder remove {} -name {}".format(
            self.vboxmanage_path(),
            vm_name,
            folder_name
        )

    def sharedfolder_add(self, vm_name, local_path, folder_name='Users'):
        return "\"{}\" sharedfolder add {} -name {} -hostpath {} --automount".format(
            self.vboxmanage_path(),
            vm_name,
            folder_name,
            local_path
        )

    def sharedfolder_symlinks(self, vm_name, folder_name='Users', value=True):
        return "\"{}\" setextradata {} VBoxInternal2/SharedFoldersEnableSymlinksCreate/{} {}".format(
            self.vboxmanage_path(),
            vm_name,
            folder_name,
            int(value)
        )

    def get_driver_name(self):
        return 'virtualbox'

def _call_p(env, command):
    path = os.path.join(os.path.dirname(__file__), 'command.cmd')

    # writing to file and then calling it seems to pass on admin rights... !?
    with open(path, 'w') as fh:
        fh.write("CALL {}".format(command))

    subprocess.call([path], env=env, shell=True)


class DockerContainer:
    def __init__(self, image_name, tag, container_name, env, image: 'DockerImage'):
        self._container_name = container_name
        self._image_name = image_name
        self._tag = tag
        self._env = env
        self._image = image

    def exists(self):
        return True

    def stop(self) -> "DockerContainer":
        _call_p(self._env, "docker stop {}".format(self._container_name))
        return self

    def remove(self) -> "DockerContainer":
        _call_p(self._env, "docker rm {}".format(self._container_name))
        return self

    def start(self) -> "DockerContainer":
        _call_p(self._env, "docker start {}".format(self._container_name))
        return self

    def get_image(self):
        return self._image


class DockerImage:

    def __init__(self, env, image_name, tag):
        self._env = env
        self._image_name = image_name
        self._tag = tag

    def tag(self, repo_name, repo_tag='latest'):
        _call_p(self._env, "docker tag {}:{} {}:{}".format(self._image_name, self._tag, repo_name, repo_tag))

    def push(self, repo_name):
        _call_p(self._env, "docker push {}".format(repo_name))

    def get_container(self, container_name) -> DockerContainer:
        return DockerContainer(self._image_name, self._tag, container_name, self._env, self)

    def _get_shared_folder(self, folder):
        if SHARED_FOLDER in folder:
            return folder

        return SHARED_FOLDER + "/" + folder

    def run(self, volume=None, env: Dict[str,str]=None, remove=True, port_map=None, container_name=None,
                    entrypoint=None, restart:str="no") -> DockerContainer:

        args = []
        if volume is not None:
            if not isinstance(volume, list):
                volume = [volume]

            for v in volume:
                if isinstance(v, tuple):
                    host_folder = self._get_shared_folder(v[0])
                    machine_folder = v[1]
                else:
                    host_folder = SHARED_FOLDER
                    machine_folder = v

                args.append("--volume {}:{}".format(host_folder, machine_folder))

        if not isinstance(port_map, list):
            port_map = [port_map]

        for m in port_map:
            args.append("-p {}:{}".format(m[0], m[1]))

        args.append("--restart {}".format(restart))

        if remove:
            args.append("--rm")

        if env is not None:
            if isinstance(env, list):
                for key in env:
                    args.append("-e {}".format(key))

                env = {}
            else:
                for key, value in env.items():
                    args.append("-e {}".format(key))
        else:
            env = {}

        if container_name is not None:
            args.append("--name {}".format(container_name))

        if entrypoint is not None:
            args.append("--entrypoint {}".format(entrypoint))


        _call_p({**self._env, **env}, "docker run {} {}:{}".format(" ".join(args), self._image_name, self._tag))

        return self.get_container(container_name)

class Docker:

    def __init__(self, env):
        self._env = env

    def build(self, image_name, tag='latest', dir='.') -> DockerImage:
        _call_p(self._env, "docker build -t {}:{} {}".format(image_name, tag, dir))
        return DockerImage(self._env, image_name, tag)

    def login(self, username, password):
        _call_p(self._env, "docker login --username={} --password={}".format(username, password))

    def get_image(self, image_name, tag='latest') -> DockerImage:
        return DockerImage(self._env, image_name, tag)


class DockerMachine:

    def __init__(self, vm_name:str, vbox:VirtualBoxDriverCommands,
                 docker_cert_path:str=r"C:\Users\{}\.docker\machine\machines".format(getpass.getuser()),
                 docker_tls_verify:str='1'):

        self._vbox = vbox
        self._vm_name = vm_name
        self._docker_cert_path = docker_cert_path
        self._host = None
        self._docker_tls_verify = docker_tls_verify

    def _get_env(self):
        return {
            **os.environ, **{
            'DOCKER_HOST': self._host if self._host is not None else '',
            'DOCKER_CERT_PATH': os.path.join(self._docker_cert_path, self._vm_name),
            'DOCKER_TLS_VERIFY': self._docker_tls_verify,
            'DOCKER_MACHINE_NAME': self._vm_name
        }}

    def _call(self, command:str):
        _call_p(self._get_env(), command)

    def set_host_name(self, ip):
        self._host = ip

    def get_vm_tcp(self):
        ip = self.get_vm_ip()
        if ip is None:
            return None

        return "tcp://{}:2376".format(ip)

    def get_vm_ip(self):
        try:
            out = subprocess.check_output("docker-machine ip {}".format(self._vm_name),
                                          env=self._get_env(), shell=True)
            ip = out.decode("utf-8").strip()
            return ip
        except subprocess.CalledProcessError:
            return None

    def vm_create(self, memory="1024"):
        return self._call("docker-machine create --driver {} --virtualbox-memory {} {}".format(self._vbox.get_driver_name(),
                                                                                               memory, self._vm_name))

    def vm_start(self):
        return self._call("docker-machine start {}".format(self._vm_name))

    def vm_stop(self):
        return self._call("docker-machine stop {}".format(self._vm_name))

    def vm_delete(self):
        return self._call("docker-machine rm -y {}".format(self._vm_name))

    def vm_sharedfolder_create(self, local_share_path):
        return self._call(self._vbox.sharedfolder_add(self._vm_name, local_share_path))

    def vm_sharedfolder_delete(self):
        return self._call(self._vbox.sharedfolder_remove(self._vm_name))

    def vm_regenerate_certs(self):
        return self._call("docker-machine regenerate-certs -f {}".format(self._vm_name))

    def vm_sharedfolder_symlinks(self):
        return self._call(self._vbox.sharedfolder_symlinks(self._vm_name))

    def vm_status(self):
        try:
            out = subprocess.check_output("docker-machine status {}".format(self._vm_name),
                                      env=self._get_env(), shell=True)
            return out.decode("utf-8").strip()
        except subprocess.CalledProcessError:
            return None

    def vm_status_running(self):
        return self.vm_status() == "Running"

    def vm_status_stopped(self):
        return self.vm_status() == "Stopped"

    def vm_exists(self):
        return self.vm_status() != None

    def remove_local_env(self):
        self.vm_delete()

        return self

    def create_local_env(self, local_shared_folder=None, symlinks=True, memory=None):

        if self.vm_exists():

            if self.vm_status_stopped():
                self.vm_start()

            self.vm_regenerate_certs()

            self.set_host_name(self.get_vm_tcp())
            print("HOST: {}".format(self._host))
            return self

        if memory is not None:
            self.vm_create(memory)
        else:
            self.vm_create()

        self.set_host_name(self.get_vm_ip())

        if local_shared_folder is not None:
            if not os.path.exists(local_shared_folder):
                os.mkdir(local_shared_folder)

            self.vm_stop()
            self.vm_sharedfolder_create(local_shared_folder)
            if symlinks:
                self.vm_sharedfolder_symlinks()

        self.vm_start()
        self.set_host_name(self.get_vm_tcp())
        self.vm_regenerate_certs()
        print("HOST: {}".format(self._host))

        return self

    def get_docker_client(self) -> Docker:
        if self._host is None:
            self.set_host_name(self.get_vm_tcp())

        return Docker(self._get_env())

    def interact(self):
        from sys import executable
        from subprocess import Popen, CREATE_NEW_CONSOLE

        Popen(executable, creationflags=CREATE_NEW_CONSOLE, shell=True)