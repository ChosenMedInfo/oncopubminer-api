# -*- coding: utf-8 -*-
# @Time : 2021/10/19 11:38
# @File : utils.py
# @Project : OncoPubMinerAPI
import json
import os
import time
import re
import xml.etree.cElementTree as etree
import logging

import pandas as pd
import requests
from flask import jsonify, request
from sqlalchemy import or_, desc, and_
from Bio import Entrez

from model import *
from config import Config


def get_page(page):
    # 判断page参数
    try:
        page = int(page)
    except Exception as e:
        logging.warning(f'{e}')
        page = 1
    return page


def get_limit(per_page):
    # 判断per_page参数
    try:
        per_page = 100 if int(per_page) == 0 else int(per_page)
    except Exception as e:
        logging.warning(f'{e}')
        per_page = Config.per_page
    return per_page


def get_library(query_field):
    """根据输入的字符串获取标准库"""
    query_field = query_field.strip()
    if query_field.startswith('@GE@'):
        libraries = Library.query.filter(and_(Library.label == 0,
                                              Library.identifier == query_field[4:]))
    elif query_field.startswith('@CA@'):
        libraries = Library.query.filter(and_(Library.label == 1,
                                              Library.identifier == query_field[4:]))
    elif query_field.startswith('@DR@'):
        libraries = Library.query.filter(and_(Library.label == 2,
                                              Library.identifier == query_field[4:]))
    else:
        libraries = Library.query.filter(or_(Library.symbol.startswith(query_field),
                                             and_(and_(Library.synonyms.like(f'%|{query_field}%')),
                                                  Library.label.in_([0, 2])),
                                             and_(and_(Library.synonyms.like(f'%{query_field}%')),
                                                  Library.label == 1))).order_by(desc(Library.label))
    return libraries


def get_sorted_library(query_field):
    """根据匹配度排序"""
    query_field = query_field.strip()
    libraries_1 = Library.query.filter(Library.symbol == query_field)
    libraries_2 = Library.query.filter(Library.synonyms.like(f'%|{query_field}|%'))
    libraries_3 = Library.query.filter(Library.symbol.startswith(query_field))
    libraries_4 = Library.query.filter(or_(Library.symbol.like(f'%{query_field}%'),
                                           and_(Library.synonyms.like(f'%|{query_field}%'),
                                                Library.label.in_([1, 2])),
                                           and_(Library.synonyms.like(f'%{query_field}%'),
                                                Library.label == 0)))
    libraries = libraries_1.all()
    for library in libraries_2.all() + libraries_3.all() + libraries_4.all():
        if library not in libraries:
            libraries.append(library)
    return libraries


def get_pub_by_mention(query_field):
    """根据文章涉及词获取PubMed id"""
    query_field = query_field.strip()
    mentions = Mention.query.filter(Mention.mention.startswith(query_field))
    pub_ids = set()
    mention_ids = [mention.id for mention in mentions]
    mention_pubs = MentionPubMed.query.filter(MentionPubMed.mention_id.in_(mention_ids))
    for mention_pub in mention_pubs:
        pubs_ids = {int(pub_id) for pub_id in mention_pub.pubmeds.split('|') if pub_id}
        pub_ids |= pubs_ids
    return pub_ids


def get_pubmed_by_query_field(query_field):
    """通过用户输入的字符串查询PubMed Id"""
    query_field = query_field.strip()
    libraries = get_library(query_field)
    pub_ids = set()
    for library in libraries:
        pub_ids |= get_pubmed_by_library(library)
    return pub_ids


def get_pubmed_by_library(library):
    """通过标准库查询PubMed Id"""
    pub_ids = set()
    library_pubs = LibraryPubMed.query.filter(LibraryPubMed.library_id == library.id)
    for library_pub in library_pubs:
        pubs_ids = library_pub.pubmeds
        if pubs_ids.strip():
            new_pub_ids = {int(pub_id) for pub_id in pubs_ids.strip().split('|')}
        else:
            new_pub_ids = set()
        pub_ids |= new_pub_ids
    return pub_ids


def SelectGetFilename(label):
    timestamp = time.strftime("%Y-%m-%d", time.localtime(time.time()))
    # header 指定列名，index 默认为True，写行名
    if label == 0:
        filename = f'gene{timestamp}.xlsx'
    elif label == 1:
        filename = f'disease{timestamp}.xlsx'
    else:
        filename = f'chemical{timestamp}.xlsx'
    filepath = os.path.join(Config.BASE_DIR, 'static', filename)
    if not os.path.exists(filepath):
        results = db.session.query(Library.symbol, LibraryPubMed.length).filter(Library.label == label).join(
            LibraryPubMed, Library.id == LibraryPubMed.library_id).order_by(desc(LibraryPubMed.length)).all()
        results = pd.DataFrame.from_records(list(results))  # mysql查询的结果为元组，需要转换为列表
        # header 指定列名，index 默认为True，写行名
        results.to_excel(filepath, index=False, header=("symbol", "num"))
    return filename


def PAD_for_document(pub_med):
    """填充/补充 document 第一个段落的infons信息"""
    infons = {}
    impact_factor = db.session.query(Journal.impact_factor).filter(Journal.id == pub_med.journal_id).first()
    cite_cited_num = db.session.query(CiteCitedSimilarPubMed.cite_num, CiteCitedSimilarPubMed.cited_num). \
        filter(CiteCitedSimilarPubMed.pubmed_id == pub_med.id).first()
    # 杂志影响因子，名称，关键词
    if pub_med.pmc_id:
        infons['article_id_pmc'] = pub_med.pmc_id[3:]
    infons['article_id_pmid'] = pub_med.id
    infons['if2020'] = impact_factor[0] if impact_factor and impact_factor[0] != 0.0 else None
    infons['citedNums'] = cite_cited_num[1] if cite_cited_num and cite_cited_num[1] else 0
    infons['refNums'] = cite_cited_num[0] if cite_cited_num and cite_cited_num[0] else 0
    infons['hasAnnotation'] = pub_med.has_annotation
    return infons


def get_document(pub_med, source='pubmed'):
    """
    获取文献BioC Json
    :param pub_med: PubMed object
    :param source: pubmed/pmc
    :return:
    """
    document = {}
    if pub_med:
        if not (source == 'pmc' and pub_med.pmc_id and pub_med.pmc_json_path):
            source = 'pubmed'
            try:
                # PubMed文献id
                pid = pub_med.id
                psd = pub_med.pubmed_json_path
                pmc_second_dir = pub_med.pmc_json_path
                # 文献对应的PubMed文献的路径
                pub_json_path = os.path.join(Config.BioCJsonDirPATH, 'PUBMED', psd[-1], psd, f'{pid}.json')
                # 文献对应的PMC文献的路径
                pmc_json_path = os.path.join(Config.BioCJsonDirPATH, 'PMC', pmc_second_dir[-1], pmc_second_dir,
                                             f'{pub_med.pmc_id}.json') if pmc_second_dir else ''
                json_path = pub_json_path if source == 'pubmed' else pmc_json_path
                # 该文献是否有对应的PMC文献
                hasPMC = True if os.path.exists(pmc_json_path) else False
                if json_path and os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        document = json.load(f)
                    if document:
                        # 获取文献基本信息
                        info_path = os.path.join(Config.BioCJsonDirPATH, 'PUBMED_INFOS', psd[-1], psd, f'{pid}.json')
                        if os.path.exists(info_path):
                            with open(info_path, 'r', encoding='utf-8') as f:
                                infos = json.load(f)
                            document['passages'][0]['infons'].update(infos)
                        document['passages'][0]['infons'].update({"hasPMC": hasPMC})
            except Exception as e:
                return logging.error(f"get document error: {str(e)}")
    if document:
        document['passages'][0]['infons'].update(PAD_for_document(pub_med))
    return document


def get_document_by_pub_ids(pub_ids, page, per_page, count=None):
    """获取根据 PubMed id PubMed BioC 数据"""
    document_list = []
    non_content = []
    for pub_id in pub_ids:
        pub_med = PubMed.query.filter(PubMed.id == pub_id).first()
        document = {}
        if pub_med:
            document = get_document(pub_med)
        if document:
            document_list.append(document)
        else:
            non_content.append({'id': pub_id, 'nocontent': True})

    count = count if count else len(pub_ids)
    data = {
        "code": 200,
        "msg": "Request success",
        "success": True,
        "page": page,
        "next": page + 1 if page * per_page < count else None,
        "count": count,
        "limit": 0 if per_page == 1000 else per_page,
        "data": document_list
    }
    return data


def get_document_by_query_field(pub_ids, page, per_page, is_cancer):
    """获取PubMed BioC 数据"""
    if len(pub_ids) == 0:
        data = {
            "code": 200,
            "msg": "Request success",
            "success": True,
            "page": page,
            "next": None,
            "count": 0,
            "limit": per_page,
            "type": 2,
            "data": []
        }
        return data
    if is_cancer == 'cancer':
        all_pub_ids = pub_ids & Config.cancer_pubmed_ids
        pub_ids = sorted(all_pub_ids, reverse=True)[(page - 1) * per_page:page * per_page]
        pub_med_list = PubMed.query.filter(PubMed.id.in_(pub_ids)) \
            .order_by(desc(PubMed.id)).paginate(1, per_page=per_page, error_out=False)
    else:
        all_pub_ids = sorted(pub_ids, reverse=True)
        pub_ids = all_pub_ids[(page - 1) * per_page:page * per_page]
        pub_med_list = PubMed.query.filter(PubMed.id.in_(pub_ids)) \
            .order_by(desc(PubMed.id)).paginate(1, per_page=per_page, error_out=False)
    count = len(all_pub_ids)
    document_list = []
    for pub_med in pub_med_list.items:
        document = get_document(pub_med)
        if document:
            document_list.append(document)
        else:
            document_list.append({'id': pub_med.id, 'nocontent': True})
    if document_list:
        data = {
            "code": 200,
            "msg": "Request success",
            "success": True,
            "page": page,
            "next": page + 1 if page * per_page < count else None,
            "count": count,
            "limit": per_page,
            "type": 2,
            "data": document_list
        }
    else:
        data = {
            "code": 200,
            "msg": "Request success",
            "success": True,
            "page": page,
            "next": None,
            "count": 0,
            "limit": per_page,
            "type": 2,
            "data": []
        }
    return data


def search_correlation_pub_med(t='cited_by'):
    pm_id = request.args.get("q")
    page = request.args.get("p", 1)
    per_page = request.args.get("l", Config.per_page)
    # 判断page参数
    try:
        page = int(page)
    except Exception as e:
        logging.warning(f'{e}')
        page = 1
    # 判断per_page参数
    try:
        per_page = 100 if int(per_page) == 0 else int(per_page)
    except Exception as e:
        logging.warning(f'{e}')
        per_page = Config.per_page
    if not pm_id:
        return badRequest()
    if t == 'similar':
        correlation = db.session.query(CiteCitedSimilarPubMed.similar). \
            filter(and_(CiteCitedSimilarPubMed.pubmed_id == int(pm_id),
                        CiteCitedSimilarPubMed.timestamp > int(time.time()) - 2592000)).first()
        if not correlation:
            pub_ids, refIds, citedIds = eutilsToXmlSimilarRef(str(pm_id))
            citeCitedSimilar = CiteCitedSimilarPubMed.query.filter_by(pubmed_id=int(pm_id))
            if citeCitedSimilar:
                citeCitedSimilar.update({"cite": '|'.join(refIds), "cited": '|'.join(citedIds),
                                         "cite_num": len(refIds), "cited_num": len(citedIds),
                                         "similar": '|'.join(pub_ids), "timestamp": int(time.time())})
            else:
                citeCitedSimilar = CiteCitedSimilarPubMed(pubmed_id=int(pm_id), cite='|'.join(refIds),
                                                          cited='|'.join(citedIds), cite_num=len(refIds),
                                                          cited_num=len(citedIds), similar='|'.join(pub_ids),
                                                          timestamp=int(time.time()))
                db.session.add(citeCitedSimilar)

            db.session.commit()
        else:
            pub_ids = [int(pid) for pid in correlation[0].split('|') if pid] if correlation and correlation[0] else []
    else:
        if t == 'cited_by':
            correlation = db.session.query(CiteCitedSimilarPubMed.cited). \
                filter(CiteCitedSimilarPubMed.pubmed_id == int(pm_id)).first()
        else:
            correlation = db.session.query(CiteCitedSimilarPubMed.cite). \
                filter(CiteCitedSimilarPubMed.pubmed_id == int(pm_id)).first()
        # 获取相关文献
        pub_ids = [int(pid) for pid in correlation[0].split('|') if pid] if correlation and correlation[0] else []

    if len(pub_ids) == 0:
        data = {
            "code": 200,
            "msg": "Request success",
            "success": True,
            "page": page,
            "next": None,
            "count": 0,
            "limit": per_page,
            "type": 2,
            "data": []
        }
        return jsonify(data)
    data = get_document_by_pub_ids(pub_ids[:per_page], page, per_page, count=len(pub_ids))

    return jsonify(data)


def extract_pub_med_from_remote(query, restart, page, per_page):
    try:
        query_url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?term={query}&' \
                    f'retstart={restart}&retmax=1000&sort='
        resp = requests.get(query_url)
        root = etree.fromstring(resp.text)
        pub_ids = [int(Id.text) for Id in root.findall('.IdList/Id')]
        count = int(root.find('./Count').text)
    except Exception as e:
        return jsonify({"code": 500, "msg": f"PubMed Remote access error: {e}", "success": False, "data": {}})
    document_list = []
    non_content_num = 0
    for pub_id in pub_ids:
        document = get_document(PubMed.query.filter(PubMed.id == pub_id).first())
        if document:
            document_list.append(document)
            if len(document_list) == per_page:
                break
        else:
            non_content_num += 1
    next_restart = restart+per_page+non_content_num
    data = {
        "code": 200,
        "msg": "Request success",
        "success": True,
        "page": page,
        "next": page + 1 if next_restart < count else None,
        "count": count,
        "limit": 0 if per_page == 1000 else per_page,
        "data": document_list,
        "restart": next_restart
    }
    return jsonify(data)


def extract_pub_med_by_id(query, page, per_page):
    if re.search(r'^\d+$', query.replace(" ", "")):
        pub_ids = {int(pm_id) for pm_id in query.split() if re.match(r'^\d+$', pm_id)}
    else:
        pmc_ids = {f"PMC" + re.search(r'\d+', pmc).group() for pmc in query.split() if re.search(r'\d+', pmc)}
        pub_ids = {pub.id for pub in PubMed.query.filter(PubMed.pmc_id.in_(pmc_ids)).all()}
    data = get_document_by_pub_ids(pub_ids, page, per_page)
    return jsonify(data)


def extract_pub_med(by_type='library'):
    try:
        # 获取参数
        is_cancer = request.args.get("t", "cancer")
        remote = request.args.get("m", "local")
        query = request.args.get("q")
        page = request.args.get("p", 1)
        limit = request.args.get("l", Config.per_page)
        # 判断page/limit参数
        page = get_page(page)
        per_page = get_limit(limit)
        if not query:
            return badRequest()
        # 远程访问
        if remote and remote == 'remote':
            restart = int(request.args.get('restart', 0))
            result = extract_pub_med_from_remote(query, restart, page, per_page)
            return result
        # 通过PubMed ID或PMC ID查询
        if re.search(r'^\d+$|PMC\d+', query.replace(" ", "")):
            result = extract_pub_med_by_id(query, page, per_page)
            return result
        else:
            if ' AND ' in query:
                # 并集查询
                query_fields = query.replace(' OR ', ' AND ').split(' AND ')
                pub_ids = set()
                i = 1
                for query_field in query_fields:
                    new_pub_ids = get_pubmed_by_query_field(query_field) if by_type == 'library' else \
                        get_pub_by_mention(query_field)
                    if len(new_pub_ids) == 0:
                        pub_ids = set()
                        break
                    pub_ids = new_pub_ids if i == 1 else pub_ids & new_pub_ids
                    i += 1
            elif ' OR ' in query:
                # 或查询
                query_fields = query.split(' OR ')
                pub_ids = set()
                for query_field in query_fields:
                    new_pub_ids = get_pubmed_by_query_field(query_field) if by_type == 'library' else \
                        get_pub_by_mention(query_field)
                    pub_ids = pub_ids | new_pub_ids
            else:
                # 字符串查询
                if by_type == 'library':
                    libraries = get_library(query.strip())
                    if len(libraries.all()) == 1:
                        pub_ids = get_pubmed_by_library(libraries.first())
                    elif len(libraries.all()) > 1:
                        libraries = get_sorted_library(query.strip())
                        data = {
                            "code": 200,
                            "msg": "Request success",
                            "success": True,
                            "page": page,
                            "next": page,
                            "count": 0,
                            "limit": per_page,
                            "type": 1,
                            "data": [{"symbol": library.symbol,
                                      "identifier": library.identifier,
                                      "synonyms": library.synonyms,
                                      "label": Config.LABEL_DICT[library.label]} for library in libraries]
                        }
                        return jsonify(data)
                    else:
                        pub_ids = set()
                else:
                    query_str = query.strip()
                    pub_ids = get_pub_by_mention(query_str)
            if len(pub_ids) == 0:
                data = {
                    "code": 200,
                    "msg": "Request success",
                    "success": True,
                    "page": page,
                    "next": None,
                    "count": 0,
                    "limit": per_page,
                    "type": 2,
                    "data": []
                }
                return jsonify(data)
            data = get_document_by_query_field(pub_ids, page, per_page, is_cancer)
            return jsonify(data)

    except Exception as e:
        logging.error(f"Request Failed {e}")
        return jsonify({"code": 500, "msg": f"Request Failed {e}", "success": False})


def eutilsToXmlSimilarRef(document_id):
    """调用PubMed远程接口获取相似文献/引用文献/被引用文献的接口"""
    Entrez.email = Config.Entrez_email
    handle = Entrez.elink(db='pubmed', dbfrom='pubmed', cmd='neighbor', id=document_id)
    xml = handle.read()
    xml_data = xml.decode('utf-8') if isinstance(xml, bytes) else xml
    root = etree.fromstring(xml_data)
    LinkSetDbs = root.findall('./LinkSet/LinkSetDb')
    similarIds, refIds, citedIds = [], [], []
    for LinkSetDb in LinkSetDbs:
        link_name = LinkSetDb.find('./LinkName')
        if link_name.text == 'pubmed_pubmed':
            similarIds = [Id.text for Id in LinkSetDb.findall('./Link/Id')
                          if Id.text != str(document_id) and re.search(r'^\d+$', Id.text)]
        elif link_name.text == 'pubmed_pubmed_refs':
            refIds = [Id.text for Id in LinkSetDb.findall('./Link/Id')
                      if Id.text != str(document_id) and re.search(r'^\d+$', Id.text)]
        elif link_name.text == 'pubmed_pubmed_citedin':
            citedIds = [Id.text for Id in LinkSetDb.findall('./Link/Id')
                        if Id.text != str(document_id) and re.search(r'^\d+$', Id.text)]
    return similarIds, refIds, citedIds


def extract_library_symbols(library_type='cancer'):
    try:
        query = request.args.get("q")
        if not query:
            return badRequest()
        if library_type == 'cancer':
            libraries = CancerLibrary.query.filter(or_(CancerLibrary.symbol.like(f'%{query}%'),
                                                       CancerLibrary.synonyms.like(f'%{"|" + query + "|"}%'))).all()
        elif library_type == 'gene':
            libraries = GeneLibrary.query.filter(or_(GeneLibrary.symbol.contains(query),
                                                     GeneLibrary.synonyms.like(f'%{"|" + query + "|"}%'))).all()
        else:
            libraries = ChemLibrary.query.filter(or_(ChemLibrary.symbol.contains(query),
                                                     ChemLibrary.synonyms.like(f'%{"|" + query + "|"}%'))).all()
        data = {
            "code": 200,
            "msg": "Request success",
            "success": True,
            "data": [library.symbol for library in libraries if library.symbol],
        }
        return jsonify(data)
    except Exception as e:
        logging.error(f"Request Failed {e}")
        return jsonify({"code": 500, "msg": f"Request Failed {e}", "success": False})


def badRequest():
    return jsonify({"code": 400, "msg": "Bad Request: Empty term and query_key - nothing todo, "
                                        "The request must carry parameters: q", "success": False})


def date_style_transformation_timestamp(date):
    """不同时间格式字符串转换为时间戳"""
    try:
        if '-' in date:
            input_format_string = "%Y-%m-%d"
        else:
            input_format_string = "%Y/%m/%d"
        time_array = time.strptime(date, input_format_string)
        return int(time.mktime(time_array))
    except Exception as e:
        logging.error(f'date_style_transformation_timestamp error, date {date}, errorInfo: {str(e)}')
        date = time.strftime("%Y-%m-%d", time.localtime(time.time()))
        time_array = time.strptime(date, "%Y-%m-%d")
        return int(time.mktime(time_array))


def get_new_pub_list(pub_id, pub_date, pub_type, pub_title, pub_authors, pub_journal, pub_year, limit, offset):
    """多条件查询"""
    try:
        condition = (NewPub.id > 0)
        if pub_id:
            condition = and_(condition, NewPub.pub_id == pub_id)
        if pub_title:
            print(pub_title)
            condition = and_(condition, NewPub.pub_title == pub_title)
        if pub_date:
            # 将日期字符串转化为时间戳
            pub_date = date_style_transformation_timestamp(pub_date)
            condition = and_(condition, and_(NewPub.pub_date >= pub_date, NewPub.pub_date < pub_date + 24 * 3600))
        if pub_type:
            pub_type = 0 if isinstance(pub_type, str) and pub_type.lower() == 'update' else 1
            condition = and_(condition, NewPub.pub_type == pub_type)
        if pub_journal:
            condition = and_(condition, NewPub.pub_journal == pub_journal)
        if pub_year:
            condition = and_(condition, NewPub.pub_year == pub_year)
        if pub_authors:
            condition = and_(condition, NewPub.pub_authors.like(f'%{pub_authors}%'))

        new_pubs = NewPub.query.filter(condition)
        count = new_pubs.count()
        new_pubs = new_pubs.order_by(NewPub.pub_date.desc()).limit(limit).offset(offset).all()
        return new_pubs, count
    except Exception as e:
        logging.error(f"get_new_pub_list exception: {str(e)}")
    return (), 0
