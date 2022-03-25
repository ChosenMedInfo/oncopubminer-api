# -*- coding: utf-8 -*-
# @Time : 2021/10/19 13:30
# @File : aspcheduler_job.py
# @Project : OncoPubMinerAPI
from config import Config
from model import PubMed
from PubMiner import db, scheduler


class AspConfig(object):
    JOBS = [
        {
            'id': 'auto_update',
            'func': 'aspcheduler_job:update_pub_med_base',
            'trigger': 'interval',
            'seconds': 2*60
        }
    ]

    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "Asia/Shanghai"


def update_pub_med_base():
    with scheduler.app.app_context():
        is_cancer_pubs = db.session.query(PubMed.id).filter(PubMed.is_cancer == 1).all()
    Config.cancer_pubmed_ids = {is_cancer_pub[0] for is_cancer_pub in is_cancer_pubs}
    with open(Config.is_cancer_pub_path, 'w', encoding='utf-8') as f:
        f.write('|'.join([str(pub_id) for pub_id in Config.cancer_pubmed_ids]))


"""
app.config.from_object(AspConfig())

scheduler = APScheduler()
# it is also possible to enable the API directly
# scheduler.api_enabled = True
scheduler.init_app(app)
scheduler.start()
"""
