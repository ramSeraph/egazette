import urllib.parse
import datetime
import re
import os

from .basegazette import BaseGazette
from ..utils import utils
from ..utils.metainfo import MetaInfo

class Manipur(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl  = 'https://manipurgovtpress.nic.in/en/gazette_list/'
        self.hostname = 'manipurgovtpress.nic.in'
        self.page_cache = {}
 
    def download_url_cached(self, url):

        if url not in self.page_cache:
            response = self.download_url(url)

            self.page_cache[url] = response

        return self.page_cache[url]
 

    def download_nextpage(self, nextpage, curr_url):
        href = nextpage.get('href')
        if not href:
            return None

        nextpage_url = urllib.parse.urljoin(curr_url, href)

        response = self.download_url_cached(nextpage_url)

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
            elif txt and re.search('Gazette\s+Title', txt):
                order.append('subject')
            else:
                order.append('')    
        
        for field in ['gztype', 'gzdate', 'subject', 'gznum']:
            if field not in order:
                return None
        return order

    def process_row(self, tr, order, dateobj):
        metainfo = MetaInfo()
        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                txt = utils.get_tag_contents(td)
                txt = txt.strip()

                col = order[i]
                if col == 'subject':
                    metainfo[order[i]] = txt
                    link = td.find('a')
                    if link:
                        metainfo['download'] = link

                elif col == 'gztype':
                    if txt.find('Extra') >= 0:
                        metainfo.set_gztype('Extraordinary')
                    else:
                        metainfo.set_gztype('Ordinary')

                elif col == 'gzdate':
                    reobj = re.search('(?P<month>[\w.]+)\s+(?P<day>\d+),\s+(?P<year>\d+)', txt)
                    if not reobj:
                        self.logger.warning('Unable to form date for %s', txt)        
                        i += 1
                        continue

                    groupdict = reobj.groupdict()
                    month     = groupdict['month'][:3]
                    day       = groupdict['day']
                    year      = groupdict['year']

                    try:
                        d = datetime.datetime.strptime(f'{day}-{month}-{year}', '%d-%b-%Y').date()
                        metainfo['gzdate'] = d
                    except Exception as e:
                        self.logger.warning('Unable to parse date: %s', e) 
                        continue

                elif col != '':
                    metainfo[order[i]] = txt
            i += 1

        for field in ['subject', 'gztype', 'gznum', 'gzdate']:
            if field not in metainfo:
                return None

        return metainfo

    def find_next_page(self, d, curr_page):
        ul = d.find('ul', {'class': 'pagination'})
        return utils.find_next_page(ul, curr_page)

    def parse_search_results(self, webpage, dateobj, curr_page):
        nextpage  = None
        metainfos = []

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
                 
        if result_table is None:
            self.logger.warning('Unable to find the result table for %s', dateobj)
            return metainfos, nextpage

        metainfos = []
        seen_older = False
        for tr in result_table.find_all('tr'):
            if tr.find('a') is None:
                continue

            metainfo = self.process_row(tr, order, dateobj)
            if not metainfo:
                continue

            gzdate = metainfo.pop('gzdate')
            if gzdate == dateobj:
                metainfo.set_date(dateobj)
                metainfos.append(metainfo)
            elif gzdate < dateobj:
                seen_older = True
 
        if not seen_older:
            ul = d.find('ul', {'class': 'pagination'})
            nextpage = utils.find_next_page(ul, curr_page)

        return metainfos, nextpage

    def get_download_url(self, detail_url):
        response = self.download_url(detail_url)
        if not response or not response.webpage:
            self.logger.warning('Unable to get page %s', detail_url)
            return None

        d = utils.parse_webpage(response.webpage, self.parser)
        if d is None:
            return  None

        div = d.find('div', {'class': 'body-section'})
        if div is None:
            return None

        link = div.find('a')
        if link is None:
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
                self.logger.warning('Unable to get link for %s', metainfo)
                continue

            detail_url = urllib.parse.urljoin(curr_url, href)
            gzurl      = self.get_download_url(detail_url)

            if not gzurl:
                self.logger.warning('Unable to get download url for %s', detail_url)
                continue

            gztype = metainfo['gztype'].lower()
            gznum  = metainfo['gznum']
            relurl = os.path.join(relpath, f'{gztype}-{gznum}')

            if self.save_gazette(relurl, gzurl, metainfo):
                relurls.append(relurl)

        return relurls
                

    def download_oneday(self, relpath, dateobj):
        dls = []

        response = self.download_url_cached(self.baseurl)

        pagenum = 1
        while response is not None and response.webpage is not None:
            curr_url = response.response_url

            metainfos, nextpage = self.parse_search_results(response.webpage, dateobj, pagenum)

            relurls = self.download_metainfos(relpath, metainfos, curr_url)
            dls.extend(relurls)

            if nextpage is None:
                break

            pagenum += 1
            #self.logger.info('Going to page %d for date %s', pagenum, dateobj)
            response = self.download_nextpage(nextpage, curr_url)

        return dls
 
