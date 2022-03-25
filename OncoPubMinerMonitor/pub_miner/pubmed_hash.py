# -*- coding: utf-8 -*-
# @Time : 2021/8/2 14:58
# @File : pubmed_hash.py
# @Project : OncoPubMinerMonitor
"""
加密pubmed .xml文件
"""

import pub_miner
import hashlib
import json
from collections import defaultdict


def md5(text):
    if text is None:
        return ''
    if isinstance(text, list):
        text = "\n".join(text)
    if not isinstance(text, str):
        text = str(text)

    m = hashlib.md5()
    m.update(text.encode('utf8'))
    return m.hexdigest()


def pubMedHash(PubMedXMLFiles, outHashJSON):
    if not isinstance(PubMedXMLFiles, list):
        PubMedXMLFiles = [PubMedXMLFiles]

    allHashes = defaultdict(dict)
    docCount = 0
    for f in PubMedXMLFiles:
        for doc in pub_miner.processMedLineFile(f):
            pid = doc['pid']

            hashes = {'year': md5(doc['pubYear']), 'title': md5(doc['title']), 'abstract': md5(doc['abstract']),
                      'journal': md5(doc['journal']), 'journalISO': md5(doc['journalISO'])}

            allHashes[f][pid] = hashes
            docCount += 1

    with open(outHashJSON, 'w') as f:
        json.dump(allHashes, f, indent=2, sort_keys=True)

    pub_miner.Config.Logger.info(f"Hashes for {docCount} documents across {len(PubMedXMLFiles)} "
                                 f"PubMed XML files written to {outHashJSON}")
