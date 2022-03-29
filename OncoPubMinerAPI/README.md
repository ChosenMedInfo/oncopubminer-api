## OncoPubMinerAPI

    OncoPubMiner background retrieval interface

###  config

    config.py: Background retrieval requires configuration files

### pub_miner

    - data: Data storage directory
    - logs: Log directory
    - PubMiner
    aspcheduler_job.py: Scheduled task script file
    config.py: Background retrieves configuration files
    manage.py: Background retrieval service startup script
    model.py: Database model design script

### manage.py

    manage.py: The background retrieval service starts running the entry script

### requirements.txt

    pip3 install -r requirements.txt

### Advise
```bash
cd oncopubminer-api/OncoPubMinerAPI
docker pull mysql
docker run --name mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=.. -d mysql
docker build -t onco_pub_miner_api .
docker run --name onco_pub_miner_api -p 9001:9001 --link mysql:mysql -d onco_pub_miner_api
```
