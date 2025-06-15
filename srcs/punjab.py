import urllib.parse
import re
import os
import json
import base64

from .basegazette import BaseGazette
from ..utils import utils
from ..utils import ext_ops
from ..utils.metainfo import MetaInfo

class Punjab(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.hostname  = 'esarkar.punjab.gov.in'
        self.searchurl = 'http://esarkar.punjab.gov.in/web/guest/customepage?p_p_id=guestPortlet&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1&requestType=ApplicationRH&actionVal=searchRecord&queryType=Select&screenId=400176'
       
    def get_post_data(self, dateobj):
        datestr = utils.dateobj_to_str(dateobj, '/')
        postdata = [\
            ('cmb_Cat', '-1'), ('cmb_Name', '-1'), ('cmb_Not_For', '-1'),     \
            ('ComboDept', '-1'), ('eAttachId', ''), ('freetextradio', 'No'),  \
            ('NewSearchFlag', 'false'), ('PriorityName', '--Select--'),       \
            ('refDocId', ''), ('reportEndIndex', '10'),                       \
            ('reportStartIndex', '1'), ('txtEmail', ''), ('txtFreeText', ''), \
            ('txtFrom', datestr), ('txtGazetteNo', ''), ('txtNotNo', ''),     \
            ('txtNotTitle', ''), ('txtTo', datestr), \
        ]
        return postdata
      
    def download_oneday(self, relpath, dateobj):
        dls = []
        postdata = self.get_post_data(dateobj)
        response = self.download_url(self.searchurl, postdata = postdata)

        if not response or not response.webpage:
            self.logger.warning('Could not download search result for date %s', \
                              dateobj)
            return dls
        
        d = utils.parse_webpage(response.webpage, self.parser)
        if not d:
            self.logger.warning('Could not parse search result for date %s', \
                              dateobj)
            return dls
        
        minfos = self.get_metainfos(d, dateobj)
        for metainfo in minfos:
            if 'docid' not in metainfo:
                self.logger.warning('Ignoring metainfo: %s', metainfo)
                continue

            filename = metainfo.pop('docid')
            relurl   = os.path.join(relpath, filename)
            gzurl    = self.get_doc_url(filename)
            if self.save_gazette(relurl, gzurl, metainfo):
                dls.append(relurl)

        return dls        

    def get_metainfos(self, d, dateobj):             
        minfos = []
        tables = d.find_all('table', {'id': 'tblData'})
        if len(tables) == 0:
            self.logger.warning('Could not find the result table for %s', dateobj)
            return minfos

        
        order  = None
        for tr in tables[0].find_all('tr'):   
            if not order:
                order = self.get_field_order(tr)
                continue

            metainfo = self.process_row(tr, order, dateobj)    
            if metainfo:
                minfos.append(metainfo)

        # group metainfo by docid
        docids = {}
        final  = []
        for metainfo in minfos:        
            if 'docid' in metainfo:
                docid = metainfo['docid'] 
                if docid in docids:
                    last = docids[docid]
                    if 'additional' not in last:
                        last['additional']= []
                    metainfo.pop('docid')    
                    last['additional'].append(metainfo)
                else:
                    final.append(metainfo)
                    docids[docid] = metainfo    
        return final

    def get_field_order(self, tr):
        order = []
        for td in tr.find_all('td'):
            txt = utils.get_tag_contents(td)
            if txt and re.search(r'Department', txt):
                order.append('department')
            elif txt and re.search(r'Notification\s+No', txt):
                order.append('notification_num')
            elif txt and re.search(r'Subject', txt):
                order.append('subject')
            elif txt and re.search(r'Notification\s+For', txt):
                order.append('notification_type')
            elif txt and re.search(r'Gazette\s+No', txt):
                order.append('gznum')
            elif txt and re.search(r'Type', txt):
                order.append('gztype')
            elif txt and re.search(r'Category', txt):
                order.append('category')
            elif txt and re.search(r'Detail', txt):
                order.append('download')
            else:    
                order.append('')

        return order
    
    def get_doc_url(self, docid):
        href = '/web/guest/customepage?p_p_id=guestPortlet&p_p_lifecycle=1&p_p_state=exclusive&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1&requestType=ApplicationRH&actionVal=openAttachmentFile&queryType=Select&screenId=400176&refDocId=%s' % docid 
        return urllib.parse.urljoin(self.searchurl, href)

    def process_row(self, tr, order, dateobj):
        metainfo = MetaInfo()
        metainfo.set_date(dateobj)
        i = 0
        for td in tr.find_all('td'):
            if len(order) > i:
                if order[i] in ['department', 'notification_num', 'subject', \
                            'notification_type', 'gznum', 'gztype', 'category']:
                    txt = utils.get_tag_contents(td)
                    metainfo[order[i]] = txt
                elif order[i] == 'download':
                    link = td.find('a')
                    if link and link.get('onclick'):
                        onclick = link.get('onclick')
                        reobj   = re.search(r'\d+', onclick) 
                        if reobj:
                            metainfo['docid'] = onclick[reobj.start():reobj.end()]
            i += 1           
        return metainfo   


class PunjabDSA(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.hostname  = 'dsa.punjab.gov.in'
        self.baseurl = 'https://dsa.punjab.gov.in'
        self.dateurl = urllib.parse.urljoin(self.baseurl, '/egazette/api/Final/FinalFilter')
        self.gzurl   = urllib.parse.urljoin(self.baseurl, '/egazette/api/Final/Output_Copy')

    def get_post_data(self, dateobj):
        datestr = utils.dateobj_to_str(dateobj, '-', reverse=True)
        postdata = "{'fromdate': '%s', 'todate': '%s'}" % (datestr, datestr)
        return postdata.encode('utf-8')

    def get_metainfo(self, d, dateobj):
        metainfo = MetaInfo()
        metainfo.set_date(dateobj)

        if 'Request_Id' in d:
            metainfo['Request_Id'] = d['Request_Id']
        
        if 'Dept_Name' in d:
            metainfo.set_field('department', d['Dept_Name'])
           
        if 'Gazette_Type_Name' in d:
            metainfo.set_gztype(d['Gazette_Type_Name'])

        if 'Gazette_Number' in d:
            metainfo.set_field('gazetteid', d['Gazette_Number'])

        if 'Notification_Number' in d:
            metainfo.set_field('notification_num', d['Notification_Number'])

        if 'Notification_Title' in d:
            metainfo.set_title(d['Notification_Title'])

        return metainfo

    def pull_gazette(self, gurl, referer = None, postdata = None,
                     cookiefile = None, headers = {}, \
                     encodepost = True):

        response = BaseGazette.pull_gazette(self, gurl, referer = referer, postdata = postdata,
                                            cookiefile = cookiefile, headers = headers,
                                            encodepost = encodepost)

        if response is None or response.webpage is None:
            return None

        try:
            x = json.loads(response.webpage)
        except Exception:
            self.logger.warning('Error in parsing json on the request')
            return None

        if 'data' in x and len(x['data']) > 0 and 'Output_File' in x['data'][0]:
            try:
                doc = base64.b64decode(x['data'][0]['Output_File'])
                response.webpage = doc
            except Exception:
                return None
        else:
            return None

        return response

    def download_gazette(self, relpath, metainfo):
        if 'Request_Id' not in metainfo:
            return None

        request_id = metainfo.pop('Request_Id')
        relurl = os.path.join(relpath, request_id)

        postdata = '{"Request_Id":"%s"}' % request_id
        postdata =  postdata.encode('utf-8')
        accept_hdr = {'Content-Type': 'application/json'}

        gurl = self.gzurl
        if self.save_gazette(relurl, gurl, metainfo, postdata = postdata, \
                             encodepost = False, hdrs = accept_hdr, \
                             validurl = False):
            return relurl

        return None
 
    def is_valid_gazette(self, doc, min_size):
        mtype = ext_ops.get_buffer_type(doc)

        if mtype != 'application/pdf':
            return False

        return BaseGazette.is_valid_gazette(self, doc, min_size)

    def download_oneday(self, relpath, dateobj):
        dls = []
        postdata = self.get_post_data(dateobj)
        accept_hdr = {'Content-Type': 'application/json'}
        response = self.download_url(self.dateurl, postdata = postdata, \
                                     encodepost = False, headers= accept_hdr)

        if not response or not response.webpage:
            self.logger.warning('Could not download search result for date %s', \
                              dateobj)
            return dls

        try:
            x = json.loads(response.webpage)
        except Exception:
            self.logger.warning('Unable to parse json for %s', dateobj)
            return dls


        for d in x['data']:
            metainfo =  self.get_metainfo(d, dateobj)
            if metainfo:
                relurl =  self.download_gazette(relpath, metainfo)
                if relurl:
                    dls.append(relurl) 
        return dls

           
