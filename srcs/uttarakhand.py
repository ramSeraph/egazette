import os
import json
import urllib.parse
from http.cookiejar import CookieJar
from datetime import datetime

from .basegazette import BaseGazette
from ..utils.metainfo import MetaInfo

class UttarakhandGO(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl     = 'https://go.uk.gov.in/'
        self.base_endp   = 'en/Search/index'
        self.search_endp = 'en/Search/SearchGO'
        self.hostname    = 'go.uk.gov.in'


    def get_postdata(self, dateobj):
        date_str = dateobj.strftime('%Y-%m-%d')
        postdata = {
            'CategoryID': "",
            'DepartmentID': "",
            'GONo': "",
            'SearchText': "",
            'SectionID': "",
            'Subject': "",
            'fromdate': date_str,
            'todate': date_str,
        }
        return json.dumps(postdata).encode('utf8')

    def get_metainfo(self, x, dateobj):
        metainfo = MetaInfo()
        metainfo.set_date(dateobj)

        metainfo['subject']    = x['Subject']
        metainfo['department'] = x['DepartmentNameE']
        metainfo['section']    = x['SectionNameE']
        metainfo['category']   = x['CategoryNameE']
        metainfo['gonum']      = x['GONo']
        metainfo['url']        = x['FilePath']

        metainfo['gotype'] = 'Amendment' if x['G0Type'] == 'A' else 'New'

        if not metainfo['url']:
            metainfo['url'] = x['File_Path_Word']

        return metainfo

    def download_oneday(self, relpath, dateobj):
        dls = []

        cookiejar = CookieJar()
        baseurl   = urllib.parse.urljoin(self.baseurl, self.base_endp)
        response  = self.download_url(baseurl, savecookies = cookiejar)
        if not response or not response.webpage:
            self.logger.warning('Could not get base page for date %s', \
                              dateobj)
            return dls

        searchurl = urllib.parse.urljoin(self.baseurl, self.search_endp)

        postdata = self.get_postdata(dateobj)

        accept_hdr = {'Content-Type': 'application/json'}
        response = self.download_url(searchurl, postdata = postdata, \
                                     encodepost = False, headers=accept_hdr)

        if not response or not response.webpage:
            self.logger.warning('Could not download search result for date %s', \
                                dateobj)
            return dls

        try:
            x = json.loads(response.webpage)
        except Exception:
            self.logger.warning('Unable to parse json for %s', dateobj)
            return dls

        metainfos = []
        for d in x: 
            metainfo = self.get_metainfo(d, dateobj)
            metainfos.append(metainfo)

        for metainfo in metainfos:
            gzurl = metainfo.pop('url')
            gzurl = gzurl.replace('http://', 'https://')
            if not gzurl.startswith('https'):
                gzurl = urllib.parse.urljoin(self.baseurl, gzurl)

            docid = gzurl.split('/')[-1].rsplit('.', 1)[0]
            docid = docid.replace('\\', '-')

            relurl = os.path.join(relpath, docid)   
             
            if self.save_gazette(relurl, gzurl, metainfo):
                dls.append(relurl)

        return dls

class Uttarakhand(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl     = 'https://gazettes.uk.gov.in/'
        self.hostname    = 'gazettes.uk.gov.in'
        self.base_endp   = 'en/Search/index'
        self.search_endp = 'en/Search/SearchGazette'

    def get_postdata(self, dateobj, section):
        date_str = dateobj.strftime('%Y-%m-%d')
        postdata = {
            'BhagID': "",
            'CategoryID': "",
            'DepartmentID': "",
            'EntryType': 2 if section == 'Weekly' else 1,
            'GONo': "",
            'SearchText': "",
            'SectionID': "",
            'Subject': "",
            'WeekDate2': date_str,
            'fromdate': "",
            'todate': "",
        }
        return json.dumps(postdata).encode('utf8')

    def get_metainfo(self, x, section):
        metainfo = MetaInfo()

        def get_val(k):
            hk = f'{k}H'
            ek = f'{k}E'
            v = x[ek]
            if v == '':
                v = x[hk]
            if v is None:
                v = ''
            return v

        metainfo['subject']    = get_val('Subject')
        metainfo['department'] = get_val('DepartmentName')
        metainfo['section']    = get_val('SectionName')
        metainfo['category']   = get_val('CategoryName')
        metainfo['url']        = x['File_Path_PDF']
        metainfo['partnum']    = x['BhagID']
        metainfo['notification_num']  = x['GONO']
        metainfo['notification_date'] = datetime.strptime(x['GoDate2'], '%d-%m-%Y').strftime('%Y-%m-%d')
        metainfo['pageno'] = x['PageNo']
        if section == 'Daily':
            metainfo['gztype'] = 'Extraordinary'

        if not metainfo['url']:
            metainfo['url'] = x['File_Path_Word']

        return metainfo

    def download_onesection(self, dls, relpath, dateobj, section):

        cookiejar = CookieJar()
        baseurl   = urllib.parse.urljoin(self.baseurl, self.base_endp)
        response  = self.download_url(baseurl, savecookies = cookiejar)
        if not response or not response.webpage:
            self.logger.warning('Could not get base page for date %s', \
                              dateobj)
            return dls

        searchurl = urllib.parse.urljoin(self.baseurl, self.search_endp)

        postdata = self.get_postdata(dateobj, section)

        accept_hdr = {'Content-Type': 'application/json'}
        response = self.download_url(searchurl, postdata = postdata, \
                                     encodepost = False, headers=accept_hdr)

        if not response or not response.webpage:
            self.logger.warning('Could not download search result for date %s', \
                                dateobj)
            return dls

        try:
            x = json.loads(response.webpage)
        except Exception:
            self.logger.warning('Unable to parse json for %s', dateobj)
            return dls

        metainfos_by_url = {}
        for d in x: 
            metainfo = self.get_metainfo(d, section)
            url = metainfo.pop('url')
            if url not in metainfos_by_url:
                metainfos_by_url[url] = []
            metainfos_by_url[url].append(metainfo)

        for gzurl, metainfos in metainfos_by_url.items():
            new_meta = MetaInfo()
            new_meta.set_date(dateobj)

            new_meta['notifications'] = []
            for metainfo in metainfos:
                notification = {}
                for k in metainfo.keys():
                    notification[k] = metainfo[k]
                new_meta['notifications'].append(notification)

            gzurl = gzurl.replace('http://', 'https://')
            if not gzurl.startswith('https'):
                gzurl = urllib.parse.urljoin(self.baseurl, gzurl)

            docid = gzurl.split('/')[-1].rsplit('.', 1)[0]
            docid = docid.replace('\\', '-')

            relurl = os.path.join(relpath, docid)   

            if self.save_gazette(relurl, gzurl, new_meta):
                dls.append(relurl)

        return dls

    def download_oneday(self, relpath, dateobj):
        dls = []

        self.download_onesection(dls, relpath, dateobj, section='Daily')
        self.download_onesection(dls, relpath, dateobj, section='Weekly')

        return dls


