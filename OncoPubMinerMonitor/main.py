# -*- coding: utf-8 -*-
# @Time : 2021/10/24 22:13
# @File : main.py
# @Project : OncoPubMinerMonitor
"""服务启动入口"""
import os

from apscheduler.schedulers.blocking import BlockingScheduler

from pub_miner import Config, pub_run


def main():
    PubMinerLockPath = os.path.join(Config.root_path, Config.PubMinerLockFileName)
    if os.path.exists(PubMinerLockPath):
        os.remove(PubMinerLockPath)
    # 启动定时任务每日3:30/16:30更新
    # BlockingScheduler
    scheduler = BlockingScheduler()
    scheduler.add_job(pub_run, 'cron', second='10', minute='*', hour='*', max_instances=2)
    scheduler.start()


if __name__ == '__main__':
    main()
