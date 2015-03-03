import json
from jbox_util import unquote
from handlers.handler_base import JBoxHandler
from db import JBoxUserV2, JBoxAPISpec


class APIManagement(JBoxHandler):
    def get(self):
        self.log_debug("API management handler got GET request")
        return self.post()

    def post(self):
        self.log_debug("API management handler got POST request")
        sessname = unquote(self.get_cookie("sessname"))
        jbox_cookie = self.get_session_cookie()

        if (None == sessname) or (len(sessname) == 0) or (None == jbox_cookie):
            self.log_info("Read only mode. sessname[%r] or cookie[%r]", sessname, jbox_cookie)
            manage_mode = False
            user_id = None
            is_admin = False
        else:
            user_id = jbox_cookie['u']
            user = JBoxUserV2(user_id)
            is_admin = sessname in self.config("admin_sessnames", []) or user.has_role(JBoxUserV2.ROLE_SUPER)
            manage_mode = True
            self.log_info("API manage mode. user_id[%s] is_admin[%r]", user_id, is_admin)

        if self.handle_get_api_info(user_id, is_admin):
            return
        if manage_mode:
            if self.handle_create_api(user_id, is_admin):
                return

        self.log_error("no handlers found")
        # only AJAX requests responded to
        self.send_error()

    def handle_get_api_info(self, user_id, is_admin):
        mode = self.get_argument('mode', None)
        if (mode is None) or (mode != "info"):
            return False

        params = self.get_argument('params', None)
        params = json.loads(params)

        api_name = params['api_name'] if 'api_name' in params else None

        if user_id is None:
            publisher = None
        else:
            publisher = params['publisher'] if 'publisher' in params else None

        apiinfo = JBoxAPISpec.get_api_info(publisher, api_name)
        response = {'code': 0, 'data': apiinfo}
        self.write(response)
        return True

    def handle_create_api(self, user_id, is_admin):
        mode = self.get_argument('mode', None)
        if (mode is None) or (mode != "create"):
            return False

        if user_id is None:
            response = {'code': -1, 'data': 'could not determine creator user_id'}
            self.write(response)
            return True

        params = self.get_argument('params', None)
        params = json.loads(params)

        if 'publisher' not in params:
            params['publisher'] = user_id

        for mandatory in ['api_name', 'cmd', 'endpt_in', 'endpt_out', 'methods', 'publisher']:
            if mandatory not in params:
                response = {'code': -1, 'data': 'manadatory attributes missing'}
                self.write(response)
                return True

        timeout_secs = params['timeout_secs'] if 'timeout_secs' in params else None
        image_name = params['image_name'] if 'image_name' in params else None

        JBoxAPISpec.set_api_info(params['api_name'],
                                 cmd=params['cmd'],
                                 endpt_in=params['endpt_in'],
                                 endpt_out=params['endpt_out'],
                                 image_name=image_name,
                                 methods=params['methods'],
                                 publisher=params['publisher'],
                                 timeout_secs=timeout_secs)

        response = {'code': 0, 'data': ''}
        self.write(response)
        return True