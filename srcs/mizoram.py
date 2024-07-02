import re
import os
import json
import urllib.parse
import datetime

from ..utils import utils
from ..utils.metainfo import MetaInfo
from .basegazette import BaseGazette

class MizoramOld(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl = 'https://egazette.mizoram.gov.in/'
        self.searchurl = 'https://egazette.mizoram.gov.in/api/gazettes?page={}&per_page={}&subject=&status=published&category_id=&department_id=&type=&month={}&year={}&raw_text='
        self.hostname = 'egazette.mizoram.gov.in'
        self.end_date = datetime.datetime(2020, 3, 17)
        self.page_cache = {}

    def download_url_cached(self, url):

        if url not in self.page_cache:
            response = self.download_url(url)

            self.page_cache[url] = response

        return self.page_cache[url]

                
    def process_item(self, metainfos, item, dateobj):
        issuedate = datetime.datetime.strptime(item['issue_date'], '%Y-%m-%d').date()
        if issuedate != dateobj:
            return

        metainfo = MetaInfo()
        metainfo.set_date(dateobj)
        
        media = item['media']
        if media is not None:
            metainfo['download'] = item['media']['path']
        else:
            self.logger.warning('Media field empty for date: %s', dateobj)
            return

        if len(item['departments']) > 1:
            self.logger.warning('Item has multiple departments %s', item) 

        if len(item['departments']) > 0:
            metainfo['department'] = item['departments'][0]['name']
        metainfo['category']   = item['category']['name']
        metainfo['gznum']      = item['issue_no']
        metainfo['volume_num'] = item['volume_no']
        metainfo['id']         = item['id']
        metainfo['subject']    = item['subject']
        metainfo['status']     = item['status']
        metainfo['rawtext']    = item['raw_text']

        if item['type'] == 'extraordinary':
            metainfo.set_gztype('Extraordinary')
        else:
            metainfo.set_gztype('Ordinary')

        metainfos.append(metainfo)

    def process_results(self, webpage, curr_page, dateobj):
        hasnext = False
        metainfos = []

        try:
            x = json.loads(webpage)
        except Exception:
            self.logger.warning('Unable to parse json for %s, page: %s', dateobj, curr_page)
            return metainfos, hasnext

        gazettes  = x['gazettes']
        last_page = gazettes['last_page']
        hasnext   = last_page != curr_page
        data      = gazettes['data']

        for item in data:
            self.process_item(metainfos, item, dateobj)

        return metainfos, hasnext

    def download_metainfos(self, relpath, metainfos, dateobj):
        relurls = []
                    
        for metainfo in metainfos:
            href  = metainfo.pop('download')
            gzurl = urllib.parse.urljoin(self.baseurl, href)

            gztype = metainfo['gztype'].lower()
            docid  = f'{gztype}-issue-{metainfo["gznum"].lower()}-vol-{metainfo["volume_num"].lower()}'

            #raw_text = metainfo.pop('rawtext')
            # TODO: figure out how to properly write the txt file

            relurl = os.path.join(relpath, docid)
            if self.save_gazette(relurl, gzurl, metainfo):
                relurls.append(relurl)

        return relurls
              
    def download_oneday(self, relpath, dateobj):
        dls = []
        pagenum = 1
        per_page = 100
        while True:
            url = self.searchurl.format(pagenum, per_page, dateobj.month, dateobj.year)

            response = self.download_url_cached(url)
            if response is None or response.webpage is None:
                self.logger.warning('Unable to get data from %s for date %s', url, dateobj) 
                return dls

            metainfos, hasnext = self.process_results(response.webpage, pagenum, dateobj)

            relurls = self.download_metainfos(relpath, metainfos, dateobj)
            dls.extend(relurls)

            if not hasnext:
                break

            pagenum += 1

        return dls

class Mizoram(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl = 'https://printingstationery.mizoram.gov.in/gazettes'
        self.hostname = 'printingstationery.mizoram.gov.in'

    def get_page_count(self, webpage):
        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
            return None

        ids = []
        uls = d.find_all('ul', {'class': 'pagination'})
        for ul in uls:
            for li in ul.find_all('li'):
                txt = utils.get_tag_contents(li)
                try:
                    pnum = int(txt.strip())
                except Exception:
                    pnum = None
                if pnum is not None:
                    ids.append(pnum)
        ids.sort()
        return ids[-1]
 
    def parse_results(self, webpage, url):
        metainfos = []

        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
            self.logger.warning('Unable to get parse page from %s', url)
            return None

        for div in d.find_all('div', {'class': 'strip list_view'}):
            metainfo = MetaInfo()

            h3 = div.find('h3')
            if h3:
                metainfo['subject'] = utils.get_tag_contents(h3)

            for small in div.find_all('small'):
                txt = utils.get_tag_contents(small)

                reobj = re.search(r'VOL\s+-\s+(?P<volnum>\w+(\s+\w+)?)', txt)
                if reobj is not None:
                    volnum = reobj.groupdict()['volnum']
                    volnum = volnum.replace(' ', '')
                    metainfo['volume_num'] = volnum
                    continue

                reobj = re.search(r'ISSUE\s+-\s+(?P<issnum>\d+\s*\(?\w?\)?)', txt)
                if reobj is not None:
                    gznum = reobj.groupdict()['issnum']
                    gznum = re.sub(r'(\(|\)|\s+)', '', gznum)
                    metainfo['gznum'] = gznum
                    continue

                reobj = re.search(r'Date\s+-\s+(?P<date>\d+/\d+/\d+)', txt)
                if reobj is not None:
                    datestr = reobj.groupdict()['date']

                    try: 
                        metainfo['issuedate'] = datetime.datetime.strptime(datestr, '%d/%m/%Y').date()
                    except Exception:
                        self.logger.warning('Unable to parse date string from %s', txt)

                    continue

            spans = div.find_all('span')
            for span in spans:
                spanid = span.get('id')
                if spanid is None:
                    continue
                reobj  = re.search(r'^more(?P<id>\d+)$', spanid)
                if reobj is None:
                    continue
                id = reobj.groupdict()['id']
                metainfo['id'] = id
                raw_text = '\n'.join(span.stripped_strings)
                metainfo['rawtext'] = raw_text

            links = div.find_all('a')
            for link in links:
                txt = utils.get_tag_contents(link)
                txt = txt.strip()
                if txt == 'VIEW FILE':
                    metainfo['download'] = urllib.parse.urljoin(url, link.get('href'))
                    continue
                click_handler = link.get('onclick')
                if click_handler:
                    if click_handler.startswith('searchByDepartment'):
                        metainfo['department'] = txt
                    elif click_handler.startswith('searchByCategory'):
                        metainfo['category'] = txt
                    continue
                if txt == 'Extra-Ordinary':
                    metainfo['gztype'] = 'Extraordinary'
                elif txt == 'Regular':
                    metainfo['gztype'] = 'Ordinary'

            invalid = False
            for field in ['subject', 'volume_num', 'gznum', 'issuedate', 'id', 'download', 'gztype']:
                if field not in metainfo:
                    invalid = True
            if not invalid:
                metainfos.append(metainfo)

        return metainfos

    def download_metainfos(self, metainfos, fromdate, todate):
        relurls = []

        for metainfo in metainfos:
            issuedate = metainfo.pop('issuedate')

            if issuedate > todate or issuedate < fromdate:
                continue

            metainfo.set_date(issuedate)

            gztype = metainfo['gztype'].lower()
            gznum  = metainfo['gznum'].lower()
            volnum = metainfo['volume_num'].lower()
            docid  = f'{gztype}-issue-{gznum}-vol-{volnum}'

            gzurl = metainfo.pop('download')

            relpath = os.path.join(self.name, issuedate.__str__())
            relurl  = os.path.join(relpath, docid)
            if self.save_gazette(relurl, gzurl, metainfo):
                relurls.append(relurl)

        return relurls

    def sync(self, fromdate, todate, event):
        dls = []

        fromdate = fromdate.date()
        todate   = todate.date()

        self.logger.info('From date %s to date %s', fromdate, todate)

        curr_url = self.baseurl
        response = self.download_url(self.baseurl)
        if response is None or response.webpage is None:
            self.logger.warning('Unable to get data from %s for date %s to date %s', self.baseurl, fromdate, todate)
            return dls

        pagecount = self.get_page_count(response.webpage)
        if pagecount is None:
            self.logger.warning('Unable to get page count from %s for date %s to date %s', self.baseurl, fromdate, todate) 
            return dls

        metainfos = self.parse_results(response.webpage, curr_url)

        pagenum = 1
        while pagenum <= pagecount:
            if event.is_set():
                self.logger.warning('Exiting prematurely as timer event is set')
                break
            relurls = self.download_metainfos(metainfos, fromdate, todate)
            self.logger.info('Got %d gazettes for pagenum %s', len(relurls), pagenum)
            dls.extend(relurls)

            pagenum += 1
            curr_url = self.baseurl + f'?page={pagenum}'
            response = self.download_url(curr_url)
            if response is None or response.webpage is None:
                self.logger.warning('Unable to get data from %s for date %s to date %s', curr_url, fromdate, todate)
                metainfos = []
                continue
            metainfos = self.parse_results(response.webpage, curr_url)

        return dls
