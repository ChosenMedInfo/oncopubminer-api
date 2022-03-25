# -*- coding: utf-8 -*-
# @Time : 2021/8/2 10:51
# @File : config.py
# @Project : OncoPubMinerMonitor
import logging
import os


def get_logger(filename):
    """Return a logger instance that writes in filename

    Args:
        filename: (string) path to log.txt

    Returns:
        logger: (instance of logger)

    """
    logger = logging.getLogger('logger')
    logger.setLevel(logging.DEBUG)
    logging.basicConfig(format='%(message)s', level=logging.DEBUG)
    handler = logging.FileHandler(filename)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s: %(message)s'))
    logging.getLogger().addHandler(handler)

    return logger


class Config:
    # general config
    # 项目根路径
    root_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    LogPath = os.path.join(BASE_DIR, "logs", "result.log")

    Entrez_email = "xxx"  # Always tell NCBI who you are
    # mysql username
    DB_USERNAME = "xxx"
    # mysql password
    DB_PASSWORD = "xxx"
    # mysql host
    DB_HOST = "xxx"
    # mysql port
    DB_PORT = 3306
    # database name
    DB_NAME = "xxx"
    PubMinerLockFileName = '.PubMiner_lock'
    # log
    Logger = get_logger(LogPath)

    # XML elements to ignore the contents of 'table', 'table-wrap',
    ignoreList = ['ref-list', 'xref', 'disp-formula', 'inline-formula', 'bio', 'graphic',
                  'media', 'tex-math', 'mml:math', 'object-id', 'ext-link', 'string', 'uri']

    # XML elements to separate text between
    separationList = ['title', 'p', 'sec', 'break', 'def-item', 'list-item', 'table', 'table-wrap', 'ack', 'caption']
