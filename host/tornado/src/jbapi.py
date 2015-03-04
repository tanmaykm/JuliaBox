#! /usr/bin/env python

import random
import string

import tornado.ioloop
import tornado.web
import tornado.auth
import docker

from zmq.eventloop import ioloop

from utils.jbox_util import read_api_config, LoggerMixin
from cloud.aws import CloudHost
import db
from handlers import JBoxHandler, APIServer
from api.container import APIContainer


class JBApi(LoggerMixin):
    cfg = None

    def __init__(self):
        dckr = docker.Client()
        cfg = JBApi.cfg = read_api_config()
        cloud_cfg = cfg['cloud_host']

        LoggerMixin.setup_logger(level=cfg['root_log_level'])
        LoggerMixin.DEFAULT_LEVEL = cfg['jbox_log_level']

        JBoxHandler.configure(cfg)
        db.configure_db(cfg)

        CloudHost.configure(has_s3=cloud_cfg['s3'],
                            has_dynamodb=cloud_cfg['dynamodb'],
                            has_cloudwatch=cloud_cfg['cloudwatch'],
                            has_autoscale=cloud_cfg['autoscale'],
                            has_route53=cloud_cfg['route53'],
                            has_ebs=cloud_cfg['ebs'],
                            has_ses=cloud_cfg['ses'],
                            scale_up_at_load=cloud_cfg['scale_up_at_load'],
                            scale_up_policy=cloud_cfg['scale_up_policy'],
                            autoscale_group=cloud_cfg['autoscale_group'],
                            route53_domain=cloud_cfg['route53_domain'],
                            region=cloud_cfg['region'],
                            install_id=cloud_cfg['install_id'])

        APIContainer.configure(dckr, cfg['docker_image'], cfg['mem_limit'], cfg['cpu_limit'],
                               cfg['numlocalmax'], cfg['async_job_ports'])

        self.application = tornado.web.Application([
            (r"/api/.*", APIServer)
        ])
        self.application.settings["cookie_secret"] = self.get_cookie_secret()
        self.application.listen(cfg["port"])

        self.ioloop = ioloop.IOLoop.instance()

        # run container maintainence every 5 minutes
        run_interval = 5 * 60 * 1000
        self.log_info("Container maintenance every " + str(run_interval / (60 * 1000)) + " minutes")
        self.ct = ioloop.PeriodicCallback(JBApi.do_housekeeping, run_interval, self.ioloop)

    @staticmethod
    def get_cookie_secret():
        secret = []
        secret_chars = string.ascii_uppercase + string.digits
        while len(secret) < 32:
            secret.append(random.choice(secret_chars))
        return ''.join(secret)

    def run(self):
        APIContainer.publish_container_stats()
        APIContainer.refresh_container_list()
        self.ct.start()
        self.ioloop.start()

    @staticmethod
    def do_housekeeping():
        APIContainer.maintain()
        if JBApi.cfg['cloud_host']['scale_down'] and (APIContainer.num_active() == 0) and \
                (APIContainer.num_stopped() == 0) and CloudHost.can_terminate(False):
            JBApi.log_info("terminating to scale down")
            CloudHost.terminate_instance()


if __name__ == "__main__":
    ioloop.install()
    JBApi().run()