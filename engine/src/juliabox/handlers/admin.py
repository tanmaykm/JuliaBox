from datetime import datetime, timedelta

import isodate
import re

from juliabox.cloud import Compute
from juliabox.jbox_util import JBoxCfg
from handler_base import JBoxHandler
from juliabox.interactive import SessContainer
from juliabox.jbox_tasks import JBoxAsyncJob
from juliabox.db import JBoxUserV2, JBoxDynConfig, JBPluginDB, JBoxSessionProps, JBoxInstanceProps
from juliabox.api import APIContainer


class AdminHandler(JBoxHandler):
    def get(self):
        sessname = self.get_session_id()
        user_id = self.get_user_id()
        if (sessname is None) or (user_id is None):
            self.send_error()
            return

        user = JBoxUserV2(user_id)
        is_admin = sessname in JBoxCfg.get("admin_sessnames", [])
        manage_containers = is_admin or user.has_role(JBoxUserV2.ROLE_MANAGE_CONTAINERS)
        show_report = is_admin or user.has_role(JBoxUserV2.ROLE_ACCESS_STATS)
        cont = SessContainer.get_by_name(sessname)

        if cont is None:
            self.send_error()
            return

        if self.handle_if_logout(cont):
            return
        if self.handle_if_stats(is_admin or show_report):
            return
        if self.handle_if_show_cfg(is_admin):
            return
        if self.handle_if_instance_info(is_admin):
            return
        if self.handle_if_open_port(sessname, user_id):
            return

        juliaboxver, _upgrade_available = self.get_upgrade_available(cont)

        expire = JBoxCfg.get('interactive.expire')
        d = dict(
            manage_containers=manage_containers,
            show_report=show_report,
            sessname=sessname,
            user_id=user_id,
            created=isodate.datetime_isoformat(cont.time_created()),
            started=isodate.datetime_isoformat(cont.time_started()),
            allowed_till=isodate.datetime_isoformat((cont.time_started() + timedelta(seconds=expire))),
            mem=cont.get_memory_allocated(),
            cpu=cont.get_cpu_allocated(),
            disk=cont.get_disk_allocated(),
            expire=expire,
            juliaboxver=juliaboxver
        )

        self.rendertpl("ipnbadmin.tpl", d=d)

    def handle_if_show_cfg(self, is_allowed):
        show_cfg = self.get_argument('show_cfg', None)
        if show_cfg is None:
            return False
        if not is_allowed:
            AdminHandler.log_error("Show config not allowed for user")
            response = {'code': -1, 'data': 'You do not have permissions to view these stats'}
        else:
            response = {'code': 0, 'data': JBoxCfg.nv}
        self.write(response)
        return True

    def handle_if_open_port(self, sessname, user_id):
        port = self.get_argument('open_port', None)
        if port is None:
            return False

        portname = self.get_argument('port_name', "", strip=True)
        if re.match(r"^[a-zA-Z0-9]{1,20}$", portname) is None:
            response = {'code': -1, 'data': 'Port name must be alpha numeric only.'}
        elif portname in ['shell', 'nb', 'file']:
            response = {'code': -1, 'data': 'Port names "shell", "nb" and "file" are reserved for use by JuliaBox.'}
        else:
            port = int(port)
            if port < 8050 or port > 8052:
                response = {'code': -1, 'data': 'Only ports in the range 8050-8052 can be used.'}
            else:
                cont = SessContainer.get_by_name(sessname)
                hostport = cont._get_host_ports([port])[0]
                self.set_container_ports({
                    portname: hostport
                })
                response = {'code': 0, 'data': ''}
        self.write(response)
        return True

    def handle_if_logout(self, cont):
        logout = self.get_argument('logout', False)
        if logout == 'me':
            SessContainer.invalidate_container(cont.get_name())
            JBoxAsyncJob.async_backup_and_cleanup(cont.dockid)
            response = {'code': 0, 'data': ''}
            self.write(response)
            return True
        return False

    def handle_if_instance_info(self, is_allowed):
        stats = self.get_argument('instance_info', None)
        if stats is None:
            return False

        if not is_allowed:
            AdminHandler.log_error("Show instance info not allowed for user")
            response = {'code': -1, 'data': 'You do not have permissions to view these stats'}
        else:
            try:
                if stats == 'load':
                    result = {}
                    # get cluster loads
                    average_load = Compute.get_cluster_average_stats('Load')
                    if average_load is not None:
                        result['Average Load'] = average_load

                    machine_loads = Compute.get_cluster_stats('Load')
                    if machine_loads is not None:
                        for n, v in machine_loads.iteritems():
                            result['Instance ' + n] = v
                elif stats == 'sessions':
                    result = JBoxSessionProps.get_active_sessions()
                elif stats == 'apis':
                    result = JBoxInstanceProps.get_instance_status()
                else:
                    raise Exception("unknown command %s" % (stats,))

                response = {'code': 0, 'data': result}
            except:
                AdminHandler.log_error("exception while getting stats")
                AdminHandler._get_logger().exception("exception while getting stats")
                response = {'code': -1, 'data': 'error getting stats'}

        self.write(response)
        return True

    @staticmethod
    def get_session_stats():
        plugin = JBPluginDB.jbox_get_plugin(JBPluginDB.JBP_USAGE_ACCOUNTING)
        if plugin is None:
            return None

        today = datetime.now()
        week_dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
        today_dates = [today]
        stats = {
            'day': plugin.get_stats(today_dates),
            'week': plugin.get_stats(week_dates)
        }
        return stats

    def handle_if_stats(self, is_allowed):
        stats = self.get_argument('stats', None)
        if stats is None:
            return False

        if not is_allowed:
            AdminHandler.log_error("Show stats not allowed for user")
            response = {'code': -1, 'data': 'You do not have permissions to view these stats'}
        else:
            try:
                if stats == 'stat_sessions':
                    stats = self.get_session_stats()
                else:
                    stats = JBoxDynConfig.get_stat(Compute.get_install_id(), stats)
                response = {'code': 0, 'data': stats} if stats is not None else {'code': 1, 'data': {}}
            except:
                AdminHandler.log_error("exception while getting stats")
                AdminHandler._get_logger().exception("exception while getting stats")
                response = {'code': -1, 'data': 'error getting stats'}

        self.write(response)
        return True

    @staticmethod
    def get_upgrade_available(cont):
        cont_images = cont.get_image_names()
        juliaboxver = cont_images[0]
        if (SessContainer.DCKR_IMAGE in cont_images) or ((SessContainer.DCKR_IMAGE + ':latest') in cont_images):
            upgrade_available = None
        else:
            upgrade_available = SessContainer.DCKR_IMAGE
            if ':' not in upgrade_available:
                upgrade_available += ':latest'
        return juliaboxver, upgrade_available
