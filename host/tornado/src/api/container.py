import time
import multiprocessing

import isodate
import psutil

from utils.jbox_util import LoggerMixin, unique_container_name, continer_name_prefix
from jbox_tasks import JBoxAsyncJob
from queue import APIQueue
from connector import APIConnector
from cloud.aws import CloudHost


class APIContainer(LoggerMixin):
    # keep shellinabox for troubleshooting
    CONTAINER_PORT_BINDINGS = {4200: ('127.0.0.1',)}
    HOST_VOLUMES = None
    DCKR = None
    DCKR_IMAGE_PFX = None
    MEM_LIMIT = None

    # By default all groups have 1024 shares.
    # A group with 100 shares will get a ~10% portion of the CPU time (https://wiki.archlinux.org/index.php/Cgroups)
    CPU_LIMIT = 1024
    PORTS = [4200]
    LOCAL_TZ_OFFSET = 0
    MAX_CONTAINERS = 0
    INITIAL_DISK_USED_PCT = None
    LAST_CPU_PCT = None

    API_CONTAINERS = {}
    DESIRED_CONTAINER_COUNTS = {}

    ASYNC_JOB = None

    def __init__(self, dockid):
        self.dockid = dockid
        self.props = None
        self.dbgstr = None
        self.host_ports = None

    def refresh(self):
        self.props = None
        self.dbgstr = None

    def get_props(self):
        if self.props is None:
            self.props = APIContainer.DCKR.inspect_container(self.dockid)
        return self.props

    def get_cpu_allocated(self):
        props = self.get_props()
        cpu_shares = props['Config']['CpuShares']
        num_cpus = multiprocessing.cpu_count()
        return max(1, int(num_cpus * cpu_shares / 1024))

    def get_memory_allocated(self):
        props = self.get_props()
        mem = props['Config']['Memory']
        if mem > 0:
            return mem
        return psutil.virtual_memory().total

    def debug_str(self):
        if self.dbgstr is None:
            self.dbgstr = "APIContainer id=" + str(self.dockid) + ", name=" + str(self.get_name())
        return self.dbgstr

    def get_name(self):
        props = self.get_props()
        return props['Name'] if ('Name' in props) else None

    def get_api_name(self):
        if self.get_name() is None:
            return None
        parts = self.get_name().split('_')
        if len(parts) != 3:
            return None
        return parts[1]

    def get_image_names(self):
        props = self.get_props()
        img_id = props['Image']
        for img in APIContainer.DCKR.images():
            if img['Id'] == img_id:
                return img['RepoTags']
        return []

    @staticmethod
    def configure(dckr, image_pfx, mem_limit, cpu_limit, max_containers,
                  async_job_ports, async_mode=JBoxAsyncJob.MODE_PUB):
        APIContainer.DCKR = dckr
        APIContainer.DCKR_IMAGE_PFX = image_pfx
        APIContainer.MEM_LIMIT = mem_limit
        APIContainer.CPU_LIMIT = cpu_limit
        APIContainer.LOCAL_TZ_OFFSET = APIContainer.local_time_offset()
        APIContainer.MAX_CONTAINERS = max_containers
        APIContainer.ASYNC_JOB = JBoxAsyncJob(async_job_ports, async_mode)

    @staticmethod
    def get_image_name(api_name):
        return APIContainer.DCKR_IMAGE_PFX + '_' + api_name

    @staticmethod
    def ensure_container_available(api_name):
        if api_name in APIContainer.API_CONTAINERS:
            containers = APIContainer.API_CONTAINERS[api_name]
            if len(containers) > 0:
                APIContainer.log_debug("container already up for %s. count %r", api_name, len(containers))
                return
        APIContainer.create_new(api_name)

    @staticmethod
    def create_new(api_name):
        container_name = unique_container_name(api_name)
        queue = APIQueue.get_queue(api_name)
        env = {
            "JBAPI_NAME": api_name,
            "JBAPI_QUEUE": queue.get_endpoint_out(),
            "JBAPI_CMD": queue.get_command()
        }
        image_name = queue.get_image_name()
        if image_name is None:
            image_name = APIContainer.get_image_name(api_name)
        jsonobj = APIContainer.DCKR.create_container(image_name,
                                                     detach=True,
                                                     mem_limit=APIContainer.MEM_LIMIT,
                                                     cpu_shares=APIContainer.CPU_LIMIT,
                                                     ports=APIContainer.PORTS,
                                                     environment=env,
                                                     hostname='juliabox',
                                                     name=container_name)
        dockid = jsonobj["Id"]
        cont = APIContainer(dockid)
        APIContainer.log_info("Created " + cont.debug_str())
        cont.start(api_name)
        APIContainer.publish_container_stats()
        return cont

    @staticmethod
    def publish_container_stats():
        """ Publish custom cloudwatch statistics. Used for status monitoring and auto scaling. """
        nactive = APIContainer.num_active()
        CloudHost.publish_stats("NumActiveContainers", "Count", nactive)

        curr_cpu_used_pct = psutil.cpu_percent()
        last_cpu_used_pct = curr_cpu_used_pct if APIContainer.LAST_CPU_PCT is None else APIContainer.LAST_CPU_PCT
        APIContainer.LAST_CPU_PCT = curr_cpu_used_pct
        cpu_used_pct = int((curr_cpu_used_pct + last_cpu_used_pct)/2)

        mem_used_pct = psutil.virtual_memory().percent
        CloudHost.publish_stats("MemUsed", "Percent", mem_used_pct)

        disk_used_pct = 0
        for x in psutil.disk_partitions():
            try:
                disk_used_pct = max(psutil.disk_usage(x.mountpoint).percent, disk_used_pct)
            except:
                pass
        if APIContainer.INITIAL_DISK_USED_PCT is None:
            APIContainer.INITIAL_DISK_USED_PCT = disk_used_pct
        disk_used_pct = max(0, (disk_used_pct - APIContainer.INITIAL_DISK_USED_PCT))
        CloudHost.publish_stats("DiskUsed", "Percent", disk_used_pct)

        cont_load_pct = min(100, max(0, nactive * 100 / APIContainer.MAX_CONTAINERS))
        CloudHost.publish_stats("ContainersUsed", "Percent", cont_load_pct)

        overall_load_pct = max(cont_load_pct, disk_used_pct, mem_used_pct, cpu_used_pct)
        CloudHost.publish_stats("Load", "Percent", overall_load_pct)

    @staticmethod
    def calc_desired_container_counts():
        for api_name in APIContainer.API_CONTAINERS:
            queue = APIQueue.get_queue(api_name, alloc=False)
            if queue is None:
                APIContainer.DESIRED_CONTAINER_COUNTS[api_name] = 0
                continue

            desired = APIContainer.DESIRED_CONTAINER_COUNTS[api_name]
            APIContainer.log_debug("re-calculating desired capacity with %s. now %d.", queue.debug_str(), desired)
            if queue.mean_outstanding > 1:
                incr = int(queue.mean_outstanding)
                desired += incr
            elif queue.mean_outstanding < 0.01:  # approx 5 polls where 0 q length was found
                desired = 0
            elif queue.mean_outstanding < 0.5:  # nothing is queued when mean is 1/3
                if desired > 1:
                    desired -= 1
            APIContainer.DESIRED_CONTAINER_COUNTS[api_name] = desired
            APIContainer.log_debug("calculated desired capacity with %s to %d.", queue.debug_str(), desired)

            if queue.num_outstanding == 0:
                queue.incr_outstanding(0)   # recalculate mean if no requests are coming

    @staticmethod
    def refresh_container_list():
        APIContainer.API_CONTAINERS = {}

        for c in APIContainer.DCKR.containers(all=True):
            cont = APIContainer(c['Id'])
            if not (cont.is_running() or cont.is_restarting()):
                cont.delete()
                continue

            api_name = cont.get_api_name()
            if api_name is None:
                continue

            APIContainer.register_api_container(api_name, cont.dockid)

    @staticmethod
    def maintain():
        """
        For each API type, maintain a desired capacity calculated based on number of outstanding requests.
        """
        APIContainer.log_info("Starting container maintenance...")
        APIContainer.refresh_container_list()
        APIContainer.publish_container_stats()
        APIContainer.calc_desired_container_counts()

        for (api_name, clist) in APIContainer.API_CONTAINERS.iteritems():
            ndiff = len(clist) - APIContainer.DESIRED_CONTAINER_COUNTS[api_name]

            # terminate if in excess
            # TODO: this does not handle non-responsive containers yet
            while ndiff > 0:
                APIConnector.send_terminate_msg(api_name)
                ndiff -= 1

            # launch if more required
            while ndiff < 0:
                APIContainer.create_new(api_name)
                ndiff += 1

        APIContainer.log_info("Finished container maintenance.")

    @staticmethod
    def num_active():
        active_containers = APIContainer.DCKR.containers(all=False)
        return len(active_containers)

    @staticmethod
    def num_stopped():
        all_containers = APIContainer.DCKR.containers(all=True)
        return len(all_containers) - APIContainer.num_active()

    @staticmethod
    def get_by_name(name):
        nname = "/" + unicode(name)

        for c in APIContainer.DCKR.containers(all=True):
            if ('Names' in c) and (c['Names'] is not None) and (c['Names'][0] == nname):
                return APIContainer(c['Id'])
        return None

    @staticmethod
    def get_by_api(api_name):
        nname = continer_name_prefix(api_name)

        api_containers = []
        for c in APIContainer.DCKR.containers(all=True):
            if ('Names' in c) and (c['Names'] is not None) and (c['Names'][0]).startswith(nname):
                api_containers.append(APIContainer(c['Id']))
        return api_containers

    @staticmethod
    def parse_iso_time(tm):
        if tm is not None:
            tm = isodate.parse_datetime(tm)
        return tm

    @staticmethod
    def local_time_offset():
        """Return offset of local zone from GMT"""
        if time.localtime().tm_isdst and time.daylight:
            return time.altzone
        else:
            return time.timezone

    def is_running(self):
        props = self.get_props()
        state = props['State']
        return state['Running'] if 'Running' in state else False

    def is_restarting(self):
        props = self.get_props()
        state = props['State']
        return state['Restarting'] if 'Restarting' in state else False

    def time_started(self):
        props = self.get_props()
        return APIContainer.parse_iso_time(props['State']['StartedAt'])

    def time_finished(self):
        props = self.get_props()
        return APIContainer.parse_iso_time(props['State']['FinishedAt'])

    def time_created(self):
        props = self.get_props()
        return APIContainer.parse_iso_time(props['Created'])

    def stop(self):
        APIContainer.log_info("Stopping " + self.debug_str())
        self.refresh()
        if self.is_running():
            APIContainer.DCKR.stop(self.dockid, timeout=5)
            self.refresh()
            APIContainer.log_info("Stopped " + self.debug_str())
        else:
            APIContainer.log_info("Already stopped or restarting" + self.debug_str())

    @staticmethod
    def register_api_container(api_name, container_id):
        clist = APIContainer.API_CONTAINERS[api_name] if api_name in APIContainer.API_CONTAINERS else []
        clist.append(container_id)
        APIContainer.API_CONTAINERS[api_name] = clist
        if api_name not in APIContainer.DESIRED_CONTAINER_COUNTS:
            APIContainer.DESIRED_CONTAINER_COUNTS[api_name] = 1
        APIContainer.log_info("Registered " + container_id)

    @staticmethod
    def deregister_api_container(api_name, container_id):
        clist = APIContainer.API_CONTAINERS[api_name] if api_name in APIContainer.API_CONTAINERS else []
        if container_id in clist:
            clist.remove(container_id)
        APIContainer.API_CONTAINERS[api_name] = clist
        APIContainer.log_info("Deregistered " + container_id)

    def start(self, api_name):
        self.refresh()
        APIContainer.log_info("Starting " + self.debug_str())
        if self.is_running() or self.is_restarting():
            APIContainer.log_info("Already started " + self.debug_str())
            return

        APIContainer.DCKR.start(self.dockid, port_bindings=APIContainer.CONTAINER_PORT_BINDINGS)
        self.refresh()
        APIContainer.log_info("Started " + self.debug_str())
        APIContainer.register_api_container(api_name, self.get_name())

    def restart(self):
        self.refresh()
        APIContainer.log_info("Restarting " + self.debug_str())
        APIContainer.DCKR.restart(self.dockid, timeout=5)
        self.refresh()
        APIContainer.log_info("Restarted " + self.debug_str())

    def kill(self):
        APIContainer.log_info("Killing " + self.debug_str())
        APIContainer.DCKR.kill(self.dockid)
        self.refresh()
        APIContainer.log_info("Killed " + self.debug_str())

    def delete(self):
        APIContainer.log_info("Deleting " + self.debug_str())
        self.refresh()
        if self.is_running() or self.is_restarting():
            self.kill()

        APIContainer.DCKR.remove_container(self.dockid)
        APIContainer.log_info("Deleted " + self.debug_str())
        APIContainer.deregister_api_container(self.get_api_name(), self.get_name())