# -*- coding: utf-8 -*-
# @Time : 2022/8/20 12:34
# @File : NER.py
# @Project : OncoPubMinerMonitor
import math
import multiprocessing
import os
import re
import shutil
import time

import bioc
from bioc import BioCAnnotation, BioCLocation

from pub_miner import PubMinerDB, Config, save_json_data


def progressIsSuccessfullyExecuted(task_name, input_dir, output_dir, execute_failure_xml_dir):
    """Determine whether the program is successfully executed"""
    successFlag = True
    input_pub_xml_files = os.listdir(input_dir)
    if len(input_pub_xml_files) > 0:
        for pub_xml_filename in os.listdir(output_dir):
            if pub_xml_filename.startswith('.'):
                pub_xml_filename = pub_xml_filename[1:-4]
                if pub_xml_filename in input_pub_xml_files:
                    shutil.move(os.path.join(input_dir, pub_xml_filename),
                                os.path.join(execute_failure_xml_dir, pub_xml_filename))
                    Config.Logger.error(f'{task_name} execution failure for {pub_xml_filename}')
                    successFlag = False
    return successFlag


def progressFinishedExecuted(task_name, input_dir, output_dir, execute_failure_xml_dir):
    """识别完毕执行该命令"""
    if task_name == 'GNormPlus':
        exec_failure_files = set(os.listdir(input_dir)) - set(os.listdir(output_dir))
    else:
        exec_failure_files = set(os.listdir(input_dir)) - set([filename[:-9] for filename in os.listdir(output_dir)
                                                               if filename.endswith('.BioC.XML')])
    if len(exec_failure_files) > 0:
        Config.Logger.error(f'{task_name} execution failure total {len(exec_failure_files)} files')
        for exec_failure_file in exec_failure_files:
            shutil.copy(os.path.join(input_dir, exec_failure_file),
                        os.path.join(execute_failure_xml_dir, exec_failure_file))
            Config.Logger.error(f'{task_name} execution failure for {exec_failure_file}')


def cleanWorkDir(INPUT, OUTPUT):
    if INPUT:
        shutil.rmtree(INPUT)
    if OUTPUT:
        os.system(f'chmod -R 777 {OUTPUT}')
        if not os.path.exists(f'{OUTPUT}.ner'):
            shutil.move(OUTPUT, f'{OUTPUT}.ner')
        else:
            shutil.copytree(OUTPUT, f'{OUTPUT}.ner')
            shutil.rmtree(OUTPUT)
        os.system(f'chmod -R 777 {OUTPUT}.ner')


def diseaseNER(toolDir, resource, INPUT, OUTPUT, execute_failure_xml_dir):
    try:
        os.chdir(toolDir)
        os.makedirs(os.path.join(toolDir, f'{resource}_tmp'), exist_ok=True)
        os.system(f'./PollDNorm.sh config/banner_BC5CDR_UMLS2013AA_SAMPLE.xml data/CTD_diseases-2015-06-04.tsv output/'
                  f'simmatrix_BC5CDR_e4_TRAINDEV.bin AB3P_DIR {resource}_tmp {INPUT} {OUTPUT}')
        execute_result = progressIsSuccessfullyExecuted('DNorm', INPUT, OUTPUT, execute_failure_xml_dir)
        if not execute_result and len(os.listdir(INPUT)):
            diseaseNER(toolDir, resource, INPUT, OUTPUT, execute_failure_xml_dir)
        cleanWorkDir(INPUT, OUTPUT)
    except Exception as e:
        Config.Logger.error(f'disease_ner running error, resource: {resource}, input: {INPUT} \nERROR INFO: {str(e)}')


def chemicalNER(toolDir, resource, INPUT, OUTPUT, execute_failure_xml_dir):
    try:
        os.chdir(toolDir)
        os.makedirs(os.path.join(toolDir, f'{resource}_tmp'), exist_ok=True)
        os.system(f'./Run.sh config/banner_JOINT.xml data/dict.txt AB3P_DIR {resource}_tmp {INPUT} {OUTPUT}')
        execute_result = progressIsSuccessfullyExecuted('tmChem', INPUT, OUTPUT, execute_failure_xml_dir)
        if not execute_result and len(os.listdir(INPUT)):
            chemicalNER(toolDir, resource, INPUT, OUTPUT, execute_failure_xml_dir)
        cleanWorkDir(INPUT, OUTPUT)
    except Exception as e:
        Config.Logger.error(f'chemical_ner running error, resource: {resource}, input: {INPUT} \nERROR INFO: {str(e)}')


def mutationNER(toolDir, resource, INPUT, OUTPUT, execute_failure_xml_dir):
    try:
        os.chdir(toolDir)
        os.system(f'./tmVar.sh {INPUT} {OUTPUT}')
        progressFinishedExecuted('tmVar', INPUT, OUTPUT, execute_failure_xml_dir)
        cleanWorkDir(INPUT, OUTPUT)
    except Exception as e:
        Config.Logger.error(f'mutation_ner running error, resource: {resource}, input: {INPUT} \nERROR INFO: {str(e)}')


def geneNER(toolDir, resource, INPUT, OUTPUT, execute_failure_xml_dir):
    try:
        os.chdir(toolDir)
        os.system(f'java -Xmx50G -Xms50G -jar GNormPlus.jar {INPUT} {OUTPUT}')
        try_num = 1
        while len(set(os.listdir(INPUT)) - set(os.listdir(OUTPUT))) > 0 and try_num <= 5:
            os.system(f'./GNormPlus.sh {INPUT} {OUTPUT}')
            try_num += 1
        progressFinishedExecuted('GNormPlus', INPUT, OUTPUT, execute_failure_xml_dir)
        cleanWorkDir(INPUT, OUTPUT)
        os.rename(os.path.join(toolDir, 'tmp'), os.path.join(toolDir, 'tmp1'))
        os.makedirs(os.path.join(toolDir, 'tmp'))
        shutil.rmtree(os.path.join(toolDir, 'tmp1'))
    except Exception as e:
        Config.Logger.error(f'gene_ner running error, resource: {resource}, input: {INPUT} \nERROR INFO: {str(e)}')


def formatAnnotationIdentifier(annotation):
    # 格式化注释的identifier NAN数据改为-
    if 'Identifier' in annotation.infons:
        identifier = annotation.infons['Identifier']
        del annotation.infons['Identifier']
    elif 'identifier' in annotation.infons:
        identifier = annotation.infons['identifier']
    elif 'MESH' in annotation.infons:
        identifier = f'MESH:{annotation.infons["MESH"]}'
    elif 'OMIM' in annotation.infons:
        identifier = f'OMIM:{annotation.infons["OMIM"]}'
    elif 'CHEBI' in annotation.infons:
        identifier = f'CHEBI:{annotation.infons["CHEBI"]}'
    elif 'NCBI Gene' in annotation.infons:
        identifier = annotation.infons["NCBI Gene"]
    else:
        identifier = '-'
    annotation.infons['identifier'] = identifier if isinstance(identifier, str) else '-'
    return annotation


def modifyAnnotation(annotation, annotations, identifier_symbol, mesh_cancer_id_dict, do_identifier_symbol):
    try:
        if annotation.infons.get('type') in ['Chemical', 'Disease', 'Gene']:
            annotation.infons['type'] = annotation.infons['type'].lower()
        elif annotation.infons.get('type') in ['SNP', 'DNAMutation', 'ProteinMutation']:
            annotation.infons['type'] = 'mutation'
        else:
            return
        annotation = formatAnnotationIdentifier(annotation)
        if annotation.infons['type'] == 'disease':
            identifier, annotation_text = annotation.infons['identifier'], annotation.text.lower()
            if isCancerEntity(identifier, annotation_text, mesh_cancer_id=mesh_cancer_id_dict):
                do_identifiers = mesh_cancer_id_dict.get(identifier, [])
                annotation.infons['do_items'] = [{'do_identifier': do_identifier,
                                                  'do_symbol': do_identifier_symbol.get(do_identifier, '-')}
                                                 for do_identifier in do_identifiers]
            else:
                return
        # 如果当前注释和已有注释位置重叠或相交,返回None
        ann_start_offset, ann_length = annotation.locations[0].offset, annotation.locations[0].length
        ann_end_offset = ann_start_offset + ann_length
        for other_ann in annotations:
            other_ann_start_offset, other_ann_length = other_ann.locations[0].offset, other_ann.locations[0].length
            if ann_start_offset <= other_ann_start_offset < ann_end_offset or \
                    ann_start_offset < other_ann_start_offset + other_ann_length <= ann_end_offset:
                return
        # 格式化注释的identifier NAN数据改为-
        annotation = formatAnnotationIdentifier(annotation)

        symbols = [identifier_symbol.get(identifier) for identifier in annotation.infons['identifier'].split(';')
                   if identifier in identifier_symbol]
        annotation.infons['symbol'] = ';'.join(symbols) or '-'
        annotations.append(annotation)
    except Exception as e:
        Config.Logger.error(f'modify annotation error: {str(e)}')


def PADEvidenceAnnotation(evidence_dict, document_text, document_annotations, BioCXmlFile, evidence_pattern):
    # 添加证据注释
    try:
        start_pos = 0
        result = evidence_pattern.search(document_text, pos=start_pos)
        while result:
            offset = result.span()[0] + 1
            key = result.group()[1:-1]
            flag = False
            for annotation in document_annotations:
                ann_offset, ann_length = annotation.locations[0].offset, annotation.locations[0].length
                if ann_offset <= offset < (ann_offset + ann_length) or \
                        ann_offset < (offset + len(key)) <= (ann_offset + ann_length):
                    flag = True
                    break
            if not flag:
                normal = evidence_dict[key.lower()]['normalization']
                annotation = BioCAnnotation()
                annotation.text = key
                annotation.id = '1000'
                annotation.infons['type'] = evidence_dict[key.lower()]['label']
                annotation.infons['identifier'] = normal if normal and isinstance(normal, str) else '-'
                annotation.infons['symbol'] = normal if normal and isinstance(normal, str) else '-'
                annotation.locations = [BioCLocation(offset=offset, length=len(key))]
                document_annotations.append(annotation)
            result = evidence_pattern.search(document_text, pos=result.span()[1] - 1)
    except Exception as e:
        Config.Logger.error(f'file: {BioCXmlFile}, add evidence annotation Error: {str(e)}')


def mm(sentence, max_len, word_dict):
    """正向最大匹配算法"""
    result = []
    if not sentence or sentence is None:
        return []

    i = 0
    words = re.sub(r'\W', ' ', sentence).split(' ')
    words_lengths = [len(word) for word in words]
    while i < len(words):
        end = i + max_len if i + max_len < len(words) else len(words)
        temp = words[i]
        index = i
        for j in range(end, i, -1):
            chars = " ".join(words[i:j])
            if chars.lower() in word_dict:  # 词典分割
                start_pos = sum(words_lengths[:i]) + i
                end_pos = start_pos + len(chars)
                temp = (chars.lower(), start_pos, end_pos)
                index = j
                break
        if index == i:
            i += 1
        else:
            result.append(temp)
            i = index
    return result


def rePADAnnotation(passage, library_symbol_dict, passage_annotation_id, mesh_cancer_id_dict, do_identifier_symbols):
    # 补充漏掉的注释
    passage = sortedPassageAnnotation(passage, passage_annotation_id)
    new_annotations, delete_annotation_id_list = [], []
    results = mm(passage.text, 17, library_symbol_dict)
    for result in results:
        flag = False
        key, mention = result[0], passage.text[result[1]:result[2]]
        start_offset, end_offset = passage.offset + result[1], passage.offset + result[2]
        # 如果匹配到的原生词中[只包含小写字符，并且长度小于等于4]或[包含空格或者-之外的\W字符]或[只包含数字和\W字符]则过滤掉
        if (len(mention) <= 4 and mention.islower()) or re.search(r'[^a-zA-Z\d\s-]+|^[\d\W]+$', mention):
            flag = True
        # 如果该词是基因，匹配到的原生词中[包含两个连续的小写字母，并且长度小于等于10]则过滤掉
        elif library_symbol_dict[key.lower()]['type'] == 'gene' and len(key) <= 10 and re.search(r'[a-z]{2,}', mention):
            flag = True
        elif library_symbol_dict[key.lower()]['type'] in ['evidirt', 'clinsig']:
            # 判断是否与当前段落中的注释重叠
            for a_index, annotation in enumerate(passage.annotations):
                ann_start_offset = annotation.locations[0].offset
                ann_end_offset = ann_start_offset + annotation.locations[0].length
                if ann_start_offset <= start_offset < ann_end_offset or ann_start_offset < end_offset <= ann_end_offset:
                    flag = True
                    break
        else:
            # 判断是否与当前段落中的注释重叠
            for a_index, annotation in enumerate(passage.annotations):
                ann_start_offset = annotation.locations[0].offset
                ann_end_offset = ann_start_offset + annotation.locations[0].length
                # 如果在当前注释的后置位则继续遍历下一个注释
                if ann_end_offset <= start_offset:
                    continue
                # 如果包含当前注释 则添加新注释并删除当前注释及其后的所有出现交叉的注释 退出循环
                if (start_offset < ann_start_offset and end_offset >= ann_end_offset) or \
                        (start_offset <= ann_start_offset and end_offset > ann_end_offset):
                    delete_annotation_id_list.append(annotation.id)
                    for next_index in range(a_index + 1, len(passage.annotations)):
                        next_annotation = passage.annotations[next_index]
                        next_start_offset = next_annotation.locations[0].offset
                        next_end_offset = next_start_offset + next_annotation.locations[0].length
                        if next_start_offset >= end_offset:
                            break
                        elif next_start_offset < end_offset <= next_end_offset:
                            delete_annotation_id_list.append(next_annotation.id)
                            break
                        else:
                            delete_annotation_id_list.append(next_annotation.id)
                    break
                # 如果与当前注释交叉(如果当前注释为证据注释，删除当前注释，添加新注释，否则不添加新注释，也不删除当前注释）退出循环
                elif ann_start_offset <= start_offset <= ann_end_offset or \
                        ann_start_offset <= end_offset <= ann_end_offset:
                    # 如果当前注释为证据注释，删除当前注释，添加新注释
                    if annotation.infons['type'] in ['evidirt', 'clinsig']:
                        delete_annotation_id_list.append(annotation.id)
                    # 否则不添加新注释，也不删除当前注释
                    else:
                        flag = True
                    break
                # 如果在当前注释的前置位则退出循环
                elif ann_start_offset >= end_offset:
                    break
        if not flag:
            # 段落添加新注释
            new_annotation = BioCAnnotation()
            new_annotation.text = passage.text[result[1]:result[2]]
            new_annotation.id = '100000'
            symbol_dict = library_symbol_dict[key.lower()]
            new_annotation.infons = symbol_dict
            if symbol_dict['type'] == 'disease':
                do_identifiers = mesh_cancer_id_dict.get(symbol_dict['identifier'], [])
                new_annotation.infons['do_items'] = [{'do_identifier': do_identifier,
                                                      'do_symbol': do_identifier_symbols.get(do_identifier, '-')}
                                                     for do_identifier in do_identifiers]
            new_annotation.locations = [BioCLocation(offset=start_offset, length=len(key))]
            new_annotations.append(new_annotation)

    # 遍历剔除需要删除的注释
    annotations = passage.annotations if not delete_annotation_id_list else \
        [annotation for annotation in passage.annotations if annotation.id not in delete_annotation_id_list]
    annotations.extend(new_annotations)
    passage.annotations = annotations
    passage = sortedPassageAnnotation(passage, passage_annotation_id)
    passage_annotation_id = int(passage.annotations[-1].id) + 1 if passage.annotations else passage_annotation_id
    return passage, passage_annotation_id


def sortedPassageAnnotation(passage, passage_annotation_id):
    """将BioCPassage中的BioCAnnotation按照BioCLocation[offset]进行排序，并赋予BioCAnnotation新的id"""
    passage_annotation_dict = {annotation.locations[0].offset: annotation for annotation in passage.annotations}
    for i, offset in enumerate(sorted(passage_annotation_dict.keys())):
        annotation = passage_annotation_dict[offset]
        annotation.id = str(passage_annotation_id)
        passage.annotations[i] = annotation
        passage_annotation_id += 1
    return passage


def mergerXmlFileAnnotations(identifier_symbols, mesh_cancer_id, do_identifier_symbol, BioCXmlFile, second_dir,
                             resource, library_symbol_dict, tools_info, global_setting):
    """
    合并chemical_ner/disease_ner/mutation_ner/gene_ner结果，并添加证据注释
    :param identifier_symbols:
    :param mesh_cancer_id: mesh cancer id list
    :param do_identifier_symbol: do
    :param BioCXmlFile: BioCXml文件名
    :param second_dir: BioCXml文件所在目录
    :param resource: PUBMED/PMC
    :param library_symbol_dict: library标准词信息
    :param tools_info: 实体识别工具基本信息（工具名/工具路径）
    :param global_setting:
    :return:
    """
    resultDir = os.path.expanduser(global_setting["storage"]["result"])
    nerDir = os.path.expanduser(global_setting["storage"]["ner"])
    BioCPath = os.path.expanduser(global_setting["storage"]["upload"]["local-directory"])
    document_annotations = []
    try:
        for task_name in ['chemical_ner', 'mutation_ner', 'disease_ner', 'gene_ner']:
            # 依次获取chemical/mutation/disease/gene实体识别工具的识别结果并合并
            OutPutDir = f'{tools_info[task_name]["toolName"]}_OUTPUT'
            file_path = os.path.join(nerDir, OutPutDir, resource, second_dir,
                                     BioCXmlFile if task_name != 'mutation_ner' else f'{BioCXmlFile}.BioC.XML')
            annotations = []
            try:
                if os.path.exists(file_path):
                    reader = bioc.load(open(file_path, 'r', encoding='utf8'))
                    document = reader.documents[0]
                    annotations = [annotation for passage in document.passages for annotation in passage.annotations]
            except Exception as e:
                Config.Logger.error(f'extract annotation error, filepath: {file_path} error: {str(e)}')
            for annotation in annotations:
                modifyAnnotation(annotation, document_annotations, identifier_symbols, mesh_cancer_id,
                                 do_identifier_symbol)

        base_file = os.path.join(nerDir, f"{tools_info['disease_ner']['toolName']}_OUTPUT", resource, second_dir,
                                 BioCXmlFile)
        reader = bioc.load(open(base_file, 'r', encoding='utf8'))
        document = reader.documents[0]

        # 给注释按起始位置排序
        annotation_dict = {annotation.locations[0].offset: annotation for annotation in document_annotations}
        new_document_annotations = [annotation_dict[offset] for offset in sorted(annotation_dict.keys())]
        passage_annotation_id, annotation_index = 1, 0
        for passage in document.passages:
            passage.annotations = []
            passage_start_offset, passage_end_offset = passage.offset, passage.offset + len(passage.text)
            for index in range(annotation_index, len(new_document_annotations)):
                current_annotation = new_document_annotations[index]
                ann_start_offset = current_annotation.locations[0].offset
                if passage_start_offset <= ann_start_offset < passage_end_offset:
                    passage.annotations.append(current_annotation)
                elif ann_start_offset >= passage_end_offset:
                    annotation_index = index
                    break
            # 补充漏掉的实体
            passage, passage_annotation_id = rePADAnnotation(passage, library_symbol_dict, passage_annotation_id,
                                                             mesh_cancer_id, do_identifier_symbol)
            # 给句子分配注释
            passage_annotation_num = len(passage.annotations)
            start_annotation_index = 0
            for sentence in passage.sentences:
                sentence.annotations = []
                sent_start_offset, sent_end_offset = sentence.offset, sentence.offset + len(sentence.text)
                for ann_index in range(start_annotation_index, passage_annotation_num):
                    current_annotation = passage.annotations[ann_index]
                    ann_start_offset = current_annotation.locations[0].offset
                    ann_end_offset = ann_start_offset + current_annotation.locations[0].length
                    if sent_start_offset > ann_start_offset:
                        continue
                    if sent_start_offset <= ann_start_offset and sent_end_offset >= ann_end_offset:
                        sentence.annotations.append(current_annotation)
                    else:
                        start_annotation_index = ann_index
                        break
        # 合并注释后的文献BioC结果存储
        with bioc.BioCXMLDocumentWriter(os.path.join(resultDir, resource, second_dir, BioCXmlFile)) \
                as writer:
            writer.write_document(document)
        # BioC结果上传
        pid = document.id
        psd = str(math.ceil(int(pid) / 10000))
        BioCDocJsonFilePath = os.path.join(BioCPath, resource, f'{psd[-1]}/{psd}/'
                                                               f'{"PMC" if resource == "PMC" else ""}{pid}.json')
        save_json_data(BioCDocJsonFilePath, bioc.toJSON(document))
        for task_name in ['chemical_ner', 'mutation_ner', 'disease_ner', 'gene_ner']:
            # 依次删除chemical/mutation/disease/gene实体识别工具的识别结果文件
            OutPutDir = f'{tools_info[task_name]["toolName"]}_OUTPUT'
            file_path = os.path.join(nerDir, OutPutDir, resource, second_dir,
                                     BioCXmlFile if task_name != 'mutation_ner' else f'{BioCXmlFile}.BioC.XML')
            if os.path.exists(file_path):
                os.remove(file_path)
    except Exception as e:
        print(f'file:{BioCXmlFile} extract annotations error: {str(e)}')
    # 依次删除chemical/mutation/disease/gene实体识别工具的识别结果目录
    for task_name in ['chemical_ner', 'mutation_ner', 'disease_ner', 'gene_ner']:
        OutPutDir = f'{tools_info[task_name]["toolName"]}_OUTPUT'
        shutil.rmtree(os.path.join(nerDir, OutPutDir, resource, second_dir))


def mergerXMLFilesAnnotation(identifier_symbols, mesh_cancer_id, do_identifier_symbol, process_lock, BioCXmlFiles,
                             second_dir, resource, library_symbol_dict, file_num, tasks_info, global_setting):
    """多进程合并多任务实体识别结果"""
    while BioCXmlFiles:
        process_lock.acquire()
        if len(BioCXmlFiles) % 500 == 0:
            print(f'merge completed ratio: {round(1 - len(BioCXmlFiles) / file_num, 2)}%')
        BioCXmlFile = BioCXmlFiles.pop(0)
        process_lock.release()
        mergerXmlFileAnnotations(identifier_symbols, mesh_cancer_id, do_identifier_symbol, BioCXmlFile,
                                 second_dir, resource, library_symbol_dict, tasks_info, global_setting)


def isCancerEntity(identifier, annotation_text, mesh_cancer_id):
    """判断是否为癌症实体"""
    cancer_feature_words = ['cancer', 'tumor', 'neoplasm', 'carcinoma', 'tumour', 'malignancy', 'metastases',
                            'malignancies']
    if (identifier not in ['', '-'] and identifier in mesh_cancer_id) or \
            re.search(f'|'.join(cancer_feature_words), annotation_text):
        return True


def extractMeshCancerIdDict():
    db = PubMinerDB()
    cancer_infos = db.search_cancer_library_info()

    cancer_identifier_dict = {}
    for cancer_info in cancer_infos:
        cancer_identifier_dict[cancer_info[0]] = []
        if cancer_info[2]:
            identifiers = cancer_info[2].split('|')
            for identifier in identifiers:
                if identifier and identifier not in cancer_identifier_dict:
                    if identifier.startswith('DOID:'):
                        cancer_identifier_dict[cancer_info[0]].append(identifier)
                    else:
                        cancer_identifier_dict[identifier] = cancer_identifier_dict[cancer_info[0]]
    db.close()
    return cancer_identifier_dict


def extractLibraryIdentifierSymbol():
    db = PubMinerDB()
    library_infos = db.search_library_identifier_symbol()
    identifier_symbol_dict = {}
    # identifier, symbol
    for library_info in library_infos:
        identifier_symbol_dict[library_info[0]] = library_info[1]
    db.close()
    return identifier_symbol_dict


def extractCancerSymbolIdentifier():
    """cancer symbol identifier字典"""
    cancer_symbol_identifier_dict = {}
    cancer_path = './data/cancer.tsv'
    for line in open(cancer_path, 'r', encoding='utf-8').read().strip().split('\n')[1:]:
        fields = line.split('\t')
        synonyms = [fields[2]] + fields[5].split('|') if len(fields) >= 6 else [fields[2]]
        for synonym in synonyms:
            sub_str = re.sub(r'\W', ' ', synonym.lower())
            sub_str = re.sub(r'\s{2,}', ' ', sub_str)
            if sub_str and len(sub_str) >= 4:
                cancer_symbol_identifier_dict[sub_str] = {'identifier': fields[1], 'type': 'disease',
                                                          'symbol': fields[2]}
    return cancer_symbol_identifier_dict


def extractGeneSymbolIdentifier():
    """gene symbol identifier字典"""
    gene_symbol_identifier_dict = {}
    gene_path = './data/gene.tsv'
    with open('stopwords_gene', 'r', encoding='utf-8') as f:
        stop_genes = [stop_gene.lower() for stop_gene in f.read().split('\n')]
    for line in open(gene_path, 'r', encoding='utf-8').read().strip().split('\n')[1:]:
        fields = line.split('\t')
        synonyms = [fields[1]] + [synonym for field in fields[6:8] for synonym in field.split('|') if synonym]
        for synonym in synonyms:
            sub_str = re.sub(r'\W', ' ', synonym.lower())
            sub_str = re.sub(r'\s{2,}', ' ', sub_str)
            if sub_str and len(sub_str) >= 3 and sub_str not in stop_genes:
                gene_symbol_identifier_dict[sub_str] = {'identifier': fields[2], 'type': 'gene', 'symbol': fields[1]}
    return gene_symbol_identifier_dict


def extractChemicalSymbolIdentifier():
    """chemical symbol identifier字典"""
    chemical_symbol_identifier_dict = {}
    chemical_path = './data/chemical.tsv'
    for line in open(chemical_path, 'r', encoding='utf-8').read().strip().split('\n')[1:]:
        fields = line.split('\t')
        synonyms = [fields[2]] + fields[4].split('|') if len(fields) >= 5 else [fields[2]]
        for synonym in synonyms:
            # 替换非字母数字字符为空格
            sub_str = re.sub(r'\W', ' ', synonym.lower())
            # 替换两个以上的空格为一个空格
            sub_str = re.sub(r'\s{2,}', ' ', sub_str)
            if sub_str and len(sub_str) >= 4:
                chemical_symbol_identifier_dict[sub_str] = {'identifier': fields[1], 'type': 'chemical',
                                                            'symbol': fields[2]}
    chemical_symbol_identifier_dict['tyrosine kinase inhibitor'] = {'identifier': '-', 'type': 'chemical',
                                                                    'symbol': '-'}
    chemical_symbol_identifier_dict['tyrosine kinase inhibitors'] = {'identifier': '-', 'type': 'chemical',
                                                                     'symbol': '-'}
    chemical_symbol_identifier_dict['tki'] = {'identifier': '-', 'type': 'chemical', 'symbol': '-'}
    chemical_symbol_identifier_dict['tkis'] = {'identifier': '-', 'type': 'chemical', 'symbol': '-'}
    return chemical_symbol_identifier_dict


def extractDoIdentifierSymbol():
    with open('./data/doid.tsv', 'r', encoding='utf-8') as f:
        lines = f.read().strip().split('\n')[1:]
    do_identifier_symbol = {}
    for line in lines:
        fields = line.split('\t')
        do_identifiers = [fields[0]] + fields[2].split('|') if fields[2] != '-' else [fields[0]] + []
        if fields[1]:
            for do_identifier in do_identifiers:
                do_identifier_symbol[do_identifier] = fields[1]
    return do_identifier_symbol


def extractEvidenceDict():
    db = PubMinerDB()
    evidence_dict = {}
    evidence_infos = db.search_table_data('evidence_library', fields=['identifier', 'symbol', 'synonyms', 'type'])
    for evidence_info in evidence_infos:
        symbol = evidence_info[1]
        synonyms = [symbol] + evidence_info[2].split('|') if evidence_info[2] else [symbol]
        for synonym in set(synonyms):
            evidence_dict[synonym.lower()] = {'symbol': symbol,
                                              'identifier': evidence_info[0],
                                              'type': evidence_info[3]}
    db.close()
    return evidence_dict


def merger(second_dir, resource, tasks_info, global_setting):
    """合并多任务实体识别结果"""
    resultDir = os.path.expanduser(global_setting["storage"]["result"])
    nerDir = os.path.expanduser(global_setting["storage"]["ner"])
    if not os.path.exists(os.path.join(resultDir, resource, second_dir)):
        os.makedirs(os.path.join(resultDir, resource, second_dir))
    data_path = os.path.join(nerDir, 'DNorm_OUTPUT', resource, second_dir)
    _all_files = os.listdir(data_path)
    _length = len(_all_files)
    Config.Logger.info(f'Merge multi-task model recognition results second_dir: {second_dir}, total: {_length} files')
    _library_symbol_dicts = extractEvidenceDict()
    _library_symbol_dicts.update(extractCancerSymbolIdentifier())
    _library_symbol_dicts.update(extractGeneSymbolIdentifier())
    _library_symbol_dicts.update(extractChemicalSymbolIdentifier())
    start_time = time.time()
    with multiprocessing.Manager() as MG:  # 重命名
        lock = multiprocessing.Lock()
        identifier_symbol = MG.dict(extractLibraryIdentifierSymbol())  # 主进程与子进程共享这个字典
        mesh_cancer_id = MG.dict(extractMeshCancerIdDict())  # 主进程与子进程共享这个List
        do_identifier_symbol = MG.dict(extractDoIdentifierSymbol())
        library_symbol_dicts = MG.dict(_library_symbol_dicts)
        tasks_info = MG.dict(tasks_info)
        all_files = MG.list(_all_files)
        pool_list = []
        for _ in range(20):
            p = multiprocessing.Process(target=mergerXMLFilesAnnotation,
                                        args=(identifier_symbol, mesh_cancer_id, do_identifier_symbol, lock, all_files,
                                              second_dir, resource, library_symbol_dicts, _length, tasks_info,
                                              global_setting))
            pool_list.append(p)
        for p in pool_list:
            p.start()
        for p in pool_list:
            p.join()
        for p in pool_list:
            p.close()
    print('finished:', time.time() - start_time)
