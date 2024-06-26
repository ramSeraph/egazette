import re
import os
import time
from io import BytesIO
from http.cookiejar import CookieJar
import urllib.request, urllib.parse, urllib.error
import datetime

from ..utils import utils
from .basegazette import BaseGazette
from .central import CentralBase

class Karnataka(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)

        self.baseurl    = 'https://www.gazette.kar.nic.in/%s/'
        self.hostname   = 'www.gazette.kar.nic.in'
        self.flip_date1 = datetime.date(2009, 0o3, 0o5)
        self.flip_date2 = datetime.date(2013, 0o3, 0o7)

    def download_oneday(self, relpath, dateobj):
        dls = []
        if dateobj >= self.flip_date1:
            if dateobj >= self.flip_date2:
                datestr = '%d-%d-%d' % (dateobj.day, dateobj.month, dateobj.year)
            else:
                datestr = '%s-%s-%d' % (utils.pad_zero(dateobj.day), utils.pad_zero(dateobj.month), dateobj.year)
            mainhref = 'Contents-(%s).pdf' % datestr
        else:
            datestr = utils.dateobj_to_str(dateobj, '', reverse=True)    
            mainhref = 'Contents(%s-%s-%s).pdf' % (utils.pad_zero(dateobj.day), utils.pad_zero(dateobj.month), utils.pad_zero(dateobj.year % 100))

        dateurl = self.baseurl % datestr
        docurl  = urllib.parse.urljoin(dateurl, mainhref)

        mainmeta = utils.MetaInfo()
        mainmeta.set_date(dateobj)
        mainmeta.set_url(self.url_fix(docurl))
       
        response = self.download_url(docurl)
        if not response or not response.webpage or response.error:
            return dls

        mainrelurl = os.path.join(relpath, 'main')
        updated = False
        if self.storage_manager.save_rawdoc(self.name, mainrelurl, response.srvresponse, response.webpage):
            self.logger.info('Saved rawfile %s' % mainrelurl)
            updated = True


        page_type = self.get_file_extension(response.webpage)
        if page_type != 'pdf':
            self.logger.warning('Got a non-pdf page and we can\'t handle it for datte %s', dateobj)
            return dls

        links = []
        linknames = []
        hrefs = utils.extract_links_from_pdf(BytesIO(response.webpage))
        for href in hrefs:
            reobj = re.search('(?P<num>Part-\w+)', href)
            if reobj:
                partnum = reobj.groupdict()['num']
            else:
                partnum = '%s' % href
                reobj = re.search('.pdf$', partnum)
                if partnum:
                    partnum = partnum[:reobj.start()]
                 
            relurl = os.path.join(relpath, partnum)
            docurl = urllib.parse.urljoin(dateurl, href) 

            metainfo = utils.MetaInfo()
            metainfo.set_date(dateobj)
            metainfo['partnum'] = partnum

            links.append(relurl)
            linknames.append(partnum)

            if self.save_gazette(relurl, docurl, metainfo):
                dls.append(relurl)

        mainmeta['links']     = links
        mainmeta['linknames'] = linknames
        if self.storage_manager.save_metainfo(self.name, mainrelurl, mainmeta):
            updated = True
            self.logger.info('Saved metainfo %s' % mainrelurl)

        if updated:    
            dls.append(mainrelurl)

        return dls    
       

class KarnatakaErajyapatra(CentralBase):
    def __init__(self, name, storage):
        CentralBase.__init__(self, name, storage)
        self.baseurl       = 'https://erajyapatra.karnataka.gov.in/'
        self.start_date    = datetime.datetime(2020, 1, 1)
        self.result_table  = 'ContentPlaceHolder1_dgGeneralUser'
        self.subject_re    = re.compile('\u0cb5\u0cbf\u0cb7\u0caf')
        self.department_re = re.compile('\u0c87\u0cb2\u0cbe\u0c96\u0cc6\s+/\s+\u0cb8\u0c82\u0cb8\u0ccd\u0ca5\u0cc6')
        self.download_re   = re.compile('\u0ca1\u0ccc\u0ca8\u0ccd.*\u0cb2\u0ccb\u0ca1\u0ccd\s+\u0cae\u0cbe\u0ca1\u0cbf')
        self.gztype        = 'Weekly'
        self.gztype_str    = 'Weekly'

    def get_column_order(self, tr):
        order = []
        for td in tr.find_all('td'):
            txt = utils.get_tag_contents(td)
            #printuni(txt)
            if txt and self.subject_re.search(txt):
                order.append('subject')
            elif txt and self.download_re.search(txt):
                order.append('download')
            elif txt and self.department_re.search(txt):
                order.append('department')
            else:
                order.append('')
        return order


    def get_post_data(self, tags, dateobj, gztype_str):
        datestr  = utils.get_egz_date(dateobj)
        postdata = []

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input' or tag.name == 'textarea':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')
                if t == 'image':
                    continue

                if name == 'ctl00$ContentPlaceHolder1$txtDateIssueF' or \
                   name == 'ctl00$ContentPlaceHolder1$txtDateIssueT':
                    value = datestr
                elif name == 'btnDetail':
                    value = 'Detailed Report'
            elif tag.name == 'select':        
                name = tag.get('name')
                if name == 'ctl00$ContentPlaceHolder1$ddlcate':
                    value = gztype_str
                else:
                    value = utils.get_selected_option(tag)
            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))

        return postdata

    def get_form_data(self, webpage, dateobj, form_href, gztype_str):
        search_form = self.get_search_form(webpage, dateobj, form_href)
        if search_form == None:
            self.logger.warning('Unable to get the search form for %s for day: %s', gztype_str, dateobj)
            return None 

        reobj  = re.compile('^(input|select|textarea)$')
        inputs = search_form.find_all(reobj)
        postdata = self.get_post_data(inputs, dateobj, gztype_str)

        return postdata

    def process_result_row(self, tr, metainfos, dateobj, order, gztype):
        metainfo = utils.MetaInfo()
        metainfos.append(metainfo)
        metainfo.set_date(dateobj)
        metainfo.set_gztype(gztype)

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()

                if col == 'subject':
                    metainfo.set_subject(txt)
                elif col == 'download':
                    inp = td.find('input')
                    if inp:
                        name = inp.get('name')
                        if name:
                            metainfo[col] = name
                elif col == 'department':
                    metainfo[col] = txt
            i += 1



    def get_metainfos(self, webpage, dateobj, gztype):
        metainfos = []
        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse search result page for %s for %s', gztype, dateobj)
            return metainfos

        table = d.find('table', {'id': self.result_table})
        if table == None:
            self.logger.warning('Could not find the result table for %s for %s', gztype, dateobj)
            return metainfos

        order = None
        for tr in table.find_all('tr'):
            if not order:
                order = self.get_column_order(tr)
                continue
            if tr.find('input') == None and tr.find('a') == None:
                continue

            self.process_result_row(tr, metainfos, dateobj, order, gztype)

        return metainfos


    def download_onetype(self, relpath, dateobj, gztype, gztype_str):
        dls = []
        cookiejar  = CookieJar()
        session = self.get_session()
        session.cookies = cookiejar
        response = self.download_url_using_session(self.baseurl, session = session)
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s for %s for the day %s', self.baseurl, gztype_str, dateobj)
            return dls

        curr_url = response.response_url
        form_href = curr_url.split('/')[-1]

        postdata = self.get_form_data(response.webpage, dateobj, form_href, gztype_str)
        postdata = self.replace_field(postdata, '__EVENTTARGET', 'sgzt')

        response = self.download_url(curr_url, savecookies = cookiejar, \
                                     loadcookies = cookiejar, referer = curr_url, \
                                     postdata = postdata)
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s for %s for the day %s', curr_url, gztype_str, dateobj)
            return dls

        curr_url = response.response_url
        form_href = curr_url.split('/')[-1]
        postdata = self.get_form_data(response.webpage, dateobj, form_href, gztype_str)
        if postdata == None:
            return None

        postdata = self.remove_fields(postdata, set(['ctl00$ContentPlaceHolder1$imgbtn_week', \
                                                     'ctl00$ContentPlaceHolder1$Button1', \
                                                     'ctl00$ContentPlaceHolder1$Button2', \
                                                     'ctl00$ContentPlaceHolder1$Button3']))
        response = self.download_url(curr_url, savecookies = cookiejar, \
                                     referer = curr_url, \
                                     loadcookies = cookiejar, postdata = postdata)           
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s for %s for the day %s', curr_url, gztype_str, dateobj)
            return dls

        curr_url = response.response_url
        form_href = curr_url.split('/')[-1]

        postdata = self.get_form_data(response.webpage, dateobj, form_href, gztype_str)
        postdata = self.replace_field(postdata, '__EVENTTARGET', 'ctl00$ContentPlaceHolder1$ddlcate')
        response = self.download_url(curr_url, savecookies = cookiejar, \
                                     referer = curr_url, \
                                     loadcookies = cookiejar, postdata = postdata)           
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s while picking category for %s for the day %s', curr_url, gztype_str, dateobj)
            return dls

        curr_url = response.response_url
        form_href = curr_url.split('/')[-1]

        postdata = self.get_form_data(response.webpage, dateobj, form_href, gztype_str)
        postdata = self.replace_field(postdata, '__SCROLLPOSITIONX', '109')
        postdata = self.replace_field(postdata, '__SCROLLPOSITIONY', '0')

        response = self.download_url(curr_url, savecookies = cookiejar, \
                                     referer = curr_url, \
                                     loadcookies = cookiejar, postdata = postdata)
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s while retrieving search results for %s for the day %s', curr_url, gztype_str, dateobj)
            return dls

        curr_url = response.response_url
        form_href = curr_url.split('/')[-1]

        metainfos = self.get_metainfos(response.webpage, dateobj, gztype)

        postdata = self.get_form_data(response.webpage, dateobj, form_href, gztype_str)

        i = 0
        for metainfo in metainfos:
            dlfieldname = metainfo.pop('download')
            newpost = []
            newpost.extend(postdata)
            newpost.append((f'{dlfieldname}.x', '10'))
            newpost.append((f'{dlfieldname}.y', '10'))

            prefix = gztype_str.lower().replace(' ', '-')
            docid = f'{prefix}-{i}'
            relurl = os.path.join(relpath, docid)

            if self.save_gazette(relurl, curr_url, metainfo, postdata = newpost, \
                                 cookiefile = cookiejar, validurl = False):
                dls.append(relurl)
            i += 1
        return dls

    def download_oneday(self, relpath, dateobj):
        edls = self.download_onetype(relpath, dateobj, 'Extraordinary', 'Extra Ordinary')
        ddls = self.download_onetype(relpath, dateobj, 'Ordinary', 'Daily')
        wdls = self.download_onetype(relpath, dateobj, 'Ordinary', 'Weekly')
        return edls + ddls + wdls



