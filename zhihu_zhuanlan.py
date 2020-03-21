# coding: utf8
# author: AIpha

import requests
import hmac
import hashlib
import execjs
from urllib.parse import urlencode
import time
import re
from PIL import Image
import matplotlib.pyplot as plt
import base64
import json
import copy
from hyper.contrib import HTTP20Adapter
from lxml import etree
import pymongo
from urllib.parse import quote,urlencode
import logging
import asyncio
from aiohttp import ClientSession
from redis import StrictRedis, ConnectionPool
from gevent import monkey
monkey.patch_all()
# from hashlib import md5
from queue import Queue

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)
cookie_queue = {}
pool = ConnectionPool(host="localhost", port=6379, db=2)
num = 0
num_1 = 0
num_2 = 0


class ZhihuSpider():
    def __init__(self, username, password):
        self.login_url = "https://www.zhihu.com/signin"
        self.login_check = "https://www.zhihu.com/api/v3/oauth/sign_in"
        self.login_data = {
            "client_id": "c3cef7c66a1843f8b3a9e6a1e3160e20",
            "grant_type": "password",
            "timestamp": "",
            "source": "com.zhihu.web",
            "signature": "",
            "username": username,
            "password": password,
            "captcha": "",
            "lang": "cn",
            "utm_source": "",
            "ref_source": "other_https://www.zhihu.com/signin",
        }
        self.headers = {
            "Host": "www.zhihu.com",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.zhihu.com/signin",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.page_headers = copy.deepcopy(self.headers)
        self.page_headers["Referer"] = 'https://www.zhihu.com/'
        self.page_headers["X-API-VERSION"] = '3.0.53'
        self.headers_login = {
            ":authority": "www.zhihu.com",
            ":method": "GET",
            ":path": "/",
            ":scheme": "https",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "accept-encoding": "gzip, deflate",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://www.zhihu.com/signin",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
        }

    def login(self, captcha_lang="en"):
        '''
        登陆
        :param captcha_lang: 验证码类型
        :return:
        '''
        xsrf = self._get_xsrf()
        timestamp = str(int(time.time() * 1000))
        self.login_data['signature'] = self._get_signature(timestamp)
        self.login_data['timestamp'] = timestamp
        self.login_data['captcha'] = self._get_captcha(captcha_lang, self.headers)[0]
        self.headers['x-xsrftoken'] = xsrf.strip()
        self.headers['x-zse-83'] = '3_2.0'
        self.headers['content-type'] = 'application/x-www-form-urlencoded'
        # print(execjs.get().name)
        with open('zhihu.js', 'r', errors='ignore') as f:
            js_code = f.read()
        exejs = execjs.compile(js_code)
        encrypt_js = exejs.call('b', urlencode(self.login_data))
        # print(encrypt_js)
        # print(self.headers)
        response = requests.post(self.login_check, headers=self.headers, data=encrypt_js)
        # print(response.text)
        if 'error' in response.text:
            print(json.loads(response.text)['error']['message'])
        if response.status_code in [200, 201, 202]:
            print('登录成功')
            cookies = response.headers['Set-Cookie'].split(';')
            res_cookie = []
            set_cookie = []
            for cookie in cookies:
                set_cookie.append(cookie.split(','))
            for sets in set_cookie:
                # _zap、 tgw_l7_route参数备用
                for set in sets:
                    if 'z_c0' in set:
                        res_cookie.append(set)
                    else:
                        continue
            login_cookie = self.headers['Cookie']+";"+res_cookie[0]
            self.headers_login['Cookie'] = login_cookie
            self.headers['Cookie'] = login_cookie
            # self.headers['Cookie'] = self.headers['Cookie']+";"+res_cookie[0]
            # zhihu_http2 = HTTP20Connection(self.login_url)
            # req_http2 = requests.Session()
            # req_http2.mount(self.login_url, HTTP20Adapter())
            # res_login = req_http2.get(url=self.login_url, headers=self.headers_login)
            # res_login = requests.get(url=self.login_url, headers=self.headers)
            # for i in self.zhihu_parse(res_login):
            #     pass
            # session_token = re.findall('session_token=(.*?)&', str(res_login.text), re.S)[0]
            # self.next_page(session_token)
            # return login_cookie
            cookie_queue.update({"cookie":login_cookie})
        else:
            print('登录失败')
            return False

    def _get_xsrf(self):
        response = requests.head(url=self.login_url, headers=self.headers)
        cookies = response.headers['Set-Cookie'].split(';')
        res_cookie = []
        set_cookie = []
        for cookie in cookies:
            set_cookie.append(cookie.split(','))
        for sets in set_cookie:
            # _zap、 tgw_l7_route参数备用
            for set in sets:
                if '_xsrf' in set or 'tgw_l7_route' in set:
                    res_cookie.append(set)
                else:
                    continue
        # print(res_cookie)
        self.headers['Cookie'] = ';'.join(res_cookie).strip()
        return res_cookie[-1]

    def _get_signature(self, timestamp):
        ha = hmac.new(b'd1b964811afb40118a12068ff74a12f4', digestmod=hashlib.sha1)
        grant_type = self.login_data['grant_type']
        client_id = self.login_data['client_id']
        source = self.login_data['source']
        ha.update(bytes((grant_type + client_id + source + timestamp), 'utf-8'))
        return ha.hexdigest()

    def _get_captcha(self, lang, headers):
        """
        请求验证码的 API 接口，无论是否需要验证码都需要请求一次
        如果需要验证码会返回图片的 base64 编码
        根据 lang 参数匹配验证码，需要人工输入
        :param lang: 返回验证码的语言(en/cn)
        :param headers: 带授权信息的请求头部
        :return: 验证码的 POST 参数
        """
        if lang == 'cn':
            api = 'https://www.zhihu.com/api/v3/oauth/captcha?lang=cn'
        else:
            api = 'https://www.zhihu.com/api/v3/oauth/captcha?lang=en'
        resp = requests.get(api, headers=headers)
        show_captcha = re.search(r'true', resp.text)
        capt_headers = copy.deepcopy(headers)
        cookies = resp.headers['Set-Cookie'].split(';')
        res_cookie = []
        set_cookie = []
        for cookie in cookies:
            set_cookie.append(cookie.split(','))
        for sets in set_cookie:
            # _zap、 tgw_l7_route参数备用
            for set in sets:
                if 'capsion_ticket' in set:
                    res_cookie.append(set)
                else:
                    continue
        # print(res_cookie)
        capt_headers['Cookie'] = ';'.join(res_cookie).strip()
        self.headers['Cookie'] = self.headers['Cookie']+";"+res_cookie[0]

        if show_captcha:
            put_resp = requests.put(api, headers=capt_headers)
            json_data = json.loads(put_resp.text)
            # print(put_resp.text)
            img_base64 = json_data['img_base64'].replace(r'\n', '')
            with open('./captcha.jpg', 'wb') as f:
                f.write(base64.b64decode(img_base64))
            img = Image.open('./captcha.jpg')
            if lang == 'cn':
                plt.imshow(img)
                print('点击所有倒立的汉字，按回车提交')
                points = plt.ginput(7)
                capt = json.dumps({'img_size': [200, 44],
                                   'input_points': [[i[0]/2, i[1]/2] for i in points]})
            else:
                img.show()
                capt = input('请输入图片里的验证码：')
            # 这里必须先把参数 POST 验证码接口
            requests.post(api, data={'input_text': capt}, headers=headers)
            return capt, res_cookie[-1]
        return ''


class ZhuanLan():
    def __init__(self, login_cookie=None, data_queue=None):
        self.login_cookie = login_cookie
        self.data_queue = data_queue
        self.headers = {
            "Host": "zhuanlan.zhihu.com",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.zhihu.com/signin",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.redis_cnn = StrictRedis(connection_pool=pool)

    async def zhuanlan_page(self, semaphore, page):
        '''
        请求知乎的首页AJAX请求
        :param response:
        :param session_token:
        :return:
        '''
        # zhuanlan_url = 'https://zhuanlan.zhihu.com/'
        zhuanlan_url = 'https://zhuanlan.zhihu.com/api/recommendations/columns?'
        headers = copy.deepcopy(self.headers)
        headers.update(self.login_cookie)
        # for offset in range(page_size):
        '''后台接口没有关闭，可以一次性请求多次数据'''
        form_data = {
            "limit": 8,
            "offset": page * 8,
            "seed": 7
        }
        # if page == 499:
        #     print(page)
        async with semaphore:
            async with ClientSession() as session:
                async with session.get(zhuanlan_url + urlencode(form_data), headers=headers) as response:
                    try:
                        global num
                        num += 1
                        response = await response.read()
                        # print(response)
                        data = json.loads(response)
                        # print(len(data['data']))
                        for node in data['data']:
                            item  = {}
                            # item['zl_xq_url'] = node.get('url', "").encode('utf-8').decode('utf-8')
                            type = node.get('type', "").encode('utf-8').decode('utf-8')
                            url_token = node.get('url_token', "").encode('utf-8').decode('utf-8')
                            if type != 'column':
                                print(type)
                            self.redis_cnn.sadd('zhuanlan_xq_url', type.replace("column", "columns") + '/' + url_token)
                    except Exception as msg:
                        print(msg)


class XqZhuanLan(ZhuanLan):
    def __init__(self, login_cookie=None):
        super(XqZhuanLan, self).__init__()
        self.headers.update(login_cookie)

    async def get_page(self, semaphore):
        async with semaphore:
            async with ClientSession() as session:
                article_str = self.redis_cnn.spop('zhuanlan_xq_url')
                if article_str:
                    for offset in range(10):
                        page_data = {
                            "include": "data[*].admin_closed_comment,comment_count,suggest_edit,is_title_image_full_screen,can_comment,upvoted_followees,can_open_tipjar,can_tip,voteup_count,voting,topics,review_info,author.is_following,is_labeled,label_info",
                            "limit": "10",
                            "offset": offset * 10
                        }
                        zhuanlan_url = "https://zhuanlan.zhihu.com/api/" + article_str.decode() + '/articles?' + urlencode(page_data).replace("%2A", "*")
                        async with session.get(zhuanlan_url, headers=self.headers) as response:
                            try:
                                global num_1
                                num_1 += 1
                                response = await response.read()
                                # print(response)
                                data = json.loads(response.decode())
                                # print(len(data['data']))
                                # html = etree.HTML(response.decode())
                                # item = {}
                                # item['doc'] = html.xpath('normalize-space(.//div[contains(@class, "RichText")])')
                                # item['title'] = html.xpath('normalize-space(.//h1[contains(@class, "Post-Title")])')
                                # item['img_url'] = html.xpath('.//div[contains(@class, "RichText")]//img/@src')
                                for node in data['data']:
                                    article_xq_url = node.get('url', "").encode('utf-8').decode('utf-8')
                                    self.redis_cnn.sadd('xq_aticle_url', article_xq_url)
                                # self.redis_cnn.sadd("xq_aticle_url", zl_xq_url)
                            except Exception as msg:
                                print(msg)
                else:
                    print('redis-zhuanlan_xq_url队列为空')


class ArticleZhuanlan(ZhuanLan):
    def __init__(self, login_cookie=None):
        super(ArticleZhuanlan, self).__init__()
        self.headers.update(login_cookie)
        self.conn = pymongo.MongoClient("localhost")
        self.mydb = self.conn["zhihu_artcile_zhuanlan"]

    async def article(self, semaphore):
        article_url = self.redis_cnn.spop("xq_aticle_url")
        if article_url:
            async with semaphore:
                async with ClientSession() as session:
                    async with session.get(article_url.decode(), headers=self.headers) as response:
                        global num_2
                        num_2 += 1
                        response = await response.read()
                        html = etree.HTML(response.decode())
                        item = {}
                        item['doc'] = html.xpath('normalize-space(.//div[contains(@class, "RichText")])')
                        item['title'] = html.xpath('normalize-space(.//h1[contains(@class, "Post-Title")])')
                        item['img_url'] = html.xpath('.//div[contains(@class, "RichText")]//img/@src')
                        print(item)
                        self.mydb['Zhihu_Article'].insert(item)
        else:
            print('redis-xq_aticle_url队列为空')


# class Parse():
#     def __init__(self, data_queue=None, xq_queue=None):
#         self.data_queue = data_queue
#         self.xq_queue = xq_queue
#
#     async def zhihu_parse_ajax(self, response):
#         data = json.loads(self.data_queue.get(False))
#         print(data)
#         for node in data['data']:
#             item_zhuanlan = {}
#             item_zhuanlan['title'] = node.get('title','').encode('utf-8').decode('utf-8')
#             item_zhuanlan['description'] = node.get('description', "").encode('utf-8').decode('utf-8')
#             item_zhuanlan['url'] = node.get('url', "").encode('utf-8').decode('utf-8')
#             item_zhuanlan['url_token'] = node.get('url_token', "").encode('utf-8').decode('utf-8')
#             item_zhuanlan['intro'] = node.get('intro', "").encode('utf-8').decode('utf-8')
#             print(item_zhuanlan)
#             self.redis_cnn.sadd(item_zhuanlan)

    # def zhihu_parse(self, response):
    #     '''
    #     解析知乎首页
    #     :param response:
    #     :return:
    #     '''
    #     response.encoding='utf-8'
    #     html = etree.HTML(response.text)
    #     node_list = html.xpath('//div[contains(@class,Card) and contains(@class,TopstoryItem) and contains(@class,TopstoryItem-isRecommend)]//div[contains(@class, "Feed")]')
    #     for node in node_list:
    #         item = {}
    #         item['title'] = node.xpath('normalize-space(.//h2)')
    #         item['article_url'] = node.xpath('normalize-space(.//h2//a/@href)')
    #         item['article_short'] = node.xpath('normalize-space(.//div[contains(@class, RichContent-inner)]//span[contains(@class,"RichText") and contains(@class, "CopyrightRichText-richText")])')
    #         item['article_Agree'] = node.xpath('normalize-space(.//div[contains(@class,"RichContent")]//div[contains(@class, "ContentItem-actions")]//span)').replace('\u200b', "").split(' ')[-1]
    #         print(item)
    #         self.mydb['zhihu_test'].insert(item)
    #         yield

async def run():
    semaphore = asyncio.Semaphore(500)
    zhuanlan = ZhuanLan(cookie_queue)
    to_get = [zhuanlan.zhuanlan_page(semaphore, i) for i in range(1, 500)]
    await asyncio.wait(to_get)


async def run_xq():
    semaphore = asyncio.Semaphore(500)
    xq_zhuanlan = XqZhuanLan(cookie_queue)
    to_get = [xq_zhuanlan.get_page(semaphore) for i in range(1, 150)]
    await asyncio.wait(to_get)


async def run_article():
    semaphore = asyncio.Semaphore(500)
    article = ArticleZhuanlan(cookie_queue)
    to_get = [article.article(semaphore) for i in range(1, 7000)]
    await asyncio.wait(to_get)

if __name__ == '__main__':
    zhihu = ZhihuSpider(username='username', password="password")
    zhihu.login()
    # if zhihu.login():
    #     #     print('数据抓取-解析-入库-结束')
    #     # else:
    #     #     print('出现错误')
    start = time.time()
    loop = asyncio.get_event_loop()
    # run()
    loop.run_until_complete(run())

    # loop = asyncio.get_event_loop()
    # run()
    loop.run_until_complete(run_xq())

    # loop = asyncio.get_event_loop()
    # run()
    loop.run_until_complete(run_article())

    print(time.time()-start)
    print(num, num_1, num_2)