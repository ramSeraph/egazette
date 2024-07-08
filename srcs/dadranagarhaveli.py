import re
import os
import urllib.request, urllib.parse, urllib.error
import datetime

from ..utils import utils
from .basegazette import BaseGazette

class DadraNagarHaveli(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl = 'https://ddd.gov.in/document-category/official-gazette/'
        self.hostname = 'ddd.gov.in'
        self.start_date = datetime.datetime(2021, 1, 1)


    def find_nextpage(self, d, curr_page):
        nextpage = None

        div = d.find('div', {'class': 'pagination'})
        if div == None:
            self.logger.warning('Unable to get pagination div for page %s', curr_page)
            return nextpage

        for link in div.find_all('a'):
            txt = utils.get_tag_contents(link)
            try: 
                page_no = int(txt)
            except:
                page_no = None
            if page_no == curr_page + 1:
                nextpage = link.get('href')
                break

        return nextpage


    def parse_results_page(self, webpage, curr_page):
        metainfos = []
        has_nextpage = False

        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            self.logger.warning('Unable to parse webpage for page %s', curr_page)
            return metainfos, has_nextpage

        div = d.find('div', {'class': 'data-table-container'})
        if div == None:
            self.logger.warning('Unable to get div for page %s', curr_page)
            return metainfos, has_nextpage

        table = div.find('table')
        if table == None:
            self.logger.warning('Unable to get table for page %s', curr_page)
            return metainfos, has_nextpage

        for tr in table.find_all('tr'):
            if tr.find('a') == None:
                continue

            metainfo = utils.MetaInfo()

            tds = tr.find_all('td')
            name_td = tds[0]

            txt = utils.get_tag_contents(name_td)
            txt = txt.strip().lower()

            reobj = re.search('official\s+gazette\s*(:|-|–)?\s*series\s*[-]*\s*(?P<series>.+)\s+no\s*(\.)?\s+(?P<num>\d+)', txt, flags=re.IGNORECASE)
            if reobj:
                g = reobj.groupdict()
                metainfo['series_num'] = g['series']
                metainfo['gznum'] = g['num'] 
                metainfo.set_gztype('Ordinary')
            else:
                reobj = re.search('official\s+gazette\s*(:|-)?\s*extra\s*ordinary\s+no\s*(\.)?\s+(?P<num>\d+)', txt, flags=re.IGNORECASE)
                if reobj:
                    g = reobj.groupdict()
                    metainfo['gznum'] = g['num'] 
                    metainfo.set_gztype('Extraordinary')
                else:
                    self.logger.warning('Unable to parse %s', txt)
                    continue

            date_td = tds[1]
            txt = utils.get_tag_contents(date_td)
            txt = txt.strip()
            issuedate = datetime.datetime.strptime(txt, '%d/%m/%Y').date()
            metainfo.set_date(issuedate)

            download_td = tds[2]
            link = download_td.find('a')
            if link == None or link.get('href') == None:
                self.logger.warning('Unable to get link for %s', txt)
                continue
            metainfo['download']   = link.get('href')

            metainfos.append(metainfo)
        
        nextpage = self.find_nextpage(d, curr_page)
        
        return metainfos, nextpage

    def download_oneday(self, relpath, dateobj):
        dls = []

        response = self.download_url(self.baseurl)
        pagenum = 1
        while response != None and response.webpage != None:

            metainfos, nextpage = self.parse_results_page(response.webpage, pagenum)

            for metainfo in metainfos:
                if metainfo.get_date() != dateobj:
                    continue
                gzurl = metainfo.pop('download')
                docid = gzurl.split('/')[-1][:-4]

                relurl = os.path.join(relpath, docid)
                if self.save_gazette(relurl, gzurl, metainfo):
                    dls.append(relurl)

            if nextpage == None:
                break

            pagenum += 1
            response = self.download_url(nextpage)

        return dls

