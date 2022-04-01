# -*- coding: utf-8 -*-
# @Time : 2021/8/22 10:39
# @File : update_database.py
# @Project : OncoPubMinerMonitor
import math
import os
import shutil
import time
from ast import literal_eval

import bioc

import pub_miner


def makeDirs(resource):
    """
    生成指定目录
    :param resource: PUBMED/PMC
    :return:
    """
    global_setting = pub_miner.get_global_settings(True)
    # 最终NER生成的BioC的存放路径
    BioCPath = os.path.expanduser(global_setting["upload"]["local-directory"])
    resourceBioCPath = os.path.join(BioCPath, resource)
    if not os.path.isdir(resourceBioCPath):
        os.makedirs(resourceBioCPath)

    resourceInfoDir = 'PUBMED_INFOS'
    resourceBioCInfoPath = os.path.join(BioCPath, resourceInfoDir)
    if resource == 'PUBMED':
        if not os.path.isdir(resourceBioCInfoPath):
            os.makedirs(resourceBioCInfoPath)
    return resourceBioCPath, resourceBioCInfoPath


def update_pub_med_info(PubMedBioCFilePath, deleteBioC=True):
    """PubMed基本信息上传Mysql数据库"""
    resourceBioCPath, resourceBioCInfoPath = makeDirs('PUBMED')
    # 获取数据库中所有杂志名和杂志id
    db = pub_miner.PubMinerDB()
    journals = {journal[1].lower(): journal[0] for journal in
                db.search_table_data('journal', fields=['id', 'name'], count=-1) if journal and journal[1]}
    db.close()
    # 文献被引用信息
    cited_by_infos = {}
    # 文献批量插入和更新列表
    batch_insert_pubs, batch_update_pubs, batch_insert_new_pubs, batch_update_new_pubs = [], [], [], []
    # 文献引用批量插入和更新列表
    batch_insert_ref_pubs, batch_update_ref_pubs = [], []
    # 遍历BioC文件，解析其中的每一篇文献的基本信息
    for document in bioc.BioCXMLDocumentReader(PubMedBioCFilePath):
        # 文献PubMed id
        pid = document.id
        # 文献
        document_infos = document.passages[0].infons
        # 文献对应的PMC id
        pmc_id = document_infos.get('article_id_pmc', '')
        # PMC文献的存储文件夹
        pmc_second_dir = document_infos.get('pmc_second_dir', '')
        # PubMed文献对应的文件夹
        psd = document_infos.get('psd', '')
        # 文献标题
        pub_title = document.passages[0].text
        # 如果标题过长截取前2048个字符（为了节省数据库存储空间）
        pub_title = pub_title[:2048] if pub_title else ''
        # 文献对应的doi
        doi = document_infos.get('article_id_doi', '')
        # 文献对应的杂志全称
        journal = document_infos.get('journal_full_name', '')
        # 文献对应的杂志缩写
        journal_iso = document_infos.get('journal_name', '')
        # 文献是否有摘要信息
        has_abstract = document_infos.get('has_abstract', 0)
        # 文献是否已经存在
        is_new = int(document_infos.get('is_new', 1))
        # 年份
        year = document_infos.get('year', '')
        # 文献关键词
        pub_keywords = '|'.join(literal_eval(document_infos.get('keywords', '[]')))
        # 文献作者
        pub_authors = '|'.join(literal_eval(document_infos.get('authors', '[]')))
        # 文献应用列表
        refs = literal_eval(document_infos.get('refIds', '[]'))
        # 计算当前PubMed数据的存储文件夹
        if not psd:
            psd = str(math.ceil(int(pid) / 10000))

        # 获取杂志id
        if journal.lower() in journals:
            journal_id = journals[journal.lower()]
        else:
            db = pub_miner.PubMinerDB()
            db.insert_journal(journal, journal_iso)
            res = db.search_journal(journal)
            if res:
                journal_id = res[0]
            else:
                journal_id = 1
            journals[journal.lower()] = journal_id
            db.close()

        new_pub_data = [pub_title, pub_authors, journal_iso or journal, year, str(pid)]
        pub_data = [pmc_id, doi, journal_id, year, pub_keywords, has_abstract, psd, pmc_second_dir, int(pid)]
        ref_data = ['|'.join(set(refs)), len(set(refs)), pid]
        # 在数据表中插入或者更新一条数据
        if is_new:
            dir_path = os.path.join(resourceBioCPath, f'{psd[-1]}/{psd}')
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            BioCDocJsonFilePath = os.path.join(resourceBioCPath, f'{psd[-1]}/{psd}/{pid}.json')
            pub_miner.save_json_data(BioCDocJsonFilePath, bioc.toJSON(document))
            batch_insert_pubs.append(pub_data)
            batch_insert_new_pubs.append([int(time.time()), '1'] + new_pub_data)
            batch_insert_ref_pubs.append(ref_data)
        else:
            batch_update_pubs.append(pub_data)
            batch_update_new_pubs.append([int(time.time()), '0'] + new_pub_data)
            batch_update_ref_pubs.append(ref_data)
        # 保存PubMed基本信息
        PubMedInfoJsonFilePath = os.path.join(resourceBioCInfoPath, f'{psd[-1]}/{psd}/{pid}.json')
        document_infos['keywords'] = literal_eval(document_infos.get('keywords', '[]'))
        document_infos['authors'] = literal_eval(document_infos.get('authors', '[]'))
        document_infos['refIds'] = refs
        pub_miner.save_json_data(PubMedInfoJsonFilePath, document_infos)
        if refs:
            pid_str = str(pid)
            for pub_id in refs:
                if pub_id in cited_by_infos:
                    if pid_str not in cited_by_infos[pub_id]:
                        cited_by_infos[pub_id].append(pid_str)
                else:
                    cited_by_infos[pub_id] = [pid_str]
    statistic_time = time.time()
    pub_miner.Config.Logger.info(f'upload PubMed: {len(batch_update_pubs)} PubMed data items to be updated and '
                                 f'{len(batch_insert_pubs)} PubMed data items to be created')
    # 上传数据至数据库
    db = pub_miner.PubMinerDB()
    # 批量插入文献基本信息
    db.batch_insert_pub_med_base_info(batch_data=batch_insert_pubs)
    # 批量插入新文献信息
    db.batch_insert_new_pub_info(batch_data=batch_insert_new_pubs)
    # 更新统计信息
    db.update_stat_abstract_fullText_fields(new_pmc=0)
    # 批量更新新文献信息
    db.batch_update_new_pub_info(batch_data=batch_update_new_pubs)
    # 批量更新文献基本信息
    db.batch_update_pub_med_base_info(batch_data=batch_update_pubs)
    # 批量更新文献引用信息
    db.batch_update_ref_pub_info(batch_data=batch_update_ref_pubs)
    # 批量插入文献引用信息
    db.batch_insert_ref_pub_info(batch_data=batch_insert_ref_pubs)
    # 更新文献被引用信息
    for pub_id, citedIds in cited_by_infos.items():
        db.insert_or_update_cite_cited_similar_table(int(pub_id), citedIds, field='cited')
    db.close()
    pub_miner.Config.Logger.info(f'takes time to upload PubMed data: {time.time() - statistic_time}')
    # 是否删除源文件
    if deleteBioC:
        os.remove(PubMedBioCFilePath)


def update_pmc_info(PMCBioCDirPath, deleteBioC=True):
    """PMC基本信息上传Mysql数据库"""
    resourceBioCPath, _ = makeDirs('PMC')
    db = pub_miner.PubMinerDB()
    new_pmc = 0
    for BioCXmlFile in os.listdir(PMCBioCDirPath):
        try:
            reader = bioc.load(open(os.path.join(PMCBioCDirPath, BioCXmlFile), 'r', encoding='utf-8'))
            document = reader.documents[0]
            # 文献PMC id
            pid = 'PMC' + document.id
            # PMC文献基本信息
            document_infos = document.passages[0].infons
            # PMC文献标题
            pub_title = document.passages[0].text
            # PMC文献杂志全称
            journal = document_infos.get('journal_full_name', '')
            # PMC文献杂志缩写
            journal_iso = document_infos.get('journal_name', '')
            # 年份
            year = document_infos.get('year', '')
            # PMC文献作者信息
            authors = literal_eval(document_infos.get('authors', '[]'))
            pub_authors = '|'.join(authors)
            # PMC文献基本数据
            pub_data = [pub_title, pub_authors, journal_iso or journal, year, str(pid)]

            # 计算当前PMC数据的存储目录
            psd = str(math.ceil(int(pid[3:]) / 10000))
            # PMC BioC数据的存储路径
            dest_dir_path = os.path.join(resourceBioCPath, f'{psd[-1]}/{psd}')
            if not os.path.isdir(dest_dir_path):
                os.makedirs(dest_dir_path, exist_ok=True)
            dest_path = os.path.join(dest_dir_path, f'{pid}.json')
            # 如果当前PMC数据不存在，保存BioC数据到存储路径用于查询并更新new pub数据表信息，否则只更新new pub数据表信息
            if not os.path.exists(dest_path):
                db.insert_new_pub_info([int(time.time()), '1'] + pub_data)
                pub_miner.save_json_data(dest_path, bioc.toJSON(document))
                new_pmc += 1
            else:
                db.update_new_pub_info([int(time.time()), '0'] + pub_data)
            # 是否删除源文件
            if deleteBioC:
                os.remove(os.path.join(PMCBioCDirPath, BioCXmlFile))
        except Exception as e:
            pub_miner.Config.Logger.error(f'upload PMC: {BioCXmlFile} error, errorInfo: {str(e)}')
    # 更新数据表stat中的fullText字段信息
    db.update_stat_abstract_fullText_fields(new_pmc=new_pmc)
    db.close()


def update_pub_base_info(resource, deleteBioC=True):
    """上传基本信息至数据库"""
    pub_miner.Config.Logger.info(f"Running update resource: {resource}")
    globalSettings = pub_miner.get_global_settings(True)
    workspaceDir = os.path.expanduser(globalSettings["storage"]["workspace"])
    resourceInfo = pub_miner.getResourceInfo(resource)
    # BioC格式输出路径
    BioCDir = os.path.join(workspaceDir, resourceInfo['BioCDir'])
    if resource == 'PUBMED':
        inFiles = [os.path.join(root_path, filename) for root_path, _, files in os.walk(BioCDir) for filename in files]
        sortedInFiles = sorted(inFiles, key=lambda x: time.strftime('%Y-%m-%d %H:%M:%S',
                                                                    time.localtime(os.path.getctime(x))))
        for BioCFilePath in sortedInFiles:
            update_pub_med_info(BioCFilePath, deleteBioC)
    elif resource == 'PMC':
        update_pmc_info(BioCDir, deleteBioC)
    else:
        raise RuntimeError(f"Unknown resource: {resource}, {resource} is not an accepted resource. "
                           f"Options are: PUBMED/PMC")
    pub_miner.Config.Logger.info(f"update resource: {resource} baseInfo finished")


def update_pub_ner_result(resource, second_dir):
    """更新命名实体识别结果"""
    globalSettings = pub_miner.get_global_settings(True)
    # 实体识别结果存放路径
    resultDir = os.path.expanduser(globalSettings["storage"]["result"])
    resourceResultDir = os.path.join(resultDir, resource, second_dir)
    # 从数据库中查询library标准库的identifier和id
    db = pub_miner.PubMinerDB()
    identifier_lib_id = {identifier: library_id for identifier, library_id in db.search_library('identifier', 'id')}
    db.close()
    # 文献——library字典{library_id: [pub_id1, pub_id2, pub_id3...]
    # 文献--mention字典{mention: [pub_id1, pub_id2, pub_id3...]
    library_pub, mention_pub = {}, {}
    pubs_infos = {}
    for BioCXmlFile in os.listdir(resourceResultDir):

        reader = bioc.load(open(os.path.join(resourceResultDir, BioCXmlFile), 'r', encoding='utf8'))
        document = reader.documents[0]
        annotations = [annotation for passage in document.passages for annotation in passage.annotations
                       if passage.infons.get('section_type', '') not in ['REF', 'SUPPL', 'TABLE', 'BACK']]
        pub_id = document.passages[0].infons.get('article_id_pmid') if resource == 'PMC' else BioCXmlFile[:-4]
        # 如果pub_id不存在则略过该文献
        if not pub_id:
            continue
        is_cancer = 0
        for annotation in annotations:
            if annotation.infons['type'] == 'disease':
                is_cancer = 1
            if annotation.infons['type'] in ['gene', 'disease', 'chemical', 'mutation']:
                if annotation.infons['symbol'] != '-':
                    for identifier in annotation.infons['identifier'].split(';'):
                        library_id = identifier_lib_id.get(identifier)
                        if not library_id:
                            continue
                        if library_id not in library_pub:
                            library_pub[library_id] = [pub_id]
                        else:
                            library_pub[library_id].append(pub_id)

                mention = annotation.text
                if mention not in mention_pub:
                    mention_pub[mention] = [pub_id]
                else:
                    mention_pub[mention].append(pub_id)
        pubs_infos[pub_id] = [is_cancer, int(pub_id)]
    # 连接数据库
    db = pub_miner.PubMinerDB()
    # 批量更新pub基本信息（是否是癌症文献）
    db.batch_update_pub_med_is_cancer(list(pubs_infos.values()))
    for library_id, pubs in library_pub.items():
        db.insert_or_update_library_pub(library_id, pubs)
    mention_id_dict = {mention.lower(): mention_id for mention, mention_id in db.search_mentions('mention', 'id')}

    for mention, pubs in mention_pub.items():
        if mention.lower() in mention_id_dict:
            mention_id = mention_id_dict[mention.lower()]
        else:
            db.insert_mentions(mention.lower())
            result = db.search_mentions_by_mention(mention.lower())
            mention_id = result[0]
            mention_id_dict[mention.lower()] = mention_id
        db.insert_or_update_mention_pub(mention_id, pubs)
    db.close()
    shutil.rmtree(resourceResultDir)
    pub_miner.Config.Logger.info(f'update pub ner result finished')


if __name__ == '__main__':
    update_pub_base_info('PUBMED')
    update_pub_base_info('PMC')
    update_pub_ner_result('PUBMED', '202111120338.split.ner')
