# -*- coding: utf-8 -*-
# @Time : 2021/10/18 12:26
# @File : model.py
# @Project : OncoPubMinerAPI
from PubMiner import db


class Journal(db.Model):
    # 杂志基本信息表
    # 定义表名
    __tablename__ = "journal"
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    # 定义列对象
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    name = db.Column(db.String(1024), comment='杂志全称')
    iso = db.Column(db.String(1024), nullable=False, comment='杂志缩写名')
    other_iso = db.Column(db.Text, nullable=False, comment='杂志其他缩写名以 | 隔开')
    impact_factor = db.Column(db.Float, default=0.0, comment='杂志影响因子')


class PubMed(db.Model):
    # pubmed/pmc文献基本信息表
    __tablename__ = 'pubmed'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, comment='PubMed文献id')
    pmc_id = db.Column(db.String(16), index=True, comment='PMC文献id')
    doi = db.Column(db.String(128), index=True, comment='doi文献id')
    journal_id = db.Column(db.Integer, index=True, comment='杂志id')
    year = db.Column(db.Integer, index=True, comment='年份')
    kwds = db.Column(db.Text, comment='关键词')
    is_cancer = db.Column(db.Boolean, default=False, comment='是否是癌症文献')
    has_abstract = db.Column(db.Boolean, default=True, comment='是否有摘要')
    pubmed_json_path = db.Column(db.String(256), comment='bioc json文献路径')
    pmc_json_path = db.Column(db.String(256), comment='pmc bioc json文献路径')
    has_annotation = db.Column(db.Boolean, default=False, comment='是否是被标注过')


class NewPub(db.Model):
    """
    1. 新增数据库表，记录每日更新的文献的信息，字段如下：
    1）更新日期（pub_date，数据库表中以时间格式记录，前端有可能就只显示到日期）；
    2）更新类型（pub_type）：新增的文献，或者已有文献的更新；
    3）PMID或者PMCID（pub_id）；
    4）文献标题（pub_title）；
    5）作者列表（pub_authors）（用英文逗号或者英文分号分隔）；
    6）期刊（pub_journal）；
    7）发表年份（pub_year）。

    2. 新增相应查询接口：
        1）允许利用对上述各个字段进行模糊查询，传递多个参数的话用“AND”连接查询；
        2）参数举例：page=1&limit=10&sortBy=pmid&orderBy=asc&pubTitle=EGFR&pubYear=2020...

    3. 备注：不需要加入之前已更新的文献，就从功能上线后开始记录即可。
    """
    # pubmed/pmc文献每日更新信息表
    __tablename__ = 'pub_updates'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键')
    pub_id = db.Column(db.Integer, unique=True, comment='PubMed/PMC文献id')
    pub_date = db.Column(db.Integer, index=True, comment='更新日期, 以时间格式记录')
    pub_type = db.Column(db.String(16), comment='New or updated')
    pub_title = db.Column(db.String(2048), comment='文献标题')
    pub_authors = db.Column(db.String(2048), comment='作者列表')
    pub_journal = db.Column(db.String(512), comment='期刊名称')
    pub_year = db.Column(db.Integer, comment='发表年份')


class CiteCitedSimilarPubMed(db.Model):
    # 杂志自相关信息表(引用/被引用/相似)
    __tablename__ = 'cite_cited_similar_relationship'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    pubmed_id = db.Column(db.Integer, unique=True, comment='pubmed外键id')
    cite = db.Column(db.Text, comment='引用的文档以 | 隔开')
    cited = db.Column(db.Text, comment='引用的文档以 | 隔开')
    cite_num = db.Column(db.Integer, comment='引用文献的数量')
    cited_num = db.Column(db.Integer, comment='文献被引用的数量')
    similar = db.Column(db.Text, comment='引用的文档以 | 隔开')
    timestamp = db.Column(db.Integer, comment='时间戳')


class Author(db.Model):
    # 作者信息表
    __tablename__ = 'author'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    name = db.Column(db.String(32), nullable=False, comment='简称')


class AuthorPubMed(db.Model):
    # 文献关键词基本信息表
    __tablename__ = 'author_pubmed'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    author_id = db.Column(db.Integer, unique=True, comment='author外键ID')
    pubmeds = db.Column(db.Text, comment='标准库关联的PubMed')


class PubMedAuthor(db.Model):
    # 文献关键词基本信息表
    __tablename__ = 'pubmed_author'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    pubmed_id = db.Column(db.Integer, unique=True, comment='pubmed外键ID')
    authors = db.Column(db.Text, comment='pubmed关联的author信息')


class Library(db.Model):
    # 文献关键词基本信息表
    __tablename__ = 'library'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    identifier = db.Column(db.String(64), unique=True, comment='mesh标准库id')
    symbol = db.Column(db.String(2048), comment='标准词')
    synonyms = db.Column(db.Text, comment='同义词')
    label = db.Column(db.SmallInteger, default=0, nullable=False,
                      comment='类别:Gene 0 Disease 1 Chemical 2 Mutation 3')


class GeneLibrary(db.Model):
    # 基因标准库
    __tablename__ = 'gene_library'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    identifier = db.Column(db.String(64), comment='mesh标准库id')
    symbol = db.Column(db.String(128), comment='标准词')
    synonyms = db.Column(db.Text, comment='同义词')
    HGNC_identifier = db.Column(db.String(32), comment='HGNC标准id')
    MIM_identifier = db.Column(db.String(32), comment='HGNC标准id')
    Ensembl_identifier = db.Column(db.String(32), comment='Ensembl标准id')
    full_name = db.Column(db.String(512), comment='全称')
    description = db.Column(db.Text, default='', comment='描述')
    library_id = db.Column(db.Integer, db.ForeignKey('library.id'), comment='library外键')


class ChemLibrary(db.Model):
    # 化学物标准库
    __tablename__ = 'chemical_library'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    identifier = db.Column(db.String(64), comment='mesh标准库id')
    symbol = db.Column(db.String(512), comment='标准词')
    synonyms = db.Column(db.Text, comment='同义词')
    parent_identifier = db.Column(db.String(512), comment='父类identifier')
    description = db.Column(db.Text, default='', comment='描述')
    library_id = db.Column(db.Integer, db.ForeignKey('library.id'), comment='library外键')


class CancerLibrary(db.Model):
    # 癌症标准库
    __tablename__ = 'cancer_library'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    identifier = db.Column(db.String(64), comment='mesh标准库id')
    symbol = db.Column(db.String(512), comment='标准词')
    synonyms = db.Column(db.Text, comment='同义词')
    other_identifiers = db.Column(db.String(2048), comment='其他标准库id')
    description = db.Column(db.Text, comment='描述')
    library_id = db.Column(db.Integer, db.ForeignKey('library.id'), comment='library外键')


class LibraryPubMed(db.Model):
    # 文献关键词基本信息表
    __tablename__ = 'library_pubmed'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    library_id = db.Column(db.Integer, unique=True, comment='library外键')
    pubmeds = db.Column(db.Text, comment='标准库关联的PubMed')
    length = db.Column(db.Integer, comment='关联的PubMed文献个数')


class LibraryPubMedSortInfo(db.Model):
    # 文献关键词基本信息表
    __tablename__ = 'library_pubmed_sort_info'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    library_id = db.Column(db.Integer, unique=True, comment='library外键')
    pubmed_sort_infos = db.Column(db.Text, comment='标准库关联的PubMed排序需要的详细信息')


class PubMedLibrary(db.Model):
    # 文献关键词基本信息表
    __tablename__ = 'pubmed_library'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    pubmed_id = db.Column(db.Integer, unique=True, comment='pubmed外键')
    library = db.Column(db.Text, comment='PubMed关联的library信息')


class Mention(db.Model):
    # 文献关键词基本信息表
    __tablename__ = 'mentions'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    mention = db.Column(db.String(64), nullable=False, unique=True, comment='原生词')


class MentionPubMed(db.Model):
    # 标准词文献关联信息表
    __tablename__ = 'mention_pubmed'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    mention_id = db.Column(db.Integer, unique=True, comment='标准词ID')
    pubmeds = db.Column(db.Text, comment='文章原生词关联的PubMed')
    length = db.Column(db.Integer, comment='关联的PubMed文献个数')


class MentionPubMedSortInfo(db.Model):
    # 标准词文献关联信息排序表
    __tablename__ = 'mention_pubmed_sort_info'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    mention_id = db.Column(db.Integer, unique=True, comment='标准词ID')
    pubmed_sort_infos = db.Column(db.Text, comment='标准库关联的PubMed排序需要的详细信息')


class PubMedMention(db.Model):
    # 文献标准词关联信息表
    __tablename__ = 'pubmed_mention'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    pubmed_id = db.Column(db.Integer, unique=True, comment='标准词ID')
    mentions = db.Column(db.Text, comment='pubmed关联的文章原生词')


class GeneCancerRelationShip(db.Model):
    # 基因-癌症关联信息表
    __tablename__ = 'gene_cancer_relationship'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    gene = db.Column(db.String(64), comment='基因标准词')
    cancer = db.Column(db.String(1024), comment='癌症标准词')
    num = db.Column(db.Integer, comment='当前关系在句子中出现的次数')


class GeneChemicalRelationShip(db.Model):
    # 基因-化合物/药物关联信息表
    __tablename__ = 'gene_chemical_relationship'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    gene = db.Column(db.String(64), comment='基因标准词')
    chemical = db.Column(db.String(1024), comment='化合物/药物标准词')
    num = db.Column(db.Integer, comment='当前关系在句子中出现的次数')


class CancerChemicalRelationShip(db.Model):
    # 癌症-化合物/药物关联信息表
    __tablename__ = 'cancer_chemical_relationship'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    cancer = db.Column(db.String(1024), comment='癌症标准词')
    chemical = db.Column(db.String(1024), comment='化合物/药物标准词')
    num = db.Column(db.Integer, comment='当前关系在句子中出现的次数')


class GeneGeneRelationShip(db.Model):
    # 基因-基因关联信息表
    __tablename__ = 'gene_gene_relationship'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, comment='自增主键')
    gene_1 = db.Column(db.String(64), comment='基因标准词')
    gene_2 = db.Column(db.String(64), comment='基因标准词')
    num = db.Column(db.Integer, comment='当前关系在句子中出现的次数')


class CancerCancerRelationShip(db.Model):
    # 癌症-癌症关联信息表
    __tablename__ = 'cancer_cancer_relationship'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    cancer_1 = db.Column(db.String(1024), comment='癌症标准词')
    cancer_2 = db.Column(db.String(1024), comment='癌症标准词')
    num = db.Column(db.Integer, comment='当前关系在句子中出现的次数')


class ChemicalChemicalRelationShip(db.Model):
    # 化合物-化合物关联信息表
    __tablename__ = 'chemical_chemical_relationship'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    chemical_1 = db.Column(db.String(64), comment='基因标准词')
    chemical_2 = db.Column(db.String(1024), comment='癌症标准词')
    num = db.Column(db.Integer, comment='当前关系在句子中出现的次数')


class ThreeLibraryRelationShip(db.Model):
    # 三个标准词关联信息表
    __tablename__ = 'three_library_relationship'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    library_1 = db.Column(db.String(1024), comment='基因标准词')
    label_1 = db.Column(db.SmallInteger, comment='第一个标准词的类型 0: 基因 1: 癌种 2: 化合物')
    library_2 = db.Column(db.String(1024), comment='基因标准词')
    label_2 = db.Column(db.SmallInteger, comment='第二个标准词的类型 0: 基因 1: 癌种 2: 化合物')
    library_3 = db.Column(db.String(1024), comment='基因标准词')
    label_3 = db.Column(db.SmallInteger, comment='第三个标准词的类型 0: 基因 1: 癌种 2: 化合物')
    num = db.Column(db.Integer, comment='当前关系在句子中出现的次数')


class Stat(db.Model):
    # 文献标准词关联信息表
    __tablename__ = 'stat'
    __table_args__ = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  # 设置引擎、字符集
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='自增主键')
    statAbstracts = db.Column(db.Integer, comment='PUBMED文献总量(包含摘要)')
    statFullTexts = db.Column(db.Integer, comment='PMC文献总量')
    statEntityPubPairs = db.Column(db.BigInteger, comment='实体-文献对数量')
    statPubMed = db.Column(db.Integer, comment='PUBMED文献总量(包含摘要)')
    statPMC = db.Column(db.Integer, comment='PUBMED文献总量(包含摘要)')
    statCancers = db.Column(db.Integer, comment='PUBMED文献总量(包含摘要)')
    version = db.Column(db.String(32), comment='当前系统版本号')
