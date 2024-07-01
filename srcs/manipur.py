import urllib.request, urllib.parse, urllib.error
import datetime
import re
import os

from .basegazette import BaseGazette
from ..utils import utils

class Manipur(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl  = 'https://manipurgovtpress.nic.in/en/gazette_list/'
        self.hostname = 'manipurgovtpress.nic.in'
        self.start_date   = datetime.datetime(2010, 4, 1)
 
    def download_nextpage(self, nextpage, curr_url):
        href = nextpage.get('href') 
        if not href:
            return None

        nextpage_url = urllib.parse.urljoin(curr_url, href)
        response = self.download_url(nextpage_url)
        return response

    def find_field_order(self, tr):
        order  = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Gazette\s+Type', txt):
                order.append('gztype')
            elif txt and re.search('Publication\s+Date', txt):
                order.append('gzdate')
            elif txt and re.search('Gazette\s+Number', txt):
                order.append('gznum')
            elif txt and re.search('Gazzete\s+Title', txt):
                order.append('subject')
            else:
                order.append('')    
        
        for field in ['gztype', 'gzdate', 'subject', 'gznum']:
            if field not in order:
                return None
        return order

    def process_row(self, tr, order, dateobj):
        metainfo = utils.MetaInfo()
        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                txt = utils.get_tag_contents(td)
                txt = txt.strip()
                if order[i] == 'subject':
                    metainfo[order[i]] = txt
                    link = td.find('a')
                    if link:
                        metainfo['download'] = link

                elif order[i] == 'gztype':
                    if txt.find('Extra') != -1:
                        metainfo.set_gztype('Extraordinary')
                    else:
                        metainfo.set_gztype('Ordinary')

                elif order[i] == 'gzdate':
                    reobj = re.search('(?P<month>[\w.]+)\s+(?P<day>\d+),\s+(?P<year>\d+)', txt)
                    if not reobj:
                        self.logger.warning('Unable to form date for %s', txt)        
                        i += 1
                        continue
                    groupdict = reobj.groupdict()
                    month     = groupdict['month'][:3]
                    day       = groupdict['day']
                    year      = groupdict['year']

                    d = datetime.datetime.strptime(f'{day}-{month}-{year}', '%d-%b-%Y').date()
                    metainfo['gzdate'] = d

                else:
                    metainfo[order[i]] = txt
            i += 1

        return metainfo


    def find_next_page(self, d, curr_page):
        ul = d.find('ul', {'class': 'pagination'})
        for li in ul.find_all('li'):
            link = li.find('a')
            txt = utils.get_tag_contents(li)
            if txt:
                try: 
                    page_no = int(txt)
                except:
                    page_no = None
                if page_no == curr_page + 1 and link:
                    return link
        return None


    def parse_search_results(self, webpage, dateobj, curr_page):
        nextpage  = None
        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse search result page for %s', dateobj)
            return metainfos, nextpage

        result_table = None
            
        for table in d.find_all('table'):
            for tr in table.find_all('tr'):
                order = self.find_field_order(tr)
                if order:
                    result_table = table
                    break
                 
        if result_table == None:
            self.logger.warning('Unable to find the result table for %s', dateobj)
            return dls

        minfos = []
        seen_older = False
        for tr in result_table.find_all('tr'):
            if tr.find('a') == None:
                continue
            metainfo = self.process_row(tr, order, dateobj)
            if metainfo:
                gzdate = metainfo.pop('gzdate')
                if gzdate == None:
                    continue
                if gzdate == dateobj:
                    metainfo.set_date(dateobj)
                    minfos.append(metainfo)
                elif gzdate < dateobj:
                    seen_older = True
 
        if not seen_older:
            nextpage = self.find_next_page(d, curr_page)

        return minfos, nextpage

    def get_download_url(self, detail_url):
        response = self.download_url(detail_url)
        if not response or not response.webpage:
            self.logger.warning('Unable to get page %s', detail_url)
            return None

        d = utils.parse_webpage(response.webpage, self.parser)
        if d == None:
            return  None

        div = d.find('div', {'class': 'body-section'})
        if div == None:
            return None

        link = div.find('a')
        if link == None:
            return None

        href = link.get('href')
        fname = href.split('/')[-1]
        if fname == 'no-file.pdf':
            self.logger.warning('Unusable download link at %s', detail_url)
            return None
        return urllib.parse.urljoin(detail_url, href)

    def download_metainfos(self, relpath, metainfos, curr_url):
        relurls = []
        for metainfo in metainfos:
            link = metainfo.pop('download')
            href = link.get('href')
            if not href:
                continue
            detail_url = urllib.parse.urljoin(curr_url, href)
            gztype = metainfo['gztype'].lower()
            gznum  = metainfo['gznum']
            relurl = os.path.join(relpath, f'{gztype}-{gznum}')
            gzurl  = self.get_download_url(detail_url)
            if not gzurl:
                self.logger.warning('Unable to get download url for %s', detail_url)
                continue
            if self.save_gazette(relurl, gzurl, metainfo):
                relurls.append(relurl)
        return relurls
                

    def download_oneday(self, relpath, dateobj):
        dls = []

        response = self.download_url(self.baseurl)

        pagenum = 1
        while response != None and response.webpage != None:
            curr_url = response.response_url
            metainfos, nextpage = self.parse_search_results(response.webpage, dateobj, pagenum)
            relurls = self.download_metainfos(relpath, metainfos, curr_url)
            dls.extend(relurls)
            if nextpage:
                pagenum += 1
                self.logger.info('Going to page %d for date %s', pagenum, dateobj)
                response = self.download_nextpage(nextpage, curr_url)
            else:
                break
        return dls
 
