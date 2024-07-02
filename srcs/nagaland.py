import datetime
import os
import re
import urllib.request
import urllib.parse
import urllib.error

from .basegazette import BaseGazette
from ..utils import utils
from ..utils.metainfo import MetaInfo
                
class Nagaland(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.hostname = 'govtpress.nagaland.gov.in'
        self.baseurl  = 'https://govtpress.nagaland.gov.in/egazette/'

    def get_year_url(self, webpage, year):
        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
            return None
        for link in d.find_all('a'):
            txt = utils.get_tag_contents(link)
            txt = txt.strip()
            if txt == str(year):
                return link.get('href')
        return None

    def get_metainfos(self, webpage, year):
        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
            return None

        article = d.find('article')
        if article is None:
            return None

        items = []
        if year == 2017:
            for li in article.find_all('li'):
                link = li.find('a')
                if link is None:
                    continue

                href = link.get('href')
                if href is None:
                    continue

                txt = utils.get_tag_contents(link)

                items.append((txt, href))
        else:
            table = article.find('table')
            if table is None:
                return None

            for tr in table.find_all('tr'):
                if tr.find('a') is None:
                    continue

                tds = tr.find_all('td')
                if len(tds) != 2:
                    continue

                txt = utils.get_tag_contents(tds[1])

                link = tds[0].find('a')
                if link is None:
                    continue

                href = link.get('href')

                if href is not None and href.endswith('.pdf'):
                    items.append((txt, href))

        metainfos = []
        for txt, url in items:
            txt = txt.strip()

            if txt.startswith('Gazette'):
                txt = txt[len('Gazette'):]
                txt = txt.strip()

            reobj = re.search(r'(?P<day>\d+)\s*(th|st|nd)?\s*(th|st|nd)?\s*(?P<month>[a-zA-Z]+)\s*(,)?\s*(?P<year>\d+)', txt)
            if reobj is None:
                reobj = re.search(r'(?P<month>[a-zA-Z]+)\s*(?P<day>\d+)\s*(th|st)?\s*(,)?\s*(?P<year>\d+)', txt)
            if reobj is None:
                self.logger.warning('Unable to match date string for %s', txt)
                continue

            g = reobj.groupdict()

            g['month'] = g['month'][:3]

            issuedate  = datetime.datetime.strptime(f'{g["day"]}-{g["month"]}-{g["year"]}', '%d-%b-%Y').date()

            metainfo = MetaInfo()
            metainfo.set_date(issuedate)
            metainfo['download'] = url

            metainfos.append(metainfo)

        return metainfos

    def sync(self, fromdate, todate, event):
        dls = []
 
        response = self.download_url(self.baseurl)
        if response is None or response.webpage is None:
            self.logger.warning('Unable to get %s for start date %s, end data %s', 
                                self.baseurl, fromdate, todate)
            return dls

        main_webpage = response.webpage
        
        fromyear = fromdate.year
        toyear   = todate.year

        for year in range(fromyear, toyear+1):

            year_href = self.get_year_url(main_webpage, year)
            if year_href is None:
                self.logger.warning('Unable to get year url from %s for year %d', self.baseurl, year)
                return dls

            year_url = urllib.parse.urljoin(self.baseurl, year_href)
 
            response = self.download_url(year_url)
            if response is None or response.webpage is None:
                self.logger.warning('Unable to get %s for year %d', year_url, year)
                return dls
 
            metainfos = self.get_metainfos(response.webpage, year)
            if metainfos is None:
                self.logger.warning('Unable to parse year page at %s for year %s', year_url, year)
                return dls

            for metainfo in metainfos:
                if event.is_set():
                    self.logger.warning('Exiting prematurely as timer event is set')
                    return dls

                metadate = metainfo.get_date()

                if fromdate.date() <= metadate <= todate.date():
                    gzurl = metainfo.pop('download')

                    gzurl = urllib.parse.urljoin(year_url, gzurl)

                    relpath = os.path.join(self.name, metadate.__str__())
                    relurl  = os.path.join(relpath, 'gazette')

                    if self.save_gazette(relurl, gzurl, metainfo):
                        dls.append(relurl)

        return dls
