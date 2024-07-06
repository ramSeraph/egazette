from http.cookiejar import CookieJar
import re
import os
from PIL import Image
import io
import urllib.request, urllib.parse, urllib.error
import datetime

from .basegazette import BaseGazette
from ..utils import utils
from ..utils import decode_captcha


class Tripura(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl      = 'https://egazette.tripura.gov.in/eGazette/home.jsp'
        self.hostname     = 'egazette.tripura.gov.in'
        self.search_endp  = 'newsearchresultpage.jsp'
        self.start_date   = datetime.datetime(2018, 1, 1)

    def get_captcha_value(self, cookiejar, referer):
        captcha_url = urllib.parse.urljoin(self.baseurl, 'captchagen')
        response = self.download_url(captcha_url, loadcookies = cookiejar, referer = referer)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to download captcha')
            return None

        img = Image.open(io.BytesIO(response.webpage))
        captcha_val = decode_captcha.tripura(img)
        return captcha_val
        
    def get_post_data(self, tags, dateobj):
        datestr = dateobj.strftime('%Y-%m-%d')
        postdata = []

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')
                if name == 'txtdatefrom' or name == 'txtdateto':
                    value = datestr
            elif tag.name == 'select':        
                name = tag.get('name')
                value = utils.get_selected_option(tag)
            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))

        return postdata


    def get_form_data(self, webpage, cookiejar, curr_url, dateobj):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            self.logger.warning('Unable to parse page for %s', dateobj)
            return None
        
        search_form = d.find('form', {'action': self.search_endp})
        if search_form == None:
            self.logger.warning('Unable to locate search form for %s', dateobj)
            return None

        reobj  = re.compile('^(input|select)$')
        inputs = search_form.find_all(reobj)
        postdata = self.get_post_data(inputs, dateobj)

        captcha_value = self.get_captcha_value(cookiejar, curr_url)
        if captcha_value == None:
            return None

        postdata = utils.replace_field(postdata, 'txtcaptchadata', captcha_value)
        postdata.append(('btnsave', ''))

        return postdata

    def get_results_table(self, webpage):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return None

        results_table = d.find('table', {'id': 'qryresults'})

        return results_table

    def process_row(self, tr, order, dateobj):
        metainfo = utils.MetaInfo()
        metainfo.set_date(dateobj)

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()

                if col in [ 'notification_num', 'category', 'department', 'gznum' ]:
                    metainfo[col] = txt
                elif col == 'gztype':
                    if txt == 'Extra-Ordinary':
                        metainfo.set_gztype('Extraordinary')
                    else:
                        metainfo.set_gztype('Ordinary')
                elif col == 'download':
                    link = td.find('a')
                    if link and link.get('href'):
                        metainfo['href'] = link.get('href')
            i += 1

        if 'href' in metainfo:
            return metainfo

        return None


    def get_result_order(self, tr):
        order = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Notification-No', txt):
                order.append('notification_num')
            elif txt and re.search('Category', txt):
                order.append('category')
            elif txt and re.search('Department', txt):
                order.append('department')
            elif txt and re.search('Notification-Type', txt):
                order.append('gztype')
            elif txt and re.search('Gazette\s+No', txt):
                order.append('gznum')
            elif txt and re.search('Download', txt):
                order.append('download')
            else:
                order.append('')
        return order

    def parse_results(self, results_table, dateobj):
        metainfos = []
        order = None

        for tr in results_table.find_all('tr'):
            if order == None:
                order = self.get_result_order(tr)
                continue

            metainfo = self.process_row(tr, order, dateobj)
            if metainfo != None:
                metainfos.append(metainfo)
        return metainfos

    def download_oneday(self, relpath, dateobj):
        dls = []
        cookiejar  = CookieJar()
        response = self.download_url(self.baseurl, savecookies = cookiejar)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to download page at %s for %s', search_url, dateobj)
            return dls

        results_table = None
        while results_table == None:
            curr_url = response.response_url
            postdata = self.get_form_data(response.webpage, cookiejar, curr_url, dateobj)
            if postdata == None:
                return dls
            
            search_url = urllib.parse.urljoin(curr_url, self.search_endp)
            response = self.download_url(search_url, postdata = postdata, referer = curr_url, \
                                         loadcookies = cookiejar, savecookies = cookiejar)
            if response == None or response.webpage == None:
                self.logger.warning('Unable to get search results at %s for %s', search_url, dateobj)
                return dls

            results_table = self.get_results_table(response.webpage)

        metainfos = self.parse_results(results_table, dateobj)

        for metainfo in metainfos:
            href = metainfo.pop('href')
            gzurl = urllib.parse.urljoin(curr_url, href)

            parsed = urllib.parse.urlparse(gzurl)
            gztslno = urllib.parse.parse_qs(parsed.query)['gaztslno'][0]

            relurl = os.path.join(relpath, gztslno)
            if self.save_gazette(relurl, gzurl, metainfo, validurl=False):
                dls.append(relurl)

        return dls

