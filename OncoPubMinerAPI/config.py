# -*- coding: utf-8 -*-
# @Time : 2021/10/19 14:21
# @File : config.py
# @Project : OncoPubMinerAPI
import logging
import os

# Mysql user
DB_USERNAME = "xxx"
# Mysql password
DB_PASSWORD = "xxx"
# Mysql host
DB_HOST = "xxx"
# Mysql port
DB_PORT = "xxx"
# database name
DB_NAME = "xxx"


class Config:
    # general config
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    dir_output = os.path.join(BASE_DIR, "logs")
    if not os.path.exists(dir_output):
        os.makedirs(dir_output, exist_ok=True)

    SECRET_KEY = "lyy"
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    # white ip list
    white_ips = ['xxx', 'xxx']

    # 数据库
    SQLALCHEMY_DATABASE_URI = f'mysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

    LABEL_DICT = {0: "Gene", 1: "Disease", 2: "Chemical", 3: "Mutation"}
    per_page = 10
    is_cancer_pub_path = os.path.join(BASE_DIR, "logs", 'is_cancer.txt')
    with open(is_cancer_pub_path, 'r', encoding='utf-8') as f:
        cancer_pubmed_ids = {int(pub_id) for pub_id in f.read().strip().split('|') if pub_id}
    LOG_LEVEL = logging.DEBUG

    Entrez_email = "xxx"  # Always tell NCBI who you are
    # OncoPubMinerMonitor项目中PubMiner.settings.default.yml全局配置中upload:local-directory对应的路径
    BioCJsonDirPATH = 'xxx'



class DevelopmentConfig(Config):
    """开发环境下的配置"""
    DEBUG = True
    # 默认日志等级
    LOG_LEVEL = logging.DEBUG


class TestingConfig(Config):
    """单元测试环境下的配置"""
    DEBUG = True
    TESTING = True
    # 默认日志等级
    LOG_LEVEL = logging.DEBUG


class ProductionConfig(Config):
    """生产环境下的配置"""
    DEBUG = False
    LOG_LEVEL = logging.WARNING


# 定义配置字典
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig
}
