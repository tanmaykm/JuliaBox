import time
import zmq
from datetime import timedelta
from zmq.devices.basedevice import ThreadDevice

from db import JBoxAPISpec
from utils.jbox_util import LoggerMixin, get_local_interface_ip
from cloud.aws import CloudHost


class APIQueue(LoggerMixin):
    BUFFER_SZ = 20
    QUEUES = {}

    def __init__(self, api_name):
        self.api_name = api_name
        self.num_outstanding = 0
        self.mean_outstanding = 0
        self.qdev = qdev = ThreadDevice(zmq.QUEUE, zmq.XREP, zmq.XREQ)

        spec = JBoxAPISpec(api_name)
        bind_pfx = "tcp://" + APIQueue.local_ip()

        endpt_in = bind_pfx + str(':') + str(spec.get_endpoint_in())
        endpt_out = bind_pfx + str(':') + str(spec.get_endpoint_out())
        self.endpoints = endpt_in, endpt_out

        timeout_secs = spec.get_timeout_secs()
        self.timeout = timedelta(seconds=timeout_secs) if timeout_secs is not None else None

        self.cmd = spec.get_cmd()
        self.image_name = spec.get_image_name()

        qdev.bind_in(endpt_in)
        qdev.bind_out(endpt_out)

        qdev.setsockopt_in(zmq.SNDHWM, APIQueue.BUFFER_SZ)
        qdev.setsockopt_out(zmq.RCVHWM, APIQueue.BUFFER_SZ)
        qdev.setsockopt_in(zmq.RCVHWM, APIQueue.BUFFER_SZ)
        qdev.setsockopt_out(zmq.SNDHWM, APIQueue.BUFFER_SZ)
        qdev.start()

        APIQueue.QUEUES[api_name] = self
        self.log_debug("Created " + self.debug_str())

    def debug_str(self):
        return "APIQueue %s (%s, %s). outstanding: %g, %g" % (self.api_name, self.get_endpoint_in(),
                                                              self.get_endpoint_out(), self.num_outstanding,
                                                              self.mean_outstanding)

    def get_endpoint_in(self):
        return self.endpoints[0]

    def get_endpoint_out(self):
        return self.endpoints[1]

    def get_timeout(self):
        return self.timeout

    def get_command(self):
        return self.cmd

    def get_image_name(self):
        return self.image_name

    @staticmethod
    def get_queue(api_name, alloc=True):
        if api_name in APIQueue.QUEUES:
            return APIQueue.QUEUES[api_name]
        elif alloc:
            queue = APIQueue(api_name)
            APIQueue.log_debug("Created queue: %s", queue.debug_str())
            return queue
        return None

    @staticmethod
    def allocate_random_endpoints():
        ctx = zmq.Context.instance()
        binder = ctx.socket(zmq.REQ)

        bind_pfx = "tcp://" + APIQueue.local_ip()
        port_in = binder.bind_to_random_port(bind_pfx)
        port_out = binder.bind_to_random_port(bind_pfx)
        binder.close()
        time.sleep(0.25)

        endpoint_in = bind_pfx + str(':') + str(port_in)
        endpoint_out = bind_pfx + str(':') + str(port_out)

        return endpoint_in, endpoint_out

    def incr_outstanding(self, num):
        self.num_outstanding += num
        self.mean_outstanding = (1.0 * self.mean_outstanding + self.num_outstanding) / 2

    @staticmethod
    def local_ip():
        local_ip = CloudHost.instance_local_ip()
        if local_ip is None or local_ip == '127.0.0.1':
            local_ip = get_local_interface_ip()
        return local_ip
