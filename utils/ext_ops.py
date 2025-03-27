import re
import magic

def get_file_type(filepath):
    mtype = magic.from_file(filepath, mime = True)

    return mtype

def get_buffer_type(buff):
    mtype = magic.from_buffer(buff, mime=True)

    return mtype


def get_extension(mtype):
    if re.match('text/html', mtype):
        return 'html'
    elif re.match('application/postscript', mtype):
        return 'ps'
    elif re.match('application/pdf', mtype):
        return 'pdf'
    elif re.match('text/plain', mtype):
        return 'txt'
    elif re.match('image/png', mtype):
        return 'png'
    elif re.match('application/msword', mtype):
        return 'doc'
    elif re.match('text/rtf', mtype):
        return 'rtf'
    elif re.match('application/vnd.ms-excel', mtype):
        return 'xls'
    return 'unkwn'

def get_file_extension(doc):
    mtype = get_buffer_type(doc)
    return get_extension(mtype)

