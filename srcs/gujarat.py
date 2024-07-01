from http.cookiejar import CookieJar
import re
import os
import datetime
import urllib.request, urllib.parse, urllib.error

from ..utils import utils
from .basegazette import BaseGazette

class Gujarat(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl      = 'https://egazette.gujarat.gov.in/GazettesSearch.aspx'
        self.hostname     = 'egazette.gujarat.gov.in'
        self.search_endp  = './GazettesSearch.aspx'
        self.result_table = 'ContentPlaceHolder1_gvDocumentList'
        self.start_date   = datetime.datetime(1991, 1, 1)

    def remove_fields(self, postdata, fields):
        newdata = []
        for k, v in postdata:
            if k not in fields:
                newdata.append((k, v))
        return newdata


    def get_column_order(self, tr):
        order = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Issue\s+No', txt):
                order.append('gznum')
            elif txt and re.search('Gazette\s+Type', txt):
                order.append('gztype')
            elif txt and re.search('Download', txt):
                order.append('download')
            elif txt and re.search('Department', txt):
                order.append('department')
            elif txt and re.search('Gazette\s+Part', txt):
                order.append('partnum')
            elif txt and re.search('Govt\.\s+Press', txt):
                order.append('govtpress')
            else:
                order.append('')
        return order

    def find_next_page(self, tr, curr_page):
        classes = tr.get('class')
        if classes and 'GridPager' in classes:
            for td in tr.find_all('td'):
                if td.find('table') != None:
                    continue
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

                if col == 'gztype':
                    metainfo.set_gztype(txt)    
                elif col == 'download':
                    link = td.find('a')
                    if link:
                        metainfo[col] = link 
                elif col != '':
                    metainfo[col] = txt
            i += 1

    

    def get_selected_option(self, select_tag):
        option = select_tag.find('option', {'selected': 'selected'})
        if option == None:
            option = select_tag.find('option')

        if option:
            val = option.get('value')
            if val:
                return val
        return ''        

    def get_option_for_year(self, select_tag, year):
        val = ''
        options = select_tag.find_all('option')
        for option in options:
            if option.text.strip() == str(year):
                val = option.get('value')
                break
        return val

    def get_post_data(self, tags, dateobj, remove_buttons):
        postdata = []
        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')

                if t == 'submit' and remove_buttons:
                    continue

                if name == 'ctl00$ContentPlaceHolder1$txtFromDate':
                    fromdateobj = dateobj - datetime.timedelta(days=1)
                    value = fromdateobj.strftime('%d/%m/%Y')
                elif name == 'ctl00$ContentPlaceHolder1$txtToDate':
                    value = dateobj.strftime('%d/%m/%Y')
            elif tag.name == 'select':        
                name = tag.get('name')
                if name == 'ctl00$ContentPlaceHolder1$cmbYear':
                    value = self.get_option_for_year(tag, dateobj.year)
                else:
                    self.get_selected_option(tag)
            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))

        return postdata


    def get_form_data(self, webpage, dateobj, form_href, remove_buttons=False):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            self.logger.warning('Unable to parse the search page for day: %s', dateobj)
            return None

        search_form = d.find('form', {'action': self.search_endp})
        if search_form == None:
            self.logger.warning('Unable to get the search form for day: %s', dateobj)
            return None 

        reobj  = re.compile('^(input|select)$')
        inputs = search_form.find_all(reobj)
        postdata = self.get_post_data(inputs, dateobj, remove_buttons)

        return postdata

    def download_nextpage(self, nextpage, postdata, search_url, cookiejar):
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
            
        for k, v in postdata:
            if k == '__EVENTTARGET':
                newdata.append((k, etarget))
            elif k == '__EVENTARGUMENT':
                newdata.append((k, page_no))
            elif k in ['btnDetail', 'btnSubmit']:
                continue
            else:
                newdata.append((k, v))
        response = self.download_url(search_url, savecookies = cookiejar, \
                                     referer = search_url, \
                                     loadcookies = cookiejar, \
                                     postdata = newdata)
            
        return response 


    def parse_search_results(self, webpage, dateobj, curr_page):
        metainfos = []
        nextpage  = None

        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse search result page for %s', dateobj)
            return metainfos, nextpage

        tables = d.find_all('table', {'id': self.result_table})

        if len(tables) != 1:
            self.logger.warning('Could not find the result table for %s', dateobj)
            return metainfos, nextpage
        
        order = None
        for tr in tables[0].find_all('tr'):
            if not order:
                order = self.get_column_order(tr)
                continue

            if nextpage == None:
                nextpage = self.find_next_page(tr, curr_page)
                if nextpage != None:
                    continue

            if tr.find('input') == None and tr.find('a') == None:
                continue

            self.process_result_row(tr, metainfos, dateobj, order)

        return metainfos, nextpage

    def download_metainfos(self, relpath, metainfos, search_url, cookiejar):
        dls = []
        for metainfo in metainfos:
            if 'download' in metainfo:
                link = metainfo.pop('download')
                url = link.get('href')
                if not url:
                    continue
                parsed_url = urllib.parse.urlparse(url)
                docid = urllib.parse.parse_qs(parsed_url.query)['docid'][0]
                if not docid.endswith('.pdf'):
                    continue
                docid = docid[:-4]
                relurl = os.path.join(relpath, docid)

                fullurl = urllib.parse.urljoin(search_url, url)
                
                if self.save_gazette(relurl, fullurl, metainfo):
                    dls.append(relurl)
        return dls


    def download_oneday(self, relpath, dateobj):
        dls = []
        cookiejar = CookieJar()
        response = self.download_url(self.baseurl, savecookies = cookiejar)
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s for the day %s', self.baseurl, dateobj)
            return dls

        curr_url = response.response_url
        postdata = self.get_form_data(response.webpage, dateobj, self.search_endp)
        postdata = self.remove_fields(postdata, set(['ctl00$ContentPlaceHolder1$btnClear']))

        response = self.download_url(self.baseurl, postdata = postdata, referer = curr_url, \
                                     savecookies = cookiejar, loadcookies = cookiejar)
        pagenum = 1
        while response != None and response.webpage != None:
            curr_url = response.response_url

            metainfos, nextpage = self.parse_search_results(response.webpage, \
                                                            dateobj, pagenum)

            relurls = self.download_metainfos(relpath, metainfos, curr_url, cookiejar)
            dls.extend(relurls)
            if nextpage:
                pagenum += 1
                self.logger.info('Going to page %d for date %s', pagenum, dateobj)
                postdata = self.get_form_data(response.webpage, dateobj, self.search_endp, remove_buttons=True)
                response = self.download_nextpage(nextpage, postdata, curr_url, cookiejar)
            else:
                break
 
        return dls
