## OncoPubMinerMonitor

    OncoPubMiner background monitor

###  config

    config.py: background monitoring configuration file

### pub_miner

    - DownloadShell: Download script directory
       - PMC.sh: PMC downloads the script file
       - PUBMED.sh: PUBMED downloads the script file
    - logs: Log directory
    - resources: resources directory
       - PMC.yml: PMC downloads the updated configuration
       - PUBMED.yml: PUBMED downloads the updated configuration
    config.py: Configuration files are required to start monitoring
    PubMiner.settings.default.yml: Configure the default YML file globally
    PubMinerNLP.yml: The entity recognition tool configures the default UML file
    get_resource.py 下载更新脚本
    FTPClient.py: FTPclient script  
    global_settings.py: Global configuration script
    PubMinerDatabase.py: Operate the PubMiner database script
    update_database.py: Updating database scripts
    NER.py: Entity recognition and standardization scripts
    upload.py: Script for uploading files
    pubrun.py: Execute the task entry script

### main

    main.py: Program launch entry script

### requirements.txt: Depend on the package

    pip3 install -r requirements.txt
    
### Aspera: Remote file download tool

    https://www.ibm.com/aspera/connect/

### tools
- tmChem: chemical tagger tool(https://www.ncbi.nlm.nih.gov/research/bionlp/Tools/tmchem/)
- DNorm: disease tagger tool(https://www.ncbi.nlm.nih.gov/research/bionlp/Tools/dnorm/)
- GNormPlus: gene/species tagger tool(https://www.ncbi.nlm.nih.gov/bionlp/Tools/gnormplus)
- tmVar: mutation tagger tool(https://www.ncbi.nlm.nih.gov/bionlp/Tools/tmvar)
- Remote file download tool Download the preceding tools to the specified path, ensure that the startup is successful, 
  and configure the path to (PubMiner.settings.default.yml storage/tools)

### Advice 
- ananconda3 is recommended
```bash
conda create -n pub_miner python=3.6
mkdir -p /data/project
cd /data/project
git clone https://github.com/ChosenMedInfo/oncopubminer-api.git
cd oncopubminer-api/OncoPubMinerMonitor
pip install -r requirements.txt
python main.py
```

