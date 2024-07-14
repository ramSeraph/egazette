from http.cookiejar import CookieJar, Cookie
import re
import os
import datetime
import urllib.parse

from .basegazette import BaseGazette
from ..utils import utils

class Maharashtra(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl      = 'https://egazzete.mahaonline.gov.in/Forms/GazetteSearch.aspx'
        self.hostname     = 'egazzete.mahaonline.gov.in'
        self.search_endp  = 'GazetteSearch.aspx'
        self.result_table = 'CPH_GridView2'
        self.start_date   = datetime.datetime(2010, 1, 1)
        self.section_input_field_name = 'ctl00$CPH$ddlSection'

    def remove_fields(self, postdata, fields):
        newdata = []
        for k, v in postdata:
            if k not in fields:
                newdata.append((k, v))
        return newdata

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

    def replace_field(self, postdata, field_name, field_value):
        newdata = []
        for k, v in postdata:
            if k == field_name:
                newdata.append((field_name, field_value))
            else:
                newdata.append((k, v))
        return newdata

    def get_post_data(self, tags, dateobj, section_value):
        postdata = []

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')
                if t == 'image':
                    continue

                if name == 'ctl00$CPH$txtToDate' or \
                        name == 'ctl00$CPH$txtfromDate':
                    value = dateobj.strftime('%d/%m/%Y')
            elif tag.name == 'select':
                name = tag.get('name')
                if name == self.section_input_field_name:
                    value = section_value
                else:
                    value = self.get_selected_option(tag)
            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))
        return postdata

    def get_column_order(self, tr):
        order = []
        for th in tr.find_all('th'):
            txt = utils.get_tag_contents(th)
            if txt and re.search('Division\s+Name', txt):
                order.append('division')
            elif txt and re.search('Subject', txt):
                order.append('subject')
            elif txt and re.search('View\s+Gazette', txt):
                order.append('download')
            elif txt and re.search('Section\s+Name', txt):
                order.append('partnum')
            elif txt and re.search('Gazette\s+Type', txt):
                order.append('gztype')
            else:
                order.append('')
        return order

    def process_result_row(self, tr, metainfos, dateobj, order):
        metainfo = utils.MetaInfo()
        metainfo.set_date(dateobj)

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
                    metainfo.set_gztype(txt)
                elif col == 'download':
                    link = td.find('a')
                    if link:
                        href = link.get('href')
                        if href:
                            metainfo['download'] = href
                elif col in ['partnum', 'division', 'subject']:
                    metainfo[col] = txt
  
            i += 1
        if 'download' not in metainfo:
            self.logger.warning('No download link, ignoring: %s', tr)
        else:
            metainfos.append(metainfo)
            
    def download_metainfos(self, relpath, metainfos, postdata, cookiejar):
        dls = []
        for metainfo in metainfos:
            if 'download' not in metainfo or 'gztype' not in metainfo:
                self.logger.warning('Required fields not present. Ignoring- %s' % metainfo) 
                continue

            href = metainfo.pop('download')
            reobj = re.search('javascript:__doPostBack\(\'(?P<event_target>[^\']+)\'', href)
            if not reobj:
                self.logger.warning('No event_target in the gazette link. Ignoring - %s' % metainfo)
                continue 

            groupdict    = reobj.groupdict()
            event_target = groupdict['event_target']

            newpost = []
            newpost.extend(postdata)
            newpost = self.replace_field(newpost, '__EVENTTARGET', event_target)
            newpost = self.remove_fields(newpost, set(['ctl00$CPH$btnSearch']))
                   
            gztype = metainfo['gztype']
            if 'division' in metainfo:
                gztype = '%s_%s' % (gztype, metainfo['division'])
            if 'partnum' in metainfo:
                gztype = '%s_%s' % (gztype, metainfo['partnum'])

            gztype, n = re.subn('[()\s-]+', '-', gztype)
            relurl = os.path.join(relpath, gztype)
            if self.save_gazette(relurl, self.baseurl, metainfo, \
                                 postdata = newpost, cookiefile = cookiejar, \
                                 validurl = False):
                dls.append(relurl)

        return dls

    def find_search_form(self, webpage):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return None

        form = d.find('form', {'action': self.search_endp})
        return form


    def get_section_list(self):
        sections = []
        
        response = self.download_url(self.baseurl)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to get main page at %s', self.baseurl)
            return sections

        search_form = self.find_search_form(response.webpage)
        if search_form == None:
            self.logger.warning('Unable to parse main page at %s to collect section list', self.baseurl)
            return sections

        select = search_form.find('select', {'name': self.section_input_field_name})        
        if select == None:
            self.logger.warning('Unable to locate section list at %s', self.baseurl)
            return sections

        options = select.find_all('option')
        for option in options:
            txt   = utils.get_tag_contents(option)
            value = option.get('value')
            try:
                val_num = int(value)
                sections.append((txt.strip(), value))
            except:
                pass

        return sections

    def get_hidden_field(self, webpage):
        hidden_field = None

        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            return hidden_field

        scripts = d.find_all('script')
        for script in scripts:
            src = script.get('src')
            if src == None:
                continue
            if not src.startswith('/Forms/GazetteSearch.aspx'):
                continue

            src_parsed = urllib.parse.urlparse(src)
            src_query  = urllib.parse.parse_qs(src_parsed.query)
            hidden_field = src_query['_TSM_CombinedScripts_'][0]
            break

        return hidden_field

    def get_form_data(self, webpage, dateobj, section):
        section_name, section_value = section

        hidden_field = self.get_hidden_field(webpage)
        if hidden_field == None:
            self.logger.warning('Unable to parse main page at %s to get hidden field for %s, %s', self.baseurl, dateobj, section_name)
            return None

        search_form = self.find_search_form(webpage)
        if search_form == None:
            self.logger.warning('Unable to parse main page at %s to get search form for %s, %s', self.baseurl, dateobj, section_name)
            return None

        reobj  = re.compile('^(input|select)$')
        inputs = search_form.find_all(reobj)

        postdata = self.get_post_data(inputs, dateobj, section_value)
        postdata = self.remove_fields(postdata, set(['ctl00$CPH$btnReset']))
        postdata = self.replace_field(postdata, 'ScriptManager1_HiddenField', hidden_field)

        return postdata

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

    def parse_search_results(self, webpage, dateobj, section_name, curr_page):
        metainfos = []
        nextpage  = None

        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse search result page for %s, %s', dateobj, section_name)
            return metainfos, nextpage

        table = d.find('table', {'id': self.result_table})

        if table == None:
            self.logger.warning('Could not find the result table for %s, %s', dateobj, section_name)
            return metainfos, nextpage
        
        order = None
        for tr in table.find_all('tr'):
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


    def download_nextpage(self, nextpage, postdata, cookiejar):
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
        
        newpost = []
        newpost.extend(postdata)
        newpost = self.replace_field(newpost, '__EVENTTARGET', etarget)
        newpost = self.replace_field(newpost, '__EVENTARGUMENT', page_no)
        newpost = self.remove_fields(newpost, set(['ctl00$CPH$btnSearch']))

        response = self.download_url(self.baseurl, savecookies = cookiejar, \
                                     referer = self.baseurl, \
                                     loadcookies = cookiejar, \
                                     postdata = newpost)
            
        return response 



    def download_onesection(self, dls, relpath, dateobj, section):
        cookiejar = CookieJar()
        section_name, section_value = section

        response = self.download_url(self.baseurl, savecookies=cookiejar)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to get main page at %s for section %s', self.baseurl, section_name)
            return


        postdata = self.get_form_data(response.webpage, dateobj, section)
        if postdata == None:
            return

        postdata = self.replace_field(postdata, '__EVENTTARGET', self.section_input_field_name)
        postdata = self.remove_fields(postdata, set(['ctl00$CPH$btnSearch']))
        
        response = self.download_url(self.baseurl, postdata = postdata, \
                                     savecookies = cookiejar, loadcookies = cookiejar, \
                                     referer = self.baseurl)
        if response == None or response.webpage == None:
            self.logger.warning('Unable to change to section for page at %s for section %s', self.baseurl, section_name)
            return

        postdata = self.get_form_data(response.webpage, dateobj, section)
        if postdata == None:
            return

        response = self.download_url(self.baseurl, postdata = postdata, \
                                     savecookies = cookiejar, loadcookies = cookiejar, \
                                     referer = self.baseurl)

        pagenum = 1
        while response != None and response.webpage != None:
            metainfos, nextpage = self.parse_search_results(response.webpage, dateobj, section_name, pagenum)

            postdata = self.get_form_data(response.webpage, dateobj, section)
            if postdata == None:
                break

            relurls = self.download_metainfos(relpath, metainfos, postdata, cookiejar)
            dls.extend(relurls)

            if nextpage == None:
                break

            pagenum += 1
            response = self.download_nextpage(nextpage, postdata, cookiejar)


    def download_oneday(self, relpath, dateobj):
        dls = []

        sections = self.get_section_list()
        for section in sections:
            self.download_onesection(dls, relpath, dateobj, section)

        return dls
