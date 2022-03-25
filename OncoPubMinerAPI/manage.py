# -*- coding: utf-8 -*-
# @Time : 2021/10/19 14:20
# @File : manage.py
# @Project : OncoPubMinerAPI
from gevent.pywsgi import WSGIServer
from gevent import monkey

monkey.patch_all()
from flask import url_for
from flask_restplus import Api, Resource, fields, reqparse

from PubMiner import create_app, scheduler
from utils import *
from aspcheduler_job import AspConfig


app = create_app('production')
app.config.from_object(AspConfig())

# it is also possible to enable the API directly
# scheduler.api_enabled = True
scheduler.init_app(app)
scheduler.start()


@app.route('/')
def index():
    return 'welcome OncoPubMiner API'


@app.route('/stat')
def stat():
    PubMinerStat = Stat.query.filter(Stat.id == 1).first()

    data = {
        "code": 200,
        "msg": "Request success",
        "success": True,
        "data": {
            'statAbstracts': PubMinerStat.statAbstracts,
            'statFullTexts': PubMinerStat.statFullTexts,
            'statEntityPubPairs': PubMinerStat.statEntityPubPairs,
            'version': PubMinerStat.version
        }

    }
    return jsonify(data)


@app.route('/search')
def search_pub_med_by_library():
    """
    1. pmid list 查询 /search?q=25826565 25826566 25826567
    2. PMCid list 查询 /search?q=PMC23534 PMC23533 23537
    3. AND 查询 /search?q=EGFR AND tumor
    4. OR 查询 /search?q=EGFR OR ABL1
    5. 单词查询 /search?q=EGFR
    :return:
    """
    start_time = time.time()
    result = extract_pub_med(by_type='library')
    print('select_time', time.time()-start_time)
    return result


@app.route('/keyword')
def search_pub_med_by_keyword():
    result = extract_pub_med(by_type='mention')
    return result


@app.route('/cancer')
def search_cancer_list():
    result = extract_library_symbols(library_type='cancer')
    return result


@app.route('/chemical')
def search_chemical_list():
    result = extract_library_symbols(library_type='chemical')
    return result


@app.route('/gene')
def search_gene_list():
    result = extract_library_symbols(library_type='gene')
    return result


@app.route('/id')
def search_pub_pmc_info():
    try:
        query = request.args.get("q")
        if not query:
            return badRequest()
        if not re.match(r'^PMC\d+$|^\d+$', query):
            return jsonify({"code": 404, "msg": "formal error", "success": True})
        if 'PMC' not in query:
            pub_med = PubMed.query.filter_by(id=query).first()
        else:
            pub_med = PubMed.query.filter_by(pmc_id=query).first()
        if pub_med:
            document = {}
            if pub_med.pmc_json_path:
                document = get_document(pub_med, 'pmc')
            if not document and pub_med.pubmed_json_path:
                document = get_document(pub_med)
            if document:
                return jsonify({"code": 200, "msg": "Request success", "success": True, "data": document})

        return jsonify({"code": 200, "msg": "not Found", "success": True, "data": {}})
    except Exception as e:
        logging.info(f"Request Failed {e}")
        return jsonify({"code": 500, "msg": f"Request Failed {e}", "success": False, "data": {}})


@app.route('/cited_by')
def search_cited_pub_med_info():
    """搜索该文献被引用的pubmed文献"""
    try:
        result = search_correlation_pub_med(t='cited_by')
        return result
    except Exception as e:
        logging.info(f"Request Failed {e}")
        return jsonify({"code": 500, "msg": f"Request Failed {e}", "success": False, "data": {}})


@app.route('/ref')
def search_ref_pub_med_info():
    """搜索该文献引用的pubmed文献"""
    try:
        result = search_correlation_pub_med(t='ref')
        return result
    except Exception as e:
        logging.info(f'{e}')
        return jsonify({"code": 500, "msg": f"Request Failed {e}", "success": False, "data": {}})


@app.route('/similar')
def search_similar_pub_med_info():
    """搜索该文献相似的pubmed文献"""
    try:
        result = search_correlation_pub_med(t='similar')
        return result
    except Exception as e:
        logging.info(f"Request Failed {e}")
        return jsonify({"code": 500, "msg": f"Request Failed {e}", "success": False})


@app.route('/pub_updates')
def search_new_pub():
    try:
        pub_id = request.args.get("pub_id")
        pub_date = request.args.get("pub_date")
        pub_type = request.args.get("pub_type")
        pub_title = request.args.get("pub_title")
        pub_authors = request.args.get("pub_authors")
        pub_journal = request.args.get("pub_journal")
        pub_year = request.args.get("pub_year")
        # 转换page, per_page参数
        page_num = request.args.get("page", 1)
        limit = request.args.get("limit", Config.per_page)
        p = get_page(page_num)
        limit = get_limit(limit)
        offset = (p-1)*limit
        new_pubs, count = get_new_pub_list(pub_id, pub_date, pub_type, pub_title, pub_authors, pub_journal, pub_year,
                                           limit, offset)
        data = {
            "code": 0,
            "msg": "Request success",
            "success": True,
            "page": p,
            "next": p+1 if (p-1)*limit < count else None,
            "count": count,
            "limit": limit,
            "data": [{"pub_id": new_pub.pub_id,
                      "pub_date": time.strftime("%Y-%m-%d", time.localtime(new_pub.pub_date)),
                      "pub_type": 'New' if new_pub.pub_type == 1 else 'Update',
                      "pub_title": new_pub.pub_title,
                      "pub_authors": new_pub.pub_authors,
                      "pub_journal": new_pub.pub_journal,
                      "pub_year": new_pub.pub_year} for new_pub in new_pubs]
        }
        return jsonify(data)
    except Exception as e:
        logging.info(f"Request Failed {e}")
        return jsonify({"code": 500, "msg": f"Request Failed {e}", "success": False})


@property
def specs_url(self):
    return url_for(self.endpoint('specs'), _external=True, _scheme='https')


Api.specs_url = specs_url

logging.info(f"environ: {os.environ}")
api = Api(app, version='v1.0.2', title='OncoPubMiner API',
          description='Note: In order to avoid overloading the OnPubMiner server, we require users to make no more '
                      'than 5 requests per second. ', doc='/api/doc')

# 模块命名空间
ns = api.namespace(name="Search", description='search operations', path='/')

# Bad Request
BadRequest = api.model('BadRequest', {
    "code": fields.Integer(required=True, description='Response code'),
    "msg": fields.String(required=True, description='Response Info'),
    "success": fields.Boolean(required=True, description='Response Info')
})
# Error
Error = api.model('Error', {
    "code": fields.Integer(required=True, description='Response code'),
    "msg": fields.String(required=True, description='Response Error Info'),
    "success": fields.Boolean(required=True, description='Response success')
})
BioCRelationJson = api.model('BioCRelationJson', {})
BioCLocationJson = api.model('BioCLocationJson', {
    "offset": fields.Integer(required=True, description='BioC start offest'),
    "length": fields.Integer(required=True, description='BioC Document Id')
})
BioCInfoJson = api.model('BioCInfoJson', {})
BioCAnnotationJson = api.model('BioCAnnotationJson', {
    "id": fields.Integer(required=True, description='Annotation identifier'),
    "infons": fields.Nested(model=BioCInfoJson, required=True, description='AnnotationInfo Json'),
    "locations": fields.List(cls_or_instance=fields.Nested(model=BioCLocationJson, required=True,
                                                           description='BioCRelation Json'),
                             required=True, description='BioC Location Info'),
    "text": fields.String(required=True, description='Annotation context')
})
BioCSentenceJson = api.model('BioCSentenceJson', {
    "offset": fields.Integer(required=True, description='BioC Document Id'),
    "text": fields.String(required=True, description='BioC Passage context'),
    "infons": fields.Nested(required=True, model=BioCInfoJson, description='BioC Infons'),
    "annotations": fields.List(cls_or_instance=fields.Nested(model=BioCAnnotationJson,
                                                             description='BioCAnnotation Json'),
                               required=True, description='BioC Annotations Info'),
    "relations": fields.List(cls_or_instance=fields.Nested(model=BioCRelationJson, description='BioCRelation Json'),
                             required=True, description='BioC Relations Info')
})
PassageInfoJson = api.model('PassageInfoJson', {
    "article_id_pmid": fields.String(description='Document PubMed Id'),
    "article_id_doi": fields.String(description='Document DOI identifier'),
    "article_id_pmc": fields.String(description='Document PMC identifier'),
    "journal": fields.String(description='Document Citation Info'),
    "journal_name": fields.String(description='Document journal name'),
    "section": fields.String(description='Passage section name'),
    "type": fields.String(description='Passage section type'),
    "year": fields.String(description='Document year'),
    "keywords": fields.List(cls_or_instance=fields.String(description='Document keyword'),
                            description='Document keywords'),
    "authors": fields.List(cls_or_instance=fields.String(description='Document author'),
                           description='Document authors'),
    "refNums": fields.Integer(description='refNums'),
})
BioCPassageJson = api.model('BioCPassageJson', {
    "offset": fields.Integer(required=True, description='BioC Document Id'),
    "text": fields.String(required=True, description='BioC Passage context'),
    "infons": fields.Nested(required=True, model=PassageInfoJson, description='BioC Infons'),
    "annotations": fields.List(cls_or_instance=fields.Nested(model=BioCAnnotationJson,
                                                             description='BioCAnnotation Json'),
                               required=True, description='BioC Annotations Info'),
    "relations": fields.List(cls_or_instance=fields.Nested(model=BioCRelationJson, description='BioCRelation Json'),
                             required=True, description='BioC Relations Info'),
    "sentences": fields.List(cls_or_instance=fields.Nested(model=BioCSentenceJson, description='BioCSentence Json'),
                             required=True, description='BioC Sentences Info')
})
BioCJson = api.model('BioCJson', {
    "id": fields.Integer(required=True, description='BioC Document Id'),
    "infons": fields.Nested(required=True, model=BioCInfoJson, description='BioC Infons'),
    "passages": fields.List(cls_or_instance=fields.Nested(model=BioCPassageJson, required=True,
                                                          description='BioCRelation Json'),
                            required=True, description='BioC Passage'),
    "annotations": fields.List(cls_or_instance=fields.Nested(model=BioCAnnotationJson,
                                                             description='BioCAnnotation Json'),
                               required=True, description='BioC Annotations Info'),
    "relations": fields.List(cls_or_instance=fields.Nested(model=BioCRelationJson, description='BioCRelation Json'),
                             required=True, description='BioC Relations Info')
})
LibraryJson = api.model('LibraryJson', {
    "symbol": fields.String(required=True, description='Library Symbol'),
    "identifier": fields.String(required=True, description='Library identifier'),
    "synonyms": fields.String(required=True, description='Library synonyms'),
    "label": fields.String(required=True, description='Library label Disease/Chemical/Gene')
})
BioCJsonResponse = api.model('BioCJsonResponse', {
    "code": fields.Integer(required=True, description='Response'),
    "msg": fields.String(required=True, description='Response Info'),
    "success": fields.Boolean(required=True, description='Response Info'),
    "data": fields.Nested(model=BioCJson, required=True, description='PubMed/PMC BioCJson')
})
BioCJsonList = api.model('BioCJsonList', {
    "code": fields.Integer(required=True, description='Response'),
    "msg": fields.String(required=True, description='Response Info'),
    "success": fields.Boolean(required=True, description='Response Info'),
    "page": fields.Integer(required=True, description='page num'),
    "next": fields.Integer(required=True, description='next page num'),
    "count": fields.Integer(required=True, description='total count'),
    "limit": fields.Integer(required=True, description='page limit count'),
    "type": fields.Integer(required=True, description='1 Library list, 2 BioC list'),
    "data": fields.List(cls_or_instance=fields.Nested(model=BioCJson, required=True, description='BioCJson'),
                        required=True, description='BioCJson list'),
})
LibraryList = api.model('LibraryList', {
    "code": fields.Integer(required=True, description='Response'),
    "msg": fields.String(required=True, description='Response Info'),
    "success": fields.Boolean(required=True, description='Response Info'),
    "page": fields.Integer(required=True, description='page num'),
    "next": fields.Integer(required=True, description='next page num'),
    "count": fields.Integer(required=True, description='total count'),
    "limit": fields.Integer(required=True, description='page limit count'),
    "type": fields.Integer(required=True, description='1 Library list, 2 BioC list'),
    "data": fields.List(cls_or_instance=fields.Nested(model=LibraryJson, required=True, description='LibraryJson'),
                        required=True, description='LibraryJson list'),
})
cancer_library = api.model('cancer_library', {
    "code": fields.Integer(required=True, description='Response'),
    "msg": fields.String(required=True, description='Response Info'),
    "success": fields.Boolean(required=True, description='Response Info'),
    "data": fields.List(cls_or_instance=fields.String(required=True, description='Cancer Symbol'),
                        required=True, description='Cancer symbol list'),
})
gene_library = api.model('gene_library', {
    "code": fields.Integer(required=True, description='Response'),
    "msg": fields.String(required=True, description='Response Info'),
    "success": fields.Boolean(required=True, description='Response Info'),
    "data": fields.List(cls_or_instance=fields.String(required=True, description='Gene Symbol'),
                        required=True, description='Gene symbol list'),
})
chemical_library = api.model('chemical_library', {
    "code": fields.Integer(required=True, description='Response'),
    "msg": fields.String(required=True, description='Response Info'),
    "success": fields.Boolean(required=True, description='Response Info'),
    "data": fields.List(cls_or_instance=fields.String(required=True, description='Chemical Symbol'),
                        required=True, description='Chemical symbol list'),
})

search_keyword_parser = reqparse.RequestParser()  # 参数模型
search_keyword_parser.add_argument('q', type=str, required=True, help="keyword")
page = reqparse.Argument('p', type=int, required=False, default=1, help='page num')
per_page = reqparse.Argument('l', type=str, required=False, default=10, help='per page limit num')
is_cancer = reqparse.Argument('t', type=str, required=False, default='cancer', help='cancer or all')
is_remote = reqparse.Argument('m', type=str, required=False, default='local',
                              help='call the remote interface or local interface')
search_keyword_parser.add_argument(page)
search_keyword_parser.add_argument(per_page)
search_keyword_parser.add_argument(is_cancer)
search_keyword_parser.add_argument(is_remote)

keyword_parser = reqparse.RequestParser()
keyword_parser.add_argument('q', type=str, required=True, help="mention")
keyword_parser.add_argument(page)
keyword_parser.add_argument(per_page)
keyword_parser.add_argument(is_cancer)
keyword_parser.add_argument(is_remote)

cancer_parser = reqparse.RequestParser()
cancer_parser.add_argument('q', type=str, required=True, help="cancer word")

gene_parser = reqparse.RequestParser()
gene_parser.add_argument('q', type=str, required=True, help="gene word")

chemical_parser = reqparse.RequestParser()
chemical_parser.add_argument('q', type=str, required=True, help="chemical word")

id_parser = reqparse.RequestParser()
id_parser.add_argument('q', type=str, required=True, help="PubMed Id or PMC Id")

cite_parser = reqparse.RequestParser()
cite_parser.add_argument('q', type=str, required=True, help="PubMed ID")
cite_parser.add_argument(page)
cite_parser.add_argument('l', type=int, required=False, default=10, help="per page limit num, max value: 100")


@ns.route('/search', endpoint=search_pub_med_by_library)
class Search(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = search_keyword_parser.parse_args()

    @ns.expect(search_keyword_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", BioCJsonList)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract Entity-based Matching related PubMed BioC-JSON list"""
        return self.params


@ns.route('/keyword', endpoint=search_pub_med_by_keyword)
class KeyWord(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = keyword_parser.parse_args()

    @ns.expect(keyword_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", BioCJsonList)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract Mention-based Matching related PubMed BioC-JSON list"""
        return self.params


@ns.route('/cancer', endpoint=search_cancer_list)
class Cancer(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = cancer_parser.parse_args()

    @ns.expect(cancer_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", cancer_library)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract cancer related library symbol list"""
        return self.params


@ns.route('/gene', endpoint=search_gene_list)
class Gene(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = gene_parser.parse_args()

    @ns.expect(gene_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", gene_library)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract gene related library symbol list"""
        return self.params


@ns.route('/chemical', endpoint=search_chemical_list)
class Chemical(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = chemical_parser.parse_args()

    @ns.expect(chemical_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", chemical_library)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract chemical related library symbol list"""
        return self.params


@ns.route('/id', endpoint=search_pub_pmc_info)
class PubID(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = id_parser.parse_args()

    @ns.expect(id_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", BioCJsonResponse)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract PMID/PMCID related PubMed BioC-JSON"""
        return self.params


@ns.route('/ref', endpoint=search_ref_pub_med_info)
class Cite(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = cite_parser.parse_args()

    @ns.expect(cite_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", BioCJsonList)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract PMID reference PubMed BioC-JSON list"""
        return self.params


@ns.route('/cited_by', endpoint=search_cited_pub_med_info)
class CitedBy(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = cite_parser.parse_args()

    @ns.expect(cite_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", BioCJsonList)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract PMID referenced PubMed BioC-JSON list"""
        return self.params


@ns.route('/similar', endpoint=search_similar_pub_med_info)
class Similar(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = cite_parser.parse_args()

    @ns.expect(cite_parser)  # 用于解析对应文档参数，
    @ns.response(200, "success response", BioCJsonList)  # 对应解析文档返回值
    @ns.response(400, "bad request", BadRequest)  # 对应解析文档返回值
    @ns.response(500, "Failed response", Error)  # 对应解析文档返回值
    def get(self):
        """Extract PMID similar PubMed BioC-JSON list"""
        return self.params


if __name__ == '__main__':
    http_server = WSGIServer(('0.0.0.0', 9001), app)
    http_server.serve_forever()
