import tornado.web

from handlers.handler_base import JBoxHandler
from api.container import APIContainer
from api.connector import APIConnector


class APIServer(JBoxHandler):
    def get(self):
        self.log_debug("API server handler got GET request")
        return self.post()

    @tornado.web.asynchronous
    def post(self):
        self.log_debug("API server handler got POST request")
        uri = self.request.uri
        self.log_debug("called with uri: " + uri)

        comps = filter(bool, uri.split('/'))
        if (len(comps) < 3) or (comps[0] != 'api'):
            self.send_error(status_code=404)
            return

        api_name = comps[1]
        cmd = comps[2]
        args = comps[3:]
        vargs = self.request.arguments

        self.log_debug("calling service:" + api_name +
                       ". cmd:" + cmd +
                       " num args:" + str(len(args)) +
                       " num vargs:" + str(len(vargs)))
        APIContainer.ensure_container_available(api_name)
        APIConnector.send_recv(api_name, cmd, args=args, vargs=vargs, on_recv=self.on_recv, on_timeout=self.on_timeout)

    def on_recv(self, msg):
        self.log_debug("responding for " + self.request.uri)
        self.log_info("response: [" + str(msg) + "]")
        self.write(str(msg))
        self.finish()

    def on_timeout(self):
        self.log_error("timed out serving " + self.request.uri)
        self.send_error(status_code=408)
    #
    # def is_valid_api(self, api_name):
    #     return api_name in self.config("api_names", [])
