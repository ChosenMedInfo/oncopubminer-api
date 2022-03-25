# -*- coding: utf-8 -*-
# @Time : 2021/11/11 17:20
# @File : utils.py
# @Project : OncoPubMinerMonitor
import os
import shutil
import xml.etree.cElementTree as etree

from Bio import Entrez
import json

import pub_miner


def save_json_data(json_file, json_data):
    """保存json数据"""
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, fp=f)


def read_json_data(json_file):
    """读取json数据"""
    with open(json_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    return json_data


def save_data(filepath, content):
    """保存普通文本数据"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def read_data(filepath):
    """读取普通文本数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = f.read()
    return data


def copy_dir(resource_dir_path, dest_dir_path):
    """拷贝当前目录下的所有文件到指定目录"""
    try:
        if os.path.isdir(resource_dir_path):
            for filename in os.listdir(resource_dir_path):
                shutil.copyfile(os.path.join(resource_dir_path, filename), os.path.join(dest_dir_path))
        else:
            pub_miner.Config.Logger.info(resource_dir_path, 'not is dir')
    except Exception as e:
        pub_miner.Config.Logger.info(f'copy_dir has error, resource_path: {resource_dir_path}, '
                                     f'dest_path: {dest_dir_path}\n ErrorInfo:{str(e)}')


def eutilsToXmlData(db, document_id, email):
    """
    下载指定id的pubmed或pmc文献数据
    :param db: PUBMED/PMC
    :param document_id: 指定id
    :param email:
    :return:
    """
    Entrez.email = email  # Always tell NCBI who you are
    handle = Entrez.efetch(db=db, id=document_id, rettype="gb", retmode="xml")
    xml = handle.read()
    if isinstance(xml, bytes):
        xml = xml.decode('utf-8')
    return xml


def eutilsToXmlSimilarRef(document_id, email):
    """
    获取文献的相似/引用/被引用文献
    :param document_id: 指定id
    :param email:
    :return:
    """
    Entrez.email = email
    handle = Entrez.elink(db='pubmed', dbfrom='pubmed', cmd='neighbor', id=document_id)
    xml = handle.read()
    xml_data = xml.decode('utf-8') if isinstance(xml, bytes) else xml
    root = etree.fromstring(xml_data)
    LinkSetDbs = root.findall('./LinkSet/LinkSetDb')
    simIds, rIds, cIds = [], [], []
    for LinkSetDb in LinkSetDbs:
        link_name = LinkSetDb.find('./LinkName')
        if link_name.text == 'pubmed_pubmed':
            simIds = [Id.text for Id in LinkSetDb.findall('./Link/Id') if Id.text != str(document_id)]
        elif link_name.text == 'pubmed_pubmed_refs':
            rIds = [Id.text for Id in LinkSetDb.findall('./Link/Id') if Id.text != str(document_id)]
        elif link_name.text == 'pubmed_pubmed_citedin':
            cIds = [Id.text for Id in LinkSetDb.findall('./Link/Id') if Id.text != str(document_id)]
    return simIds, rIds, cIds
