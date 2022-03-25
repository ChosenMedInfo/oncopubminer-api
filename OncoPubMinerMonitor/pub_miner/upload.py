# -*- coding: utf-8 -*-
# @Time : 2021/8/2 10:32
# @File : upload.py
# @Project : OncoPubMinerMonitor
"""
上传结果数据
"""
import math
import time
from ast import literal_eval
import os
import json

import requests
import bioc
import markdown2

import pub_miner


def pushToFTP(outputList, toolSettings, globalSettings):
    """
    上传ftp服务器
    :param outputList:
    :param toolSettings:
    :param globalSettings:
    :return:
    """
    FTP_ADDRESS = globalSettings["upload"]["ftp"]["url"]
    FTP_USERNAME = globalSettings["upload"]["ftp"]["username"]
    FTP_PASSWORD = globalSettings["upload"]["ftp"]["password"]

    # 1. 登录ftp服务器
    ftp_client = pub_miner.FTPClient(FTP_ADDRESS, FTP_USERNAME, FTP_PASSWORD)

    # 2. Go the the right directory, or create it
    ftp_client.cdTree(toolSettings["name"] + "/" + str(toolSettings["version"]) + "/")

    assert len(outputList) == 1 and os.path.isdir(
        outputList[0]), "FTP only accepted a single output directory at the moment"
    outputDir = outputList[0]
    for f in os.listdir(outputDir):
        fPath = os.path.join(outputDir, f)
        if os.path.isfile(fPath):
            ftp_client.upload(outputDir, f)

    # 4. Close session
    ftp_client.quit()


def pushToLocalDirectory(resource):
    globalSettings = pub_miner.get_global_settings(True)
    # 最终NER生成的BioC的存放路径
    BioCPath = os.path.expanduser(globalSettings["storage"]["upload"]["local-directory"])
    resourceBioCPath = os.path.join(BioCPath, resource)
    # BioCInfo的存放路径
    resourceBioCInfoPath = os.path.join(BioCPath, f'{resource}_INFOS')
    # 程序开始运行时间
    start_time = time.time()
    workspaceDir = os.path.expanduser(globalSettings["storage"]["workspace"])
    resourceInfo = pub_miner.getResourceInfo(resource)
    # BioC格式输出路径
    BioCDir = os.path.join(workspaceDir, resourceInfo['NerDir'])
    for BioCXmlFile in os.listdir(BioCDir):
        for document in bioc.BioCXMLDocumentReader(os.path.join(BioCDir, BioCXmlFile)):
            pid = document.id
            """将PubMed基本信息和BioC数据保存"""
            # 计算当前PubMed数据的二级存储路径
            psd = str(math.ceil(int(pid) / 10000))

            BioCDocJsonFilePath = os.path.join(resourceBioCPath, f'{psd[-1]}/{psd}/{pid}.json')
            if not os.path.exists(BioCDocJsonFilePath):
                pub_miner.save_json_data(BioCDocJsonFilePath, bioc.toJSON(document))

            document_infos = document.passages[0].infons
            document_infos['authors'] = literal_eval(document_infos.get('authors', '[]'))
            document_infos['keywords'] = literal_eval(document_infos.get('keywords', '[]'))
            document_infos['refIds'] = literal_eval(document_infos.get('refIds', '[]'))
            PubMedInfoJsonFilePath = os.path.join(resourceBioCInfoPath, f'{psd[-1]}/{psd}/{pid}.json')
            # 保存PubMed基本信息
            pub_miner.save_json_data(PubMedInfoJsonFilePath, document_infos)
    pub_miner.Config.Logger.info(f'upload BioC time: {time.time()-start_time}')


def pushToZenodo(outputList, toolSettings, globalSettings):
    for f in outputList:
        assert os.path.isfile(f) or os.path.isdir(f), "Output (%s) was not found. It must be a file or directory." % f

    if "sandbox" in globalSettings["upload"]["zenodo"] and globalSettings["upload"]["zenodo"]["sandbox"]:
        ZENODO_URL = 'https://sandbox.zenodo.org'
    else:
        ZENODO_URL = 'https://zenodo.org'

    ZENODO_AUTHOR = globalSettings["upload"]["zenodo"]["author"]
    ZENODO_AUTHOR_AFFILIATION = globalSettings["upload"]["zenodo"]["authorAffiliation"]

    ACCESS_TOKEN = globalSettings["upload"]["zenodo"]["token"]

    headers = {"Content-Type": "application/json"}

    if "zenodo" in toolSettings:
        existingZenodoID = int(toolSettings["zenodo"])

        print("  Creating new version of Zenodo submission %d" % existingZenodoID)

        r = requests.get(ZENODO_URL + '/api/records/%d' % existingZenodoID, json={}, headers=headers)
        assert r.status_code == 200, 'Unable to find existing Zenodo record %d to update' % existingZenodoID

        # Update with the latest ID
        existingZenodoID = r.json()['id']

        r = requests.post(ZENODO_URL + '/api/deposit/depositions/%d/actions/newversion' % existingZenodoID,
                          params={'access_token': ACCESS_TOKEN}, json={},
                          headers=headers)

        assert r.status_code == 201, 'Unable to create new version of Zenodo record %d' % existingZenodoID

        # jsonResponse = r.json()
        newversion_draft_url = r.json()['links']['latest_draft']
        deposition_id = newversion_draft_url.split('/')[-1]

        r = requests.get(ZENODO_URL + '/api/deposit/depositions/%s' % deposition_id,
                         params={'access_token': ACCESS_TOKEN})

        assert r.status_code == 200, 'Unable to find Zenodo record %s' % deposition_id

        bucket_url = r.json()['links']['bucket']
        doi = r.json()["metadata"]["prereserve_doi"]["doi"]
        doiURL = "https://doi.org/" + doi

        print("  Clearing old files from new version of %d" % existingZenodoID)
        for f in r.json()['files']:
            file_id = f['id']
            r = requests.delete(ZENODO_URL + '/api/deposit/depositions/%s/files/%s' % (deposition_id, file_id),
                                params={'access_token': ACCESS_TOKEN})

            assert r.status_code == 204, 'Unable to clear old files in Zenodo record %s' % deposition_id

        print("  Got provisional DOI: %s" % doiURL)
    else:
        print("  Creating new Zenodo submission")
        r = requests.post(ZENODO_URL + '/api/deposit/depositions',
                          params={'access_token': ACCESS_TOKEN}, json={},
                          headers=headers)

        assert r.status_code == 201, "Unable to create Zenodo submission (error: %d) " % r.status_code

        bucket_url = r.json()['links']['bucket']
        deposition_id = r.json()['id']
        doi = r.json()["metadata"]["prereserve_doi"]["doi"]
        doiURL = "https://doi.org/" + doi

        print("  Got provisional DOI: %s" % doiURL)

    print("  Adding files to Zenodo submission")
    if len(outputList) > 1:
        for f in outputList:
            assert not os.path.isdir(f), "If output includes a directory, it must be the only output"

    # Replace output list with directory listing
    if os.path.isdir(outputList[0]):
        outputDir = outputList[0]
        outputList = [os.path.join(outputDir, f) for f in os.listdir(outputDir)]

    for f in outputList:
        assert os.path.isfile(f), "Cannot upload non-file (%s) to Zenodo" % f
        basename = os.path.basename(f)

        r = requests.put('%s/%s' % (bucket_url, basename),
                         data=open(f, 'rb'),
                         headers={"Accept": "application/json",
                                  "Authorization": "Bearer %s" % ACCESS_TOKEN,
                                  "Content-Type": "application/octet-stream"})

        assert r.status_code == 200, "Unable to add file to Zenodo submission (error: %d) " % r.status_code

    description = 'Results from %s tool executed using PubRunner' % toolSettings['name']
    if "output_description_file" in toolSettings:
        output_description_file = toolSettings["output_description_file"]
        assert os.path.isfile(
            output_description_file), "Unable to find output_description_file (%s)" % output_description_file
        with open(output_description_file) as f:
            description = f.read().strip()

        if output_description_file.endswith('.md'):
            description = markdown2.markdown(description)
    elif "output_description" in toolSettings:
        description = toolSettings["output_description"]

    print("  Adding metadata to Zenodo submission")
    data = {
        'metadata': {
            'title': toolSettings['name'],
            'upload_type': 'dataset',
            'description': description,
            'creators': [{'name': ZENODO_AUTHOR,
                          'affiliation': ZENODO_AUTHOR_AFFILIATION}]
        }
    }

    r = requests.put(ZENODO_URL + '/api/deposit/depositions/%s' % deposition_id,
                     params={'access_token': ACCESS_TOKEN}, data=json.dumps(data),
                     headers=headers)

    assert r.status_code == 200, "Unable to metadata to Zenodo submission (error: %d) " % r.status_code

    print("  Publishing Zenodo submission")
    r = requests.post(ZENODO_URL + '/api/deposit/depositions/%s/actions/publish' % deposition_id,
                      params={'access_token': ACCESS_TOKEN})
    assert r.status_code == 202, "Unable to publish to Zenodo submission (error: %d) " % r.status_code

    return doiURL


if __name__ == '__main__':
    pushToLocalDirectory('PUBMED')
