# -*- coding: utf-8 -*-
# @Time : 2021/8/19 14:34
# @File : pubrun.py
# @Project : OncoPubMinerMonitor
import datetime
import glob
import multiprocessing
import os
import re
import time

import pub_miner


def getResourceLocation(resource):
    """
    获取文件源路径
    :param resource: PUBMED/PMC
    :return:
    """
    globalSettings = pub_miner.get_global_settings(True)
    resourceDir = os.path.expanduser(globalSettings["storage"]["resources"])
    thisResourceDir = os.path.join(resourceDir, resource)
    return thisResourceDir


def getToolYamlInfo(directory, doTest):
    """
    :param directory:
    :param doTest:
    :return:
    """
    mode = "test" if doTest else "full"
    globalSettings = pub_miner.get_global_settings(True)
    os.chdir(directory)
    toolYamlFile = 'PubMinerNLP.yml'
    if not os.path.isfile(toolYamlFile):
        pub_miner.Config.Logger.error(f"Expected a {toolYamlFile} file in root of codebase")
        raise RuntimeError(f"Expected a {toolYamlFile} file in root of codebase")

    toolSettings = pub_miner.loadYAML(toolYamlFile)
    toolName = toolSettings["name"]

    workspaceDir = os.path.expanduser(globalSettings["storage"]["workspace"])
    workingDirectory = os.path.join(workspaceDir, toolName, mode)
    return mode, globalSettings, toolSettings, toolName, workspaceDir, workingDirectory


def getToolsYamlInfo():
    """
    :return:
    """
    toolYamlFile = 'PubMinerNLP.yml'
    if not os.path.isfile(toolYamlFile):
        pub_miner.Config.Logger.error(f"Expected a {toolYamlFile} file in root of codebase")
        raise RuntimeError(f"Expected a {toolYamlFile} file in root of codebase")

    toolSettings = pub_miner.loadYAML(toolYamlFile)
    tasksInfo = toolSettings['tasks']
    return tasksInfo


def makeDir(dir_path):
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        pub_miner.Config.Logger.info(f"making Directory: {dir_path}")


def makeWorkingDirectory(toolsInfo, globalSettings):
    """创建程序运行目录"""
    pub_miner.Config.Logger.info(f"making WorkingDirectory")
    makeDir(globalSettings['storage']['resources'])
    makeDir(globalSettings['storage']['workspace'])
    makeDir(globalSettings['storage']['tools'])
    makeDir(globalSettings['storage']['NERWorking'])
    makeDir(globalSettings['storage']['NERResult'])
    makeDir(globalSettings['upload']['local-directory'])

    for toolInfo in toolsInfo.values():
        for dir_name in ['INPUT', 'OUTPUT']:
            makeDir(os.path.join(globalSettings['storage']['NERWorking'], f"{toolInfo['toolName']}_{dir_name}"))


def findFiles(dirName):
    allFiles = [os.path.join(root, f) for root, dirs, files in os.walk(dirName) for f in files]

    nums = [re.findall('[0-9]+', f) for f in allFiles]
    nums = [0 if num == [] else int(num[-1]) for num in nums]
    sortedByNum = sorted(list(zip(nums, allFiles)))
    sortedFilePaths = [filepath for num, filepath in sortedByNum]
    return sortedFilePaths


def getPMCIDFromFilename(filename):
    """从文件名中提取pmc id"""
    PMCidSearch = re.search(r'PMC\d+', filename)
    if PMCidSearch:
        return PMCidSearch.group()
    else:
        return None


def task(task_name, resource, tasks_info, global_setting):
    """
    执行命名实体识别及合并结果上传任务
    :param task_name: 任务名称
    :param resource: PubMed/PMC
    :param tasks_info: 任务信息
    :param global_setting: 全局配置信息
    :return:
    """
    nerDir = os.path.expanduser(global_setting["storage"]["ner"])
    toolsDir = os.path.expanduser(global_setting["storage"]["tools"])
    if 'ner' in task_name:
        taskInfo = tasks_info[task_name]
        tool_name = taskInfo['toolName']
        toolDir = os.path.join(toolsDir, tool_name)
        executeFailDir = os.path.join(nerDir, f'{tool_name}_OUTPUT', 'execute_failure_xml_dir')
        toolINPUT = os.path.join(nerDir, f'{tool_name}_INPUT', resource)
        toolOUTPUT = os.path.join(nerDir, f'{tool_name}_OUTPUT', resource)
        while os.listdir(toolINPUT):
            # 子目录按时间升序排序
            pubInputDirs = sorted(glob.glob(os.path.join(toolINPUT, '*')),
                                  key=lambda x: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getctime(x))))
            for pubInputDir in pubInputDirs:
                basename = os.path.basename(pubInputDir)
                if not basename.endswith('.split'):
                    continue
                pubOutputDir = os.path.join(toolOUTPUT, basename)
                if not os.path.exists(pubOutputDir):
                    os.makedirs(pubOutputDir)
                if task_name == 'disease_ner':
                    pub_miner.diseaseNER(toolDir, resource, pubInputDir, pubOutputDir, executeFailDir)
                elif task_name == 'gene_ner':
                    pub_miner.geneNER(toolDir, resource, pubInputDir, pubOutputDir, executeFailDir)
                elif task_name == 'mutation_ner':
                    pub_miner.mutationNER(toolDir, resource, pubInputDir, pubOutputDir, executeFailDir)
                elif task_name == 'chemical_ner':
                    pub_miner.chemicalNER(toolDir, resource, pubInputDir, pubOutputDir, executeFailDir)
                else:
                    pub_miner.Config.Logger.error(f"Unknown ner task: {task_name}, {task_name} is not an accepted "
                                                  f"ner task. Options are: disease_ner/gene_ner/chemical_ner/"
                                                  f"gene_ner")
                    raise RuntimeError(f"Unknown ner task: {task_name}, {task_name} is not an accepted ner task. "
                                       f"Options are: disease_ner/gene_ner/chemical_ner/gene_ner")
            time.sleep(10 * 60)
    elif task_name == 'merger':
        GNormOUTPUT = os.path.join(nerDir, f'{tasks_info["gene_ner"]["toolName"]}_OUTPUT', resource)
        workspaceDir = os.path.expanduser(global_setting["storage"]["workspace"])
        resourceInfo = pub_miner.getResourceInfo(resource)
        while os.listdir(GNormOUTPUT):
            # 子目录按时间升序排序
            pubOutputDirs = sorted(glob.glob(os.path.join(GNormOUTPUT, '*')),
                                   key=lambda x: time.strftime('%Y-%m-%d %H:%M:%S',
                                                               time.localtime(os.path.getctime(x))),
                                   reverse=True)

            if len(pubOutputDirs) > 0 and pubOutputDirs[0].endswith('.split.ner'):
                pubOutputDir = pubOutputDirs[0]
                flag = True
                for task_name in ['mutation_ner', 'disease_ner', 'chemical_ner']:
                    OutPutDir = f'{tasks_info[task_name]["toolName"]}_OUTPUT'
                    if os.path.exists(os.path.join(nerDir, OutPutDir, resource, pubOutputDir)):
                        flag = False
                        break
                if flag and not os.listdir(os.path.join(workspaceDir, resourceInfo['BioCDir'])):
                    basename = os.path.basename(pubOutputDir)
                    pub_miner.merger(basename, resource, tasks_info, global_setting)
                    pub_miner.update_pub_ner_result(resource, basename)
            else:
                time.sleep(10 * 60)


def pub_run():
    # 如果.PubMiner_lock文件存在，退出程序（该文件存在说明已经存在pub_run运行未结束，所以退出程序）
    PubMinerLockPath = os.path.join(pub_miner.Config.root_path, pub_miner.Config.PubMinerLockFileName)
    if os.path.exists(PubMinerLockPath):
        pub_miner.Config.Logger.info('pub_run unfinished, wait next run')
        return
    open(PubMinerLockPath, 'w').close()
    # 获取实体识别工具信息
    toolsInfo = getToolsYamlInfo()
    # 获取全局配置信息
    globalSettings = pub_miner.get_global_settings(True)
    makeWorkingDirectory(toolsInfo, globalSettings)
    if datetime.datetime.now().hour == 3:
        resName = 'PUBMED'
    else:
        resName = 'PMC'
    pub_miner.Config.Logger.info(f"Getting resource {resName}")
    pub_miner.getResource(resName)
    pub_miner.Config.Logger.info(f"Running conversion {resName} to BioC XML")
    pub_miner.converts(resName)
    pub_miner.Config.Logger.info(f"Splitting BioC XML {resName}")
    pub_miner.splitBioC2ToolsDir(resName, toolsInfo)
    pub_miner.Config.Logger.info(f"Running update_database_base_info {resName}")
    pub_miner.update_pub_base_info(resName)
    pub_miner.Config.Logger.info(f"Running NER {resName}")
    pool_list = []
    for task_name in ['gene_ner', 'mutation_ner', 'disease_ner', 'chemical_ner', 'merger']:
        p = multiprocessing.Process(target=task, args=(task_name, resName, toolsInfo, globalSettings))
        pool_list.append(p)
    for p in pool_list:
        p.start()
    for p in pool_list:
        p.close()
    os.remove(PubMinerLockPath)


if __name__ == '__main__':
    _PubMinerLockPath = os.path.join(pub_miner.Config.root_path, pub_miner.Config.PubMinerLockFileName)
    if os.path.exists(_PubMinerLockPath):
        os.remove(_PubMinerLockPath)
    # 启动定时任务每日3:30/16:30更新
    from apscheduler.schedulers.blocking import BlockingScheduler

    # BlockingScheduler
    scheduler = BlockingScheduler()
    scheduler.add_job(pub_run, 'cron', hour='3, 16', minute=30)
    scheduler.start()
