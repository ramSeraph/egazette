import urllib.parse
from http.cookiejar import CookieJar
import datetime
import re
import os
import io
import time

from PIL import Image

from .basegazette import BaseGazette
from ..utils import utils
from ..utils.metainfo import MetaInfo
from ..utils import decode_captcha

class ManipurNew(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl  = 'https://egazettemanipur.mn.gov.in/SearchG.aspx'
        self.hostname = 'egazettemanipur.mn.gov.in'
        self.search_endp = './SearchG.aspx'
        self.result_table = 'ContentPlaceHolder1_GVNotification'
        self.captcha_key = 'ctl00$ContentPlaceHolder1$txtCaptcha'


    def find_next_page(self, tr, curr_page):
        if tr.find('table') is None:
            return None

        nextpage = None

        links = tr.findAll('a')

        if len(links) <= 0:
            return None

        lastpage = None
        for link in links:
            contents = utils.get_tag_contents(link)
            if link.get('href'):
                lastpage = {'href': link.get('href'), 'title': contents}

            try:
                val = int(contents)
            except ValueError:
                continue

            if val == curr_page + 1 and link.get('href'):
                nextpage = {'href': link.get('href'), 'title': f'{val}'}
                break

        if nextpage is None and lastpage is not None and lastpage['title'] == '...':
            nextpage = lastpage

        return nextpage



    def get_form_data(self, webpage, fromdate, todate, form_href):
        search_form = utils.get_search_form(webpage, self.parser, form_href)
        if search_form is None:
            self.logger.warning('Unable to get the search form for day: %s to %s', \
                                fromdate, todate)
            return None 

        reobj  = re.compile('^(input|select)$')
        inputs = search_form.find_all(reobj)
        postdata = self.get_post_data(inputs, fromdate, todate)

        return postdata

    def get_column_order(self, tr):
        order = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search(r'Subject', txt):
                order.append('subject')
            elif txt and re.search(r'Department', txt):
                order.append('department')
            elif txt and re.search(r'Notification\s+Number', txt):
                order.append('notification_num')
            elif txt and re.search(r'Gazette\s+Number', txt):
                order.append('gazetteid')
            elif txt and re.search(r'Date', txt):
                order.append('issuedate')
            else:
                order.append('')
        return order

    def get_post_data(self, tags, fromdate, todate):
        fromstr = fromdate.strftime('%d/%m/%Y')
        tostr   = todate.strftime('%d/%m/%Y')
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
                    value = fromstr
                elif name == 'ctl00$ContentPlaceHolder1$txtEndDate':
                    value = tostr
            elif tag.name == 'select':
                name = tag.get('name')

            if name:
                if value is None:
                    value = ''
                postdata.append((name, value))
        return postdata

    def process_result_row(self, tr, metainfos, order):
        metainfo = MetaInfo()

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()

                if col in ['department', 'notification_num', 'issuedate']:
                    metainfo[col] = txt

                elif col in ['subject', 'gazetteid']:
                    metainfo[col] = td
            i += 1

        if 'subject' in metainfo:
            metainfos.append(metainfo)

    def update_metainfo(self, field, url_field, metainfo):
        td = metainfo.pop(field)

        txt = utils.get_tag_contents(td)
        metainfo[field] = txt.strip()

        link = td.find('a')
        if link and link.get('onclick'):
            onclick = link.get('onclick')

            reobj = re.search(r'window\.open\(\'(?P<href>[^\']+)', onclick)
            if reobj:
                href  = reobj.groupdict()['href']
                metainfo[url_field] = href

    def clean_id(self, docid):
        docid = docid.strip()
        docid = docid.replace('/','_')
        docid = docid.replace(' ','_')
        return docid

    def download_metainfos(self, metainfos, search_url, fromdate, todate, cookiejar):
        dls = []

        by_gazetteid = {}
        for metainfo in metainfos:
            self.update_metainfo('gazetteid', 'gzurl', metainfo)
            self.update_metainfo('subject', 'notification_url', metainfo)
            gazetteid = metainfo['gazetteid']
            if gazetteid not in by_gazetteid:
                by_gazetteid[gazetteid] = []
            by_gazetteid[gazetteid].append(metainfo)

        for gazetteid, metainfos in by_gazetteid.items():
            newmeta = MetaInfo()

            gznum = gazetteid.split('/')[0]
            newmeta['gznum'] = gznum
            newmeta['gazetteid'] = gazetteid

            gzdate = metainfos[0]['issuedate']
            try:
                gzdate = datetime.datetime.strptime(gzdate, '%d-%m-%Y').date()
            except Exception:
                self.logger.warning('Unable to get issuedate: %s', gzdate)
                continue

            if gzdate > todate or gzdate < fromdate:
                continue

            newmeta.set_date(gzdate)

            newmeta['notifications'] = []
            for metainfo in metainfos:
                newmeta['notifications'].append({
                    'number'     : metainfo['notification_num'],
                    'department' : metainfo['department'],
                    'subject'    : metainfo['subject']
                })

            gzurl = metainfos[0]['gzurl']
            gzurl = urllib.parse.urljoin(search_url, gzurl)

            gzurl_parsed = urllib.parse.urlparse(gzurl)
            docid = urllib.parse.parse_qs(gzurl_parsed.query)['ID'][0]

            docid = self.clean_id(docid)
            docid = docid.lower()

            relpath = os.path.join(self.name, gzdate.__str__())
            relurl  = os.path.join(relpath, docid)
            if self.save_gazette(relurl, gzurl, newmeta, cookiefile=cookiejar):
                dls.append(relurl)

        return dls


    def download_captcha(self, search_url, webpage, cookiejar):
        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
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
        captcha_val = decode_captcha.manipur(img).strip()
        # there is either a delay check on the server or a race condition.. so the sleep is needed
        time.sleep(5)
        return captcha_val

    def submit_captcha_form(self, search_url, webpage, cookiejar, fromdate, todate):
        captcha = self.download_captcha(search_url, webpage, cookiejar)
        if captcha is None or captcha.webpage is None:
            self.logger.warning('Unable to download captcha')
            return None

        img = Image.open(io.BytesIO(captcha.webpage))

        captcha_val = self.solve_captcha(img)

        postdata = self.get_form_data(webpage, fromdate, todate, self.search_endp)
        if postdata is None:
            return None

        newpost = utils.replace_field(postdata, self.captcha_key, captcha_val)

        response = self.download_url(search_url, savecookies = cookiejar, \
                                     loadcookies = cookiejar, postdata = newpost, \
                                     referer = search_url)
        return response


    def check_captcha_failure(self, webpage):
        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            return None

        div = d.find('div', {'id': 'ContentPlaceHolder1_alertdivW'})
        if div is None:
            return False

        msg = div.find('span')
        if msg is None:
            return False

        alerttxt = utils.get_tag_contents(msg)

        if re.search(r'Verfication\s+Code\s+is\s+Incorrect', alerttxt):
            return True

        return False

    def parse_search_results(self, webpage, fromdate, todate, curr_page):
        metainfos = []
        nextpage  = None

        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse search result page for %s to %s', \
                                fromdate, todate)
            return metainfos, nextpage

        tables = d.find_all('table', {'id': self.result_table})

        if len(tables) != 1:
            self.logger.warning('Could not find the result table for %s to %s', \
                                fromdate, todate)
            return metainfos, nextpage

        order = None
        for tr in tables[0].find_all('tr'):
            if not order:
                order = self.get_column_order(tr)
                continue

            if nextpage is not None:
                continue

            if nextpage is None:
                nextpage = self.find_next_page(tr, curr_page)
                if nextpage is not None:
                    continue

            if tr.find('input') is None and tr.find('a') is None:
                continue

            self.process_result_row(tr, metainfos, order)

        return metainfos, nextpage


    def get_search_results(self, search_url, fromdate, todate, cookiejar):
        response = self.download_url(search_url, savecookies = cookiejar, \
                                     referer=search_url)

        while response and response.webpage:
            response = self.submit_captcha_form(search_url, response.webpage, \
                                                cookiejar, fromdate, todate)

            if not response or not response.webpage:
                self.logger.warning('Failed to post to search form for %s to %s', \
                                    fromdate, todate)
                return None

            has_captcha_failure = self.check_captcha_failure(response.webpage)
            if has_captcha_failure is None:
                self.logger.warning('Failed to parse search form response for %s', \
                                    fromdate, todate)
                return None

            if not has_captcha_failure:
                break

            cookiejar.clear()
            response = self.download_url(search_url, savecookies=cookiejar, \
                                         referer=search_url)

        return response

    def download_nextpage(self, nextpage, search_url, postdata, cookiejar):
        href = nextpage.get('href') 
        if not href:
            return None

        groups = []
        for reobj in re.finditer(r"'(?P<obj>[^']+)'", href):
            groups.append(reobj.groupdict()['obj'])

        if len(groups) < 2:
            return None

        etarget = groups[0]
        page_no = groups[1]

        postdata = utils.remove_fields(postdata, set(['ctl00$ContentPlaceHolder1$btnBack',
                                                      'ctl00$ContentPlaceHolder1$BtnSendMail']))
        postdata = utils.replace_field(postdata, '__EVENTTARGET', etarget)
        postdata = utils.replace_field(postdata, '__EVENTARGUMENT', page_no)
        response = self.download_url(search_url, savecookies = cookiejar, \
                                     referer = search_url, \
                                     loadcookies = cookiejar, \
                                     postdata = postdata)

        return response 

    def parse_non_html(self, webpage):
        resp_text = webpage.decode('utf8')

        panel_label = '|updatePanel|ctl00_ContentPlaceHolder1_UdpDatePanel|'

        idx = resp_text.find(panel_label)

        str_len = int(resp_text[:idx].split('|')[-1])

        idx = idx + len(panel_label)

        end_idx = idx + str_len
        html = resp_text[idx:end_idx]

        pieces = resp_text[end_idx+1:].split('|')

        idx = 0
        base_form_data = []

        while idx < len(pieces):
            if pieces[idx] != 'hiddenField':
                idx += 1
                continue
            idx += 1
            key = pieces[idx] 
            idx += 1
            val = pieces[idx]
            base_form_data.append((key, val))
            idx += 1

        return html.encode('utf8'), base_form_data

    def sync(self, fromdate, todate, event):
        dls = []
        cookiejar = CookieJar()

        fromdate = fromdate.date()
        todate   = todate.date()

        self.logger.info('From date %s to date %s', fromdate, todate)
        response = self.get_search_results(self.baseurl, fromdate, todate, cookiejar)

        pagenum = 1
        all_metainfos = []
        while response is not None and response.webpage is not None:
            hidden_postdata = None

            if response.webpage.decode('utf8').find('<!DOCTYPE html>') >= 0:
                webpage  = response.webpage
                postdata = self.get_form_data(webpage, fromdate, todate, self.search_endp)
            else:
                webpage, hidden_postdata = self.parse_non_html(response.webpage)
                for k,v in hidden_postdata:
                    postdata = utils.replace_field(postdata, k, v)


            metainfos, nextpage = self.parse_search_results(webpage, \
                                                            fromdate, todate, pagenum)

            if event.is_set():
                self.logger.warning('Exiting prematurely as timer event is set')
                break

            all_metainfos.extend(metainfos)

            if not nextpage:
                break

            pagenum += 1
            self.logger.info('Going to page %d for date %s to %s', pagenum, fromdate, todate)

            response = self.download_nextpage(nextpage, self.baseurl, postdata, cookiejar)

        relurls = self.download_metainfos(all_metainfos, self.baseurl, fromdate, todate, cookiejar)
        dls.extend(relurls)

        return dls


class Manipur(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl  = 'https://manipurgovtpress.nic.in/en/gazette_list/'
        self.hostname = 'manipurgovtpress.nic.in'
        self.page_cache = {}
 
    def download_url_cached(self, url):

        if url not in self.page_cache:
            response = self.download_url(url)

            self.page_cache[url] = response

        return self.page_cache[url]
 

    def download_nextpage(self, nextpage, curr_url):
        href = nextpage.get('href')
        if not href:
            return None

        nextpage_url = urllib.parse.urljoin(curr_url, href)

        response = self.download_url_cached(nextpage_url)

        return response

    def find_field_order(self, tr):
        order  = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Gazette\s+Type', txt):
                order.append('gztype')
            elif txt and re.search('Publication\s+Date', txt):
                order.append('gzdate')
            elif txt and re.search('Gazette\s+Number', txt):
                order.append('gznum')
            elif txt and re.search('Gazette\s+Title', txt):
                order.append('subject')
            else:
                order.append('')    
        
        for field in ['gztype', 'gzdate', 'subject', 'gznum']:
            if field not in order:
                return None
        return order

    def process_row(self, tr, order, dateobj):
        metainfo = MetaInfo()
        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                txt = utils.get_tag_contents(td)
                txt = txt.strip()

                col = order[i]
                if col == 'subject':
                    metainfo[order[i]] = txt
                    link = td.find('a')
                    if link:
                        metainfo['download'] = link

                elif col == 'gztype':
                    if txt.find('Extra') >= 0:
                        metainfo.set_gztype('Extraordinary')
                    else:
                        metainfo.set_gztype('Ordinary')

                elif col == 'gzdate':
                    reobj = re.search('(?P<month>[\w.]+)\s+(?P<day>\d+),\s+(?P<year>\d+)', txt)
                    if not reobj:
                        self.logger.warning('Unable to form date for %s', txt)        
                        i += 1
                        continue

                    groupdict = reobj.groupdict()
                    month     = groupdict['month'][:3]
                    day       = groupdict['day']
                    year      = groupdict['year']

                    try:
                        d = datetime.datetime.strptime(f'{day}-{month}-{year}', '%d-%b-%Y').date()
                        metainfo['gzdate'] = d
                    except Exception as e:
                        self.logger.warning('Unable to parse date: %s', e) 
                        continue

                elif col != '':
                    metainfo[order[i]] = txt
            i += 1

        for field in ['subject', 'gztype', 'gznum', 'gzdate']:
            if field not in metainfo:
                return None

        return metainfo

    def find_next_page(self, d, curr_page):
        ul = d.find('ul', {'class': 'pagination'})
        return utils.find_next_page(ul, curr_page)

    def parse_search_results(self, webpage, dateobj, curr_page):
        nextpage  = None
        metainfos = []

        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse search result page for %s', dateobj)
            return metainfos, nextpage

        result_table = None
            
        for table in d.find_all('table'):
            for tr in table.find_all('tr'):
                order = self.find_field_order(tr)
                if order:
                    result_table = table
                    break
                 
        if result_table is None:
            self.logger.warning('Unable to find the result table for %s', dateobj)
            return metainfos, nextpage

        metainfos = []
        seen_older = False
        for tr in result_table.find_all('tr'):
            if tr.find('a') is None:
                continue

            metainfo = self.process_row(tr, order, dateobj)
            if not metainfo:
                continue

            gzdate = metainfo.pop('gzdate')
            if gzdate == dateobj:
                metainfo.set_date(dateobj)
                metainfos.append(metainfo)
            elif gzdate < dateobj:
                seen_older = True
 
        if not seen_older:
            ul = d.find('ul', {'class': 'pagination'})
            nextpage = utils.find_next_page(ul, curr_page)

        return metainfos, nextpage

    def get_download_url(self, detail_url):
        response = self.download_url(detail_url)
        if not response or not response.webpage:
            self.logger.warning('Unable to get page %s', detail_url)
            return None

        d = utils.parse_webpage(response.webpage, self.parser)
        if d is None:
            return  None

        div = d.find('div', {'class': 'body-section'})
        if div is None:
            return None

        link = div.find('a')
        if link is None:
            return None

        href = link.get('href')
        fname = href.split('/')[-1]
        if fname == 'no-file.pdf':
            self.logger.warning('Unusable download link at %s', detail_url)
            return None

        return urllib.parse.urljoin(detail_url, href)

    def download_metainfos(self, relpath, metainfos, curr_url):
        relurls = []

        for metainfo in metainfos:
            link = metainfo.pop('download')
            href = link.get('href')

            if not href:
                self.logger.warning('Unable to get link for %s', metainfo)
                continue

            detail_url = urllib.parse.urljoin(curr_url, href)
            gzurl      = self.get_download_url(detail_url)

            if not gzurl:
                self.logger.warning('Unable to get download url for %s', detail_url)
                continue

            gztype = metainfo['gztype'].lower()
            gznum  = metainfo['gznum']
            relurl = os.path.join(relpath, f'{gztype}-{gznum}')

            if self.save_gazette(relurl, gzurl, metainfo):
                relurls.append(relurl)

        return relurls
                

    def download_oneday(self, relpath, dateobj):
        dls = []

        response = self.download_url_cached(self.baseurl)

        pagenum = 1
        while response is not None and response.webpage is not None:
            curr_url = response.response_url

            metainfos, nextpage = self.parse_search_results(response.webpage, dateobj, pagenum)

            relurls = self.download_metainfos(relpath, metainfos, curr_url)
            dls.extend(relurls)

            if nextpage is None:
                break

            pagenum += 1
            #self.logger.info('Going to page %d for date %s', pagenum, dateobj)
            response = self.download_nextpage(nextpage, curr_url)

        return dls
 
