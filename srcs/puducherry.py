import re
import os
import urllib.request, urllib.parse, urllib.error
import datetime

from ..utils import utils
from .basegazette import BaseGazette

class Puducherry(BaseGazette):
    def __init__(self, name, storage):
        BaseGazette.__init__(self, name, storage)
        self.baseurl  = 'https://styandptg.py.gov.in/{}/{}{}{}.{}'
        self.hostname = 'styandptg.py.gov.in'
        self.start_date = datetime.datetime(2012, 1, 1)

    def find_field_order(self, tr):
        order  = []
        for td in tr.find_all(['th', 'td']):
            txt = utils.get_tag_contents(td)
            if txt and re.search('Date\s+of\s+Issue', txt):
                order.append('issuedate')
            elif txt and re.search('(Contents|Subject|supplement\s+with\s+Gazette)', txt):
                order.append('contents')
            elif txt and re.search('Issue\s+', txt):
                order.append('issuenum')
            else:
                order.append('')    
        
        for field in ['issuedate', 'issuenum', 'contents']:
            if field not in order:
                return None
        return order
 
    def process_row(self, tr, order, dateobj):
        metainfo = utils.MetaInfo()

        i = 0
        issuedate = None
        for td in tr.find_all(['th', 'td']):
            if len(order) > i:
                txt = utils.get_tag_contents(td)
                txt = txt.strip()
                if order[i] == 'issuenum':
                    metainfo[order[i]] = txt
                elif order[i] == 'issuedate':
                    metainfo['issuedate'] = td
                    reobj = re.search('(?P<day>\d+)(\.|/)(?P<month>\d+)(\.|/)(?P<year>\d+)', txt)
                    if reobj:
                        groupdict = reobj.groupdict()
                        try:
                            year = int(groupdict['year'])
                            if year < 2000:
                                year += 2000
                            issuedate = datetime.datetime(year, int(groupdict['month']), int(groupdict['day'])).date()
                        except:
                            pass
                    if issuedate == None:
                        self.logger.warning('Unable to parse date string %s', txt)
                elif order[i] == 'contents':
                    metainfo['contents'] = td
            i += 1

        for k in ['issuenum', 'issuedate', 'contents']:
            if k not in metainfo:
                return None

        if issuedate == None or issuedate != dateobj:
            return None

        metainfo.set_date(dateobj)
        return metainfo




    def get_metainfos(self, webpage, dateobj):
        d = utils.parse_webpage(webpage, self.parser) 
        if d == None:
            return None

        result_table = None
        order = None
        for table in d.find_all('table'):
            if table.find('table') != None:
                continue
            if result_table != None:
                break
            for tr in table.find_all('tr'):
                order = self.find_field_order(tr)
                if order:
                    result_table = table
                    break

        if result_table == None:
            print('got no result page')
            return None

        metainfos = []
        for tr in result_table.find_all('tr'):
            if tr.find('a') == None:
                continue
            metainfo = self.process_row(tr, order, dateobj)
            if metainfo:
                metainfos.append(metainfo)
        return metainfos
 
    def download_metainfos(self, relpath, metainfos):
        relurls = []
        for metainfo in metainfos:
            gzurl  = metainfo.pop('download')
            docid  = metainfo.pop('docid')
            relurl = os.path.join(relpath, docid)
            if self.save_gazette(relurl, gzurl, metainfo):
                relurls.append(relurl)
        return relurls

    def clean_string(self, txt):
        txt = txt.replace('\r', ' ')
        txt = txt.replace('\n', ' ')
        txt = ' '.join(txt.split())
        txt = txt.strip()
        return txt

    def drop_colons(self, txt):
        if txt.startswith(':'):
            txt = txt[1:]
        if txt.endswith(':'):
            txt = txt[:-1]
        txt = txt.strip()
        return txt

    def download_oneday(self, relpath, dateobj):
        dls = []
        year    = dateobj.year
        month   = dateobj.strftime('%b').lower()

        section_infos = {
            'Ordinary'         : { 'prefix': 'ordinary',     'gztype': 'Ordinary',      'partnum': None },
            'Supplementary'    : { 'prefix': 'supple',       'gztype': 'Supplementary', 'partnum': None },
            'Extraordinary I'  : { 'prefix': 'exordinary1',  'gztype': 'Extraordinary', 'partnum': 'I'  },
            'Extraordinary II' : { 'prefix': 'exordinaryII', 'gztype': 'Extraordinary', 'partnum': 'II' },
        }
        
        all_metainfos = []
        for section, info in section_infos.items():
            prefix = info['prefix']
            gztype = info['gztype']
            partnum = info['partnum']
            docid_prefix = "-".join(section.lower().split(" "))
            ext = 'html' if year >= 2018 else 'htm'
            url = self.baseurl.format(year, prefix, month, year % 100, ext)
            response = self.download_url(url)
            if not response or not response.webpage:
                self.logger.warning('Unable to get year page %s for date %s', url, dateobj)
                continue

            metainfos = self.get_metainfos(response.webpage, dateobj)
            if metainfos == None:
                self.logger.warning('Unable to parse result page %s for date %s', url, dateobj)
                continue

            for metainfo in metainfos:
                metainfo.set_gztype(gztype)
                if partnum:
                    metainfo['partnum'] = partnum

                contents       = metainfo.pop('contents')
                issuenum       = metainfo['issuenum']
                issuedate_node = metainfo.pop('issuedate')
                issuedate_str  = utils.get_tag_contents(issuedate_node)

                if section == 'Ordinary':
                    for link in contents.find_all('a'):
                        txt = utils.get_tag_contents(link).strip()
                        if txt == '':
                            continue
                        txt = self.clean_string(txt)
                        category = txt
                        reobj = re.search('OG\s+No\.\d+\s+dt\.\d+\.\d+\.\d+', txt)
                        if reobj:
                            category = 'Combined'

                        new_metainfo = utils.MetaInfo()
                        new_metainfo.set_date(metainfo.get_date())
                        new_metainfo.set_gztype('Ordinary')
                        new_metainfo['issuenum'] = issuenum
                        new_metainfo['category'] = category
                        new_metainfo['download'] = urllib.parse.urljoin(url, link.get('href'))

                        category = "-".join(category.lower().split(' '))
                        new_metainfo['docid'] = f'{docid_prefix}-issue-{issuenum}-{category}'

                        all_metainfos.append(new_metainfo)
                elif section == 'Supplementary':
                    link = contents.find('a')
                    metainfo['download'] = urllib.parse.urljoin(url, link.get('href'))

                    full_txt = utils.get_tag_contents(contents)
                    full_txt = self.clean_string(full_txt)

                    strong = contents.find('strong')
                    txt = ''
                    if strong:
                        txt = utils.get_tag_contents(strong)
                        txt = self.clean_string(txt)
                        metainfo['department'] = txt

                    if full_txt.startswith(txt):
                        metainfo['subject'] = full_txt[len(txt):].strip()

                    metainfo['docid'] = f'{docid_prefix}-issue-{issuenum}'

                    all_metainfos.append(metainfo)
                else:
                    link = issuedate_node.find('a')
                    metainfo['download'] = urllib.parse.urljoin(url, link.get('href'))

                    full_txt = utils.get_tag_contents(contents)
                    full_txt = self.clean_string(full_txt)

                    fonts = contents.find_all(['font', 'strong'])
                    txts = [ self.clean_string(utils.get_tag_contents(f)) for f in fonts ]
                    txts = [ t for t in txts if t != '' ]

                    to_remove = ' '.join(txts)
                    if full_txt.startswith(to_remove):
                        metainfo['subject'] = full_txt[len(to_remove):].strip()

                    txts = [ self.drop_colons(txt) for txt in txts ]
                    metainfo['department'] = txts[0]
                    if len(txts) > 1:
                        metainfo['category'] = txts[1]

                    metainfo['docid'] = f'{docid_prefix}-issue-{issuenum}'
                    all_metainfos.append(metainfo)

        relurls = self.download_metainfos(relpath, all_metainfos)
        dls.extend(relurls)

        return dls
