from http.cookiejar import CookieJar
import re
import os
import datetime

from pprint import pprint

from ..utils import utils
from ..utils.metainfo import MetaInfo
from .basegazette import BaseGazette

def parse_ng_subject(txt):
    reobj = re.match(r'(Complete)?\s*Normal\s+Gazette\s*-?\s*(of)?\s*(?P<year>\d{4})', txt, flags=re.IGNORECASE)
    if reobj:
        g = reobj.groupdict()
        return { 'part': 'complete', 'year': g['year'] }

    reobj = re.match(r'Normal\s+Gazette\s*-?\s*No\s*\.\s*(?P<from>\d+)\s*to\s*(?P<to>\d+)\s*of\s*(?P<year>\d{4})', txt, flags=re.IGNORECASE)
    if reobj:
        g = reobj.groupdict()
        return { 'part': f'{g["from"]}-{g["to"]}', 'year': g['year'] }

    txt = re.sub(r'(Normal\s+Gazette|Noram\s+Gazette|Norma\s+Gazette)', 'NG', txt)

    reobj = re.match(r'(?P<numb>\d+)?\s*\.?\s*NG\s*(\.)?-?\s*' + 
                      r'(No)?\s*(\.|-)?\s*(?P<numa>\d+)?\s*(,|\.)?\s*' + 
                      r'(part\s*(-)?\s*(?P<part>[0-9ivxlcdm]+))?\s*' +
                      r'(,)?\s*(of)?\s*(?P<year>\d{4})?', txt, flags=re.IGNORECASE)
    if reobj:
        g = reobj.groupdict()

        num = g['numb'] if g['numb'] is not None else g['numa']

        ng_info = { 'num': num }

        if g['year'] is not None:
             ng_info['year'] = g['year']

        if g['part'] is not None:
            ng_info['part'] = g['part']

        return ng_info

    return None

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
        reobj = re.search(r'published\s+date\s+:\s+(?P<month>\w+)(\.)?\s+(?P<day>\d+)(,)?\s+(?P<year>\d+)', txt)
        if reobj is None:
            self.logger.warning('Unable to parse %s', txt)
            return None

        g = reobj.groupdict()
        pubdate = datetime.datetime.strptime(f'{g["day"]}-{g["month"][:3]}-{g["year"]}', '%d-%b-%Y').date()
        return pubdate

    def enhance_ng_metainfo(self, txt, metainfo):
        parsed = parse_ng_subject(txt)
        if 'year' in parsed:
            metainfo['year'] = parsed['year']
        else:
            metainfo['year'] = metainfo.get_date().year

        if 'num' in parsed:
            metainfo['gznum'] = parsed['num']

        if 'part' in parsed:
            metainfo['partnum'] = parsed['part']

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
        link_txt = utils.get_tag_contents(link)
        if link_txt:
            link_txt = link_txt.strip()

        self.enhance_ng_metainfo(link_txt, metainfo)

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


        pubdate = self.parse_date(splits[2])
        if pubdate is None:
            return None
        metainfo.set_date(pubdate)

        subject = splits[0]

        link = form.find('a')
        if link is None:
            self.logger.warning('Unable to find link')
            return None

        link_txt = utils.get_tag_contents(link)
        if link_txt:
            link_txt = link_txt.strip()

        if subject == 'Normal Gazette' or re.search(r'Normal(\s|_)Gazette', link_txt): 
            metainfo.set_gztype('Ordinary')
            self.enhance_ng_metainfo(link_txt, metainfo)
            return metainfo

        filename = None
        for k, v in metainfo['postdata']:
            if k == 'filename':
                filename = v.split('/')[-1].replace('.pdf', '')

        print(f'{filename=}, {link_txt=}, {subject=}')
        #metainfo['notification_num'] = link_txt
        #metainfo['subject'] = subject


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
            filename = filename[:-4].lower()
            filename = filename.replace('.', '-')


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
                self.logger.warning('Unable to get data from %s for date %s to date %s', \
                                    url, fromdate.date(), todate.date())
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
        self.logger.info('From date %s to date %s', fromdate.date(), todate.date())

        self.sync_section(dls, fromdate, todate, event, self.process_row_ordinary, self.ordinary_url)
        self.sync_section(dls, fromdate, todate, event, self.process_row_extraordinary, self.extraordinary_url)

        return dls

if __name__ == '__main__':
    ng_cases = {
        'Normal Gazette 2020'              : { 'year': '2020', 'part': 'complete', 'num': None },
        'Complete Normal Gazette of 2023'  : { 'year': '2023', 'part': 'complete', 'num': None },
        'Normal Gazette-2023'              : { 'year': '2023', 'part': 'complete', 'num': None },
        'Normal Gazette No.1 to 24 of 2024': { 'year': '2024', 'part': '1-24',     'num': None },
        'Normal Gazette No 19 of 2024'     : { 'year': '2024', 'part': None,       'num': '19' },
        'Normal Gazette No 21of 2024'      : { 'year': '2024', 'part': None,       'num': '21' },
        'Normal Gazette No. 22 of 2024'    : { 'year': '2024', 'part': None,       'num': '22' },
        'Normal Gazette No.5 of 2024'      : { 'year': '2024', 'part': None,       'num': '5' },
        'NG 4 of 2024'                     : { 'year': '2024', 'part': None,       'num': '4' },
        'NG No.5, Part-I, 2023'            : { 'year': '2023', 'part': 'I',        'num': '5' },
        '1. NG. part-1, 2024'              : { 'year': '2024', 'part': '1',        'num': '1' },
        'NG. No. 6. Part-I,  2023'         : { 'year': '2023', 'part': 'I',        'num': '6' },
        'Normal Gazette No 4 part-4'       : { 'year': None,   'part': '4',        'num': '4' },
        'NG No.2, 2024'                    : { 'year': '2024', 'part': None,       'num': '2' },
    }

    for txt, expected in ng_cases.items():
        result = parse_ng_subject(txt)
        assert result == expected, f'ng: {txt=} {expected=} {result=}'
        print(f'passed: {txt=}')
