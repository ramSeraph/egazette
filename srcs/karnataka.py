import re
import os
from io import BytesIO
from http.cookiejar import CookieJar
import urllib.request
import urllib.parse
import urllib.error
import datetime

from ..utils import utils
from ..utils.metainfo import MetaInfo
from .basegazette import BaseGazette

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

        mainmeta = MetaInfo()
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

            metainfo = MetaInfo()
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
       

class KarnatakaErajyapatra(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl      = 'https://erajyapatra.karnataka.gov.in/'
        self.start_date   = datetime.datetime(2020, 1, 1)
        self.result_table = 'ContentPlaceHolder1_dgGeneralUser'


    def pop_field(self, postdata, field):
        val = None
        newdata = []
        for k, v in postdata:
            if k == field:
                val = v
            else:
                newdata.append((k, v))
        return newdata, val


    def get_column_order(self, tr):
        subject_re    = re.compile(r'\u0cb5\u0cbf\u0cb7\u0caf')
        department_re = re.compile(r'\u0c87\u0cb2\u0cbe\u0c96\u0cc6\s*/\s*\u0cb8\u0c82\u0cb8\u0ccd\u0ca5\u0cc6')
        download_re   = re.compile(r'\u0ca1\u0ccc\u0ca8\u0ccd\u200c\u0cb2\u0ccb\u0ca1\u0ccd\s+\u0cae\u0cbe\u0ca1\u0cbf')
        type_re       = re.compile(r'\u0caa\u0ccd\u0cb0\u0cb5\u0cb0\u0ccd\u0c97')
        issuedate_re  = re.compile(r'\u0cb8\u0c82\u0c9a\u0cbf\u0c95\u0cc6\s+\u0ca6\u0cbf\u0ca8\u0cbe\u0c82\u0c95')



        order = []
        for td in tr.find_all('td'):
            txt = utils.get_tag_contents(td)
            if txt and department_re.search(txt):
                order.append('department')
            elif txt and subject_re.search(txt):
                order.append('subject')
            elif txt and type_re.search(txt):
                order.append('gztype')
            elif txt and issuedate_re.search(txt):
                order.append('issuedate')
            elif txt and download_re.search(txt):
                order.append('download')
            else:
                order.append('')

        if 'download' not in order:
            return None

        return order


    def get_post_data(self, tags):
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

                if t == 'radio':
                    continue

            elif tag.name == 'select':        
                name  = tag.get('name')
                value = utils.get_selected_option(tag)

            if name:
                if value is None:
                    value = ''
                postdata.append((name, value))

        return postdata

    def get_form_data(self, webpage, form_href, collect=None):
        search_form = utils.get_search_form(webpage, self.parser, form_href)
        if search_form is None:
            return None 

        reobj  = re.compile('^(input|select|textarea)$')
        inputs = search_form.find_all(reobj)
        postdata = self.get_post_data(inputs)

        if collect is not None:
            select = search_form.find('select', { 'name': collect })
            if select is None:
                return postdata, None

            option_vals = []
            for option in select.find_all('option'):
                val = option.get('value')
                name = utils.get_tag_contents(option)
                option_vals.append((val, name))

            return postdata, option_vals[1:]

        return postdata

    def process_result_row(self, metainfos, tr, order):
        metainfo = MetaInfo()

        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                col = order[i]
                txt = utils.get_tag_contents(td)
                if txt:
                    txt = txt.strip()
                if col == 'download':
                    inp = td.find('input')
                    if inp:
                        name = inp.get('name')
                        if name:
                            metainfo[col] = name

                elif col == 'gztype':
                    if txt == 'Daily':
                        metainfo.set_gztype('Daily')
                    elif txt == 'Weekly':
                        metainfo.set_gztype('Weekly')
                    else:
                        metainfo.set_gztype('Extraordinary')

                elif col == 'issuedate':
                    gzdate = datetime.datetime.strptime(txt, '%d-%b-%Y').date()
                    metainfo.set_date(gzdate)

                elif col != '':
                    metainfo[col] = txt

            i += 1

        if 'download' not in metainfo:
            return

        metainfos.append(metainfo)


    def parse_results(self, webpage, fromdate, todate, div_name, dist_name):
        metainfos = []

        d = utils.parse_webpage(webpage, self.parser)
        if not d:
            self.logger.warning('Unable to parse search result page for division %s, district %s, for %s to %s', \
                                div_name, dist_name, fromdate, todate)
            return metainfos

        tables = d.find_all('table')

        order = None
        for table in tables:
            if table.find('table') is not None:
                continue

            order = None
            for tr in table.find_all('tr'):
                if not order:
                    order = self.get_column_order(tr)
                    continue
                if tr.find('input') is None and tr.find('a') is None:
                    continue

                self.process_result_row(metainfos, tr, order)

            if order is not None:
                break

        if order is None:
            self.logger.warning('Could not find the result table for divsion %s, district %s, for %s to %s', \
                                div_name, dist_name, fromdate, todate)

        return metainfos


    def sync(self, fromdate, todate, event):
        dls = []
        cookiejar = CookieJar()

        fromdate = fromdate.date()
        todate   = todate.date()

        session = self.get_session()
        session.cookies = cookiejar

        response = self.download_url_using_session(self.baseurl, session = session)
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s for %s to %s', \
                                self.baseurl, fromdate, todate)
            return dls

        curr_url  = response.response_url
        form_href = './' + curr_url.split('/')[-1]


        # moving to search page

        postdata = self.get_form_data(response.webpage, form_href)
        if postdata is None:
            self.logger.warning('Unable to get the form data for %s to %s', \
                                fromdate, todate)
            return dls

        postdata = utils.replace_field(postdata, '__EVENTTARGET', 'sgzt')

        response = self.download_url(curr_url, savecookies = cookiejar, \
                                     loadcookies = cookiejar, referer = curr_url, \
                                     postdata = postdata)
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s for %s to %s', \
                                curr_url, fromdate, todate)
            return dls

        curr_url  = response.response_url
        form_href = './' + curr_url.split('/')[-1]


        # picking search type as 'by district'
                    
        postdata = self.get_form_data(response.webpage, form_href)
        if postdata is None:
            self.logger.warning('Unable to get the form data for %s to %s', \
                                fromdate, todate)
            return dls

        postdata = utils.remove_fields(postdata, set(['ctl00$ContentPlaceHolder1$Imagebutton',
                                                      'ctl00$ContentPlaceHolder1$imgbtn_week',
                                                      'ctl00$ContentPlaceHolder1$Button2', \
                                                      'ctl00$ContentPlaceHolder1$Button3']))
        response = self.download_url(curr_url, savecookies = cookiejar, \
                                     referer = curr_url, \
                                     loadcookies = cookiejar, postdata = postdata)           
        if not response or not response.webpage:
            self.logger.warning('Could not fetch %s for %s to %s', \
                                curr_url, fromdate, todate)
            return dls

        curr_url  = response.response_url
        form_href = './' + curr_url.split('/')[-1]

        # collect the divisions
        div_select_name = 'ctl00$ContentPlaceHolder1$ddlpress'
        postdata, div_options = self.get_form_data(response.webpage, form_href, \
                                                   collect=div_select_name)

        if div_options is None or postdata is None:
            self.logger.warning('Unable to get the form data for %s to %s', \
                                fromdate, todate)
            return dls

        curr_url  = response.response_url
        form_href = './' + curr_url.split('/')[-1]

        all_metainfos = []
        for div_val, div_name in div_options:
            self.logger.info('Looking in division %s for %s to %s', div_name, fromdate, todate)

            newpost  = utils.replace_field(postdata, div_select_name, div_val)
            response = self.download_url(curr_url, savecookies = cookiejar, \
                                         referer = curr_url, \
                                         loadcookies = cookiejar, postdata = newpost)

            if not response or not response.webpage:
                self.logger.warning('Could not fetch %s for division %s, for %s to %s', \
                                    curr_url, div_name, fromdate, todate)
                continue

            div_curr_url  = response.response_url
            div_form_href = './' + div_curr_url.split('/')[-1]

            dist_select_name = 'ctl00$ContentPlaceHolder1$ddldist'
            div_postdata, dist_options = self.get_form_data(response.webpage, div_form_href, \
                                                            collect=dist_select_name)

            if dist_options is None or div_postdata is None:
                self.logger.warning('Unable to get the form data for division %s for %s to %s', \
                                    div_name, fromdate, todate)
                continue


            for dist_val, dist_name in dist_options:

                self.logger.info('Looking in district %s for %s to %s', dist_name, fromdate, todate)
                div_newpost = utils.replace_field(div_postdata, dist_select_name, dist_val)

                response = self.download_url(div_curr_url, savecookies = cookiejar, \
                                             referer = curr_url, \
                                             loadcookies = cookiejar, postdata = div_newpost)

                if not response or not response.webpage:
                    self.logger.warning('Could not fetch %s for division %s, district %s, for %s to %s', \
                                        div_curr_url, div_name, dist_name, fromdate, todate)
                    continue

                dist_curr_url  = response.response_url
                dist_form_href = './' + dist_curr_url.split('/')[-1]

                dist_postdata  = self.get_form_data(response.webpage, dist_form_href)

                if dist_postdata is None:
                    self.logger.warning('Unable to get the form data for division %s, district %s, for %s to %s', \
                                        div_name, dist_name, fromdate, todate)
                    continue

                metainfos = self.parse_results(response.webpage, fromdate, todate, div_name, dist_name)

                for metainfo in metainfos:
                    gzdate = metainfo.get_date()         
                    if gzdate < fromdate or gzdate > todate:
                        continue

                    metainfo['division'] = div_name
                    metainfo['district'] = dist_name

                    dlfieldname  = metainfo.pop('download')
                    gaz_postdata = dist_postdata.copy()
                    gaz_postdata.append((f'{dlfieldname}.x', '10'))
                    gaz_postdata.append((f'{dlfieldname}.y', '10'))
                    
                    
                    response = self.download_url(dist_curr_url, referer = dist_curr_url, \
                                                loadcookies = cookiejar, postdata = gaz_postdata)
                    if not response or not response.webpage:
                        self.logger.warning('Could not fetch %s for division %s, district %s, for %s to %s', \
                                            dist_curr_url, div_name, dist_name, fromdate, todate)
                        continue

                    gaz_curr_url = response.response_url

                    reobj = re.search(r"window\.open\('(?P<href>[^']+)'", response.webpage.decode('utf8'))
                    if reobj is None:
                        self.logger.warning('Could not get download link in %s for division %s, district %s, for %s to %s', \
                                            dist_curr_url, div_name, dist_name, fromdate, todate)
                        continue
                        
                    g = reobj.groupdict()
                    href = g['href']

                    gzurl = urllib.parse.urljoin(gaz_curr_url, href)
                    metainfo['url'] = gzurl
                    all_metainfos.append(metainfo)

        by_url = {}
        for metainfo in all_metainfos:
            url = metainfo.pop('url')
            if url not in by_url:
                by_url[url] = []
            by_url[url].append(metainfo)

        for gzurl, metainfos in by_url.items():
            newmeta = MetaInfo()
            for k in metainfos[0].keys():
                vals = [ m.get(k, None) for m in metainfos ]
                vals = [ v for v in vals if v is not None ]
                vals = set(vals)
                if len(vals) == 1:
                    val = vals.pop()
                else:
                    val = list(vals)
                newmeta[k] = val

            docid = gzurl.split('/')[-1].rsplit('.', 1)[0]
            gzdate = newmeta.get_date()

            relpath = os.path.join(self.name, gzdate.__str__())
            relurl  = os.path.join(relpath, docid)
            if self.save_gazette(relurl, gzurl, newmeta, cookiefile = cookiejar):
                dls.append(relurl)

        return dls
