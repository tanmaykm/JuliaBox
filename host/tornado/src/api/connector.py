import zmq
import json
from datetime import timedelta
from zmq.eventloop import ioloop, zmqstream

from utils.jbox_util import LoggerMixin
from queue import APIQueue


class APIConnector(LoggerMixin):
    ASYNC_APIS = {}
    DEFAULT_TIMEOUT = timedelta(seconds=30)
    MAX_CONNS = 2
    CMD_TERMINATE = ":terminate"

    def __init__(self, api_name):
        self.queue = APIQueue.get_queue(api_name)
        ctx = zmq.Context.instance()
        self.api_name = api_name
        self.sock = ctx.socket(zmq.REQ)
        self.sock.connect(self.queue.get_endpoint_in())
        self.has_errors = False
        self.timeout_callback = None
        self.timeout = self.queue.get_timeout()
        if self.timeout is None:
            self.timeout = APIConnector.DEFAULT_TIMEOUT

        if api_name in APIConnector.ASYNC_APIS:
            APIConnector.ASYNC_APIS[api_name].append(self)
        else:
            APIConnector.ASYNC_APIS[api_name] = [self]

        self.log_debug("Created " + self.debug_str())

    def debug_str(self):
        return "APIConnector %s. dflt timeout:%s" % (self.api_name, str(self.timeout))

    @staticmethod
    def _get_async_api(api_name):
        if not ((api_name in APIConnector.ASYNC_APIS) and (len(APIConnector.ASYNC_APIS[api_name]) > 0)):
            APIConnector(api_name)
        return APIConnector.ASYNC_APIS[api_name].pop()

    def _release(self):
        self.queue.incr_outstanding(-1)
        cache = APIConnector.ASYNC_APIS[self.api_name]
        if not self.has_errors and (len(cache) < APIConnector.MAX_CONNS):
            cache.append(self)

    def _send_recv(self, send_data, on_recv, on_timeout, timeout=None):
        stream = zmqstream.ZMQStream(self.sock)
        loop = ioloop.IOLoop.instance()
        if timeout is None:
            timeout = self.timeout

        def _on_timeout():
            APIConnector.log_debug("timed out : " + self.debug_str())
            self.has_errors = True
            self.timeout_callback = None
            stream.stop_on_recv()
            stream.close()
            self._release()
            if on_timeout is not None:
                on_timeout()

        def _on_recv(msg):
            APIConnector.log_debug("message received : " + self.debug_str())
            if self.timeout_callback is not None:
                loop.remove_timeout(self.timeout_callback)
                self.timeout_callback = None
            stream.stop_on_recv()
            self._release()
            if on_recv is not None:
                on_recv(msg)

        self.log_debug(self.debug_str() + ". making call with timeout: " + str(timeout))
        self.timeout_callback = loop.add_timeout(timeout, _on_timeout)
        stream.on_recv(_on_recv)
        self.queue.incr_outstanding(1)
        self.sock.send(send_data)

    @staticmethod
    def send_recv(api_name, cmd, args=None, vargs=None, on_recv=None, on_timeout=None, timeout=None):
        send_data = APIConnector.make_req(cmd, args=args, vargs=vargs)
        api = APIConnector._get_async_api(api_name)
        APIConnector.log_debug(api.debug_str() + ". calling " + cmd)
        api._send_recv(send_data, on_recv, on_timeout, timeout)

    @staticmethod
    def send_terminate_msg(api_name):
        APIConnector.send_recv(api_name, APIConnector.CMD_TERMINATE)

    @staticmethod
    def make_req(cmd, args=None, vargs=None):
        req = {'cmd': cmd}
        if (args is not None) and (len(args) > 0):
            req['args'] = args
        if (vargs is not None) and (len(vargs) > 0):
            req['vargs'] = vargs

        return json.dumps(req)