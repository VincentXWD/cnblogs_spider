# -*- coding:utf-8 -*-
from multiprocessing.managers import BaseManager
from pyquery import PyQuery
import os, sys, urllib
import re, random, logging, time
import Queue, threading, multiprocessing, threadpool
import pymongo

USER_NAME = 'kirai'
TOTAL_PAGE_NUMBER = 0
INT_REGEXP = re.compile('([\d]+)')
BASE_URL = 'http://www.cnblogs.com/'+USER_NAME+'/p/?page='
ARTICLE_REGEXP = re.compile('href=\"(http://www.cnblogs.com/'+USER_NAME+'/p/[\d]+.html)\"')
THREAD_NUMBER = multiprocessing.cpu_count() * 4
ARTICLE_URLS_MUTEX = threading.Lock()
ARTICLE_URLS = []

MONGO_SERVER_ADDRESS = 'localhost'
MONGO_MUTEX = threading.Lock()
conn = pymongo.MongoClient(host=MONGO_SERVER_ADDRESS)
db = conn.cnblogs
col = db.articles


class ListWithLinkExtend(list):
	def extend(self, value):
		super(ListWithLinkExtend, self).extend(value)
		return self

def get_total_page_number():
	doc = PyQuery(url=BASE_URL)
	return int(INT_REGEXP.findall(
		doc.find('.pager .Pager').text())[0].encode('ascii'))

def get_page_url():
	global TOTAL_PAGE_NUMBER
	return map(lambda page: BASE_URL+str(page),
						 [i for i in range(1, TOTAL_PAGE_NUMBER+1)])

def read_page_urls(idx):
	url = PAGE_URLS[idx]
	doc = PyQuery(url=url)
	article_urls = ARTICLE_REGEXP.findall(str(doc.find('.PostList .postTitl2')))
	return article_urls

def get_article_url(request, result):
	global ARTICLE_URLS_MUTEX, ARTICLE_URLS
	try:
		ARTICLE_URLS_MUTEX.acquire()
		ARTICLE_URLS.append(result)
	finally:
		ARTICLE_URLS_MUTEX.release()

def cluster_process():
	global ARTICLE_URLS
	# list : urls
	task_queue = Queue.Queue()
	# str : path
	result_queue = Queue.Queue()
	KiraiManager.register('get_task_queue', callable=lambda: task_queue)
	KiraiManager.register('get_result_queue', callable=lambda: result_queue)
	manager = KiraiManager(address=('', 6969), authkey='whosyourdaddy')
	manager.start()
	manager.shutdown()
	# article_flag, article_urls = read_page_urls()

# a simple way.
def get_article(url):
	html = urllib.urlopen(url).read()
	return html, INT_REGEXP.findall(url)[0]

def save_article(request, result):
	id = result[1]
	content = result[0]
	col.insert({'id':id, 'user':USER_NAME, 'content':content})

def get_articles():
	global ARTICLE_URLS
	thread_pool = threadpool.ThreadPool(THREAD_NUMBER)
	requests = threadpool.makeRequests(get_article, ARTICLE_URLS, save_article)
	[thread_pool.putRequest(req) for req in requests]
	thread_pool.wait()

def get_article_urls():
	global ARTICLE_URLS
	thread_pool = threadpool.ThreadPool(THREAD_NUMBER)
	requests = threadpool.makeRequests(
		read_page_urls,
		[i for i in range(0, TOTAL_PAGE_NUMBER)],
		get_article_url)
	[thread_pool.putRequest(req) for req in requests]
	thread_pool.wait()
	ARTICLE_URLS = list(reduce(lambda a, b: ListWithLinkExtend(a).extend(ListWithLinkExtend(b)),
														 ARTICLE_URLS))

def __main__(argv):
	global TOTAL_PAGE_NUMBER, USER_NAME, BASE_URL, ARTICLE_REGEXP, PAGE_URLS, TOTAL_PAGE_NUMBER
	if len(argv) == 2:
		USER_NAME = argv[1]
	BASE_URL = 'http://www.cnblogs.com/'+USER_NAME+'/p/?page='
	ARTICLE_REGEXP = re.compile('href=\"(http://www.cnblogs.com/'+USER_NAME+'/p/[\d]+.html)\"')
	TOTAL_PAGE_NUMBER = get_total_page_number()
	PAGE_URLS = get_page_url()
	get_article_urls()
	get_articles()

if __name__ == '__main__':
	__main__(sys.argv)
