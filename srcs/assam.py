import urllib.parse
import re
import os
import datetime

from ..utils import utils
from ..utils.metainfo import MetaInfo
from .basegazette import BaseGazette

class Assam(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl  = 'https://dpns.assam.gov.in/'
        self.hostname = 'dpns.assam.gov.in'
        self.page_cache = {}


    def download_url_cached(self, url):

        if url not in self.page_cache:
            response = self.download_url(url)

            self.page_cache[url] = response

        return self.page_cache[url]
 

    def get_yearly_links(self):
        olinks = {}
        elinks = {}

        response = self.download_url_cached(self.baseurl)
        if response is None or response.webpage is None:
            self.logger.warning('Unable to get %s for getting top links', self.baseurl)
            return olinks, elinks

        d = utils.parse_webpage(response.webpage, self.parser)
        if d is None:
            self.logger.warning('Unable to parse %s for getting top links', self.baseurl)
            return olinks, elinks

        for li in d.find_all('li', {'data-level': '2'}):
            link = li.find('a')
            if link is None:
                continue

            href = link.get('href')
            if href is None:
                continue

            txt = utils.get_tag_contents(li)
            txt = txt.strip()

            reobj = re.match('^Extraordinary-(?P<year>\d+)$', txt)
            if reobj:
                year = reobj.groupdict()['year']
                elinks[year] = urllib.parse.urljoin(self.baseurl, href)
                continue

            reobj = re.match('^Weekly\s+Gazette-(?P<year>\d+)$', txt)
            if reobj:
                year = reobj.groupdict()['year']
                olinks[year] = urllib.parse.urljoin(self.baseurl, href)
                continue

        return olinks, elinks

    def process_row(self, li, metainfos):
        link = li.find('a')
        if link is None:
            return

        metainfo = MetaInfo()
        metainfo['subject'] = utils.get_tag_contents(link)
        metainfo['download'] = link.get('href')
        metainfos.append(metainfo)


    def parse_results(self, webpage, url, curr_page):
        metainfos = []
        nextpage  = None
        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
            self.logger('Unable to parse webpage for %s', url)
            return metainfos, nextpage

        div = d.find('div', {'class': 'content-portion'})
        if div is None:
            self.logger('Unable to locate relevant div in webpage for %s', url)
            return metainfos, nextpage

        uls = div.find_all('ul')
        pager_ul = None
        data_ul  = None
        for ul in uls:
            classes = ul.get('class')
            if classes is None:
                data_ul = ul
            elif 'pager' in classes:
                pager_ul = ul

        if data_ul is None:
            return metainfos, nextpage

        for li in data_ul.find_all('li'):
            self.process_row(li, metainfos)

        if pager_ul is not None:
            nextpage = utils.find_next_page(pager_ul, curr_page)

        return metainfos, nextpage

    def parse_download_page(self, url, metainfo):
        infos = []
        response = self.download_url(url)
        if response is None or response.webpage is None:
            self.logger.warning('Unable to get page %s for %s', url, metainfo)
            return infos
        d = utils.parse_webpage(response.webpage, self.parser)
        if d is None:
            self.logger.warning('Unable to parse page %s for %s', url, metainfo)
            return infos

        div = d.find('div', {'class': 'content-portion'})
        if div is None:
            self.logger.warning('Unable to locate relevant div in webpage for %s for %s', url, metainfo)
            return infos

        table = div.find('table')
        if table is None:
            self.logger.warning('Unable to locate download table in webpage for %s for %s', url, metainfo)
            return infos

        for tr in table.find_all('tr'):
            if tr.find('a') is None:
                continue

            tds = tr.find_all('td')
            file_td = tds[0]
            filename = utils.get_tag_contents(file_td)
            filename = filename.strip()

            link = file_td.find('a')
            if link and link.get('href'):
                download_url = link.get('href')
                infos.append([filename, download_url])

        return infos

    def handle_special_cases(self, subject):
        # 2017 page 7
        if subject == 'No. 722 LGL 175-2005-Pt-I-71_PART - B':
            return [ datetime.datetime(2017, 12, 4).date() ]
        if subject == 'No. 722 LGL 175-2005-Pt-I-71_PART - A':
            return [ datetime.datetime(2017, 12, 4).date() ]
        if subject == 'No. 720 LGL 175-2005-Pt-I-71':
            return [ datetime.datetime(2017, 12, 4).date() ]

        # 2017 page 59
        if subject == 'No. 126 ELE.144-2015-712 01-04-17':
            return [ datetime.datetime(2017, 4, 1).date() ]
        
        return []

    def dump(self, main_subject, subject, curr_url):

        import json

        parts = curr_url.split('?')
        if len(parts) == 1:
            page = '1'
        else:
            page = parts[1].split('=')[1]

        typ = parts[0].split('/')[-1]

        with open('ordinary_top_urls.jsonl', 'a') as f:
            f.write(json.dumps({'typ': typ, 'page': page, 'main_subject': main_subject, 'subject': subject}))
            f.write('\n')

    def download_metainfo(self, relpath, metainfo, curr_url, dateobj, gztype):
        relurls = []

        main_subject = metainfo.pop('subject')
        href = metainfo.pop('download')

        main_subject = main_subject.strip()


        #issuedates = []
        ## TODO: consider splitting by '&'
        #for reobj in re.finditer("(Dated|Datwd|Dateded)?\s+(?P<day>\d+)\s*(-| )\s*(?P<month>\d+)\s*(-| )\s*(?P<year>\d+)", main_subject, flags=re.IGNORECASE):
        #    g = reobj.groupdict()

        #    try:
        #        year = int(g['year'])
        #        if year < 100:
        #            year += 2000
        #        month = int(g['month'])
        #        day   = int(g['day'])
        #        issuedate = datetime.datetime(year, month, day).date()
        #        issuedates.append(issuedate)
        #    except Exception:
        #        self.logger.warning('Unable to create date from %s', g)

        #if len(issuedates) == 0:
        #    issuedates = self.handle_special_cases(main_subject)

        #if len(issuedates) == 0:
        #    self.logger.warning('Unable to get dates from %s', main_subject)
        #    return relurls

        # TODO: a simple 'in' would suffice?
        #found_date = False
        #for issuedate in issuedates:
        #    if issuedate == dateobj:
        #        found_date = True
        #        break

        #if not found_date:
        #    return relurls

        download_page_url = urllib.parse.urljoin(curr_url, href)
        infos = self.parse_download_page(download_page_url, metainfo)
        for info in infos:
            newmeta = MetaInfo()
            newmeta.set_gztype(gztype)

            subject = info[0]
            gzurl   = info[1]
            #self.dump(main_subject, subject, curr_url)
            #continue

            reobj = re.search("(dated|datwd|dateded)[_]+(?P<day>\d+)[_]*(-| )[_]*(?P<month>\d+)[_]*(-| )[_]*(?P<year>\d+)", subject)
            if reobj is None:
                self.logger.warning('Unable to get date from %s', subject)
                continue
            g = reobj.groupdict()
            try:
                year = int(g['year'])
                if year < 100:
                    year += 2000
                month = int(g['month'])
                day   = int(g['day'])
                issuedate = datetime.datetime(year, month, day).date()
                if issuedate != dateobj:
                    continue
                newmeta.set_date(dateobj)
            except Exception:
                self.logger.warning('Unable to create date from %s', g)
                continue

            reobj = re.match('^no(\.)?[_]+(?P<num>\d+).*$', subject)
            if reobj is None:
                self.logger.warning('Unable to get gazette number from %s', subject)
                continue
            g = reobj.groupdict()
            newmeta['gznum']   = g['num'].strip()
            newmeta['subject'] = main_subject

            relurl = os.path.join(relpath, newmeta['gznum'])
            if self.save_gazette(relurl, gzurl, newmeta):
                relurls.append(relurl)
        return relurls


    def download_onetype(self, dls, relpath, dateobj, url, gztype):
        pagenum = 1
        response = self.download_url_cached(url)
        while response is not None and response.webpage is not None:
            curr_url = response.response_url
            metainfos, nextpage = self.parse_results(response.webpage, curr_url, pagenum)

            for metainfo in metainfos:
                relurls = self.download_metainfo(relpath, metainfo, curr_url, dateobj, gztype)
                dls.extend(relurls)

            if nextpage is None:
                break

            pagenum += 1
            nexturl = urllib.parse.urljoin(curr_url, nextpage['href'])
            response = self.download_url_cached(nexturl)


    def download_oneday(self, relpath, dateobj):
        dls = []
        year = dateobj.year

        ordinary_urls_by_year, extraordinary_urls_by_year = self.get_yearly_links()

        ordinary_url = ordinary_urls_by_year.get(str(year), None)
        extraordinary_urls = [ extraordinary_urls_by_year.get(str(year - 1), None), \
                               extraordinary_urls_by_year.get(str(year), None), \
                               extraordinary_urls_by_year.get(str(year + 1), None) ]

        #for extraordinary_url in extraordinary_urls:
        #    if extraordinary_url is not None:
        #        self.download_onetype(dls, relpath, dateobj, extraordinary_url, 'Extraordinary')
        if ordinary_url is not None:
            self.download_onetype(dls, relpath, dateobj, ordinary_url, 'Ordinary')

        return dls
