import re
import os
import urllib.request, urllib.parse, urllib.error
import datetime

from ..utils import utils
from .basegazette import BaseGazette

class Meghalaya(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl = 'https://megpns.gov.in/gazette/archive.asp?wdate={}&wmonth={}&datepub={}'
        self.hostname = 'megpns.gov.in'
        self.start_date = datetime.datetime(2006, 3, 1)

    def get_metainfos(self, webpage, dateobj):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return None
        article = d.find('article')
        if article == None:
            return None

        metainfos = [] 
        for li in article.find_all('li'):
            link = li.find('a')
            if not link:
                continue
            href = link.get('href')
            if href == None:
                continue
            subject = utils.get_tag_contents(link)
            subject = subject.strip()
            metainfo = utils.MetaInfo()
            metainfo.set_date(dateobj)
            metainfo['subject'] = subject
            metainfo['download'] = href
            metainfos.append(metainfo)

        return metainfos

    def download_metainfos(self, relpath, metainfos, url):
        relurls = []
        for metainfo in metainfos:
            js = metainfo.pop('download')
            reobj = re.search('javascript:openwin\("(?P<gurl>[^\"]+)"\)', js)
            if reobj == None:
                self.logger.warning('Unable to get gazette url from url %s', js)
                continue
            href = reobj.groupdict()['gurl']
            fname = href.split('/')[-1]
            reobj = re.search('\d+-\d+-\d+-(?P<part>\w+).pdf', fname)
            if reobj == None:
                self.logger.warning('Unable to get part number from url %s', href)
                continue
            partnum = reobj.groupdict()['part']
            if metainfo['subject'].startswith('Extraordinary'):
                metainfo.set_gztype('Extraordinary')
            else:
                metainfo.set_gztype('Ordinary')
            gzurl = urllib.parse.urljoin(url, href)
            relurl = os.path.join(relpath, partnum)
            if self.save_gazette(relurl, gzurl, metainfo):
                relurls.append(relurl)
        return relurls

    def download_oneday(self, relpath, dateobj):
        dls = []
        url = self.baseurl.format(dateobj.year, dateobj.month, dateobj.day)

        response = self.download_url(url)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to get page %s for date %s', url, dateobj)
            return dls

        metainfos = self.get_metainfos(response.webpage, dateobj)
        if metainfos == None:
            self.logger.warning('Unable to parse page %s for date %s', url, dateobj)
            return dls
        
        relurls = self.download_metainfos(relpath, metainfos, url)
        dls.extend(relurls)
        return dls
        

