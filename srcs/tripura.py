from http.cookiejar import CookieJar
import re
import os
from PIL import Image
import io
import datetime
import urllib.request
import urllib.parse
import urllib.error

from .basegazette import BaseGazette
from ..utils import utils
from ..utils.metainfo import MetaInfo
from ..utils import decode_captcha


class Tripura(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl      = 'https://egazette.tripura.gov.in/eGazette/home.jsp'
        self.hostname     = 'egazette.tripura.gov.in'
        self.search_endp  = 'newsearchresultpage.jsp'

    def get_captcha_value(self, cookiejar, referer):
        captcha_url = urllib.parse.urljoin(self.baseurl, 'captchagen')

        response = self.download_url(captcha_url, loadcookies = cookiejar, referer = referer)
        if response is None or response.webpage is None:
            self.logger.warning('Unable to download captcha')
            return None

        img = Image.open(io.BytesIO(response.webpage))

        captcha_val = decode_captcha.tripura(img)

        return captcha_val
        
    def get_post_data(self, tags, fromdate, todate):
        fromstr = fromdate.strftime('%Y-%m-%d')
        tostr   = todate.strftime('%Y-%m-%d')
        postdata = []

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')

                if name == 'txtdatefrom':
                    value = fromstr
                elif name == 'txtdateto':
                    value = tostr

            elif tag.name == 'select':        
                name = tag.get('name')
                value = utils.get_selected_option(tag)

            if name:
                if value is None:
                    value = ''
                postdata.append((name, value))

        return postdata


    def get_form_data(self, webpage, cookiejar, curr_url, fromdate, todate):
        search_form = utils.get_search_form(webpage, self.parser, self.search_endp)
        if search_form is None:
            self.logger.warning('Unable to locate search form for %s to %s', fromdate, todate)
            return None

        reobj  = re.compile('^(input|select)$')
        inputs = search_form.find_all(reobj)
        postdata = self.get_post_data(inputs, fromdate, todate)

        captcha_value = self.get_captcha_value(cookiejar, curr_url)
        if captcha_value is None:
            return None

        postdata = utils.replace_field(postdata, 'txtcaptchadata', captcha_value)
        postdata.append(('btnsave', ''))

        return postdata

    def get_results_table(self, webpage):
        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
            return None

        results_table = d.find('table', {'id': 'qryresults'})

        return results_table

    def process_row(self, metainfos, tr, order):
        metainfo = MetaInfo()

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]

                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()

                if col == 'date':
                    issuedate = datetime.datetime.strptime(txt, '%d/%m/%Y').date()
                    metainfo.set_date(issuedate)

                elif col == 'gztype':
                    if txt == 'Extra-Ordinary':
                        metainfo.set_gztype('Extraordinary')
                    else:
                        metainfo.set_gztype('Ordinary')

                elif col == 'download':
                    link = td.find('a')
                    if link and link.get('href'):
                        metainfo['href'] = link.get('href')

                elif col != '':
                    metainfo[col] = txt
            i += 1

        if 'href' in metainfo:
            metainfos.append(metainfo)

    def get_result_order(self, tr):
        order = []

        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Notification-No', txt):
                order.append('notification_num')

            elif txt and re.search('Date', txt):
                order.append('date')

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

    def parse_results(self, results_table):
        metainfos = []
        order = None

        for tr in results_table.find_all('tr'):
            if order is None:
                order = self.get_result_order(tr)
                continue

            self.process_row(metainfos, tr, order)

        return metainfos

    def sync(self, fromdate, todate, event):
        dls = []
        cookiejar = CookieJar()
        fromdate  = fromdate.date()
        todate    = todate.date()

        response = self.download_url(self.baseurl, savecookies = cookiejar)
        if response is None or response.webpage is None:
            self.logger.warning('Unable to download page at %s for %s to %s', \
                                self.baseurl, fromdate, todate)
            return dls

        results_table = None
        while results_table is None:
            curr_url = response.response_url

            postdata = self.get_form_data(response.webpage, cookiejar, \
                                          curr_url, fromdate, todate)
            if postdata is None:
                return dls
            
            search_url = urllib.parse.urljoin(curr_url, self.search_endp)

            response = self.download_url(search_url, postdata = postdata, referer = curr_url, \
                                         loadcookies = cookiejar, savecookies = cookiejar)
            if response is None or response.webpage is None:
                self.logger.warning('Unable to get search results at %s for %s to %s', \
                                    search_url, fromdate, todate)
                return dls

            results_table = self.get_results_table(response.webpage)

        metainfos = self.parse_results(results_table)

        for metainfo in metainfos:

            if event.is_set():
                self.logger.warning('Exiting prematurely as timer event is set')
                return dls

            href   = metainfo.pop('href')
            gzurl  = urllib.parse.urljoin(curr_url, href)
            gzdate = metainfo.get_date()

            parsed  = urllib.parse.urlparse(gzurl)
            gztslno = urllib.parse.parse_qs(parsed.query)['gaztslno'][0]

            relpath = os.path.join(self.name, gzdate.__str__())
            relurl  = os.path.join(relpath, gztslno)
            if self.save_gazette(relurl, gzurl, metainfo):
                dls.append(relurl)

        return dls

