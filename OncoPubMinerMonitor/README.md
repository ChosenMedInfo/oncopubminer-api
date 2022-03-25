## OncoPubMinerMonitor

    OncoPubMiner后台监控

###  config

    config.py 启动监控需要配置文件

### pub_miner

    - DownloadShell  下载脚本目录
       - PMC.sh PMC下载脚本文件
       - PUBMED.sh PUBMED下载脚本文件
    - logs 日志目录
    - resources
       - PMC.yml    PMC下载更新配置
       - PUBMED.yml   PubMed下载更新配置
    config.py 启动监控需要配置文件
    PubMiner.settings.default.yml 全局配置默认yml文件
    PubMinerNLP.yml 实体识别工具配置默认uml文件
    get_resource.py 下载更新脚本
    FTPClient.py FTPclient脚本
    global_settings.py 全局配置脚本
    PubMinerDatabase.py 操作PubMiner数据库脚本
    update_database.py 更新数据库脚本
    NER.py 实体识别及标准化脚本
    upload.py 上传文件脚本
    pubrun.py 执行任务入口脚本

### main 监控脚本入口

    main.py 总监控运行入口脚本

### requirements.txt 依赖包

    pip3 install -r requirements.txt
    
### Aspera 远程NCBI FTP文件下载

    https://www.ibm.com/aspera/connect/

### tools
- tmChem: chemical tagger tool(https://www.ncbi.nlm.nih.gov/research/bionlp/Tools/tmchem/)
- DNorm: disease tagger tool(https://www.ncbi.nlm.nih.gov/research/bionlp/Tools/dnorm/)
- GNormPlus: gene/species tagger tool(https://www.ncbi.nlm.nih.gov/bionlp/Tools/gnormplus)
- tmVar: mutation tagger tool(https://www.ncbi.nlm.nih.gov/bionlp/Tools/tmvar)
- 下载以上工具到指定路径下，并确保启动运行成功，配置该路径到PubMiner.settings.default.yml的storage/tools中

### 建议
- 建议使用ananconda3
```bash
conda create -n pub_miner python=3.6
mkdir -p /data/project
cd /data/project
git clone https://github.com/ChosenMedInfo/oncopubminer-api.git
cd oncopubminer-api/OncoPubMinerMonitor
pip install -r requirements.txt
python main.py
```
