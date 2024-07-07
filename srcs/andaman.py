from http.cookiejar import CookieJar
import urllib.request, urllib.parse, urllib.error
import re
import os
import ssl
import datetime
import json

from .basegazette import BaseGazette
from ..utils import utils

class Andaman(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.hostname   = 'andssw1.and.nic.in'
        self.baseurl    = 'http://andssw1.and.nic.in/doip/index.php/home/srchgazette'
        self.posturl    = 'http://andssw1.and.nic.in/doip/index.php/fetch/srchgazette'
        self.gzurl      = 'http://andssw1.and.nic.in/doip/uploads/gazette/s/{}.pdf'
        self.start_date = datetime.datetime(1996, 1, 1)
        self.end_date   = datetime.datetime(2018, 3, 12)


    def encode_multiform_post(self, postdata):
        boundary = "----WebKitFormBoundaryecDC0QcQWcBRoF9a"
        payload = ''
        for key, value in postdata:
            payload += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
        payload += f'--{boundary}--'
        headers = { 'Content-Type': f'multipart/form-data; boundary={boundary}' }
        return payload.encode('utf-8'), headers

    def get_results(self, url, postdata, cookiejar, referer, dateobj):
        postdata_encoded, headers = self.encode_multiform_post(postdata)
        headers.update({
            'X-Requested-With': 'XMLHttpRequest',
        })

        response = self.download_url(url, postdata = postdata_encoded, \
                                     loadcookies = cookiejar, encodepost = False, \
                                     headers = headers, referer = referer)
        if not response or not response.webpage:
            self.logger.warning('Could not get response for %s for %s', url, dateobj)
            return None

        try:
            data = json.loads(response.webpage)
        except Exception as e:
            self.logger.warning('Unable to parse response for %s for %s', url, dateobj)
            return None

        return data

    def get_post_data(self, tags, dateobj): 
        postdata = []
        datestr = dateobj.strftime('%d-%m-%Y')

        for tag in tags:
            name  = None
            value = None

            if tag.name == 'input':
                name  = tag.get('name')
                value = tag.get('value')
                t     = tag.get('type')

                if t == 'button':
                    continue
                if name == 'txtfromdate' or name == 'txttodate':
                    value = datestr
            elif tag.name == 'select':        
                name  = tag.get('name')
                if name in ['ddcat', 'dddept']:
                    value = '0'
            if name:
                if value == None:
                    value = ''
                postdata.append((name, value))

        return postdata


    def get_form_data(self, webpage, dateobj):
        d = utils.parse_webpage(webpage, self.parser)
        if d == None:
            self.logger.warning('Could not parse page for %s', dateobj)
            return None

        search_form = d.find('form', {'action': self.baseurl})
        if search_form == None:
            self.logger.warning('Could not find search form for %s', dateobj)
            return None

        reobj  = re.compile('^(input|select)$')
        inputs = search_form.find_all(reobj)
        postdata = self.get_post_data(inputs, dateobj)

        return postdata

    def get_metainfos(self, result_data, dateobj):
        metainfos = []

        for result in result_data:
            metainfo = utils.MetaInfo()
            metainfo.set_date(dateobj)

            for k,v in result.items():
                result[k] = v.replace('&amp;','&')

            cattype = result['cattype1']
            if cattype == 'EXTRA ORDINARY GAZETTE':
                metainfo.set_gztype('Extraordinary')
            else:
                metainfo.set_gztype('Ordinary')

            metainfo['id']               = result['id'] 
            metainfo['subject']          = result['subject']
            metainfo['department']       = result['deptname']
            metainfo['notification_num'] = result['fileno']
            metainfo['registry_num']     = result['registryno']
            metainfo['ref_num']          = result['refnum']
            metainfo['ref_type']         = result['reftype1']
            metainfo['keywords']         = [result['keyword1'], result['keyword2'], result['keyword3']]
            metainfo['issdocavailable']  = result['issdocavailable']

            metainfos.append(metainfo)

        return metainfos

    def download_metainfo(self, relpath, metainfo): 

        if metainfo['issdocavailable'] == '2':
            return None

        refnum = metainfo['ref_num']
        fileno = metainfo['notification_num']
        if refnum in ['Tester', 'Hackerone', 'testing']:
            return None
        if fileno in ['Tester', 'Hackerone', 'testing', 'dafdsff4554353']:
            return None

        docid = metainfo.pop('id')

        gzurl  = self.gzurl.format(docid)
        relurl = os.path.join(relpath, docid)

        if self.save_gazette(relurl, gzurl, metainfo):
            return relurl

        return None

    def download_oneday(self, relpath, dateobj):
        dls = []

        cookiejar = CookieJar()

        response = self.download_url(self.baseurl, savecookies = cookiejar)
        if not response or not response.webpage:
            self.logger.warning('Could not get response for %s for %s', self.baseurl, dateobj)
            return dls

        postdata = self.get_form_data(response.webpage, dateobj)
        if postdata == None:
            return dls

        result_data = self.get_results(self.posturl, postdata, cookiejar, self.baseurl, dateobj)
        if result_data == None:
            self.logger.warning('Unable to get results data for %s', dateobj)
            return dls

        metainfos = self.get_metainfos(result_data, dateobj) 

        for metainfo in metainfos:
            relurl = self.download_metainfo(relpath, metainfo)
            if relurl != None:
                dls.append(relurl)

        return dls


