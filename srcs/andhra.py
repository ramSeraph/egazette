from http.cookiejar import CookieJar
import re
import os
import datetime
import urllib.parse

from ..utils import utils
from .basegazette import BaseGazette
from .central import CentralBase
from ..utils.metainfo import MetaInfo

class Andhra(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)

        self.baseurl   = 'https://apegazette.cgg.gov.in/eGazetteSearch.do'
        self.searchurl = self.baseurl
        self.hostname  = 'apegazette.cgg.gov.in'
        self.result_table= 'gvGazette'

    def get_field_order(self, tr):
        i = 0
        order  = []
        valid = False
        for th in tr.find_all('th'):
            txt = utils.get_tag_contents(th)
            if txt and re.search('gazette\s+type', txt, re.IGNORECASE):
                order.append('gztype')
            elif txt and re.search('department', txt, re.IGNORECASE):
                order.append('department')
            elif txt and re.search('abstract', txt, re.IGNORECASE):
                order.append('subject')
            elif txt and re.search('Issue\s+No', txt, re.IGNORECASE):
                order.append('gznum')
            elif txt and re.search('Notification\s+No', txt, re.IGNORECASE):
                order.append('notification_num')
            elif txt and re.search('Download', txt, re.IGNORECASE):
                order.append('download')
                valid = True
            elif txt and re.search('', txt, re.IGNORECASE):
                order.append('')

            else:
                order.append('')    

            i += 1
        if valid:    
            return order
        return None    

    def get_post_data(self, dateobj):
        datestr = utils.dateobj_to_str(dateobj, '')

        postdata = [\
            ('mode',                  'unspecified'),  \
            ('property(abstract)',    ''  ), \
            ('property(department)',  '0'), \
            ('property(docid)',       ''), \
            ('property(fromdate)',    datestr), \
            ('property(gazetteno)',   ''), \
            ('property(gazettePart)', '0'), \
            ('property(gazetteType)', '0'), \
            ('property(month1)',      '0'), \
            ('property(search)',      'search'), \
            ('property(todate)',      datestr), \
            ('property(year1)',       '0'), \
        ]
        return postdata

    def get_postdata_for_doc(self, docid, dateobj):
        postdata = [\
            ('mode',                  'viewDocument'),  \
            ('property(abstract)',    ''  ), \
            ('property(department)',  '0'), \
            ('property(docid)',       docid), \
            ('property(fromdate)',    ''), \
            ('property(gazetteno)',   ''), \
            ('property(gazettePart)', '0'), \
            ('property(gazetteType)', '0'), \
            ('property(month1)',      '0'), \
            ('property(search)',      'search'), \
            ('property(todate)',      ''), \
            ('property(year1)',       '0'), \
            ('x',                     '16'), \
            ('y',                     '16'), \
        ]
        return postdata

    def parse_search_results(self, webpage, dateobj):
        minfos = []
        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse results page for date %s', dateobj)
            return minfos

        table = d.find('table', {'id': 'displaytable'})
        if not table:
            self.logger.warning('Unable to find result table for date %s', dateobj)
            return minfos
        
        order = None
        for tr in table.find_all('tr'):
            if not order:
                order = self.get_field_order(tr)
                continue
            metainfo = self.parse_row(tr, order, dateobj)
            if metainfo and 'download' in metainfo:
                minfos.append(metainfo)

        return minfos

    def parse_row(self, tr, order, dateobj):
        metainfo = MetaInfo()
        metainfo.set_date(dateobj)

        i = 0
        for td in tr.find_all('td'):
            txt = utils.get_tag_contents(td)
            if i < len(order) and txt:
                txt = txt.strip()
                col = order[i]
                if col == 'gztype':
                    words = txt.split('/')
                    metainfo['gztype'] = words[0].strip()
                    if len(words) > 1:
                        metainfo['partnum'] = words[1].strip()
                    if len(words) > 2:
                        metainfo['district'] = words[2].strip()
                elif col == 'download':
                    inp = td.find('input')       
                    if inp and inp.get('onclick'): 
                        metainfo['download'] = inp.get('onclick')
                elif col in ['notification_num', 'gznum', 'department']:
                    metainfo[col] = txt
                elif col == 'subject':
                    metainfo.set_subject(txt)    
            i += 1
        return metainfo

    def download_oneday(self, relpath, dateobj):
        dls = []
        cookiejar  = CookieJar()
        response = self.download_url(self.baseurl, savecookies = cookiejar)
        postdata = self.get_post_data(dateobj)
        response = self.download_url(self.searchurl, postdata = postdata, \
                               loadcookies = cookiejar, savecookies = cookiejar)

        if not response or not response.webpage:
            return dls

        metainfos = self.parse_search_results(response.webpage, dateobj)
        for metainfo in metainfos:
            relurl = self.download_metainfo(metainfo, relpath, dateobj, cookiejar)
            if relurl:
                dls.append(relurl)

        return dls

    def download_metainfo(self, metainfo, relpath, dateobj, cookiejar):
        reobj = re.search('openDocument\(\'(?P<num>\d+)\'\)', metainfo['download'])        
        if not reobj:
            return None
        docid = reobj.groupdict()['num']    
        postdata = self.get_postdata_for_doc(docid, dateobj)
        metainfo.pop('download')
        relurl = os.path.join(relpath, docid)

        if self.save_gazette(relurl, self.searchurl, metainfo, \
                             cookiefile = cookiejar, \
                             postdata = postdata, validurl = False):
            return relurl
        return None    

class AndhraArchive(CentralBase):
    def __init__(self, name, storage):
        CentralBase.__init__(self, name, storage)
        self.baseurl      = 'https://gazettearchive.ap.gov.in/gt_PublicReport.aspx'
        self.hostname     = 'gazettearchive.ap.gov.in'
        self.search_endp  = 'gt_PublicReport.aspx'
        self.result_table = 'FileMoveList2'

    def get_search_results(self, search_url, dateobj, cookiejar):
        response = self.download_url(search_url, savecookies = cookiejar, loadcookies=cookiejar)

        postdata = self.get_form_data(response.webpage, dateobj, self.search_endp)
        if postdata == None:
            return None
        response = self.download_url(search_url, savecookies = cookiejar, \
                                   loadcookies = cookiejar, postdata = postdata)
        return response

    def get_post_data(self, tags, dateobj):
        datestr  = utils.dateobj_to_str(dateobj, '')
        postdata = []

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')
                if t == 'image' or name == 'Button2' or name == 'Button1':
                    continue


                if name == 'txttodate' or name == 'txtfrmdate':
                    value = datestr
                elif name in ['jobno', 'txtGoNo', 'txtSearchText']:
                    value = ''
            elif tag.name == 'select':
                name = tag.get('name')
                if name == 'BtnSearch':
                    value = 'search'
                elif name == 'DDLDeptname':
                    value = 'Select'
                elif name == 'DDLGoType':
                    value = 'Select'
                elif name == 'DropDownList1':
                    value = 'Select'

            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))

        return postdata

    def get_column_order(self, tr):
        order = []
        for th in tr.find_all('th'):
            txt = utils.get_tag_contents(th)
            if txt and re.search('GazetteType', txt):
                order.append('gztype')
            elif txt and re.search('Abstract', txt):
                order.append('subject')
            elif txt and re.search('DepartmentName', txt):
                order.append('department')
            elif txt and re.search('Gazette\s+No', txt):
                order.append('gznum')
            elif txt and re.search('Issued\s+By', txt):
                order.append('issued_by')
            else:
                order.append('')
        return order

    def process_result_row(self, tr, metainfos, dateobj, order):
        download = None
        for link in tr.find_all('a'):
            txt = utils.get_tag_contents(link)
            if txt and re.match('\s*select', txt, re.IGNORECASE):
                download = link.get('href')
                break
 
        if not download:
            return
 
        metainfo = MetaInfo()
        metainfos.append(metainfo)
        metainfo.set_date(dateobj)
        metainfo['download'] = download

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()
                else:
                    continue

                if col == 'gztype':
                    pos = txt.find('PART')
                    if pos > 0:
                        metainfo.set_gztype(txt[:pos])
                        metainfo['partnum'] = txt[pos:]
                    else:
                        metainfo.set_gztype(txt)

                elif col in ['subject', 'department', 'issued_by', 'gznum']:
                    metainfo[col] = txt
  
            i += 1

    def download_metainfos(self, relpath, metainfos, search_url, \
                           postdata, cookiejar):
        dls = []
        for metainfo in metainfos:
            if 'download' not in metainfo or 'gznum' not in metainfo:
                self.logger.warning('Required fields not present. Ignoring- %s' % metainfo) 
                continue

            href = metainfo.pop('download')
            reobj = re.search('javascript:__doPostBack\(\'(?P<event_target>[^\']+)\',\'(?P<event_arg>[^\']+)\'\)', href)
            if not reobj:
                self.logger.warning('No event_target or event_arg in the gazette link. Ignoring - %s' % metainfo)
                continue 

            groupdict    = reobj.groupdict()
            event_target = groupdict['event_target']
            event_arg    = groupdict['event_arg']

            newpost = []
            for t in postdata:
                if t[0] == 'BtnSearch':
                    continue
                if t[0] == '__EVENTTARGET':
                    t = (t[0], event_target)
                if t[0] == '__EVENTARGUMENT':
                    t = (t[0], event_arg)

                newpost.append(t)
                   
            gznum = metainfo['gznum']
            if 'partnum' in metainfo:
                gznum = '%s_%s' % (gznum, metainfo['partnum'])
            gznum, n = re.subn('[\s]+', '', gznum)
            relurl = os.path.join(relpath, gznum)
            if self.save_gazette(relurl, search_url, metainfo, \
                                 postdata = newpost, cookiefile = cookiejar, \
                                 validurl = False):
                dls.append(relurl)

        return dls

class AndhraGOIR(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl      = 'https://goir.ap.gov.in/'
        self.hostname     = 'goir.ap.gov.in'
        self.search_endp  = './'

    def remove_fields(self, postdata, fields):
        newdata = []
        for k, v in postdata:
            if k not in fields:
                newdata.append((k, v))
        return newdata


    def replace_field(self, formdata, k, v):
        newdata = []
        for k1, v1 in formdata:
            if k1 == k:
                newdata.append((k1, v))
            else:
                newdata.append((k1, v1))
        return newdata

    def get_search_form(self, webpage, endp):
        d = utils.parse_webpage(webpage, self.parser)
        if d is None:
            return None

        search_form = d.find('form', {'action': endp})
        return search_form

    def get_selected_option(self, select):
        option = select.find('option', {'selected': 'selected'})
        if option is None:
            option = select.find('option')
        if option is None:
            return ''
        val = option.get('value')
        if val is None:
            val = ''
        return val

    def get_form_data(self, webpage, dateobj):
        search_form = self.get_search_form(webpage, self.search_endp)
        if search_form is None:
            return None

        reobj  = re.compile(r'^(input|select)$')
        inputs = search_form.find_all(reobj)

        formdata = []
        for tag in inputs:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')
                if t in ['image', 'checkbox', 'button', 'submit']:
                    continue
            elif tag.name == 'select':        
                name = tag.get('name')
                value = self.get_selected_option(tag)
            if name:
                if value is None:
                    value = ''
                formdata.append((name, value))

        datestr = dateobj.strftime('%d-%m-%Y')
        formdata = self.replace_field(formdata, 'ctl00$ContentPlaceHolder1$txtfrmdate', datestr)
        formdata = self.replace_field(formdata, 'ctl00$ContentPlaceHolder1$txttodate',  datestr)

        return formdata

    def get_column_order(self, tr):
        order = []
        for td in tr.find_all('th'):
            txt = utils.get_tag_contents(td)
            if txt and re.search(r'Organization', txt):
                order.append('department')
            elif txt and re.search(r'Section', txt):
                order.append('section')
            elif txt and re.search(r'G\.O\s+N\.O', txt):
                order.append('gonum')
            elif txt and re.search(r'G\.O\s+Category', txt):
                order.append('category')
            elif txt and re.search(r'Abstract', txt):
                order.append('abstract')
            elif txt and re.search(r'Amount\s+in\s+G\.O\(₹\)', txt):
                order.append('amount')
            elif txt and re.search(r'ENGLISH\s+G\.O', txt):
                order.append('download')
            else:
                order.append('')
        return order

    def find_next_page(self, d, curr_page):
        div = d.find('div', {'id': 'divpagination'})
        links = div.find_all('a')
        for link in links:
            txt = utils.get_tag_contents(link)
            if txt:
                try: 
                    page_no = int(txt)
                except Exception:
                    page_no = None
                if page_no == curr_page + 1:
                    return link

        return None               

    def process_result_row(self, tr, metainfos, dateobj, order):
        metainfo = MetaInfo()
        metainfo.set_date(dateobj)

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()

                if col == 'download':
                    a = td.find('a')
                    if a is not None:
                        metainfo[col] = a
                elif col == 'gonum':
                    metainfo['gotype'] = 'Unknown'
                    parts = txt.split('-')
                    if len(parts) != 2:
                        metainfo[col] = txt
                    else:
                        if parts[0] == 'MS':
                            metainfo['gotype'] = 'Manuscript'
                            metainfo[col] = parts[1]
                        elif parts[0] == 'RT':
                            metainfo['gotype'] = 'Routine'
                            metainfo[col] = parts[1]
                        else:
                            metainfo[col] = txt
                elif col == 'department':
                    txt = txt.replace('\r\n', ' ')
                    metainfo[col] = txt
                elif col != '':
                    metainfo[col] = txt
            i += 1

        if len(metainfo) == 9:
            metainfos.append(metainfo)


    def parse_search_results(self, webpage, dateobj, curr_page):
        metainfos = []
        nextpage  = None

        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse search result page for %s', dateobj)
            return metainfos, nextpage

        tables = d.find_all('table', {'id': 'FileMoveList2'})

        if len(tables) != 1:
            self.logger.warning('Could not find the result table for %s', dateobj)
            return metainfos, nextpage
        
        order = None
        for tr in tables[0].find_all('tr'):
            if not order:
                order = self.get_column_order(tr)
                continue

            self.process_result_row(tr, metainfos, dateobj, order)

        nextpage = self.find_next_page(d, curr_page)

        return metainfos, nextpage

    def download_nextpage(self, nextpage, search_url, postdata, cookiejar):
        newdata = []
        href = nextpage.get('href') 
        if not href:
            return None

        reobj = re.search(r'__doPostBack\(\'(?P<etarget>[^\']+)', href)
        if not reobj:
            self.logger.warning('Could not get link for next page')
            return None

        etarget = reobj.groupdict()['etarget']

        newdata = self.replace_field(postdata, '__EVENTTARGET', etarget)
        newdata.append(('ctl00$ContentPlaceHolder1$ddlPages', '100'))

        response = self.download_url(search_url, savecookies = cookiejar, \
                                     referer = search_url, \
                                     loadcookies = cookiejar, \
                                     postdata = newdata)
            
        return response 

    def download_metainfos(self, relpath, metainfos, searchurl, \
                           postdata, cookiejar):
        dls = []
        for metainfo in metainfos:
            if 'download' in metainfo:
                download = metainfo.pop('download')
                href = download.get('href')
                if not href:
                    continue

                groups = []
                for reobj in re.finditer(r'"(?P<obj>[^"]+)"', href):
                    groups.append(reobj.groupdict()['obj'])

                if not groups or len(groups) < 2:
                    continue

                gid       = groups[0]
                file_type = groups[1]

                relurl = os.path.join(relpath, f'{file_type}-{gid}')

                gurl = urllib.parse.urljoin(self.baseurl, './dgo.ashx')
                gurl = f'{gurl}?gid={gid}&fileType={file_type}'

                if self.save_gazette(relurl, gurl, metainfo, postdata=None, \
                                     referer = searchurl, cookiefile = cookiejar, \
                                     min_size = 162):
                    dls.append(relurl)
        return dls


    def download_oneday(self, relpath, dateobj):
        dls = []
        cookiejar  = CookieJar()

        response = self.download_url(self.baseurl, savecookies = cookiejar)
        if not response or not response.webpage:
            self.logger.warning('Unable to get %s date %s', self.baseurl, dateobj)
            return dls

        curr_url = response.response_url

        postdata = self.get_form_data(response.webpage, dateobj)
        if postdata is None:
            self.logger.warning('Unable to retreive form data for date %s', dateobj)
            return dls
        postdata.append(('ctl00$ContentPlaceHolder1$BtnSearch', 'Search'))

        searchurl = urllib.parse.urljoin(curr_url, self.search_endp)

        response = self.download_url(searchurl, postdata = postdata, referer = curr_url, \
                                     loadcookies = cookiejar, savecookies = cookiejar)
        pagenum = 1
        while response is not None and response.webpage is not None:
            curr_url = response.response_url

            metainfos, nextpage = self.parse_search_results(response.webpage, \
                                                            dateobj, pagenum)
            
            postdata = self.get_form_data(response.webpage, dateobj)
            relurls = self.download_metainfos(relpath, metainfos, curr_url, \
                                              postdata, cookiejar)
            dls.extend(relurls)
            if not nextpage:
                break

            pagenum += 1
            self.logger.info('Going to page %d for date %s', pagenum, dateobj)
            response = self.download_nextpage(nextpage, curr_url, postdata, cookiejar)

        return dls

