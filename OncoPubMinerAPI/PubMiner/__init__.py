# -*- coding: utf-8 -*-
# @Time : 2021/10/19 14:23
# @File : __init__.py.py
# @Project :OncoPubMinerAPI
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.contrib.fixers import ProxyFix
from flask_apscheduler import APScheduler

from config import config, Config

# 配置数据库
db = SQLAlchemy()
scheduler = APScheduler()


def setup_log(config_name):
    """配置日志"""
    # 设置日志的记录等级
    logging.basicConfig(level=config[config_name].LOG_LEVEL)  # 调试debug级
    # 创建日志记录器，指明日志保存的路径、每个日志文件的最大大小、保存的日志文件个数上限
    file_log_handler = RotatingFileHandler("logs/log", maxBytes=1024 * 1024 * 100, backupCount=10)
    # 创建日志记录的格式 日志等级 输入日志信息的文件名 行数 日志信息
    formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')
    # 为刚创建的日志记录器设置日志记录格式
    file_log_handler.setFormatter(formatter)
    # 为全局的日志工具对象（flask app使用的）添加日志记录器
    logging.getLogger().addHandler(file_log_handler)


def request_filter():
    ip_str = get_remote_address()[0]
    return ip_str in Config.white_ips


def create_app(config_name):
    """通过传入不同的配置名字，初始化其对应配置的应用实例"""
    # 配置项目日志
    setup_log(config_name)
    app = Flask(__name__)

    # 配置
    app.config.from_object(config[config_name])

    # 配置数据库
    db.init_app(app)
    # 开启csrf保护
    CSRFProtect(app)

    CORS(app, resources={r"/*": {"origins": "*"}})

    return app
