import re
import os
import math
import urllib.request, urllib.parse, urllib.error
import datetime
from http.cookiejar import CookieJar

from ..utils import utils
from .basegazette import BaseGazette

class Sikkim(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl   = 'https://sikkim.gov.in/mygovernment/gazettes'
        self.searchurl = 'https://sikkim.gov.in/mygovernment/gazettes?SDate={}&deptId=0&ClassificationID=0&SearchTerm=&PageNo={}'
        self.hostname  = 'sikkim.gov.in'
        self.start_date = datetime.datetime(1975, 9, 8)

    def get_result_order(self, tr):
        order = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Gazette\s+No', txt):
                order.append('gznum')
            elif txt and re.search('Title', txt):
                order.append('subject')
            elif txt and re.search('Department', txt):
                order.append('department')
            elif txt and re.search('Classification', txt):
                order.append('category')
            elif txt and re.search('Download', txt):
                order.append('download')
            else:
                order.append('')
        return order

    def process_row(self, tr, order, dateobj):
        metainfo = utils.MetaInfo()
        metainfo.set_date(dateobj)

        i = 0
        for td in tr.find_all(['td', 'th']):
            if len(order) > i:
                txt = utils.get_tag_contents(td)
                txt = txt.strip()
                if order[i] in ['gznum', 'department', 'subject', 'category']:
                    metainfo[order[i]] = txt
                elif order[i] == 'download':
                    link = td.find('a')
                    if link and link.get('href'):
                        metainfo['href'] = link.get('href')    
            i += 1

        if 'href' in metainfo and 'gznum' in metainfo:
            return metainfo
        return None

    def parse_results(self, webpage, dateobj, curr_page):
        metainfos = []
        has_nextpage = False

        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            self.logger.warning('Unable to parse result page for %s', dateobj)
            return metainfos, has_nextpage

        result_table = d.find('table')
        if result_table == None:
            self.logger.warning('Unable to find table in result page for %s', dateobj)
            return metainfos, has_nextpage

        order = None
        for tr in result_table.find_all('tr'):
            if not order:
                order = self.get_result_order(tr)
                continue
 
            metainfo = self.process_row(tr, order, dateobj)
            if metainfo != None:
                metainfos.append(metainfo)

        inp = d.find('input', { 'name': 'totalRecords' })
        if inp == None or inp.get('value') == None:
            self.logger.warning('Unable to get total record count for %s', dateobj)
            return metainfos, has_nextpage

        total_record_count = int(inp.get('value')) 
        last_page = math.ceil(total_record_count / 10)
        if curr_page != last_page:
            has_nextpage = True

        return metainfos, has_nextpage

    def download_oneday(self, relpath, dateobj):
        dls = []

        cookiejar = CookieJar()
        response = self.download_url(self.baseurl, savecookies = cookiejar)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to get %s for %s', self.baseurl, dateobj)
            return dls

        curr_url = response.response_url

        date_url = self.searchurl.format(dateobj.strftime('%d %b %Y'), 1)
        headers = { 'X-Requested-With': 'XMLHttpRequest' }
        response = self.download_url(date_url, savecookies = cookiejar, \
                                     loadcookies = cookiejar, referer = curr_url, \
                                     headers = headers)

        pagenum = 1
        while response != None and response.webpage != None:
            curr_url = response.response_url

            metainfos, has_nextpage = self.parse_results(response.webpage, dateobj, pagenum)

            for metainfo in metainfos:
                gzurl = metainfo.pop('href')
                relurl = os.path.join(relpath, metainfo['gznum'])
                if self.save_gazette(relurl, gzurl, metainfo):
                    dls.append(relurl)

            if not has_nextpage:
                break

            page_num += 1

            date_url = self.searchurl.format(dateobj.strftime('%d %b %Y'), pagenum)
            response = self.download_url(date_url, savecookies = cookiejar, \
                                         loadcookies = cookiejar, referer = curr_url, \
                                         headers = headers)

        return dls


