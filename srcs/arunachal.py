from http.cookiejar import CookieJar
import re
import os
import datetime

from ..utils import utils
from ..utils.metainfo import MetaInfo
from .basegazette import BaseGazette

class Arunachal(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.ordinary_url      = 'https://printing.arunachal.gov.in/normal_gazette/?page_num={}'
        self.extraordinary_url = 'https://printing.arunachal.gov.in/extra_ordinary_gazette/?page_num={}'
        self.gzurl             = 'https://printing.arunachal.gov.in/download/' 
        self.hostname          = 'printing.arunachal.gov.in'

    def get_form_data(self, form):
        postdata = []

        tags = form.find_all('input')
        for tag in tags:
            name  = tag.get('name')
            value = tag.get('value')
            if name:
                postdata.append((name, value))

        return postdata

    def parse_date(self, txt):
        reobj = re.search('published\s+date\s+:\s+(?P<month>\w+)(\.)?\s+(?P<day>\d+)(,)?\s+(?P<year>\d+)', txt)
        if reobj is None:
            self.logger.warning('Unable to parse %s', txt)
            return None

        g = reobj.groupdict()
        pubdate = datetime.datetime.strptime(f'{g["day"]}-{g["month"][:3]}-{g["year"]}', '%d-%b-%Y').date()
        return pubdate

    def process_row_ordinary(self, form):
        metainfo = MetaInfo()
        metainfo.set_gztype('Ordinary')

        metainfo['postdata'] = self.get_form_data(form)

        span = form.find('span')
        if span is None:
            self.logger.warning('Unable to find span')
            return None
        txt = utils.get_tag_contents(span)
        if txt:
            txt = txt.strip()
        splits = txt.split('|')
        splits = [ s.strip() for s in splits if s.strip() != '' ]
        if len(splits) != 2:
            self.logger.warning('Unable to parse %s', txt)
            return None

        pubdate = self.parse_date(splits[1])
        if pubdate is None:
            return None
        metainfo.set_date(pubdate)

        link = form.find('a')
        txt = utils.get_tag_contents(link)
        if txt:
            txt = txt.strip()

        # TODO: parse parts and gazette number
        metainfo['subject'] = txt

        return metainfo


    def process_row_extraordinary(self, form):
        metainfo = MetaInfo()
        metainfo.set_gztype('Extraordinary')

        metainfo['postdata'] = self.get_form_data(form)

        span = form.find('span')
        if span is None:
            self.logger.warning('Unable to find span')
            return None

        txt = utils.get_tag_contents(span)
        if txt:
            txt = txt.strip()
        splits = txt.split('|')
        splits = [ s.strip() for s in splits if s.strip() != '' ]
        if len(splits) != 3:
            self.logger.warning('Unable to parse %s', txt)
            return None

        metainfo['subject'] = splits[0]

        pubdate = self.parse_date(splits[2])
        if pubdate is None:
            return None
        metainfo.set_date(pubdate)

        link = form.find('a')
        if link is None:
            self.logger.warning('Unable to find link')
            return None
        txt = utils.get_tag_contents(link)
        if txt:
            txt = txt.strip()
        metainfo['notification_num'] = txt

        return metainfo


    def parse_results(self, webpage, pagenum, process_row):
        metainfos = []
        has_nextpage = False

        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
            self.logger.warning('Unable to parse the %s page', pagenum)
            return metainfos, has_nextpage

        download_forms = d.find_all('form', {'action': '/download/'})
        for form in download_forms:
            metainfo = process_row(form)
            if metainfo is not None:
                metainfos.append(metainfo)

        page_links = d.find_all('a', {'class': 'page-link'})
        for link in page_links:
            txt = utils.get_tag_contents(link)
            if txt.strip() == 'Next':
                has_nextpage = True

        return metainfos, has_nextpage

    def download_metainfos(self, metainfos, fromdate, todate, cookiejar, referer):
        relurls = []
        for metainfo in metainfos:
            issuedate = metainfo.get_date() 
            if issuedate < fromdate.date() or issuedate > todate.date():
                continue

            postdata = metainfo.pop('postdata')
            postdata_dict = dict(postdata)
            filename = postdata_dict['filename'].split('/')[-1]
            filename = filename[:-4]

            relpath = os.path.join(self.name, issuedate.__str__())
            relurl = os.path.join(relpath, filename)
            if self.save_gazette(relurl, self.gzurl, metainfo, postdata = postdata, \
                                 cookiefile = cookiejar, validurl = False, referer = referer):
                relurls.append(relurl)

        return relurls


    def sync_section(self, dls, fromdate, todate, event, process_row, baseurl):
        cookiejar = CookieJar()
        pagenum   = 1

        while True:
            url = baseurl.format(pagenum)
            response = self.download_url(url, savecookies = cookiejar, loadcookies = cookiejar)
            if response is None or response.webpage is None:
                self.logger.warning('Unable to get data from %s for date %s to date %s', url, fromdate, todate)
                break

            if event.is_set():
                self.logger.warning('Exiting prematurely as timer event is set')
                break

            metainfos, has_nextpage = self.parse_results(response.webpage, pagenum, process_row)

            relurls = self.download_metainfos(metainfos, fromdate, todate, cookiejar, url)

            self.logger.info('Got %d gazettes for pagenum %s', len(relurls), pagenum)
            dls.extend(relurls)

            if not has_nextpage:
                break
            pagenum += 1

    def sync(self, fromdate, todate, event):
        dls = []
        self.logger.info('From date %s to date %s', fromdate, todate)

        self.sync_section(dls, fromdate, todate, event, self.process_row_ordinary, self.ordinary_url)
        self.sync_section(dls, fromdate, todate, event, self.process_row_extraordinary, self.extraordinary_url)

        return dls

