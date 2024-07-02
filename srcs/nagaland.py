import datetime
import os
import re
import urllib.request, urllib.parse, urllib.error

from .basegazette import BaseGazette
from ..utils import utils
                
class Nagaland(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.hostname = 'govtpress.nagaland.gov.in'
        self.baseurl  = 'https://govtpress.nagaland.gov.in/egazette/'
        self.start_date = datetime.datetime(2017, 1, 1)

    def get_year_url(self, webpage, year):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return None
        for link in d.find_all('a'):
            txt = utils.get_tag_contents(link)
            txt = txt.strip()
            if txt == str(year):
                return link.get('href')
        return None

    def get_metainfos(self, webpage, dateobj):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return None

        article = d.find('article')
        if article == None:
            return None

        items = []
        if dateobj.year == 2017:
            for li in article.find_all('li'):
                link = li.find('a')
                if link == None:
                    continue
                href = link.get('href')
                if href == None:
                    continue
                txt = utils.get_tag_contents(link)
                items.append((txt, href))
        else:
            table = article.find('table')
            if table == None:
                return None
            for tr in table.find_all('tr'):
                if tr.find('a') == None:
                    continue
                tds = tr.find_all('td')
                if len(tds) != 2:
                    continue
                txt = utils.get_tag_contents(tds[1])
                link = tds[0].find('a')
                if link == None:
                    continue
                href = link.get('href')
                if href != None and href.endswith('.pdf'):
                    items.append((txt, href))

        metainfos = []
        for txt, url in items:
            txt = txt.strip()
            if txt.startswith('Gazette'):
                txt = txt[len('Gazette'):]
                txt = txt.strip()
            reobj = re.search('(?P<day>\d+)\s*(th|st|nd)?\s*(?P<month>[a-zA-Z]+)\s*(,)?\s*(?P<year>\d+)', txt)
            if reobj == None:
                reobj = re.search('(?P<month>[a-zA-Z]+)\s*(?P<day>\d+)\s*(th|st)?\s*(,)?\s*(?P<year>\d+)', txt)
            if reobj == None:
                self.logger.warning('Unable to match date string for %s', txt)
                continue
            g = reobj.groupdict()
            g['month'] = g['month'][:3]
            issuedate = datetime.datetime.strptime(f'{g["day"]}-{g["month"]}-{g["year"]}', '%d-%b-%Y').date()
            metainfo = utils.MetaInfo()
            metainfo.set_date(issuedate)
            metainfo['download'] = url
            metainfos.append(metainfo)

        return metainfos

    def download_oneday(self, relpath, dateobj):
        dls = []

        response = self.download_url(self.baseurl)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to get %s for date %s', self.baseurl, dateobj)
            return dls

        year_href = self.get_year_url(response.webpage, dateobj.year)
        if year_href == None:
            self.logger.warning('Unable to get year url from %s for date %s', self.baseurl, dateobj)
            return dls

        year_url = urllib.parse.urljoin(self.baseurl, year_href)

        response = self.download_url(year_url)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to get %s for date %s', year_url, dateobj)
            return dls

        metainfos = self.get_metainfos(response.webpage, dateobj)
        if metainfos == None:
            self.logger.warning('Unable to parse year page at %s for date %s', year_url, dateobj)
            return dls

        for metainfo in metainfos:
            if metainfo.get_date() != dateobj:
                continue

            gzurl = metainfo.pop('download')
            relurl = os.path.join(relpath, 'gazette')
            if self.save_gazette(relurl, gzurl, metainfo):
                dls.append(relurl)

        return dls

