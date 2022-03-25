# -*- coding: utf-8 -*-
# @Time : 2021/8/2 10:23
# @File : get_resource.py
# @Project : OncoPubMinerMonitor

import os
import shutil

import yaml
import gzip
import hashlib
import six
import ftputil
import tarfile
import glob
import json
import time

from Bio import Entrez

import pub_miner


def eutilsData(db, document_id):
    """
    下载指定id的pubmed或pmc文献数据
    :param db: PUBMED/PMCOA
    :param document_id: 指定id
    :return:
    """
    # Entrez.email = "jlever@bcgsc.ca"  # Always tell NCBI who you are
    Entrez.email = "2571032993@qq.com"  # Always tell NCBI who you are
    handle = Entrez.efetch(db=db, id=document_id, rettype="gb", retmode="xml")
    xml_data = handle.read()
    if isinstance(xml_data, bytes):
        xml_data = xml_data.decode('utf-8')
    return xml_data


def calcSHA256(filename):
    return hashlib.sha256(open(filename, 'rb').read()).hexdigest()


def checkFileSuffixFilter(filename, fileSuffixFilter):
    if fileSuffixFilter is None:
        return True
    elif filename.endswith('.xml.tar.gz') or filename.endswith('.tar.gz') or filename.endswith('.xml.gz'):
        return True
    elif fileSuffixFilter and filename.endswith(fileSuffixFilter):
        return True
    else:
        return False


def download(url, out, resource, fileSuffixFilter=None):
    if url.startswith('ftp'):
        url = url.replace("ftp://", "")
        hostname = url.split('/')[0]
        path = "/".join(url.split('/')[1:])
        downloadFiles = downloadFTP(path, out, hostname, resource, fileSuffixFilter)
        return downloadFiles
    else:
        raise RuntimeError("Unsure how to download file. Expecting URL to start with ftp. Got: %s" % url)


def downloadFTP(path, out, hostname, resource, fileSuffixFilter=None, tries=10):
    assert os.path.isdir(out)
    download_paths = []
    pub_miner.Config.Logger.info(f'downloadFTP(path={path},out={out},hostname={hostname})')
    host = ftputil.FTPHost(hostname, 'anonymous', 'secret')

    if host.path.isdir(path):
        root = path
    else:
        root = None

    toProcess = [path]

    # 添加需要下载的远程文件信息到下载列表中
    while len(toProcess) > 0:
        path = toProcess.pop(0)

        success = False
        for tryNo in range(tries):
            try:
                # 判断远程路径是否为文件或者目录，
                # 如果是文件 判断格式/时间，判断通过添加到下载列表中；如果是目录，遍历该目录下的所有文件，添加到下载列表中
                if host.path.isfile(path):
                    remoteTimestamp = host.path.getmtime(path)

                    doDownload = True
                    if not checkFileSuffixFilter(path, fileSuffixFilter):
                        doDownload = False

                    if root:
                        assert path.startswith(root)
                        withoutRoot = path[len(root):].lstrip('/')
                        outFile = os.path.join(out, withoutRoot)
                    else:
                        outFile = os.path.join(out, host.path.basename(path))

                    if os.path.isfile(outFile):
                        localTimestamp = os.path.getmtime(outFile)
                        if not remoteTimestamp > localTimestamp:
                            doDownload = False

                    if outFile.endswith('.gz'):
                        outUnzipped = outFile[:-3]
                        if os.path.isfile(outUnzipped):
                            localTimestamp = os.path.getmtime(outUnzipped)
                            if not remoteTimestamp > localTimestamp:
                                doDownload = False

                    # 检查文件父目录是否存在，如果需要就创建目录
                    dirName = os.path.dirname(outFile)
                    if not os.path.isdir(dirName):
                        os.makedirs(dirName)

                    if doDownload:
                        pub_miner.Config.Logger.info(f" Download {path}")
                        pub_miner.Config.Logger.info(f"path={path}, outFile={outFile}")
                        remoteSize = host.path.getsize(path)
                        download_paths.append([path, outFile, remoteSize, remoteTimestamp])
                elif host.path.isdir(path):
                    pub_miner.Config.Logger.info(f"DIR {path}")
                    children = [host.path.join(path, child) for child in host.listdir(path)]
                    toProcess += children
                else:
                    pub_miner.Config.Logger.error(f"Path ({path}) is not a file or directory")
                success = True
                break
            except ftputil.error.FTPOSError as e:
                err_info = str(e.errno) + ' ' + str(e.strerror)
                pub_miner.Config.Logger.info(f"Try {tryNo + 1} for {hostname}/{path}: "
                                             f"Received FTPOSError({err_info})")
                time.sleep((tryNo + 1) * 2)
                if not host.closed:
                    host.close()
                host = ftputil.FTPHost(hostname, 'anonymous', 'secret')
                toProcess.insert(0, path)

        if not success:
            pub_miner.Config.Logger.error(f"Unable to download {path}")

    if not host.closed:
        host.close()
    outFiles = []
    pub_miner.Config.Logger.info(f'download {len(download_paths)} file...')
    ChosenLitReviewerTmpListPath = os.path.join(pub_miner.__path__[0], 'tmp', f'{resource}.txt')
    ChosenLitReviewerDownloadShellPath = os.path.join(pub_miner.__path__[0], 'DownShell', f'{resource}.sh')
    for tryNo in range(tries):
        with open(ChosenLitReviewerTmpListPath, 'w', encoding='utf-8') as f:
            f.write('\n'.join([download_path[0] for download_path in download_paths]))
        os.system(f'{ChosenLitReviewerDownloadShellPath} {ChosenLitReviewerTmpListPath} {out}')
        os.remove(ChosenLitReviewerTmpListPath)
        new_download_paths = []
        for download_path in download_paths:
            localFile = download_path[1]
            if os.path.isfile(localFile):
                localSize = os.path.getsize(localFile)
                if localSize < download_path[2]:
                    os.remove(localFile)
                    new_download_paths.append(download_path)
                else:
                    os.utime(download_path[1], (download_path[3], download_path[3]))
                    outFiles.append(download_path[1])
            else:
                new_download_paths.append(download_path)
        if new_download_paths:
            download_paths = new_download_paths
        else:
            download_paths = []
            break
    if download_paths:
        pub_miner.Config.Logger.error(f"Unable to download:"
                                      f"{', '.join([download_path[0] for download_path in download_paths])}")
    return outFiles


def gunzip(source, dest, deleteSource=False):
    timestamp = os.path.getmtime(source)
    with gzip.open(source, 'rb') as f_in, open(dest, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.utime(dest, (timestamp, timestamp))

    if deleteSource:
        os.unlink(source)


# https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunks(li, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(li), n):
        yield li[i:i + n]


def getResourceInfo(resource):
    ChosenLitReviewerResourcePath = os.path.join(pub_miner.__path__[0], 'resources', f'{resource}.yml')
    projectResourcePath = os.path.join('resources', f'{resource}.yml')

    options = [ChosenLitReviewerResourcePath, projectResourcePath]
    for option in options:
        if os.path.isfile(option):
            with open(option) as f:
                resourceInfo = yaml.safe_load(f)
            return resourceInfo
    pub_miner.Config.Logger.error(f"Unable to find resource YAML file for resource: {resource}")


def generateFileListing(thisResourceDir):
    listing = glob.glob(thisResourceDir + '/**', recursive=True)
    with open(f'{thisResourceDir}.listing.json', 'w') as f:
        json.dump(listing, f)


def getResource(resource):
    """更新下载ncbi远程资源并解压或者本地资源直接使用"""
    pub_miner.Config.Logger.info(f"Fetching resource: {resource}")

    globalSettings = pub_miner.get_global_settings(True)
    resourceDir = os.path.expanduser(globalSettings["storage"]["resources"])
    resourceInfo = getResourceInfo(resource)
    thisResourceDir = os.path.join(resourceDir, resource, resourceInfo['zipDir'])
    unzipDir = os.path.join(resourceDir, resource, resourceInfo['unzipDir'])
    unzipNewDir = os.path.join(resourceDir, resource, resourceInfo['unzipNewDir'])

    if resourceInfo['type'] == 'remote':
        # 下载地址列表
        URL = resourceInfo['url']
        assert isinstance(URL, six.string_types) or isinstance(URL, list), \
            'The URL for a remote resource must be a single or multiple addresses'
        urls = [URL] if isinstance(URL, six.string_types) else URL

        # 过滤文件条件(根据后缀过滤文件如.xml)
        fileSuffixFilter = resourceInfo['filter'] if 'filter' in resourceInfo else None
        # 创建文件夹如果不存在（保存下载文件）
        if not os.path.isdir(thisResourceDir):
            pub_miner.Config.Logger.info(f'Creating directory: {thisResourceDir} ...')
            os.makedirs(thisResourceDir)

        pub_miner.Config.Logger.info(f'Starting download {resource} ...')
        downloadFiles = []
        # 下载文件
        for url in urls:
            assert isinstance(url, six.string_types), 'Each URL for the dir resource must be a string'
            zipFiles = download(url, thisResourceDir, resource, fileSuffixFilter)
            if zipFiles:
                downloadFiles.extend(zipFiles)
        # 解压文件
        if 'unzip' in resourceInfo and resourceInfo['unzip']:
            pub_miner.Config.Logger.info(f"Unzipping files ...")
            for filename in downloadFiles:
                if 'baseline' in filename:
                    pub_miner.Config.Logger.info(f'skipping {filename} ...')
                pub_miner.Config.Logger.info(f'Unzipping {filename} ...')
                if filename.endswith('.tar.gz') or filename.endswith('.tgz'):
                    tar = tarfile.open(os.path.join(thisResourceDir, filename), "r:gz")
                    tar.extractall(unzipDir)
                    tar.close()
                    NewTar = tarfile.open(os.path.join(thisResourceDir, filename), "r:gz")
                    NewTar.extractall(unzipNewDir)
                    NewTar.close()
                elif filename.endswith('.gz'):
                    unzippedName = os.path.basename(filename)[:-3]
                    gunzip(os.path.join(thisResourceDir, filename), os.path.join(unzipDir, unzippedName))
                    gunzip(os.path.join(thisResourceDir, filename), os.path.join(unzipNewDir, unzippedName))
            # 根据文件后缀过滤文件
            if fileSuffixFilter is not None:
                pub_miner.Config.Logger.info(f" Removing files not matching filter ({fileSuffixFilter}) ...")
                for root, _, files in os.walk(unzipNewDir):
                    for f in files:
                        if not f.endswith(fileSuffixFilter):
                            full_path = os.path.join(root, f)
                            os.unlink(full_path)
    elif resourceInfo['type'] == 'local':
        assert isinstance(resourceInfo['directory'], six.string_types) and os.path.isdir(
            resourceInfo['directory']), 'The directory for a remote resource must be a string and exist'

        if not os.path.islink(thisResourceDir) and os.path.isdir(thisResourceDir):
            shutil.rmtree(thisResourceDir)

        if not os.path.islink(thisResourceDir):
            os.symlink(resourceInfo['directory'], thisResourceDir)
    else:
        pub_miner.Config.Logger.error(f"Unknown resource type ({resourceInfo['type']}) for resource: {resource}")


if __name__ == '__main__':
    pub_miner.Config.Logger.info('start')
    getResource('PUBMED')
    getResource('PMC')
    pub_miner.Config.Logger.info('finish')
