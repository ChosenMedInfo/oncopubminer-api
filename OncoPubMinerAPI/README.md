## OncoPubMinerAPI

    OncoPubMiner后台检索接口

###  config

    config.py 后台检索需要配置文件

### pub_miner

    - data  数据存放目录
    - logs 日志目录
    - PubMiner
    aspcheduler_job.py 定时任务脚本文件
    config.py 配置文件
    manage.py 后台检索服务启动脚本
    model.py 数据库模型设计

### manage.py 后台检索服务启动脚本入口

    manage.py 后台检索服务启动运行入口脚本

### requirements.txt 依赖包

    pip3 install -r requirements.txt

### 建议
```bash
cd oncopubminer-api/OncoPubMinerAPI
docker pull mysql
docker run --name mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=.. -d mysql
docker build -t onco_pub_miner_api .
docker run --name onco_pub_miner_api -p 9001:9001 --link mysql:mysql -d onco_pub_miner_api
```
