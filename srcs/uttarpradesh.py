from http.cookiejar import CookieJar
import re
import os
import urllib.request, urllib.parse, urllib.error
import datetime

from ..utils import utils
from .basegazette import BaseGazette

class UttarPradesh(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl  = 'https://dpsup.up.gov.in/'
        self.hostname = 'dpsup.up.gov.in'
        self.ordinary_url      = 'https://dpsup.up.gov.in/en/gazette?Gazettelistslug=en-ordinary-gazette'
        self.extraordinary_url = 'https://dpsup.up.gov.in/en/gazette?Gazettelistslug=en-extra-ordinary-gazette'
        self.start_date = datetime.datetime(2018, 12, 21)

    def get_selected_option(self, select):
        option = select.find('option', {'selected': 'selected'})
        if option == None:
            option = select.find('option')
        if option == None:
            return ''
        val = option.get('value')
        if val == None:
            val = ''
        return val

    def remove_fields(self, postdata, fields):
        newdata = []
        for k, v in postdata:
            if k not in fields:
                newdata.append((k, v))
        return newdata

    def replace_field(self, postdata, field_name, field_value):
        newdata = []
        for k, v in postdata:
            if k == field_name:
                newdata.append((field_name, field_value))
            else:
                newdata.append((k, v))
        return newdata

    def get_post_data(self, tags, dateobj):
        datestr  = dateobj.strftime('%d/%m/%Y')
        postdata = []

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                if name in [ 'ctl00$ContentPlaceHolder_Body$txtFromDate', \
                             'ctl00$ContentPlaceHolder_Body$txtToDate' ]:
                    value = datestr

            elif tag.name == 'select':        
                name = tag.get('name')
                value = self.get_selected_option(tag)

            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))

        return postdata


    def get_form_data(self, webpage, curr_url, dateobj):
        parsed = urllib.parse.urlparse(curr_url)
        parsed = parsed._replace(netloc='', scheme='')
        form_href = parsed.geturl()

        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            self.logger.warning('Unable to parse webpage of %s for %s', curr_url, dateobj)
            return None

        search_form = d.find('form', {'action': form_href})
        if search_form == None:
            self.logger.warning('Unable to find search form of %s for %s', curr_url, dateobj)
            return None

        reobj  = re.compile('^(input|select)$')
        inputs = search_form.find_all(reobj)
        postdata = self.get_post_data(inputs, dateobj)
        postdata = self.remove_fields(postdata, set(['ctl00$ContentPlaceHolder_Body$btnReset']))

        return postdata


    def get_column_order(self, tr):
        order  = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Department', txt):
                order.append('department')
            elif txt and re.search('Gazette\s+Content', txt):
                order.append('subject')
            elif txt and re.search('Gazette\s+No', txt):
                order.append('gznum')
            else:
                order.append('')    
        return order

    def find_next_page(self, tr, curr_page):
        classes = tr.get('class')
        if classes and 'pagination' in classes:
            for link in tr.find_all('a'):
                txt = utils.get_tag_contents(link)
                if txt:
                   try: 
                       page_no = int(txt)
                   except:
                       page_no = None
                   if page_no == curr_page + 1 and link:
                       return link

        return None
 
    def process_result_row(self, tr, order, dateobj, gztype):
        metainfo = utils.MetaInfo()
        metainfo.set_date(dateobj)
        metainfo.set_gztype(gztype)

        def add_text(key, node):
            txt = utils.get_tag_contents(node)
            if txt:
                txt = txt.strip()
            metainfo[key] = txt

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                if col == 'subject':
                    span = td.find('span', recursive = False)
                    if span:
                        link = span.find('a', recursive = False)
                        if link:
                            metainfo['href'] = link.get('href')
                            add_text('subject', link)
                        subspan = span.find('span')
                        if subspan:
                            txt = utils.get_tag_contents(subspan)
                            reobj = re.search('Language\s+:\s+(")?\s+(?P<lang>\w+)\s+(")?', txt)
                            if reobj:
                                matainfo['language'] = reobj.groupdict()['lang']
                elif col == 'gznum':
                    add_text(col, td)
                elif col == 'department':
                    spans = td.find_all('span', recursive = False)
                    if len(spans) == 2:
                        add_text('department', spans[0])
                        add_text('subdepartment', spans[1])
            i += 1

        if 'href' not in metainfo:
            return None

        return metainfo

    def parse_results(self, webpage, dateobj, curr_page, gztype):
        metainfos = []
        nextpage  = None

        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            self.logger.warning('Unable to parse results page for %d', dateobj)
            return metainfos, nextpage

        results_table = d.find('table', {'id': 'ContentPlaceHolder_Body_gdvGazetteContent'})
        if results_table == None:
            self.logger.warning('Unable to find results table for %d', dateobj)
            return metainfos, nextpage

        order = None
        for tr in results_table.find_all('tr'):
            if order == None:
                order = self.get_column_order(tr)
                continue

            if nextpage == None:
                nextpage = self.find_next_page(tr, curr_page)
                if nextpage != None:
                    continue

            metainfo = self.process_result_row(tr, order, dateobj, gztype)
            if metainfo != None:
                metainfos.append(metainfo)

        return metainfos, nextpage

    def download_nextpage(self, nextpage, search_url, postdata, cookiejar):
        href = nextpage.get('href') 
        if not href:
            return None

        groups = []
        for reobj in re.finditer("'(?P<obj>[^']+)'", href):
            groups.append(reobj.groupdict()['obj'])

        if not groups or len(groups) < 2:
            return None

        etarget = groups[0]
        page_no = groups[1]

        postdata = self.replace_field(postdata, '__EVENTTARGET', etarget)
        postdata = self.replace_field(postdata, '__EVENTARGUMENT', page_no)

        response = self.download_url(search_url, savecookies = cookiejar, \
                                     referer = search_url, \
                                     loadcookies = cookiejar, \
                                     postdata = postdata)
            
        return response


    def download_metainfo(self, relpath, metainfo, curr_url):
        href = metainfo.pop('href')
        gzurl = urllib.parse.urljoin(curr_url, href)

        fname = href.split('/')[-1]
        reobj = re.search('C_(?P<docid>\d+)\.pdf', fname)
        if reobj == None:
            self.logger.warning('Unable to extract docid for %s', href)
            return None
        docid = reobj.groupdict()['docid']

        relurl = os.path.join(relpath, docid)
        if self.save_gazette(relurl, gzurl, metainfo):
            return relurl

        return None


    def download_onetype(self, dls, relpath, dateobj, gztype, url):
        cookiejar = CookieJar()

        response = self.download_url(url, savecookies = cookiejar)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to get %s for %s', url, dateobj)
            return

        curr_url = response.response_url

        postdata = self.get_form_data(response.webpage, curr_url, dateobj)
        if postdata == None:
            return

        response = self.download_url(curr_url, postdata = postdata, savecookies = cookiejar, \
                                     loadcookies = cookiejar, referer = curr_url)

        pagenum = 1
        while response != None and response.webpage != None:
            curr_url = response.response_url

            metainfos, nextpage = self.parse_results(response.webpage, dateobj, pagenum, gztype)

            for metainfo in metainfos:
                relurl = self.download_metainfo(relpath, metainfo, curr_url)
                if relurl != None:
                    dls.append(relurl)

            if nextpage == None:
                break
            
            if postdata == None:
                postdata = self.get_form_data(response.webpage, curr_url, dateobj)
                if postdata == None:
                    break

            pagenum += 1
            self.logger.info('Going to page %d for date %s', pagenum, dateobj)
            response = self.download_nextpage(nextpage, curr_url, postdata, cookiejar)
            postdata = None



    def download_oneday(self, relpath, dateobj):
        dls = []
        self.download_onetype(dls, relpath, dateobj, 'Extraordinary', self.extraordinary_url)
        self.download_onetype(dls, relpath, dateobj, 'Ordinary', self.ordinary_url)
        return dls
