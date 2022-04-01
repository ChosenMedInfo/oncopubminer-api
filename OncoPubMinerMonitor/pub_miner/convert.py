# -*- coding: utf-8 -*-
# @Time : 2021/8/2 14:35
# @File : convert.py
# @Project : OncoPubMinerMonitor
import copy
import datetime
import glob
import math
import os
import shutil
import time
import xml.etree.cElementTree as etree
import re

import bioc
import unicodedata
import calendar
from html import unescape

import six
from nltk.tokenize import sent_tokenize

from pub_miner import eutilsToXmlData, save_json_data, Config, PubMinerDB, get_global_settings, getResourceInfo
from pub_miner.pubrun import getToolsYamlInfo


def removeBracketsWithoutWords(text):
    """
    删除内容为空的括号/括弧/方括号/大括号,删除多余的空格
    e.g. for citation ( [] [] ) -> ( ) -> nothing
    :param text: 目标文本
    :return:
    """
    fixed = re.sub(r'\([\W\s]*\)', ' ', text)
    fixed = re.sub(r'\[[\W\s]*\]', ' ', fixed)
    fixed = re.sub(r'{[\W\s]*}', ' ', fixed)
    return fixed


def removeExtraSpaces(text):
    """
    删除多余的空格
    e.g. for citation ( [] [] ) -> ( ) -> nothing
    :param text: 目标文本
    :return:
    """
    fixed = re.sub(r'\s+', ' ', text)
    fixed = re.sub(r'\s+([,;:!?.)}\]])', r'\1', fixed)
    fixed = re.sub(r'([({\[])\s+', r'\1', fixed)
    return fixed


def removeWeirdBracketsFromOldTitles(titleText):
    """
    删除旧标题中的起始中括号 例如 "[A study of ...].
    :param titleText: 标题文本
    :return:
    """
    titleText = titleText.strip()
    if titleText[0] == '[' and titleText[-2:] == '].':
        titleText = titleText[1:-2] + '.'
    return titleText


def cleanupText(text):
    """
    清洗文本数据，格式化标准化
    :param text:
    :return:
    """
    # 删除一些“控制类”字符(左右分隔符)
    text = text.replace(u'\u2028', ' ').replace(u'\u2029', ' ')
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    text = "".join(ch if unicodedata.category(ch)[0] != "Z" else " " for ch in text)

    # 删除重复的逗号和句号旁边的逗号
    text = re.sub(r',(\s*,)*', ',', text)
    text = re.sub(r'(,\s*)*\.', '.', text)
    return text.strip()


# 反转义HTML特殊字符 e.g. &gt; is changed to >
def htmlUnescape(text):
    """
    反转义HTML特殊字符
    :param text:
    :return:
    """
    # return htmlParser.unescape(text)
    return unescape(text)


# XML elements to separate text between
separationList = ['title', 'p', 'sec', 'break', 'def-item', 'list-item', 'table', 'table-wrap', 'ack', 'caption',
                  'ref-list', 'ref']


def extractTextFromElem(elem, ignoreList):
    """
    直接在XML元素或后面提取任何原始文本
    :param ignoreList:
    :param elem:
    :return:
    """
    if elem is None:
        return []
    head = ""
    if elem.text:
        head = elem.text
    tail = ""
    if elem.tail:
        tail = elem.tail

    # 递归地从所有XML子节点获取文本
    childText = []
    for child in elem:
        childText = childText + extractTextFromElem(child, ignoreList)

    # 检查标签是否应该被忽略(如果忽略)，如果需要分隔，请添加0分隔符，否则只添加文本内容
    if elem.tag in ignoreList:
        return [tail.strip()]
    elif elem.tag in separationList:
        return [0] + [head] + childText + [tail]
    else:
        return [head] + childText + [tail]


def extractTextFromElemList_merge(li):
    """
    合并提取的文本块列表并处理分隔符
    :param li:
    :return:
    """
    textList = []
    current = ""
    # 合并一个文本列表，除了在出现0时将其分离成一个新列表
    for t in li:
        if t == 0:  # Zero delimiter so split
            if len(current) > 0:
                textList.append(current)
                current = ""
        else:  # Just keep adding
            current = current + " " + t
            current = current.strip()
    if len(current) > 0:
        textList.append(current)
    return textList


def merge(textList):
    """合并多个text块"""
    # 合并没有分隔符的文本块
    mergedList = extractTextFromElemList_merge(textList)

    # 删除任何换行符(因为它们在语法上很重要)
    mergedList = [text.replace('\n', ' ') for text in mergedList]

    # 删除不中断空格
    mergedList = [cleanupText(text) for text in mergedList]
    return mergedList


def extractTextFromElemList(elemList, ignoreList):
    """
    从XML元素或XML元素列表中提取文本
    :param ignoreList:
    :param elemList:
    :return:
    """
    textList = []
    # 提取文本并添加分隔符(此文本稍后会合并)
    if isinstance(elemList, list):
        for e in elemList:
            textList = textList + extractTextFromElem(e, ignoreList) + [0]
    else:
        textList = extractTextFromElem(elemList, ignoreList) + [0]
    mergedList = merge(textList)
    return mergedList


def extractAuthorsNames(authorFields):
    """获取PMC文献的作者信息"""
    authors, names = [], []
    if authorFields:
        for authorField in authorFields:
            surnameField = authorField.find('./surname')
            given_namesField = authorField.find('./given-names')
            surname = surnameField.text if surnameField is not None else ''
            given_names = given_namesField.text if given_namesField is not None else ''
            authors.append(f'{surname} {given_names}')
            names.append({'surname': surname, 'given-names': given_names})
    return authors, names


def getMetaInfoForPMCArticle(articleElem):
    """
    获取pmc基本信息
    :param articleElem:
    :return:
    """
    monthMapping = {}
    for i, m in enumerate(calendar.month_name):
        monthMapping[m] = i
    for i, m in enumerate(calendar.month_abbr):
        monthMapping[m] = i

    # 提取PubMed ID, PubMed Central ID和DOIs
    pidText, pmc_idText, doiText, manuscriptText = '', '', '', ''
    article_id = articleElem.findall('./front/article-meta/article-id') + articleElem.findall('./front-stub/article-id')
    for a in article_id:
        if a.text and 'pub-id-type' in a.attrib and a.attrib['pub-id-type'] == 'pmid':
            pidText = a.text.strip().replace('\n', ' ')
        elif a.text and 'pub-id-type' in a.attrib and a.attrib['pub-id-type'] == 'pmc':
            pmc_idText = a.text.strip().replace('\n', ' ')
        elif a.text and 'pub-id-type' in a.attrib and a.attrib['pub-id-type'] == 'doi':
            doiText = a.text.strip().replace('\n', ' ')
        elif a.text and 'pub-id-type' in a.attrib and a.attrib['pub-id-type'] == 'manuscript':
            manuscriptText = a.text.strip().replace('\n', ' ')

    # 获取出版日期
    pubdates = articleElem.findall('./front/article-meta/pub-date') + articleElem.findall('./front-stub/pub-date')
    pubYear, pubMonth, pubDay = None, None, None
    if len(pubdates) >= 1:
        mostComplete, completeness = None, 0
        for pubdate in pubdates:
            pubYear_Field = pubdate.find("./year")
            if pubYear_Field is not None:
                pubYear = pubYear_Field.text.strip().replace('\n', ' ')
            pubSeason_Field = pubdate.find("./season")
            if pubSeason_Field is not None:
                pubSeason = pubSeason_Field.text.strip().replace('\n', ' ')
                monthSearch = [c for c in (list(calendar.month_name) + list(calendar.month_abbr)) if
                               c != '' and c in pubSeason]
                if len(monthSearch) > 0:
                    pubMonth = monthMapping[monthSearch[0]]
            pubMonth_Field = pubdate.find("./month")
            if pubMonth_Field is not None:
                pubMonth = pubMonth_Field.text.strip().replace('\n', ' ')
            pubDay_Field = pubdate.find("./day")
            if pubDay_Field is not None:
                pubDay = pubDay_Field.text.strip().replace('\n', ' ')

            thisCompleteness = sum(x is not None for x in [pubYear, pubMonth, pubDay])
            if thisCompleteness > completeness:
                mostComplete = pubYear, pubMonth, pubDay
        pubYear, pubMonth, pubDay = mostComplete

    licenseField = articleElem.findall('./front/article-meta/permissions/license/license-p')
    _ignoreList = copy.deepcopy(Config.ignoreList)
    _ignoreList.remove('ext-link')
    licenseTexts = extractTextFromElemList(licenseField, _ignoreList)
    tmp = [htmlUnescape(t) for t in licenseTexts if len(t) > 0]
    tmp = [removeBracketsWithoutWords(t) for t in tmp]
    tmp = [removeExtraSpaces(t) for t in tmp]
    license_info = ' '.join(tmp)

    # 获取杂志信息
    journal = articleElem.findall('./front/journal-meta/journal-title') + articleElem.findall(
        './front/journal-meta/journal-title-group/journal-title') + articleElem.findall(
        './front-stub/journal-title-group/journal-title')
    assert len(journal) <= 1

    journalTextList = extractTextFromElemList(journal, Config.ignoreList)
    journalText = journalTextList[0] if journalTextList else ''

    journalISOText = ''
    journalISO = articleElem.findall('./front/journal-meta/journal-id') + articleElem.findall('./front-stub/journal-id')
    for field in journalISO:
        if field.attrib.get('journal-id-type', None) == "iso-abbrev":
            journalISOText = field.text

    # 获取作者姓名
    authorFields = articleElem.findall('./front/article-meta/contrib-group/contrib/name')
    authors, names = extractAuthorsNames(authorFields)
    result = (pidText, pmc_idText, doiText, manuscriptText, pubYear, pubMonth, pubDay, journalText, journalISOText,
              authors, names, license_info)
    return result


def getRefInfoForPMCArticle(elements):
    """获取PMC引用文献信息"""
    passages = []
    for element in elements:
        title = element.find('title')
        if title:
            passages.append({'infos': {'section_type': 'REF', 'type': 'title'}, 'text': title.text or ''})
        for refElement in element.findall('./ref/element-citation'):
            articleTitle = refElement.findall('article-title')
            titleText = extractTextFromElemList(articleTitle, Config.ignoreList)
            titleText = [removeWeirdBracketsFromOldTitles(t) for t in titleText if len(t) > 0]
            titleText = [removeBracketsWithoutWords(htmlUnescape(t)) for t in titleText]
            titleText = ' '.join([removeExtraSpaces(t).replace('[', '').replace(']', '') for t in titleText])

            infos = {'source': str(refElement.find('./source').text) if refElement.find('./source') else '',
                     'year': str(refElement.find('./year').text) if refElement.find('./year') else '',
                     'volume': str(refElement.find('./volume').text) if refElement.find('./volume') else '',
                     'issue': str(refElement.find('./issue').text) if refElement.find('./issue') else '',
                     'fpage': str(refElement.find('./fpage').text) if refElement.find('./fpage') else '',
                     'lpage': str(refElement.find('./lpage').text) if refElement.find('./lpage') else '',
                     'section_type': 'REF', 'type': 'title'}
            # 获取作者姓名
            authorFields = refElement.findall('./person-group/name')
            _, names = extractAuthorsNames(authorFields)
            name_i = 0
            for name in names:
                infos[f'name_{name_i}'] = f'surname:{name["surname"] if "surname" in name else ""};' \
                                          f'given-names:{name["given-names"] if "given-names" in name else ""}'
                name_i += 1
            pub_ids = refElement.findall('./pub-id')
            for pub_id in pub_ids:
                if pub_id.text and pub_id.attrib.get('pub-id-type') == 'pmid':
                    infos['pmid'] = pub_id.text.strip().replace('\n', ' ')
                elif pub_id.text and pub_id.attrib.get('pub-id-type') == 'pmc':
                    infos['pmc'] = pub_id.text.strip().replace('\n', ' ')
                elif pub_id.text and pub_id.attrib.get('pub-id-type') == 'doi':
                    infos['doi'] = pub_id.text.strip().replace('\n', ' ')
                elif pub_id.text and pub_id.attrib.get('pub-id-type') == 'manuscript':
                    infos['manuscript'] = pub_id.text.strip().replace('\n', ' ')
            passages.append({'infos': infos, 'text': titleText or ''})
    return passages


def getJournalDateForMedLineFile(elem, pmid):
    """
    获取杂志发布日期
    :param elem: xml节点
    :param pmid: PubMed id
    :return:
    """
    yearRegex = re.compile(r'(18|19|20)\d{2}')

    monthMapping = {}
    for i, m in enumerate(calendar.month_name):
        monthMapping[m] = i
    for i, m in enumerate(calendar.month_abbr):
        monthMapping[m] = i

    # 提取发布日期
    pubDateField = elem.find('./MedlineCitation/Article/Journal/JournalIssue/PubDate')

    assert pubDateField is not None, f"Couldn't find PubDate field for PMID={pmid}"

    medlineDateField = pubDateField.find('./MedlineDate')
    pubDateField_Year = pubDateField.find('./Year')
    pubDateField_Month = pubDateField.find('./Month')
    pubDateField_Day = pubDateField.find('./Day')

    pubYear, pubMonth, pubDay = None, None, None
    if medlineDateField is not None:
        regexSearch = re.search(yearRegex, medlineDateField.text)
        if regexSearch:
            pubYear = regexSearch.group()
        monthSearch = [c for c in (list(calendar.month_name) + list(calendar.month_abbr)) if
                       c != '' and c in medlineDateField.text]
        if len(monthSearch) > 0:
            pubMonth = monthSearch[0]
    else:
        if pubDateField_Year is not None:
            pubYear = pubDateField_Year.text
        if pubDateField_Month is not None:
            pubMonth = pubDateField_Month.text
        if pubDateField_Day is not None:
            pubDay = pubDateField_Day.text

    if pubYear is not None:
        pubYear = int(pubYear)
        if not (1700 < pubYear < 2100):
            pubYear = None

    if pubMonth is not None:
        if pubMonth in monthMapping:
            pubMonth = monthMapping[pubMonth]
        pubMonth = int(pubMonth)
    if pubDay is not None:
        pubDay = int(pubDay)

    return pubYear, pubMonth, pubDay


def getPubMedEntryDate(elem):
    pubDateFields = elem.findall('./PubmedData/History/PubMedPubDate')
    allDates = {}
    for pubDateField in pubDateFields:
        assert 'PubStatus' in pubDateField.attrib
        pubDateField_Year = pubDateField.find('./Year')
        pubDateField_Month = pubDateField.find('./Month')
        pubDateField_Day = pubDateField.find('./Day')
        pubYear = int(pubDateField_Year.text)
        pubMonth = int(pubDateField_Month.text)
        pubDay = int(pubDateField_Day.text)

        dateType = pubDateField.attrib['PubStatus']
        if 1700 < pubYear < 2100:
            allDates[dateType] = (pubYear, pubMonth, pubDay)

    if len(allDates) == 0:
        return None, None, None

    if 'pubmed' in allDates:
        pubYear, pubMonth, pubDay = allDates['pubmed']
    elif 'entrez' in allDates:
        pubYear, pubMonth, pubDay = allDates['entrez']
    elif 'medline' in allDates:
        pubYear, pubMonth, pubDay = allDates['medline']
    else:
        pubYear, pubMonth, pubDay = list(allDates.values())[0]

    return pubYear, pubMonth, pubDay


def get_titleText(document_id, tag='pubmed'):
    if tag == 'pmc':
        document_id = document_id if 'PMC' in document_id else 'PMC' + document_id
    xml_data = eutilsToXmlData(tag, str(document_id), Config.Entrez_email)
    root = etree.fromstring(xml_data)
    if tag == 'pubmed':
        Title = root.findall('./PubmedArticle/MedlineCitation/Article/ArticleTitle')
    else:
        Title = root.findall('./article/front/article-meta/title-group/article-title') + root.findall(
            './article/front-stub/title-group/article-title')
    ArticleTitleText = [removeWeirdBracketsFromOldTitles(t) for t in extractTextFromElemList(Title, Config.ignoreList)]
    ArticleTitleText = [htmlUnescape(t) for t in ArticleTitleText if len(t) > 0]
    ArticleTitleText = [removeBracketsWithoutWords(t) for t in ArticleTitleText]
    ArticleTitleText = [removeExtraSpaces(t).replace('[', '').replace(']', '') for t in ArticleTitleText]
    return ArticleTitleText


def extractPassageSentences(textSource, offset):
    """获取BioC Passage sentences and BioC Passage text"""
    passage_sentences = []
    textSource = re.sub(r'Fig\. \d*', '', textSource, flags=re.IGNORECASE)
    sentences = sent_tokenize(textSource)
    textSource = ' '.join(sentences)
    sentence_offset = offset
    for sentence in sentences:
        Sentence = bioc.BioCSentence()
        Sentence.text = sentence
        Sentence.offset = sentence_offset
        sentence_offset += (len(sentence) + 1)
        passage_sentences.append(Sentence)
    return passage_sentences, textSource


def processMedLineFile(PubMedFile):
    for event, elem in etree.iterparse(PubMedFile, events=('start', 'end', 'start-ns', 'end-ns')):
        if event == 'end' and elem.tag == 'PubmedArticle':
            # Try to extract the pmidID
            pmidField = elem.find('./MedlineCitation/PMID')
            assert pmidField is not None
            # 版本
            version = pmidField.attrib['Version'] if 'Version' in pmidField.attrib else '1'
            pmid = pmidField.text
            articleIDs = elem.findall('./PubmedData/ArticleIdList/ArticleId')
            pmcid, doi = None, None
            for articleID in articleIDs:
                if 'IdType' in articleID.attrib and articleID.attrib['IdType'] == 'doi':
                    doi = articleID.text
                elif 'IdType' in articleID.attrib and articleID.attrib['IdType'] == 'pmc':
                    if re.search(r'^(PMC)?\d+$', articleID.text):
                        pmcid = articleID.text
            journalYear, journalMonth, journalDay = getJournalDateForMedLineFile(elem, pmid)
            entryYear, entryMonth, entryDay = getPubMedEntryDate(elem)

            jComparison = tuple(9999 if d is None else d for d in [journalYear, journalMonth, journalDay])
            eComparison = tuple(9999 if d is None else d for d in [entryYear, entryMonth, entryDay])
            # The PubMed entry has been delayed for some reason so let's try the journal data
            if jComparison < eComparison:
                pubYear, pubMonth, pubDay = journalYear, journalMonth, journalDay
            else:
                pubYear, pubMonth, pubDay = entryYear, entryMonth, entryDay

            # Extract the authors
            authorElems = elem.findall('./MedlineCitation/Article/AuthorList/Author')
            authors = []
            for authorElem in authorElems:
                fore_name = authorElem.find('./ForeName')
                last_name = authorElem.find('./LastName')
                collective_name = authorElem.find('./CollectiveName')

                if fore_name is not None and last_name is not None and \
                        fore_name.text is not None and last_name.text is not None:
                    name = f"{last_name.text} {fore_name.text.replace(' ', '').strip()}"
                elif last_name is not None and last_name.text is not None:
                    name = last_name.text.strip()
                elif fore_name is not None and fore_name.text is not None:
                    name = fore_name.text.replace(' ', '').strip()
                elif collective_name is not None and collective_name.text is not None:
                    name = collective_name.text.strip()
                else:
                    raise RuntimeError(f"Unable to find authors in Pubmed citation (PMID={pmid})")
                authors.append(name)

            # Extract the title of paper
            title = elem.findall('./MedlineCitation/Article/ArticleTitle')
            titleText = extractTextFromElemList(title, Config.ignoreList)
            titleText = [removeWeirdBracketsFromOldTitles(t) for t in titleText if len(t) > 0]
            titleText = [htmlUnescape(t) for t in titleText]
            titleText = [removeBracketsWithoutWords(t) for t in titleText]
            titleText = [removeExtraSpaces(t).replace('[', '').replace(']', '') for t in titleText]
            if not titleText:
                # print(pmid, 'not have title')
                titleText = get_titleText(pmid)

            # Extract the abstract from the paper
            abstract = elem.findall('./MedlineCitation/Article/Abstract/AbstractText')
            abstractText = extractTextFromElemList(abstract, Config.ignoreList)
            abstractText = [htmlUnescape(t) for t in abstractText if len(t) > 0]
            abstractText = [removeBracketsWithoutWords(t) for t in abstractText]
            abstractText = [removeExtraSpaces(t).replace('[', '').replace(']', '') for t in abstractText]

            journalTitleField = elem.findall('./MedlineCitation/Article/Journal/Title')
            journalTitleISOFields = elem.findall('./MedlineCitation/Article/Journal/ISOAbbreviation')
            journalTitle = extractTextFromElemList(journalTitleField, Config.ignoreList)
            journalTitle = journalTitle[0] if len(journalTitle) > 0 else ''
            journalISOTitle = extractTextFromElemList(journalTitleISOFields, Config.ignoreList)
            journalISOTitle = journalISOTitle[0] if len(journalISOTitle) > 0 else ''

            keywordField = elem.findall('./MedlineCitation/KeywordList/Keyword')
            keywords = extractTextFromElemList(keywordField, Config.ignoreList)

            ReferenceArticleIdFields = elem.findall('./PubmedData/ReferenceList/Reference/ArticleIdList/ArticleId')
            ReferenceArticleIdFields = [ArticleIdField for ArticleIdField in ReferenceArticleIdFields
                                        if 'IdType' in ArticleIdField.attrib
                                        and ArticleIdField.attrib['IdType'] == 'pubmed']
            ReferenceArticleIds = [ArticleId for ArticleId in extractTextFromElemList(ReferenceArticleIdFields,
                                                                                      Config.ignoreList)
                                   if re.search(r'^\d+$', ArticleId)]

            issnField = elem.find('./MedlineCitation/Article/Journal/ISSN')
            volumeField = elem.find('./MedlineCitation/Article/Journal/JournalIssue/Volume')
            issueField = elem.find('./MedlineCitation/Article/Journal/JournalIssue/Issue')
            medlinePgnField = elem.find('./MedlineCitation/Article/Pagination/MedlinePgn')

            issn = issnField.text if issnField is not None else ''
            volume = volumeField.text if volumeField is not None else ''
            issue = issueField.text if issueField is not None else ''
            medlinepgn = medlinePgnField.text if medlinePgnField is not None else ''
            document = {"pid": pmid, "pmc_id": pmcid, "doi": doi, "pubYear": pubYear, "pubMonth": pubMonth,
                        "pubDay": pubDay, "title": titleText, "abstract": abstractText, "journal": journalTitle,
                        "journalISO": journalISOTitle, "authors": authors, 'keywords': keywords, "issn": issn,
                        "volume": volume, "issue": issue, "medlinePgn": medlinepgn, "version": version,
                        'ReferenceIds': ReferenceArticleIds}

            yield document

            # Important: clear the current element from memory to keep memory usage low
            elem.clear()


def per_PubMed2BioC(pmDoc, PubMedInfos):
    """初始化生成单个pubmed bioc数据"""
    BioCDoc = bioc.BioCDocument()
    BioCDoc.id = pmDoc["pid"]
    offset = 0
    for section in ["title", "abstract"]:
        textSource = ' '.join(pmDoc[section]).strip()
        passage = bioc.BioCPassage()
        textSource = textSource.replace('|', '')
        if section == 'title':
            passage.infons = PubMedInfos
        else:
            passage.infons = {
                'section': section.title(),
                'type': section
            }
            sentences, textSource = extractPassageSentences(textSource, offset)
            passage.sentences = sentences
        passage.text = textSource
        passage.offset = offset
        offset += (len(textSource) + 1)
        BioCDoc.add_passage(passage)
    return BioCDoc


def per_PubMedInfo(pmDoc, source, psd, is_new):
    """获取单个PubMed的基本信息"""
    iso = pmDoc["journalISO"]
    journal = pmDoc["journal"]
    has_abstract = 1 if len(pmDoc['abstract']) > 0 else 0
    pid = pmDoc["pid"]
    PubMedInfos = {
        'journal': f'{iso if iso else journal}; '
                   f'{str(pmDoc["pubYear"])}{" " + str(pmDoc["pubMonth"]) if pmDoc["pubMonth"] else ""};'
                   f'{str(pmDoc["volume"])}'
                   f'{"(" + str(pmDoc["issue"]) + "):" if pmDoc["issue"] else ":"}'
                   f'{str(pmDoc["medlinePgn"]) + "." if pmDoc["medlinePgn"] else ""}'
                   f'{" doi:" + pmDoc["doi"] if pmDoc["doi"] else ""}',
        'authors': pmDoc["authors"],
        'keywords': pmDoc["keywords"],
        'journal_name': iso if iso else journal,
        'journal_full_name': journal,
        'section': 'Title',
        'type': 'title',
        'year': pmDoc["pubYear"],
        'month': pmDoc["pubMonth"],
        'article_id_pmid': pid,
        'source': source,
        "refIds": pmDoc["ReferenceIds"],
        "refNums": len(pmDoc["ReferenceIds"]),
        "has_abstract": has_abstract,
        "has_annotation": not is_new,
        "psd": psd,
        "is_new": is_new
    }
    pmc_id = pmDoc["pmc_id"]
    if pmc_id and isinstance(pmc_id, str) and re.search(r'^PMC\d+$', pmc_id):
        PubMedInfos['article_id_pmc'] = pmc_id
        # 文献相关基本信息
        PubMedInfos['pmc_second_dir'] = str(math.ceil(int(pmc_id[3:]) / 10000))
    if pmDoc["doi"]:
        PubMedInfos['article_id_doi'] = pmDoc["doi"]
    return PubMedInfos


def PubMedXml2BioC(PubMedXmlPath, PubMedBioCXMLPaths, deleteSource):
    """
    PubMed xml原始文件，转化为BioC格式(每个文献对应一个BioC格式的xml)输出
    :param PubMedXmlPath:
    :param PubMedBioCXMLPaths:
    :param deleteSource:
    :return:
    """
    basename = os.path.basename(PubMedXmlPath)
    global_setting = get_global_settings(True)
    BioCPath = os.path.expanduser(global_setting["upload"]["local-directory"])
    resourceBioCPath = os.path.join(BioCPath, 'PUBMED')
    Config.Logger.info(f'starting convert PubMedXml to BioC: {basename}')
    try:
        PubMedBioCXMLPaths = [PubMedBioCXMLPaths] if isinstance(PubMedBioCXMLPaths, six.string_types) else \
            PubMedBioCXMLPaths
        BioCXml_dict = {}
        new_num = 0
        for pmDoc in processMedLineFile(PubMedXmlPath):
            pid = pmDoc["pid"]
            if pid:
                try:
                    version = int(pmDoc['version']) if pmDoc['version'] and re.search(r'^\d+$', pmDoc['version']) else 1
                    if pid not in BioCXml_dict or (pid in BioCXml_dict and version > BioCXml_dict[pid][1]):
                        # 计算当前PubMed数据的二级存储路径
                        psd = str(math.ceil(int(pid) / 10000))
                        BioCDocJsonFilePath = os.path.join(resourceBioCPath, f'{psd[-1]}/{psd}/{pid}.json')

                        is_new = 0 if os.path.exists(BioCDocJsonFilePath) else 1

                        PubMedInfos = per_PubMedInfo(pmDoc, source=basename, psd=psd, is_new=is_new)
                        BioC_xml = per_PubMed2BioC(pmDoc, PubMedInfos)
                        if is_new:
                            save_json_data(BioCDocJsonFilePath, bioc.toJSON(BioC_xml))
                            new_num += 1

                        BioCXml_dict[pid] = (BioC_xml, version)
                except Exception as e:
                    Config.Logger.error(f'convert PubMedXml to BioC basename: {basename}, Pid: {pid}, Error {str(e)}')
        # 写入PubMed数据
        for PubMedBioCXMLPath in PubMedBioCXMLPaths:
            PubMedBioCXMLFilePath = os.path.join(PubMedBioCXMLPath, basename)
            with bioc.BioCXMLDocumentWriter(PubMedBioCXMLFilePath) as writer:
                for BioCXml, _ in BioCXml_dict.values():
                    writer.write_document(BioCXml)
        Config.Logger.info(f'convert PubMedXml to BioC: {basename}, '
                           f'{new_num}(New)/{len(BioCXml_dict)}(Total) PubMed article')
        # 删除源文件
        if deleteSource:
            os.remove(PubMedXmlPath)
    except Exception as e:
        Config.Logger.error(f'convert PubMedXml to BioC Error basename: {basename}, Error {e.args[0]}: {e.args[1]}')


def getSecTitle(BodyElements, titles=None, title_level=0):
    """获取章节标题"""
    if titles is None:
        titles = {}
    children = []
    for BodyElement in BodyElements:
        for child in BodyElement:
            if child.tag == 'title':
                child_texts = extractTextFromElemList([child], Config.ignoreList)
                if len(child_texts) > 0:
                    titles[child_texts[0]] = title_level
                continue
            children.append(child)
    title_level += 1
    if children:
        getSecTitle(children, titles, title_level)
    return titles


def processPMCFile(pmcFile):
    """解析pmc xml文档"""
    with open(pmcFile, 'r', encoding='utf-8') as openfile:
        # Skip to the article element in the file
        for event, elem in etree.iterparse(openfile, events=('start', 'end', 'start-ns', 'end-ns')):
            if event == 'end' and elem.tag == 'article':
                results = getMetaInfoForPMCArticle(elem)
                pidText, pmcIdText, doiText, manText, pubYear, pubMonth, pubDay, journal, journalISO = results[:9]
                sub_articles = [elem] + elem.findall('./sub-article')

                for articleElem in sub_articles:
                    if articleElem == elem:
                        subPidText, subPMCidText, subDoiText, subManText = results[:4]
                        subPubYear, subPubMonth, subPubDay = results[4:7]
                        subJournal, subJournalISO, subAuthors, subNames, subLicence = results[7:]
                    else:
                        # Check if this subArticle has any distinguishing IDs and use them instead
                        subResults = getMetaInfoForPMCArticle(articleElem)
                        subPidText, subPMCidText, subDoiText, subManText = subResults[:4]
                        subPubYear, subPubMonth, subPubDay = subResults[4:7]
                        subJournal, subJournalISO, subAuthors, subNames, subLicence = subResults[7:]
                        if subPidText == '' and subPMCidText == '' and subDoiText == '':
                            subPidText, subPMCidText, subDoiText, subManText = pidText, pmcIdText, doiText, manText
                        if subPubYear is None:
                            subPubYear = pubYear
                            subPubMonth = pubMonth
                            subPubDay = pubDay
                        if subJournal is None:
                            subJournal = journal
                            subJournalISO = journalISO

                    # Extract the title of paper
                    title = articleElem.findall('./front/article-meta/title-group/article-title') + articleElem.findall(
                        './front-stub/title-group/article-title')
                    assert len(title) <= 1
                    titleText = extractTextFromElemList(title, Config.ignoreList)
                    titleText = [removeWeirdBracketsFromOldTitles(t) for t in titleText]
                    titleText = [t for t in titleText if len(t) > 0]
                    titleText = [htmlUnescape(t) for t in titleText]
                    titleText = [removeBracketsWithoutWords(t) for t in titleText]
                    titleText = [removeExtraSpaces(t).replace('[', '').replace(']', '') for t in titleText]
                    if not titleText and str(subPidText):
                        titleText = get_titleText(str(subPidText))

                    # Extract the abstract from the paper
                    abstract = articleElem.findall('./front/article-meta/abstract') + articleElem.findall(
                        './front-stub/abstract')
                    abstractText = extractTextFromElemList(abstract, Config.ignoreList)
                    abstractSecTitles = getSecTitle(abstract)

                    # Extract the full text from the paper as well as suppleMentaries and floating blocks of text
                    BodyElements = articleElem.findall('./body')
                    BodySecTitles = getSecTitle(BodyElements)
                    articleText = extractTextFromElemList(BodyElements, Config.ignoreList)
                    backElements = articleElem.findall('./back')
                    backSecTitles = getSecTitle(backElements)
                    backText = extractTextFromElemList(backElements, Config.ignoreList)
                    referenceElements = articleElem.findall('./back/ref-list')
                    referencePassages = getRefInfoForPMCArticle(referenceElements)
                    floatElements = articleElem.findall('./floats-group')
                    floatSecTitles = getSecTitle(floatElements)
                    floatingText = extractTextFromElemList(articleElem.findall('./floats-group'), Config.ignoreList)
                    document = {'pid': subPidText, 'pmc_id': subPMCidText, 'doi': subDoiText, 'manuscript': subManText,
                                'pubYear': subPubYear, 'pubMonth': subPubMonth, 'pubDay': subPubDay, 'names': subNames,
                                'journal': subJournal, 'journalISO': subJournalISO, 'authors': subAuthors,
                                'license': subLicence, 'abstractSecTitles': abstractSecTitles,
                                'articleSecTitles': BodySecTitles, 'backSecTitles': backSecTitles,
                                'floatingSecTitles': floatSecTitles, 'refPassages': referencePassages}

                    textSources = {'title': titleText, 'abstract': abstractText, 'article': articleText,
                                   'back': backText, 'floating': floatingText}
                    for k in textSources.keys():
                        tmp = textSources[k]
                        tmp = [htmlUnescape(t) for t in tmp if len(t) > 0]
                        tmp = [removeBracketsWithoutWords(t) for t in tmp]
                        tmp = [removeExtraSpaces(t).replace('[', '').replace(']', '') for t in tmp]
                        textSources[k] = tmp
                    textSources['ref'] = referencePassages
                    document['textSources'] = textSources
                    yield document

                # Less important here (compared to abstracts) as each article file is not too big
                elem.clear()


def per_PMC2BioC(pmcDoc, pmc_id):
    """初始化生成单个PMC BioC数据"""
    BioCDoc = bioc.BioCDocument()
    BioCDoc.id = pmc_id
    textSources = pmcDoc["textSources"]
    offset = 0
    # for groupName, textSourceGroup in pmcDoc["textSources"].items():
    for groupName in ['title', 'abstract', 'article', 'back', 'ref', 'floating']:
        if not textSources.get(groupName):
            continue
        textSourceGroup = textSources.get(groupName)
        # 标题
        if groupName == 'title':
            passage = bioc.BioCPassage()
            passage.infons = per_PMCInfos(pmcDoc, pmc_id)
            passage.offset = offset
            text = ' '.join(textSourceGroup).replace('|', '')
            passage.text = text
            offset += (len(text) + 1)
            BioCDoc.add_passage(passage)
        elif groupName == 'ref':
            for textSource in textSourceGroup:
                text = textSource['text']
                passage = bioc.BioCPassage()

                sentences, text = extractPassageSentences(text, offset)
                passage.sentences = sentences
                passage.infons = textSource['infos']
                passage.offset = offset
                passage.text = text
                offset += (len(text) + 1)
        else:
            secTitles = pmcDoc[f'{groupName}SecTitles']
            section_type = None
            for textSource in textSourceGroup:
                passage = bioc.BioCPassage()

                if groupName != 'article':
                    if textSource in secTitles:
                        passage_type = f'{groupName.lower()}_title_{secTitles[textSource]}'
                    else:
                        passage_type = groupName.lower()
                    passage.infons['section_type'] = groupName.upper()
                    passage.infons['type'] = passage_type
                else:
                    if textSource in secTitles:
                        section_type = textSource.upper()
                        passage_type = f'title_{secTitles[textSource]}'
                    else:
                        passage_type = f'paragraph'
                    passage.infons['section_type'] = section_type or groupName.upper()
                    passage.infons['type'] = passage_type
                passage.infons['section'] = groupName.title()
                sentences, textSource = extractPassageSentences(textSource, offset)
                passage.sentences = sentences
                passage.text = textSource
                passage.offset = offset
                offset += (len(textSource) + 1)
                BioCDoc.add_passage(passage)
    return BioCDoc


def per_PMCInfos(pmcDoc, pmc_id):
    iso = pmcDoc["journalISO"]
    journal = pmcDoc["journal"]
    infos = {
        'journal_name': iso if iso else journal,
        'journal_full_name': journal,
        'article_id_pmc': pmc_id,
        'license': pmcDoc['license'],
        'authors': pmcDoc['authors'],
        'year': pmcDoc['pubYear'],
        'section': 'Title',
        'section_type': 'TITLE',
        'type': 'front'}
    if pmcDoc['manuscript']:
        infos['article_id_manuscript'] = pmcDoc['manuscript']
    if pmcDoc['pid']:
        infos['article_id_pmid'] = pmcDoc['pid']
    if pmcDoc['doi']:
        infos['article_id_doi'] = pmcDoc['doi']
    name_i = 0
    for name in pmcDoc['names']:
        infos[f'name_{name_i}'] = f'surname:{name["surname"] if "surname" in name else ""};' \
                                  f'given-names:{name["given-names"] if "given-names" in name else ""}'
        name_i += 1
    return infos


def PMCXml2BioC(PMCXmlPath, PMCBioCDirPaths, deleteSource):
    """
    PMC xml原始文件，转化为BioC格式(每个文献对应一个BioC格式的xml)输出
    :param PMCXmlPath: PMC xml原始文件
    :param PMCBioCDirPaths: BioC格式输出路径
    :param deleteSource: 是否删除源文件
    :return:
    """
    try:
        PMCBioCDirPaths = [PMCBioCDirPaths] if isinstance(PMCBioCDirPaths, six.string_types) else PMCBioCDirPaths
        basename = os.path.basename(PMCXmlPath)

        for pmcDoc in processPMCFile(PMCXmlPath):
            if re.search(r'^(PMC)?\d+$', pmcDoc["pmc_id"]):
                pmc_id = pmcDoc["pmc_id"]
            elif re.search(r'^(PMC)?\d+\.xml$', basename):
                pmc_id = basename[3:-4]
            else:
                continue
            pmc_id = pmc_id[3:] if 'PMC' in pmc_id else pmc_id
            BioCXml = per_PMC2BioC(pmcDoc, pmc_id)
            for PMCBioCDirPath in PMCBioCDirPaths:
                with bioc.BioCXMLDocumentWriter(os.path.join(PMCBioCDirPath, f'PMC{pmc_id}.xml')) as writer:
                    writer.write_document(BioCXml)
        if deleteSource:
            os.remove(PMCXmlPath)
    except etree.ParseError:
        Config.Logger.error(f"Parsing PMC xml file: {PMCXmlPath} error, Error: {str(etree.ParseError)}")


def splitBioCFiles(inFiles, outDirs):
    for outDir in outDirs:
        if not os.path.exists(outDir):
            os.makedirs(outDir)
    Config.Logger.info(f"Splitting a total of {len(inFiles)} BioC XML file")
    for inFile in inFiles:
        if os.path.exists(inFile):
            for document in bioc.BioCXMLDocumentReader(inFile):
                pid = document.id
                try:
                    for outDir in outDirs:
                        with bioc.BioCXMLDocumentWriter(os.path.join(outDir, f'{pid}.xml')) as writer:
                            writer.write_document(document)
                except Exception as e:
                    Config.Logger.error(f"Splitting BioC XML: {inFile} has error, pid: {pid}, error: {str(e)}")
        else:
            Config.Logger.error(f'splitBioC Error: {inFile} is not Found')


def convertFiles2BioC(inFiles, inFormat, outDirs, deleteSource=True):
    """
    转化文件格式
    :param inFiles: 输入文件列表
    :param inFormat: 输入文件格式
    :param outDirs: 输出BioC路径
    :param deleteSource: 是否删除源文件, 默认删除
    :return:
    """
    if isinstance(inFiles, str):
        inFiles = [inFiles]
    if isinstance(outDirs, str):
        outDirs = [outDirs]

    for outDir in outDirs:
        if not os.path.isdir(outDir):
            os.makedirs(outDir)
    Config.Logger.info(f"Converting {len(inFiles)} files")
    if inFormat == 'PubMedXml':
        for inFile in inFiles:
            PubMedXml2BioC(inFile, outDirs, deleteSource)
    elif inFormat == 'PMCXml':
        for inFile in inFiles:
            PMCXml2BioC(inFile, outDirs, deleteSource)
    else:
        Config.Logger.error(f"Unknown input format: {inFormat}, {inFormat} is not an accepted input format. "
                            f"Options are: PubMedXml/PMCXml")
        raise RuntimeError(f"Unknown input format: {inFormat}, {inFormat} is not an accepted input format. "
                           f"Options are: PubMedXml/PMCXml")


def convertBioCXml2BioCJson(inFile, outFile):
    try:
        reader = bioc.load(open(inFile, 'r', encoding='utf8'))
        document = reader.documents[0]
        save_json_data(outFile, bioc.toJSON(document))
    except Exception as e:
        print(f'input file: {inFile}, convert xml to json error: {str(e)}')


def converts(resource):
    """解析下载解压后的XML资源，转换为BioC格式"""
    globalSettings = get_global_settings(True)
    resourceDir = os.path.expanduser(globalSettings["storage"]["resources"])
    workspaceDir = os.path.expanduser(globalSettings["storage"]["workspace"])
    resourceInfo = getResourceInfo(resource)
    pubUnzipDir = os.path.join(resourceDir, resource, resourceInfo['unzipNewDir'])
    # BioC格式输出路径
    BioCDir = os.path.join(workspaceDir, resourceInfo['BioCDir'])
    NerDir = os.path.join(workspaceDir, resourceInfo['NerDir'])
    inFiles = [os.path.join(root_path, filename) for root_path, _, files in os.walk(pubUnzipDir) for filename in files]
    sortedInFiles = sorted(inFiles, key=lambda x: time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(os.path.getctime(x))))
    inFormat = resourceInfo['format']
    outDirs = [BioCDir, NerDir]
    # 转化PubMed xml数据为BioC
    convertFiles2BioC(sortedInFiles, inFormat, outDirs)


def splitBioC2ToolsDir(resource, tasksInfo):
    globalSettings = get_global_settings(True)
    workspaceDir = os.path.expanduser(globalSettings["storage"]["workspace"])
    nerDir = os.path.expanduser(globalSettings["storage"]["ner"])
    resourceInfo = getResourceInfo(resource)
    # BioC格式输出路径
    resourceNerDir = os.path.join(workspaceDir, resourceInfo['NerDir'])
    Config.Logger.info(f"start split {resource} BioC XML to toolDir")
    sortedBioCFiles = sorted(glob.glob(os.path.join(resourceNerDir, '*')),
                             key=lambda x: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getctime(x))))
    date_str = datetime.datetime.now().strftime('%Y%m%d%H%M')

    splitOutDirs = [os.path.join(nerDir, f'{taskInfo["toolName"]}_INPUT', resource, f'{date_str}.splitting')
                    for taskInfo in tasksInfo.values()]
    # 如果存在待拆分的文件
    if sortedBioCFiles:
        # 拆分BioC
        splitBioCFiles(sortedBioCFiles, splitOutDirs)
        # 修改拆分状态
        for splitOutDir in splitOutDirs:
            shutil.move(splitOutDir, splitOutDir.replace('.splitting', '.split'))
        # 删除BioC源文件
        for sortedBioCFile in sortedBioCFiles:
            os.remove(sortedBioCFile)
    else:
        Config.Logger.info(f"there are no {resource} BioC XML files to split")


if __name__ == '__main__':
    toolsInfo = getToolsYamlInfo()
    converts('PUBMED')
    splitBioC2ToolsDir('PUBMED', toolsInfo)
    converts('PMC')
    splitBioC2ToolsDir('PMC', toolsInfo)
