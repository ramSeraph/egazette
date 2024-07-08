import re
import os
import urllib.request, urllib.parse, urllib.error
import datetime

from ..utils import utils
from .basegazette import BaseGazette

class Lakshadweep(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl = 'https://lakshadweep.gov.in/document-category/gazatte-notifications/'
        self.hostname = 'lakshadweep.gov.in'
        self.start_date = datetime.datetime(2017, 1, 1)


    def find_nextpage(self, d, curr_page):
        nextpage = None

        div = d.find('div', {'class': 'pegination'})
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

        div = d.find('div', {'class': 'distTableContent'})
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

            tds = tr.find_all('td')
            name_td = tds[0]

            txt = utils.get_tag_contents(name_td)
            txt = txt.strip().lower()

            #VOL. LX No.9 FRIDAY, 10th MAY, 2024 / 20th VIASAKHA, 1946 (SAKA)</span></td>
            reobj = re.search('vo(l|i)(\.|,)\s*(?P<vol>\w+)(\.)?\s*no\.\s*(?P<num>\d+(\(\w+\))?)\s*(,|\.)?\s*[\w,]+\s*(?P<day>\d+)\s*(st|nd|rd|th)?\s*(?P<month>\w+)(,|\.)?\s*(?P<year>\d+)', txt)
            if reobj == None:
                self.logger.warning('Unable to parse %s', txt)
                continue
            g = reobj.groupdict()
            try:
                issuedate = datetime.datetime.strptime(f'{g["day"]}-{g["month"][:3]}-{g["year"]}', '%d-%b-%Y').date()
            except:
                self.logger.warning('Unable to get date from %s', g)
                continue

            download_td = tds[2]
            link = download_td.find('a')
            if link == None or link.get('href') == None:
                self.logger.warning('Unable to get link for %s', txt)
                continue

            metainfo = utils.MetaInfo()
            metainfo.set_date(issuedate)
            metainfo['subject']    = txt
            metainfo['download']   = link.get('href')
            metainfo['volume_num'] = g['vol']
            metainfo['gznum']      = g['num']
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
                docid = f'vol-{metainfo["volume_num"]}-no-{metainfo["gznum"]}'

                relurl = os.path.join(relpath, docid)
                if self.save_gazette(relurl, gzurl, metainfo):
                    dls.append(relurl)

            if nextpage == None:
                break

            pagenum += 1
            response = self.download_url(nextpage)

        return dls

