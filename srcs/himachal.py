import datetime
import urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar
from PIL import Image
import io
import os
import re
import time

from ..utils import utils
from ..utils import decode_captcha

from .central import CentralBase

class Himachal(CentralBase):
    def __init__(self, name, storage):
        CentralBase.__init__(self, name, storage)
        self.hostname = 'rajpatrahimachal.nic.in'
        self.baseurl  = 'https://rajpatrahimachal.nic.in/SearchG.aspx'
        self.search_endp = 'SearchG.aspx'
        self.result_table = 'ContentPlaceHolder1_GVNotification'
        self.start_date   = datetime.datetime(2007, 1, 1)
        self.captcha_key = 'ctl00$ContentPlaceHolder1$txtCaptcha'


    def find_next_page(self, tr, curr_page):
        if tr.find('table') == None:
            return None

        for td in tr.find_all('td'):
            link = td.find('a')
            txt = utils.get_tag_contents(td)
            if txt:
               try: 
                   page_no = int(txt)
               except:
                   page_no = None
               if page_no == curr_page + 1 and link:
                   return link

        return None               


    def get_column_order(self, tr):
        order = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Subject', txt):
                order.append('subject')
            elif txt and re.search('Department', txt):
                order.append('department')
            elif txt and re.search('Notification\s+Number', txt):
                order.append('notification_num')
            elif txt and re.search('Gazette\s+Number', txt):
                order.append('gazetteid')
            elif txt and re.search('Date', txt):
                order.append('issuedate')
            else:
                order.append('')
        return order

    def get_post_data(self, tags, dateobj):
        datestr  = utils.dateobj_to_str(dateobj, '/', reverse = False)
        postdata = []

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')
                if t == 'image' or t == 'checkbox':
                    continue
                elif name == 'ctl00$ContentPlaceHolder1$txtStartDate':
                    value = datestr
                elif name == 'ctl00$ContentPlaceHolder1$txtEndDate':
                    value = datestr
            elif tag.name == 'select':
                name = tag.get('name')

            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))
        return postdata

    def process_result_row(self, tr, metainfos, dateobj, order):
        metainfo = utils.MetaInfo()
        metainfos.append(metainfo)
        metainfo.set_date(dateobj)

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()

                if col in ['department', 'notification_num']:
                    metainfo[col] = txt
                elif col in ['subject', 'gazetteid']:
                    metainfo[col] = td
            i += 1

    def update_metainfo(self, field, url_field, metainfo):
        td = metainfo.pop(field)

        txt = utils.get_tag_contents(td)
        metainfo[field] = txt.strip()

        link = td.find('a')
        if link and link.get('onclick'):
            onclick = link.get('onclick')

            reobj = re.search('window\.open\(\'(?P<href>[^\']+)', onclick)
            if reobj:
                href  = reobj.groupdict()['href']
                metainfo[url_field] = href

    def clean_id(self, docid):
        docid = docid.strip()
        docid = docid.replace('/','_')
        docid = docid.replace(' ','_')
        return docid

    def download_metainfos(self, relpath, metainfos, search_url, cookiejar):
        dls = []

        by_gazette_id = {}
        for metainfo in metainfos:
            self.update_metainfo('gazetteid', 'gzurl', metainfo)
            self.update_metainfo('subject', 'notification_url', metainfo)
            gazetteid = metainfo['gazetteid']
            if gazetteid not in by_gazette_id:
                by_gazette_id[gazetteid] = []
            by_gazette_id[gazetteid].append(metainfo)

        for gazetteid, metainfos in by_gazette_id.items():
            newmeta = utils.MetaInfo()
            newmeta.set_date(metainfos[0].get_date())
            newmeta['gazetteid'] = metainfos[0]['gazetteid']
            newmeta['notification_info'] = []
            for metainfo in metainfos:
                newmeta['notification_info'].append({ 'notification_num': metainfo['notification_num'],
                                                      'department'      : metainfo['department'] })
            gzurl = metainfos[0]['gzurl']
            gzurl = urllib.parse.urljoin(search_url, gzurl)

            gzurl_parsed = urllib.parse.urlparse(gzurl)
            docid = urllib.parse.parse_qs(gzurl_parsed.query)['ID'][0]

            docid = self.clean_id(docid)

            relurl = os.path.join(relpath, docid)
            if self.save_gazette(relurl, gzurl, newmeta, cookiefile=cookiejar, validurl=False):
                dls.append(relurl)
        return dls


    def download_captcha(self, search_url, webpage, cookiejar):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return None

        imgs = d.find_all('img')
        for img in imgs:
            src = img.get('src')
            if src and src.find('CaptchaImage.axd') >= 0:
                captcha_url = urllib.parse.urljoin(search_url, src)
                return self.download_url(captcha_url, loadcookies=cookiejar, \
                                         savecookies=cookiejar, referer=search_url)
        return None

    def solve_captcha(self, img):
        captcha_val = decode_captcha.himachal(img).strip()
        time.sleep(5)
        return captcha_val

    def submit_captcha_form(self, search_url, webpage, cookiejar, dateobj):        
        captcha = self.download_captcha(search_url, webpage, cookiejar)
        if captcha == None or captcha.webpage == None:
            self.logger.warning('Unable to download captcha')
            return None

        img = Image.open(io.BytesIO(captcha.webpage))

        captcha_val = self.solve_captcha(img)
                    
        postdata = self.get_form_data(webpage, dateobj, self.search_endp)
        if postdata == None:
            return None

        newpost = self.replace_field(postdata, self.captcha_key, captcha_val)
        headers = {}

        response = self.download_url(search_url, savecookies = cookiejar, \
                                     loadcookies = cookiejar, postdata = newpost, \
                                     referer = search_url, headers=headers)
        return response


    def download_captcha(self, search_url, webpage, cookiejar):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return None

        imgs = d.find_all('img')
        for img in imgs:
            src = img.get('src')
            if src and src.find('CaptchaImage.axd') >= 0:
                captcha_url = urllib.parse.urljoin(search_url, src)
                return self.download_url(captcha_url, loadcookies=cookiejar, \
                                         savecookies=cookiejar, referer=search_url)
        return None

    def check_captcha_failure(self, webpage):
        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            return None

        div = d.find('div', {'id': 'ContentPlaceHolder1_alertdivW'})
        if div == None:
            return False

        msg = div.find('span')
        if msg == None:
            return False

        alerttxt = utils.get_tag_contents(msg)
            
        if re.search('Verfication\s+Code\s+is\s+Incorrect', alerttxt):
            return True

        return False


    def get_search_results(self, search_url, dateobj, cookiejar):
        response = self.download_url(search_url, savecookies = cookiejar, referer=search_url)

        while response and response.webpage:
            response = self.submit_captcha_form(search_url, response.webpage, \
                                                cookiejar, dateobj)
             
            if not response or not response.webpage:
                self.logger.warning('Failed to post to search form for %s', dateobj)
                return None

            has_captcha_failure = self.check_captcha_failure(response.webpage)
            if has_captcha_failure == None:
                self.logger.warning('Failed to parse search form response for %s', dateobj)
                return None

            if not has_captcha_failure:
                break

            self.logger.warning('Failed in solving captcha. Retrying.')
            cookiejar.clear()
            response = self.download_url(search_url, savecookies = cookiejar, referer=search_url)
                
        return response

    def download_nextpage(self, nextpage, search_url, cookiejar):
        newdata = []
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
            
        postdata = self.remove_fields(postdata, set(['ctl00$ContentPlaceHolder1$btnBack',
                                                     'ctl00$ContentPlaceHolder1$BtnSendMail']))
        postdata = self.replace_field(postdata, '__EVENTTARGET', etarget)
        postdata = self.replace_field(postdata, '__EVENTARGUMENT', page_no)
        response = self.download_url(search_url, savecookies = cookiejar, \
                                     referer = search_url, \
                                     loadcookies = cookiejar, \
                                     postdata = postdata)
            
        return response 


    def download_oneday(self, relpath, dateobj):
        dls = []
        cookiejar  = CookieJar()
        response = self.get_search_results(self.baseurl, dateobj, cookiejar)

        pagenum = 1
        while response != None and response.webpage != None:
            metainfos, nextpage = self.parse_search_results(response.webpage, \
                                                            dateobj, pagenum)
            relurls = self.download_metainfos(relpath, metainfos, self.baseurl, \
                                              cookiejar)
            dls.extend(relurls)

            if nextpage:
                pagenum += 1
                self.logger.info('Going to page %d for date %s', pagenum, dateobj)
                postdata = self.get_form_data(response.webpage, dateobj, self.search_endp)
                response = self.download_nextpage(nextpage, self.baseurl, cookiejar)
            else:
                break
        return dls

class HimachalArchive(Himachal):
    def __init__(self, name, storage):
        CentralBase.__init__(self, name, storage)
        self.hostname = 'himachalservices.nic.in'
        self.baseurl  = 'https://himachalservices.nic.in/eGazette1953-2007/'
        self.search_endp = './'
        self.result_table = 'ctl00_ContentPlaceHolder1_GVNotification'
        self.start_date   = datetime.datetime(1953, 11, 1)
        self.captcha_key = 'ctl00$ContentPlaceHolder1$searchtext'

    def get_column_order(self, tr):
        order = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Gazette\s+No', txt):
                order.append('gazetteid')
            elif txt and re.search('Date', txt):
                order.append('issuedate')
            else:
                order.append('')
        return order

    def process_result_row(self, tr, metainfos, dateobj, order):
        metainfo = utils.MetaInfo()
        metainfos.append(metainfo)
        metainfo.set_date(dateobj)

        i        = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()

                if col == 'issuedate':
                    metainfo['issuedate'] = txt
                elif col == 'gazetteid':
                    metainfo['gazetteid'] = td
            i += 1

    def download_metainfos(self, relpath, metainfos, search_url, cookiejar):
        dls = []
        for metainfo in metainfos:
            self.update_metainfo('gazetteid', 'gzurl', metainfo)
            gzurl = metainfo.pop('gzurl')

            gzurl_parsed = urllib.parse.urlparse(gzurl)
            docid = urllib.parse.parse_qs(gzurl_parsed.query)['ID'][0]

            docid = self.clean_id(docid)

            relurl = os.path.join(relpath, docid)
            if self.save_gazette(relurl, gzurl, metainfo, cookiefile=cookiejar, validurl=False):
                dls.append(relurl)
        return dls

    def download_nextpage(self, nextpage, search_url, cookiejar):
        newdata = []
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
            
        postdata = self.remove_fields(postdata, set(['ctl00$ContentPlaceHolder1$GVNotification$ctl02$chkview',
                                                     'ctl00$ContentPlaceHolder1$BtnSendMail']))
        postdata = self.replace_field(postdata, '__EVENTTARGET', etarget)
        postdata = self.replace_field(postdata, '__EVENTARGUMENT', page_no)
        postdata.append(('__ASYNCPOST', 'true'))
        postdata.append(('ctl00$ScriptManager1', f'ctl00$ContentPlaceHolder1$UdpDatePanel|{etarget}'))
        response = self.download_url(search_url, savecookies = cookiejar, \
                                     referer = search_url, \
                                     loadcookies = cookiejar, \
                                     postdata = postdata)
            
        return response 



    def get_post_data(self, tags, dateobj):
        datestr  = utils.dateobj_to_str(dateobj, '/', reverse = False)
        postdata = []

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')
                if t == 'image' or name == 'ctl00$BtnElectronicGazette':
                    continue
                elif name == 'ctl00$ContentPlaceHolder1$txtStartDateGR':
                    value = datestr
                elif name == 'ctl00$ContentPlaceHolder1$txtEndDateGR':
                    value = datestr
            elif tag.name == 'select':
                name = tag.get('name')

            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))
        return postdata

    def check_captcha_failure(self, webpage):
        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            return None

        msg = d.find('span', {'id': 'ctl00_ContentPlaceHolder1_lblErr'})
        if msg == None:
            return False

        alerttxt = utils.get_tag_contents(msg)
            
        if re.search('Invalid\s+Verification\s+Code,\s+Please\s+Try\s+Again', alerttxt):
            return True

        return False


    def solve_captcha(self, img):
        captcha_val = decode_captcha.himachalarchive(img).strip()
        time.sleep(5)
        return captcha_val
