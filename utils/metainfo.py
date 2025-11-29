import re

URL        = 'url'
HREF       = 'href'
TITLE      = 'title'
DATE       = 'date'
MINISTRY   = 'ministry'
SUBJECT    = 'subject'
GZTYPE     = 'gztype'

_illegal_xml_chars_RE = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]')

def replace_xml_illegal_chars(val, replacement=' '):
    """Filter out characters that are illegal in XML."""

    return _illegal_xml_chars_RE.sub(replacement, val)

class MetaInfo(dict):
    def __init__(self):
        dict.__init__(self)

    def copy(self):
        m = MetaInfo()
        for k, v in self.items():
            m[k] = v
        return m
 
    def set_field(self, field, value):
        if type(value) in (str,):
            value = replace_xml_illegal_chars(value)
        self.__setitem__(field, value)

    def get_field(self, field):
        if field in self:
            return self.get(field)
        return None

    def set_date(self, value):
        self.set_field(DATE, value)

    def set_title(self, value):
        self.set_field(TITLE, value)

    def set_url(self, value):
        self.set_field(URL, value)

    def set_href(self, value):
        self.set_field(HREF, value)

    def set_subject(self, value):
        self.set_field(SUBJECT, value)

    def set_ministry(self, value):
        self.set_field(MINISTRY, value)

    def set_gztype(self, value):
        self.set_field(GZTYPE, value)

    def get_url(self):
        return self.get_field(URL)

    def get_href(self):
        return self.get_field(HREF)

    def get_title(self):
        return self.get_field(TITLE)

    def get_date(self):
        return self.get_field(DATE)

    def get_ministry(self):
        return self.get_field(MINISTRY)

    def get_subject(self):
        return self.get_field(SUBJECT)

    def get_gztype(self):
        return self.get_field(GZTYPE)

    def add_desc_recursive(self, k, v, desc):
        if type(v) in (str,):
            v = v.strip()
            if v:
                desc.append((k.title(), v))
            return

        if type(v) in (list,):
            for i,vitem in enumerate(v):
                self.add_desc_recursive(f'{k.title()}.{i+1}', vitem, desc)
            return

        if type(v) in (dict,):
            for kv,vv in v.items():
                self.add_desc_recursive(f'{k.title()}.{kv.title()}', vv, desc)
            return

        if v:
            desc.append((k.title(), v))

    def get_ia_goir_description(self, srcinfo):
        desc = []

        keys = [ \
          ('gotype',      'Order Type'),  \
          ('gonum',       'Order Number'), \
          ('date',        'Date'), \
          ('department',  'Department'), \
          ('category',    'Category'), \
          ('section',     'Section'), \
          ('url',         'Order Source'), \
          ('abstract',    'Abstract'), \
        ]

        member_keys = set(self.keys())
        for k, kdesc in keys:
             if k not in member_keys:
                 continue

             v = self.get(k)
             if k == 'date':
                 v = f'{v}'
             elif k == 'url':
                v = f'<a href="{v}">URL</a>'
             else:    
                 v = self.get(k).strip()
                 
             if v:
                 desc.append((kdesc, v))

        known_keys = set([k for k, kdesc in keys])

        for k, v in self.items():
            if k not in known_keys:
                self.add_desc_recursive(k, v, desc)

        # style copied from orgpedia's MaharashtraGRs
        header = f'<b>{srcinfo["category"]}</b><br><br>'

        def get_row(d):
            key_cell = f'<td style="vertical-align: top"><b>{d[0]}: </b></td>'
            val_cell = f'<td style="vertical-align: bottom">{d[1]}</td>'
            return f'<tr>{key_cell} {val_cell}</tr>'

        rows_html = '\n'.join([get_row(d) for d in desc])

        return f'{header}<p><table>\n{rows_html}\n</table></p>'


    def get_ia_goir_title(self, srcinfo):
        category = srcinfo['category']
        title = [category]

        date = self.get('date', None)
        if date is not None:
            title.append(f'{date}')

        department = self.get('department', None)
        if department is not None:
            title.append(department.title())

        gotype = self.get('gotype', None)
        if gotype is not None:
            title.append(gotype.title())

        gonum = self.get('gonum', None)
        if gonum is not None:
            title.append(f'Number {gonum}')

        return ', '.join(title)


    def get_ia_gazette_description(self):
        desc = []

        ignore_keys  = set(['linknames', 'links', 'linkids', 'rawtext'])
        keys = [ \
          ('gztype',           'Gazette Type'),  \
          ('gznum',            'Gazette Number'), \
          ('date',             'Date'), \
          ('ministry',         'Ministry'),   \
          ('department',       'Department'), \
          ('subject',          'Subject'),      \
          ('office',           'Office'), \
          ('notification_num', 'Notification Number'), \
          ('registry_num',     'Registry Number'), \
          ('volume_num',       'Volume Number'), \
          ('series_num',       'Series Number'), \
          ('issuenum',         'Issue Number'), \
          ('partnum',          'Part Number'), \
          ('refnum',           'Reference Number'), \
          ('ref_type',         'Reference Type'), \
          ('linknames',        'Gazette Links'), \
          ('url',              'Gazette Source'), \
          ('upload_date',      'Upload Date'), \
          ('issuedate',        'Issue Date'), \
          ('notification_date','Notification Date'), \
          ('num',              'Number'), \
          ('document_type',    'Document Type'), \
          ('gazetteid',        'Gazette ID'), \
          ('govtpress',        'Government Press'), \
        ]

        member_keys = set(self.keys())
        for k, kdesc in keys:
             if k not in member_keys:
                 continue

             v = self.get(k)
             if k == 'date':
                 v = f'{v}'
             elif k == 'linknames':
                 linkids = self.get('linkids')
                 i = 0
                 v = []
                 for linkname in self.get(k):
                     identifier = linkids[i]
                     v.append(f'<a href="/details/{identifier}">{linkname}</a>')
                     i += 1
                 v = '<br/>'.join(v)
                 if v:
                     v = '<br/>' + v
             elif k == 'url':
                 v = f'<a href="{v}">URL</a>'
             else:    
                 v = self.get(k).strip()
                 
             if v:
                 desc.append((kdesc, v))

        known_keys = set([k for k, kdesc in keys])

        for k, v in self.items():
            if k not in known_keys and k not in ignore_keys:
                self.add_desc_recursive(k, v, desc)

        desc_html = '<br/>'.join([f'{d[0]}: {d[1]}' for d in desc])
        return f'<p>{desc_html}</p>'

    def get_ia_description(self, srctype, srcinfo):
        if srctype == 'gazette':
            return self.get_ia_gazette_description()

        return self.get_ia_goir_description(srcinfo)

    def get_ia_gazette_title(self, srcinfo):
        # If title field exists, use it directly
        custom_title = self.get('title', None)
        if custom_title is not None:
            return custom_title
        
        category = srcinfo['category']
        title = [category]

        date = self.get('date', None)
        if date is not None:
            title.append(f'{date}')
        else:
            year = self.get('year', None)
            if year is not None:
                title.append(f'{year}')

        gztype = self.get('gztype', None)
        if gztype is not None:
            title.append(gztype)

        volume_num = self.get('volume_num', None)
        if volume_num is not None:
            title.append(f'Volume {volume_num}')

        series_num = self.get('series_num', None)
        if series_num is not None:
            title.append(f'Series {series_num}')

        partnum = self.get('partnum', None)
        if partnum is not None:
            if re.search(r'\bPart\b', partnum, flags=re.IGNORECASE):
                title.append(partnum)
            else:    
                title.append(f'Part {partnum}')

        gznum = self.get('gznum', None)
        if gznum is not None:
            title.append(f'Number {gznum}')

        return ', '.join(title)

    def get_ia_title(self, srctype, srcinfo):
        if srctype == 'gazette':
            return self.get_ia_gazette_title(srcinfo)

        return self.get_ia_goir_title(srcinfo)

    def get_ia_metadata(self, srcinfo, to_sandbox):
        creator   = srcinfo['source']
        category  = srcinfo['category']
        languages = srcinfo['languages']
        srctype   = srcinfo.get('type', 'gazette')

        if to_sandbox:
            collection = 'test_collection'
        else:
            collection = srcinfo.get('collection', 'gazetteofindia')

        title = self.get_ia_title(srctype, srcinfo)

        metadata = { \
            'mediatype' : 'texts', 'language' : languages, \
            'title'     : title,   'creator'  : creator, \
            'subject'   : category
        }

        if collection != '':
            metadata['collection'] = collection

        dateobj = self.get_date()
        if dateobj:
            metadata['date'] = f'{dateobj}'
        else:
            year = self.get('year', None)
            if year is not None:
                metadata['date'] = f'{year}'
        
        metadata['description'] = self.get_ia_description(srctype, srcinfo)

        return metadata

