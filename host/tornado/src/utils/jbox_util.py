import os
import sys
import time
import errno
import hashlib
import math
import logging

import isodate


def parse_iso_time(tm):
    if tm is not None:
        tm = isodate.parse_datetime(tm)
    return tm


def retry(tries, delay=1, backoff=2):
    """Retries a function or method until it returns True.

    delay sets the initial delay in seconds, and backoff sets the factor by which
    the delay should lengthen after each failure. backoff must be greater than 1,
    or else it isn't really a backoff. tries must be at least 0, and delay
    greater than 0.

    https://wiki.python.org/moin/PythonDecoratorLibrary#Retry"""

    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")

    tries = math.floor(tries)
    if tries < 0:
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay  # make mutable

            rv = f(*args, **kwargs)  # first attempt
            while mtries > 0:
                if rv is True:  # Done on success
                    return True

                mtries -= 1      # consume an attempt
                time.sleep(mdelay)  # wait...
                mdelay *= backoff  # make future wait longer

                rv = f(*args, **kwargs)  # Try again

            return False  # Ran out of tries :-(

        return f_retry  # true decorator -> decorated function
    return deco_retry  # @retry(arg[, ...]) -> true decorator


def esc_sessname(s):
    if s is None:
        return s
    return s.replace("@", "_at_").replace(".", "_")


def get_user_name(email):
    return email.split('@')[0]


def unique_sessname(s):
    if s is None:
        return None
    name = esc_sessname(s.split('@')[0])
    hashdigest = hashlib.sha1(s).hexdigest()
    return '_'.join([name, hashdigest])


NEXT_CONTAINER_ID = 1
CONTAINER_NAME_SEP = '_'


def unique_container_name(api_name):
    global NEXT_CONTAINER_ID
    nid = str(NEXT_CONTAINER_ID) + CONTAINER_NAME_SEP + str(time.time())
    if NEXT_CONTAINER_ID >= sys.maxint:
        NEXT_CONTAINER_ID = 1
    else:
        NEXT_CONTAINER_ID += 1

    return continer_name_prefix(api_name) + hashlib.sha1(nid).hexdigest()


def continer_name_prefix(api_name):
    return 'api' + CONTAINER_NAME_SEP + api_name + CONTAINER_NAME_SEP


def get_api_name_from_container_name(container_name):
    parts = container_name.split(CONTAINER_NAME_SEP)
    if (len(parts) >= 3) and (parts[0] == 'api') and (len(parts[-1]) == 32):
        parts.pop(0)
        parts.pop()
        return CONTAINER_NAME_SEP.join(parts)
    return None


def _read_config(master_cfg, user_cfg):
    with open(master_cfg) as f:
        cfg = eval(f.read())

    def _update_config(base_cfg, add_cfg):
        for n, v in add_cfg.iteritems():
            if (n in base_cfg) and isinstance(base_cfg[n], dict):
                _update_config(base_cfg[n], v)
            else:
                base_cfg[n] = v

    if os.path.isfile(user_cfg):
        with open(user_cfg) as f:
            ucfg = eval(f.read())
        _update_config(cfg, ucfg)

    return cfg


def read_api_config():
    return _read_config("conf/jbapi_tornado.conf", "conf/jbox.user")


def read_config():
    cfg = _read_config("conf/tornado.conf", "conf/jbox.user")

    cfg["admin_sessnames"] = []
    for ad in cfg["admin_users"]:
        cfg["admin_sessnames"].append(unique_sessname(ad))

    cfg["protected_docknames"] = []
    for ps in cfg["protected_sessions"]:
        cfg["protected_docknames"].append("/" + unique_sessname(ps))

    return cfg


def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def _apply_to_path_element(path, file_fn, dir_fn, link_fn):
    if os.path.islink(path):
        link_fn(path)
    elif os.path.isfile(path):
        file_fn(path)
    elif os.path.isdir(path):
        dir_fn(path)
    else:
        raise Exception("Unknown file type for " + path)


def apply_to_path_elements(path, file_fn, dir_fn, link_fn, include_itself, topdown):
    for root, dirs, files in os.walk(path, topdown=topdown):
        for f in files:
            _apply_to_path_element(os.path.join(root, f), file_fn, dir_fn, link_fn)
        for d in dirs:
            _apply_to_path_element(os.path.join(root, d), file_fn, dir_fn, link_fn)

    if include_itself:
        _apply_to_path_element(path, file_fn, dir_fn, link_fn)


def ensure_writable(path, include_iteslf=False):
    apply_to_path_elements(path, lambda p: os.chmod(p, 0555), lambda p: os.chmod(p, 0777), lambda p: None,
                           include_iteslf, True)


def ensure_delete(path, include_itself=False):
    ensure_writable(path, include_itself)
    apply_to_path_elements(path, lambda p: os.remove(p), lambda p: os.rmdir(p), lambda p: os.remove(p), include_itself,
                           False)


def unquote(s):
    if s is None:
        return s
    s = s.strip()
    if s[0] == '"':
        return s[1:-1]
    else:
        return s


def get_local_interface_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 0))
    return s.getsockname()[0]


class LoggerMixin(object):
    _logger = None
    DEFAULT_LEVEL = logging.INFO

    @staticmethod
    def setup_logger(name=None, level=logging.INFO):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

        # default channel (stdout)
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # add separate channel (stderr) only for errors
        err_ch = logging.StreamHandler(stream=sys.stderr)
        err_ch.setLevel(logging.WARNING)
        err_ch.setFormatter(formatter)
        logger.addHandler(err_ch)

        return logger

    @classmethod
    def _get_logger(cls):
        if cls._logger is None:
            name = cls.__name__
            if (len(cls.__module__) > 0) and (cls.__module__ != '__main__'):
                name = cls.__module__ + '.' + cls.__name__
            cls._logger = LoggerMixin.setup_logger(name, LoggerMixin.DEFAULT_LEVEL)
        return cls._logger

    @classmethod
    def log_info(cls, msg, *args, **kwargs):
        cls._get_logger().info(msg, *args, **kwargs)

    @classmethod
    def log_warn(cls, msg, *args, **kwargs):
        cls._get_logger().warning(msg, *args, **kwargs)

    @classmethod
    def log_error(cls, msg, *args, **kwargs):
        cls._get_logger().error(msg, *args, **kwargs)

    @classmethod
    def log_exception(cls, msg, *args, **kwargs):
        cls._get_logger().exception(msg, *args, **kwargs)

    @classmethod
    def log_critical(cls, msg, *args, **kwargs):
        cls._get_logger().critical(msg, *args, **kwargs)

    @classmethod
    def log_debug(cls, msg, *args, **kwargs):
        cls._get_logger().debug(msg, *args, **kwargs)