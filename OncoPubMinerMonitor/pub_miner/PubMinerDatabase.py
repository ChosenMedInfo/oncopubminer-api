# -*- coding: utf-8 -*-
# @Time : 2021/8/17 11:12
# @File : MysqlDatabase.py
# @Project : OncoPubMinerMonitor

import pymysql

from pub_miner import Config


class PubMinerDB:
    def __init__(self):
        try:
            self.con = pymysql.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USERNAME,
                passwd=Config.DB_PASSWORD,
                db=Config.DB_NAME,  # 数据库名
                charset='utf8mb4'
            )
        except pymysql.Error as e:
            Config.Logger.error("db connection Error %d：%s" % (e.args[0], e.args[1]))
            exit()
        self.cursor = self.con.cursor()  # 创建游标对象

    # 增加信息
    def insert_data(self, sql, data=None):
        if data is None:
            data = []
        try:
            # 插入一条数据
            self.cursor.execute(sql, data)
            self.con.commit()
        except Exception as e:
            self.con.rollback()
            Config.Logger.error(f"sql: {sql} execute Error {str(e.args[0])}: {str(e.args[1])}")

    # 插入多条数据
    def insert_many_data(self, sql, data=None):
        if data is None:
            data = []
        try:
            # 插入多条数据
            self.cursor.executemany(sql, data)
            self.con.commit()
        except Exception as e:
            self.con.rollback()
            Config.Logger.error(f"sql: {sql} execute Error {str(e.args[0])}: {str(e.args[1])}")

    # 更新信息
    def update(self, sql):
        try:
            self.cursor.execute(sql)
            self.con.commit()
        except Exception as e:
            self.con.rollback()
            Config.Logger.error(f"sql: {sql} execute Error {str(e.args[0])}: {str(e.args[1])}")

    # 更新信息
    def update_data(self, sql, data):
        try:
            self.cursor.execute(sql, data)
            self.con.commit()
        except Exception as e:
            self.con.rollback()
            Config.Logger.error(f"sql: {sql} execute Error {str(e.args[0])}: {str(e.args[1])}")

    # 批量更新
    def update_many(self, sql, data):
        try:
            self.cursor.executemany(sql, data)
            self.con.commit()
        except Exception as e:
            self.con.rollback()
            Config.Logger.error(f"sql: {sql} execute Error {str(e.args[0])}: {str(e.args[1])}")

    # 删除信息
    def delete(self, sql):
        try:
            self.cursor.execute(sql)
            self.con.commit()
        except Exception as e:
            self.con.rollback()
            Config.Logger.error(f"sql: {sql} execute Error {str(e.args[0])}: {str(e.args[1])}")

    # 查询一条信息
    def search_one(self, sql):
        try:
            self.cursor.execute(sql)
            res = self.cursor.fetchone()
            return res
        except Exception as e:
            Config.Logger.error(f"sql: {sql} execute Error {str(e.args[0])}: {str(e.args[1])}")

    def search_journal(self, query_str, query_type='name'):
        try:
            if query_type == 'name':
                sql = f'select * from journal where name="{query_str}";'
            else:
                sql = f'select * from journal where iso="{query_str}";'
            return self.search_one(sql)
        except Exception as e:
            print(f'query journal Error: {e}')

    def insert_journal(self, journal_name, journal_iso, other_iso='', impact_factor=0.0):
        try:
            insert_sql = 'INSERT IGNORE INTO journal (name, iso, other_iso, impact_factor) values(%s, %s, %s, %s)'
            self.insert_data(insert_sql, [journal_name, journal_iso, other_iso, impact_factor])
        except Exception as e:
            print(f'insert journal Error: {e}')

    def search_journal_id(self, name, iso):
        try:
            if name:
                res = self.search_journal(name)
                if not res:
                    self.insert_journal(name, iso)
                    res = self.search_journal(name)
                journal_id = res[0]
            elif iso:
                res = self.search_journal(iso, query_type='iso')
                if res:
                    journal_id = res[0]
                else:
                    journal_id = 1
            else:
                journal_id = 1
            return journal_id
        except Exception as e:
            print(f'search journal id Error: {e}')

    # 查询全部信息
    def search_all(self, sql):
        try:
            self.cursor.execute(sql)
            res = self.cursor.fetchall()
        except Exception as e:
            print(f"sql: {sql} execute Error " + e.args[0], e.args[1])
            return []
        for r in res:
            yield r

    def search_table_data(self, table_name, fields=None, condition=None, count=None):
        """
        简单查询语句拼接
        :param count: 查询多少行数据, 如果为1，则查询一条数据符合条件的数据，否则查询所有符合条件的数据
        :param table_name: 表名
        :param fields: 字段名【字段1，字段2...】
        :param condition: 条件 只支持简单的条件
        :return:
        """
        if fields is None:
            fields = []
        try:
            fields = ', '.join(fields) or '*'
            sql = f"select {fields} from {table_name}{f' where {condition}' if condition else ''};"
            if count == 1:
                return self.search_one(sql)
            else:
                return self.search_all(sql)
        except Exception as e:
            Config.Logger.error(f'search {table_name} {f"by {condition}" if condition else ""}: Error: {str(e)}')

    def search_all_pub_med_id(self):
        # 查询全部信息
        sql = "select id from pubmed"
        self.cursor.execute(sql)
        res = self.cursor.fetchall()
        pub_ids = {pub[0] for pub in res}
        self.close()
        return pub_ids

    def search_pub_med_by_id(self, pid):
        try:
            sql = f"select * from pubmed where id={pid};"
            return self.search_one(sql)
        except Exception as e:
            Config.Logger.error(f'search pubmed by id:{pid} Error: {str(e)}')

    def update_pub_med_base_info(self, data):
        try:
            sql = f'update pubmed set pmc_id=(%s), doi=(%s), journal_id=(%s), year=(%s), kwds=(%s), has_abstract=(%s),' \
                  f'pubmed_json_path=(%s), pmc_json_path=(%s)  where id=(%s);'
            self.update_data(sql, data)
        except Exception as e:
            Config.Logger.error(f'update pubmed base info id:{data[-1]} Error: {str(e)}')

    def update_pub_med_is_cancer(self, pid, is_cancer):
        try:
            sql = f'update pubmed set is_cancer="{is_cancer}", has_annotation=1  where id={pid};'
            self.update(sql)
        except Exception as e:
            Config.Logger.error('PubMed', pid, f'update is_cancer is Error: {e}')

    def batch_update_pub_med_is_cancer(self, batch_data):
        try:
            sql = f'update pubmed set is_cancer= (%s), has_annotation=1  where id= (%s);'
            self.update_many(sql, batch_data)
        except Exception as e:
            Config.Logger.error(f'batch update PubMed is_cancer field is Error: {str(e)}')

    def insert_pub_med_base_info(self, data):
        try:
            sql = 'INSERT IGNORE INTO pubmed (pmc_id, doi, journal_id, year, kwds, has_abstract, pubmed_json_path, ' \
                  'pmc_json_path, id) values(%s, %s, %s, %s, %s, %s, %s, %s, %s)'
            self.insert_data(sql, data)
        except Exception as e:
            Config.Logger.error('PubMed', data[1], f'insert base info Error: {e}')

    def batch_update_pub_med_base_info(self, batch_data):
        try:
            sql = f'update pubmed set pmc_id=(%s), doi=(%s), journal_id=(%s), year=(%s), kwds=(%s), has_abstract=(%s),' \
                  f'pubmed_json_path=(%s), pmc_json_path=(%s)  where id=(%s);'
            self.update_many(sql, batch_data)
        except Exception as e:
            Config.Logger.error(f'batch update pubmed base info Error: {str(e)}')

    def batch_insert_pub_med_base_info(self, batch_data):
        try:
            sql = 'INSERT IGNORE INTO pubmed (pmc_id, doi, journal_id, year, kwds, has_abstract, pubmed_json_path, ' \
                  'pmc_json_path, id) values(%s, %s, %s, %s, %s, %s, %s, %s, %s)'
            self.insert_many_data(sql, batch_data)
        except Exception as e:
            Config.Logger.error(f'batch insert pubmed base info Error: {e}')

    def insert_or_update_pub_med(self, pid, data):
        try:
            res = self.search_pub_med_by_id(pid)
            if res:
                self.update_pub_med_base_info(*data)
            else:
                self.insert_pub_med_base_info(data)
        except Exception as e:
            Config.Logger.error(f"PubMed id: {pid}, ErrorInfo: {e}")

    def search_new_pub_by_pub_id(self, pub_id):
        try:
            sql = f"select pub_id from pub_updates where pub_id='{pub_id}';"
            return self.search_one(sql)
        except Exception as e:
            Config.Logger.error(f'search pub_updates by pub_id:{pub_id} ErrorInfo: {e}')

    def update_new_pub_info(self, data):
        try:
            sql = 'update pub_updates set pub_date=(%s), pub_type=(%s), pub_title=(%s), pub_authors=(%s), ' \
                  'pub_journal=(%s), pub_year=(%s) where pub_id=(%s)'
            self.update_data(sql, data)
        except Exception as e:
            Config.Logger.error(f'update pub_updates base info pub_id:{data[-1]} ErrorInfo: {str(e)}')

    def batch_update_new_pub_info(self, batch_data):
        try:
            sql = 'update pub_updates set pub_date=(%s), pub_type=(%s), pub_title=(%s), pub_authors=(%s), ' \
                  'pub_journal=(%s), pub_year=(%s) where pub_id=(%s)'
            self.update_many(sql, batch_data)
        except Exception as e:
            Config.Logger.error(f'batch update pub_updates base info ErrorInfo: {e}')

    def batch_insert_new_pub_info(self, batch_data):
        try:
            sql = 'INSERT IGNORE INTO pub_updates (pub_date, pub_type, pub_title, pub_authors, pub_journal, pub_year,' \
                  ' pub_id) values(%s, %s, %s, %s, %s, %s, %s)'
            self.insert_many_data(sql, batch_data)
        except Exception as e:
            Config.Logger.error(f'batch insert pub_updates ErrorInfo: {str(e)}')

    def insert_new_pub_info(self, data):
        try:
            sql = 'INSERT IGNORE INTO pub_updates (pub_date, pub_type, pub_title, pub_authors, pub_journal, pub_year,' \
                  ' pub_id) values(%s, %s, %s, %s, %s, %s, %s)'
            self.insert_data(sql, data)
        except Exception as e:
            Config.Logger.error('Insert pub_updates pub_id', data[-1], f'ErrorInfo: {e}')

    def insert_or_update_new_pub(self, pub_id, data):
        try:
            res = self.search_new_pub_by_pub_id(pub_id)
            if res:
                self.update_new_pub_info(*data)
            else:
                self.insert_new_pub_info(data)
        except Exception as e:
            Config.Logger.error(f"insert or update pub_updates pub_id: {pub_id}, ErrorInfo: {e}")

    def update_table_data(self, table_name, fields, data=None, conditions=None, count=-1):
        if conditions is None:
            conditions = []
        if data is None:
            if count == -1:
                data = [[]]
            else:
                data = []
        try:
            set_field = '=(%s), '.join(fields) + '=(%s)'
            condition = ' '.join(conditions)
            sql = f'update {table_name} set {set_field}{f" where {condition}" if condition else ""}'
            return self.update_many(sql, data)
        except Exception as e:
            Config.Logger.error(f"{'batch ' if count == -1 else ''}update {table_name} error: {e}")

    def update_stat_abstract_fullText_fields(self, new_pmc=0):
        try:
            sql = 'select count(*) from pubmed where has_abstract=1;'
            abstracts = self.search_one(sql)[0]
            sql = 'select count(*) from pubmed'
            pubs = self.search_one(sql)[0]
            sql = f'update stat set statFullTexts=statFullTexts+{new_pmc}, statAbstracts=(%s), statPubMed=(%s)'
            self.update_data(sql, [abstracts, pubs])
        except Exception as e:
            Config.Logger.error(f"update stat abstract fullText fields error: {e}")

    def search_cancer_library_info(self):
        try:
            sql = f"select identifier, symbol, other_identifiers from cancer_library"
            return self.search_all(sql)
        except Exception as e:
            Config.Logger.error(f"query cancer_library all data ErrorInfo: {e}")

    def search_library_identifier_symbol(self):
        try:
            sql = f"select identifier, symbol, synonyms, label from library;"
            return self.search_all(sql)
        except Exception as e:
            Config.Logger.error(f"query cancer_library all data ErrorInfo: {e}")

    def search_library(self, *fields):
        try:
            select_fields = ', '.join(fields) or '*'
            sql = f"select {select_fields} from library"
            return self.search_all(sql)
        except Exception as e:
            Config.Logger.error(f"query library all data ErrorInfo: {e}")

    def search_cite_cited_similar_table(self, pid):
        try:
            sql = f"select * from cite_cited_similar_relationship where pubmed_id={pid};"
            return self.search_one(sql)
        except Exception as e:
            Config.Logger.error(f"PubMed id: {pid}, query cite_cited_similar_relationship ErrorInfo: {e}")

    def update_cite_cited_similar_table(self, pid, Ids, field='cite'):
        try:
            Ids, num = "|".join([str(Id) for Id in Ids]), len(Ids)
            if field == 'cite':
                sql = f'update cite_cited_similar_relationship set cite="{Ids}", cite_num="{num}"' \
                      f'  where pubmed_id={pid};'
            else:
                sql = f'update cite_cited_similar_relationship set cited="{Ids}", cited_num="{num}"' \
                      f'  where pubmed_id={pid};'
            self.update(sql)
        except Exception as e:
            Config.Logger.error(f"PubMed id: {pid}, update cite_cited_similar_relationship {field} ErrorInfo: {e}")

    def insert_cite_cited_similar_table(self, pid, Ids, field='cite'):
        try:
            Ids, num = "|".join([str(Id) for Id in Ids]), len(Ids)
            if field == 'cite':
                sql = f'INSERT IGNORE INTO cite_cited_similar_relationship (pubmed_id, cite, cite_num) ' \
                      f'values(%s, %s, %s)'
            else:
                sql = f'INSERT IGNORE INTO cite_cited_similar_relationship (pubmed_id, cited, cited_num) ' \
                      f'values(%s, %s, %s)'
            self.insert_data(sql, [pid, Ids, num])
        except Exception as e:
            Config.Logger.error(f"PubMed id: {pid}, insert cite_cited_similar_relationship {field} ErrorInfo: {e}")

    def insert_or_update_cite_cited_similar_table(self, pid, Ids, field='cite'):
        try:
            if Ids:
                res = self.search_cite_cited_similar_table(int(pid))
                if field == 'cite':
                    if res:
                        self.update_cite_cited_similar_table(int(pid), Ids)
                    else:
                        self.insert_cite_cited_similar_table(int(pid), Ids)
                else:
                    if res:
                        citedIds = res[3] if res[3] else ''
                        if len(set(Ids) - set(citedIds.split('|'))) > 0:
                            Ids = sorted([int(pub_id) for pub_id in set(citedIds.split('|')) | set(Ids) if pub_id])
                            self.update_cite_cited_similar_table(int(pid), Ids, field='cited')
                    else:
                        self.insert_cite_cited_similar_table(int(pid), Ids, field='cited')

        except Exception as e:
            Config.Logger.error(f"cite_cited_similar_relationship pid: {pid} insert or update error, ErrorInfo: {e}")

    def batch_insert_ref_pub_info(self, batch_data):
        try:
            sql = f'INSERT IGNORE INTO cite_cited_similar_relationship (cite, cite_num, pubmed_id) values(%s, %s, %s)'
            self.insert_many_data(sql, batch_data)
        except Exception as e:
            print(f"batch insert cite_cited_similar_relationship cite ErrorInfo: {str(e)}")

    def batch_update_ref_pub_info(self, batch_data):
        try:
            sql = f'update cite_cited_similar_relationship set cite=(%s), cite_num=(%s)' \
                  f'  where pubmed_id=(%s);'
            self.update_many(sql, batch_data)
        except Exception as e:
            Config.Logger.error(f"batch update cite_cited_similar_relationship cite ErrorInfo: {str(e)}")

    def search_lib_pub_by_library_id(self, lib_id):
        try:
            sql = f"select pubmeds from library_pubmed where library_id={lib_id};"
            return self.search_one(sql)
        except Exception as e:
            Config.Logger.error(f'search library_pubmed by id:{lib_id} Error: {e}')

    def update_library_pub(self, lib_id, Ids):
        try:
            Ids, num = "|".join([str(Id) for Id in Ids]), len(Ids)
            sql = f'update library_pubmed set pubmeds="{Ids}", length="{num}"' \
                  f'  where library_id={lib_id};'
            self.update(sql)
        except Exception as e:
            Config.Logger.error(f"Library id: {lib_id}, update library_pubmed pubmeds fields ErrorInfo: {e}")

    def insert_library_pub(self, lib_id, pub_ids):
        try:
            Ids, num = "|".join([str(Id) for Id in pub_ids]), len(pub_ids)
            sql = f'INSERT IGNORE INTO library_pubmed (library_id, pubmeds, length) values(%s, %s, %s)'
            self.insert_data(sql, [lib_id, Ids, num])
        except Exception as e:
            Config.Logger.error(f"Library id: {lib_id}, insert library_pubmed ErrorInfo: {e}")

    def insert_or_update_library_pub(self, lib_id, pubs):
        try:
            res = self.search_lib_pub_by_library_id(lib_id)
            if res:
                pub_ids = res[0] if res[0] else ''
                if len(set(pubs) - set(pub_ids.split('|'))) > 0:
                    Ids = sorted([int(pub_id) for pub_id in set(pub_ids.split('|')) | set(pubs) if pub_id],
                                 reverse=True)
                    self.update_library_pub(lib_id, Ids)
            else:
                self.insert_library_pub(lib_id, set(pubs))
        except Exception as e:
            Config.Logger.error(f"update_insert library_pubmed library_id: {lib_id}, ErrorInfo: {e}")

    def search_mentions(self, *fields):
        try:
            select_fields = ', '.join(fields) or '*'
            sql = f"select {select_fields} from mentions"
            return self.search_all(sql)
        except Exception as e:
            Config.Logger.error(f'search mentions Error: {e}')

    def insert_mentions(self, mention):
        try:
            sql = f'INSERT IGNORE INTO mentions (mention) values(%s)'
            self.insert_data(sql, [mention])
        except Exception as e:
            Config.Logger.error(f'search mentions Error: {e}')

    def search_mentions_by_mention(self, mention):
        try:
            sql = f"select id from mentions where mention=(%s);"
            self.cursor.execute(sql, [mention])
            res = self.cursor.fetchone()
            return res
        except Exception as e:
            Config.Logger.error(f'search mention by mention: {mention} Error: {e}')

    def select_mention_pub(self, mention_id):
        try:
            sql = f"select pubmeds from mention_pubmed where mention_id={mention_id};"
            return self.search_one(sql)
        except Exception as e:
            Config.Logger.error(f'search mention_pubmed by id:{mention_id} Error: {e}')

    def update_mention_pub(self, mention_id, Ids):
        try:
            Ids, num = "|".join([str(Id) for Id in Ids]), len(Ids)
            sql = f'update mention_pubmed set pubmeds="{Ids}", length="{num}"' \
                  f'  where mention_id={mention_id};'
            self.update(sql)
        except Exception as e:
            Config.Logger.error(f"Mention id: {mention_id}, update mention_pubmed pubmeds fields ErrorInfo: {e}")

    def insert_mention_pub(self, mention_id, pub_ids):
        try:
            Ids, num = "|".join([str(Id) for Id in pub_ids]), len(pub_ids)
            sql = f'INSERT IGNORE INTO mention_pubmed (mention_id, pubmeds, length) values(%s, %s, %s)'
            self.insert_data(sql, [mention_id, Ids, num])
        except Exception as e:
            Config.Logger.error(f"Mention id: {mention_id}, insert mention_pubmed ErrorInfo: {e}")

    def insert_or_update_mention_pub(self, mention_id, pubs):
        try:
            res = self.select_mention_pub(mention_id)
            if res:
                pub_ids = res[0] if res[0] else ''
                if len(set(pubs) - set(pub_ids.split('|'))) > 0:
                    Ids = sorted([int(pub_id) for pub_id in set(pub_ids.split('|')) | set(pubs) if pub_id],
                                 reverse=True)
                    self.update_mention_pub(mention_id, Ids)
            else:
                self.insert_mention_pub(mention_id, set(pubs))
        except Exception as e:
            Config.Logger.error(f"update_insert mention_pubmed mention_id: {mention_id}, ErrorInfo: {e}")

    # 关闭游标和数据库的连接
    def close(self):
        self.cursor.close()
        self.con.close()
