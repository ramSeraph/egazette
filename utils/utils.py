import os
import re
import types
import urllib.parse
import calendar
import datetime
import sys
import calendar
import logging

from xml.parsers.expat import ExpatError
from xml.dom import minidom, Node
from bs4 import BeautifulSoup, NavigableString, Tag

from . import proxylist

def get_proxydict(hostname):
    if hostname in proxylist.hostdict:
        return proxylist.hostdict[hostname]

    if '*' in proxylist.hostdict:
        return proxylist.hostdict['*']
    
    return None

def parse_xml(xmlpage):
    try: 
        d = minidom.parseString(xmlpage)
    except ExpatError:
        d = None
    return d

def get_node_value(xmlNodes):
    value = [] 
    ignoreValues = ['\n']
    for node in xmlNodes:
        if node.nodeType == Node.TEXT_NODE:
            if node.data not in ignoreValues:
                value.append(node.data)
    return ''.join(value)

def remove_spaces(x):
    x, n = re.subn('\s+', ' ', x)
    return x.strip()

def get_selected_option(select):
    option = select.find('option', {'selected': 'selected'})
    if option == None:
        option = select.find('option')

    if option == None:
        return ''

    val = option.get('value')
    if val == None:
        val = ''

    return val

def replace_field(formdata, k, v):
    newdata = []
    for k1, v1 in formdata:
        if k1 == k:
            newdata.append((k1, v))
        else:
            newdata.append((k1, v1))
    return newdata

def remove_fields(postdata, fields):
    newdata = []
    for k, v in postdata:
        if k not in fields:
            newdata.append((k, v))
    return newdata


def find_next_page(el, pagenum):
    nextpage = None

    links = el.findAll('a')

    if len(links) <= 0:
        return None

    for link in links:
        contents = get_tag_contents(link)
        try:
            val = int(contents)
        except ValueError:
            continue

        if val == pagenum + 1 and link.get('href'):
            nextpage = {'href': link.get('href'), 'title': f'{val}'}
            break

    return nextpage


def check_next_page(tr, pagenum):
    links    = tr.findAll('a')

    if len(links) <= 0:
        return False, None

    for link in links:
        contents = get_tag_contents(link)
        if not contents:
            continue
        contents = contents.strip()
        if  not re.match('[\d.]+$', contents):
            return False, None

    pageblock = True
    nextlink  = None

    for link in links:
        contents = get_tag_contents(link)
        try:
            val = int(contents)
        except ValueError:
            continue

        if val == pagenum + 1 and link.get('href'):
            nextlink = {'href': link.get('href'), 'title': '%d' % val}
            break

    return pageblock, nextlink

def month_to_num(month):
    month = month.lower()
    if month in ['frbruary', 'februay']:
        month = 'february'

    count = 0
    for mth in calendar.month_name:
        if mth.lower() == month:
            return count
        count += 1

    count = 0
    for mth in calendar.month_abbr:
        if mth.lower() == month:
            return count
        count += 1

    return None

def to_dateobj(x):
    reobj = re.search('(?P<day>\d+)-(?P<month>jan|feb|mar|apr|may|jun|jul|aug|sep|aug|sep|oct|nov|dec)-(?P<year>\d+)', x, re.IGNORECASE)
    if reobj:
        groupdict = reobj.groupdict()
        month = month_to_num(groupdict['month'])
        day   = int(groupdict['day'])
        year  = int(groupdict['year'])
        return datetime.date(year, month, day)

    return None    

def get_month_num(month, monthnames):
    i = 0
    month = month.lower()
    for m in monthnames:
        if m.lower() == month:
            return i
        i += 1
    return -1
            
def parse_datestr(datestr):
    reobj = re.search('(?P<day>\d+)\s*(?P<month>\w+)\s*(?P<year>\d+)', datestr)
    if reobj:
        groupdict = reobj.groupdict()
        month_num = get_month_num(groupdict['month'], calendar.month_abbr)
        if month_num <= 0:
            return None
        try:
            year = int(groupdict['year'])
            day  = int(groupdict['day'])    
        except:
            return None    
        return datetime.datetime(year, month_num, day)

    return None         

def parse_webpage(webpage, parser):
    try:
        d = BeautifulSoup(webpage, parser)
        return d
    except:
        return None

def get_search_form(webpage, parser, search_endp):
    d = parse_webpage(webpage, parser)
    if d is None:
        return None

    search_form = d.find('form', {'action': search_endp})
    if search_form is None:
        return None 

    return search_form


def url_to_filename(url, catchpath, catchquery):
    htuple = urllib.parse.urlparse(url)
    path   = htuple[2]

    words = []

    if catchpath:
        pathwords = path.split('/')
        words.extend(pathwords)
    
    if catchquery:
        qs = htuple[4].split('&')
        qdict = {}
        for q in qs:
            x = q.split('=')
            if len(x) == 2:
                qdict[x[0]] = x[1]
        for q in catchquery:
            if q in qdict:
                words.append(qdict[q])

    if words:
        wordlist = []
        for word in words:
            word =  word.replace('/', '_')
            word = word.strip()
            wordlist.append(word)
            
        filename = '_'.join(wordlist)
        return filename
    return None

def get_tag_contents(node):
    if type(node) == NavigableString:
        return '%s' % node 

    retval = [] 
    for content in node.contents:
        if type(content) == NavigableString:
            retval.append(content)
        elif type(content) == Tag and content.name not in ['style', 'script']:
            if content.name not in ['span']:
                retval.append(' ')
            retval.append(get_tag_contents(content))

    return ''.join(retval) 

def get_date_from_title(title):
    months =  '|'.join(calendar.month_name[1:]) 
    reobj = re.search(r'(?P<day>\d+)\s*(st|nd|rd|th)\s*(?P<month>%s)\s*(?P<year>\d{4})\b' % months, title, re.IGNORECASE)
    if not reobj:
        return None

    groupdict = reobj.groupdict()

    day    = groupdict['day']
    month  = groupdict['month']
    year   = groupdict['year']

    month_num = get_month_num(groupdict['month'], calendar.month_name)
    if month_num <= 0:
        return None

    try:
        dateobj = datetime.date(int(year), month_num, int (day))
    except:    
        dateobj = None    
    return dateobj
        
def tag_contents_without_recurse(tag):
    contents = []
    for content in tag.contents:
        if type(content) == NavigableString:
            contents.append(content)

    return contents
 
def mk_dir(dirname):
    if not os.path.exists(dirname):
        os.mkdir(dirname)

def pad_zero(t):
    if t < 10:
        tstr = '0%d' % t
    else:
        tstr = '%d' % t

    return tstr

def get_egz_date(dateobj):
    return '%s-%s-%s' % (pad_zero(dateobj.day), calendar.month_abbr[dateobj.month], dateobj.year)

def dateobj_to_str(dateobj, sep, reverse = False):
    if reverse:
        return '%s%s%s%s%s' % (pad_zero(dateobj.year), sep, \
                pad_zero(dateobj.month), sep, pad_zero(dateobj.day))
    else:
        return '%s%s%s%s%s' % (pad_zero(dateobj.day), sep, \
                pad_zero(dateobj.month), sep, pad_zero(dateobj.year))
  

def stats_to_message(stats):
    rawstats  = stats[0]
    metastats = stats[1]

    messagelist = ['Stats on documents']
    messagelist.append('======================')
    courtnames = [x['courtname'] for x in rawstats]
    rawnum     = {x['courtname']: x['num'] for x in rawstats}
    metanum    = {x['courtname']: x['num'] for x in metastats}

    for courtname in courtnames:
        if courtname in metanum:
            meta = metanum[courtname]
        else:
            meta = 0
        messagelist.append('%s\t%s\t%s' % (rawnum[courtname], meta, courtname))
 
    return '\n'.join(messagelist)

def setup_logging(loglevel, logfile):
    leveldict = {'critical': logging.CRITICAL, 'error': logging.ERROR, \
                 'warning': logging.WARNING,   'info': logging.INFO, \
                 'debug': logging.DEBUG}

    logfmt  = '%(asctime)s: %(name)s: %(levelname)s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    if logfile:
        logging.basicConfig(\
            level   = leveldict[loglevel], \
            format  = logfmt, \
            filename = logfile, \
            datefmt = datefmt \
        )
    else:
        logging.basicConfig(\
            level   = leveldict[loglevel], \
            format  = logfmt, \
            datefmt = datefmt \
        )




