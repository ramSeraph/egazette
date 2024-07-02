import re
import os
import json
import urllib.request, urllib.parse, urllib.error
import datetime

from ..utils import utils
from .basegazette import BaseGazette

class MizoramArchive(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl = 'https://egazette.mizoram.gov.in/api/gazettes?page={}&per_page={}&subject=&status=published&category_id=&department_id=&type=&month={}&year={}&raw_text='
        self.hostname = 'egazette.mizoram.gov.in'
        self.start_date = datetime.datetime(1980, 2, 28)
        self.end_date = datetime.datetime(2020, 3, 17)

                
    def process_item(self, item, dateobj):
        issuedate = datetime.datetime.strptime(item['issue_date'], '%Y-%m-%d').date()
        if issuedate != dateobj:
            return None

        metainfo = utils.MetaInfo()
        metainfo.set_date(dateobj)

        if len(item['departments']) != 1:
            self.logger.warning('Item has multiple departments %s', item) 

        metainfo['department'] = item['departments'][0]['name']
        metainfo['category']   = item['category']['name']
        metainfo['issuenum']   = item['issue_no']
        metainfo['volumenum']  = item['volume_no']
        metainfo['gznum']      = item['id']
        metainfo['issueplace'] = item['issue_place']
        metainfo['subject']    = item['subject']
        metainfo['status']     = item['status']
        metainfo['download']   = item['media']['path']

        # TODO: use the raw text?
        # metainfo['rawtext'] = item['raw_text']

        if item['type'] == 'extraordinary':
            metainfo['gztype'] = 'Extraordinary'
        else:
            metainfo['gztype'] = 'Ordinary'

        return metainfo

    def process_results(self, webpage, curr_page, dateobj):
        hasnext = False
        metainfos = []

        try:
            x = json.loads(webpage)
        except Exception as e:
            self.logger.warning('Unable to parse json for %s, page: %s', dateobj, curr_page)
            return metainfos, hasnext

        gazettes  = x['gazettes']
        last_page = gazettes['last_page']
        hasnext   = last_page != curr_page
        data      = gazettes['data']

        for item in data:
            metainfo = self.process_item(item, dateobj)
            if metainfo != None:
                metainfos.append(metainfo)

        return metainfos, hasnext

    def download_metainfos(self, relpath, metainfos, dateobj, url):
        relurls = []
                    
        for metainfo in metainfos:
            href   = metainfo.pop('download')
            url    = urllib.parse.urljoin(url, href)
            gztype = metainfo['gztype'].lower()
            docid  = f'{gztype}-issue-{metainfo["issuenum"]}-vol-{metainfo["volumenum"]}'
            relurl = os.path.join(relpath, docid)
            if self.save_gazette(relurl, url, metainfo):
                relurls.append(relurl)
        return relurls
              
    def download_oneday(self, relpath, dateobj):
        dls = []
        pagenum = 1
        per_page = 100
        while True:
            url = self.baseurl.format(pagenum, per_page, dateobj.month, dateobj.year)
            response = self.download_url(url)
            if response == None or response.webpage == None:
                self.logger.warning('Unable to get data from %s for date %s', url, dateobj) 
                return dls

            metainfos, hasnext = self.process_results(response.webpage, pagenum, dateobj)
            relurls = self.download_metainfos(relpath, metainfos, dateobj, url)
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
        self.start_date = datetime.datetime(2013, 1, 30)

    def get_page_count(self, webpage):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return None

        ids = []
        uls = d.find_all('ul', {'class': 'pagination'})
        for ul in uls:
            for li in ul.find_all('li'):
                txt = utils.get_tag_contents(li)
                try:
                    pnum = int(txt.strip())
                except:
                    pnum = None
                if pnum != None:
                    ids.append(pnum)
        ids.sort()
        return ids[-1]
 
    def parse_results(self, webpage, url):
        metainfos = []
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            self.logger.warning('Unable to get parse page from %s', url)
            return None

        for div in d.find_all('div', {'class': 'strip list_view'}):
            metainfo = utils.MetaInfo()
            h3 = div.find('h3')
            if h3:
                metainfo['subject'] = utils.get_tag_contents(h3)

            for small in div.find_all('small'):
                txt = utils.get_tag_contents(small)
                reobj = re.search('VOL\s+-\s+(?P<volnum>\w+)', txt)
                if reobj != None:
                    metainfo['volumenum'] = reobj.groupdict()['volnum']
                    continue
                reobj = re.search('ISSUE\s+-\s+(?P<issnum>\d+)', txt)
                if reobj != None:
                    metainfo['issuenum'] = reobj.groupdict()['issnum']
                    continue
                reobj = re.search('Date\s+-\s+(?P<date>\d+/\d+/\d+)', txt)
                if reobj != None:
                    datestr = reobj.groupdict()['date']
                    try: 
                        metainfo['issuedate'] = datetime.datetime.strptime(datestr, '%d/%m/%Y').date()
                    except:
                        self.logger.warning('Unable to parse date string from %s', txt)
                    continue

            spans = div.find_all('span')
            for span in spans:
                spanid = span.get('id')
                if spanid == None:
                    continue
                reobj  = re.search('^more(?P<gnum>\d+)$', spanid)
                if reobj == None:
                    continue
                gznum = reobj.groupdict()['gnum']
                metainfo['gznum'] = gznum
                # TODO: extract raw text as well?
                # raw_text = '\n'.join(span.stripped_strings)

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
            for field in ['subject', 'volumenum', 'issuenum', 'issuedate', 'gznum', 'download', 'gztype']:
                if field not in metainfo:
                    invalid = True
            if not invalid:
                metainfos.append(metainfo)

        return metainfos

    def download_metainfos(self, metainfos, fromdate, todate):
        relurls = []

        for metainfo in metainfos:
            gzurl = metainfo.pop('download')
            issuedate = metainfo.pop('issuedate')
            if issuedate < fromdate.date() or issuedate > todate.date():
                continue
            metainfo.set_date(issuedate)
            gztype = metainfo['gztype'].lower()
            docid  = f'{gztype}-issue-{metainfo["issuenum"]}-vol-{metainfo["volumenum"]}'

            relpath = os.path.join(self.name, issuedate.__str__())
            relurl = os.path.join(relpath, docid)
            if self.save_gazette(relurl, gzurl, metainfo):
                relurls.append(relurl)

        return relurls

    def sync(self, fromdate, todate, event):
        dls = []
        self.logger.info('From date %s to date %s', fromdate, todate)

        curr_url = self.baseurl
        response = self.download_url(self.baseurl)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to get data from %s for date %s to date %s', self.baseurl, fromdate, todate)
            return dls

        pagecount = self.get_page_count(response.webpage)
        if pagecount == None:
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
            if response == None or response.webpage == None:
                self.logger.warning('Unable to get data from %s for date %s to date %s', curr_url, fromdate, todate)
                metainfos = []
                continue
            metainfos = self.parse_results(response.webpage, curr_url)

        return dls
