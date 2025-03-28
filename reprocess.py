import sys
import logging
import argparse
from pathlib import Path

import internetarchive as ia

import gdrive
from srcs.datasrcs_info import srcinfos, get_prefix
from utils import ext_ops

def get_enabled_srcnames():
    return [ k for k,v in srcinfos.items() if v.get('enabled', True) ]

def setup_logging(loglevel):
    leveldict = {'critical': logging.CRITICAL, 'error': logging.ERROR,
                 'warning' : logging.WARNING,   'info': logging.INFO,
                 'debug'   : logging.DEBUG}

    logfmt  = '%(asctime)s: %(name)s: %(levelname)s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    logging.basicConfig(level   = leveldict[loglevel],
                        format  = logfmt,
                        datefmt = datefmt)

def get_converted_name(name):
    ext = Path(name).suffix
    return name[:-len(ext)] + '.pdf'

def get_ext_map(files):
    ext_map = {}
    for file in files:
        ext = Path(file.name).suffix
        if ext not in ext_map:
            ext_map[ext] = []
        ext_map[ext].append(file)

    return ext_map


UNKWN = 'unkwn'

class IdentifierFileIterator:
    def __init__(self, fname):
        self.file = Path(fname)
        self._num_found = None
        self.id_list = None
        self.logger = logging.getLogger('iditerator')

    @property
    def num_found(self):
        if self._num_found is None:
            if self.id_list is None:
                self.load_id_list()

        self._num_found = len(self.id_list)

        return self._num_found

    def load_id_list(self):
        self.id_list = []
        if not self.file.exists():
            self.logger.warning(f'id list file provided {self.file} is non existent')
            return

        lines = self.file.read_text().split('\n')
        self.id_list = [ line.strip('\n') for line in lines if line.strip('\n') != '' ]

    def __iter__(self):
        if self.id_list is None:
            self.load_id_list()

        for identifier in self.id_list:
            yield { 'identifier': identifier }


class BaseProcess:
    def __init__(self, args, requires_ia_auth=True):
        if requires_ia_auth:
            if args.ia_access_key is None:
                raise Exception('missing ia access key argument')

            if args.ia_secret_key is None:
                raise Exception('missing ia secret key argument')

            self.ia_access_key = args.ia_access_key
            self.ia_secret_key = args.ia_secret_key

        self.base_working_dir = Path(args.datadir) / 'working' / args.process / args.srcname

    def get_working_dir(self, identifier):
        return self.base_working_dir / identifier

    def download(self, ia_file):
        working_dir = self.get_working_dir(ia_file.identifier)
        file = working_dir / ia_file.name

        working_dir.mkdir(exist_ok=True, parents=True)

        ia_file.download(str(file))
        return file

    def upload(self, file):
        identifier = file.parent.name
        self.logger.info(f'uploading file {file} to {identifier}')
        ia.upload(identifier, str(file),
                  access_key = self.ia_access_key,
                  secret_key = self.ia_secret_key)

    def delete(self, ia_file):
        self.logger.info(f'deleting file {ia_file.name} of {ia_file.identifier}')
        ia_file.delete(access_key=self.ia_access_key,
                       secret_key=self.ia_secret_key)

class ExtensionChecker(BaseProcess):
    def __init__(self, args):
        BaseProcess.__init__(self, args, requires_ia_auth=False)
        self.logger = logging.getLogger('extensionchecker')

    def process(self, item):
        files = item.get_files()
        originals = []
        all_names = set()
        for file in files:
            all_names.add(file.name)
            if file.source == 'original' and not \
               file.name.endswith('.xml') and \
               file.format not in ['Metadata', 'Item Tile']:
                originals.append(file)

        ext_map = get_ext_map(originals)

        unexpected = []
        for ext, files in ext_map.items():
            if ext not in [ '.pdf', '.doc', '.rtf', '.png', '.xls' ]:
                unexpected.extend([f.name for f in files])

        unexpected = [ f for f in unexpected if get_converted_name(f) not in all_names ]
        if len(unexpected) == 0:
            return False
        
        raise Exception(f'{unexpected}')

class DeleterByExtension(BaseProcess):
    def __init__(self, args):
        BaseProcess.__init__(self, args)
        self.logger = logging.getLogger('deleterbyextension')

        self.minsize = args.size_to_delete 
        if self.minsize is not None:
            self.minsize = int(self.minsize)

        if args.ext_to_delete is None:
            raise Exception('need ext-to-delete argument')
        self.ext = args.ext_to_delete

        self.minsize = args.size_to_delete

        if args.ext_to_delete is None:
            raise Exception('need ext-to-delete argument')
        self.ext = args.ext_to_delete

    def process(self, item):
        files = item.get_files()
        originals = []
        all_names = set()
        for file in files:
            all_names.add(file.name)
            if file.source == 'original' and not \
               file.name.endswith('.xml') and \
               file.format not in ['Metadata', 'Item Tile']:
                originals.append(file)

        ext_map = get_ext_map(originals)

        interested = []
        for ext, files in ext_map.items():
            if ext == self.ext:
                interested.extend(files)

        interested = [ f for f in interested if self.minsize is None or f.size <= self.minsize ]

        if len(interested) == 0:
            return False

        for file in interested:
            self.delete(file)

        return True
        

class ExtensionFixer(BaseProcess):
    def __init__(self, args):
        BaseProcess.__init__(self, args)
        self.logger = logging.getLogger('extensionfixer')


    def fix_ext(self, orig_file, ia_file):
        orig_name = str(orig_file)
        new_ext = ext_ops.get_file_extension(orig_file.read_bytes())
        if new_ext == UNKWN:
            raise Exception('couldnt determine file extension')
        new_name  = orig_name[:-len(UNKWN)] + new_ext

        new_file  = Path(new_name)
        orig_file.rename(new_file)

        self.upload(new_file)
        self.delete(ia_file)
        return new_file

    def process(self, item):
        files = item.get_files()
        originals = []
        all_names = set()
        for file in files:
            all_names.add(file.name)
            if file.source == 'original' and not \
               file.name.endswith('.xml') and \
               file.format not in ['Metadata', 'Item Tile']:
                originals.append(file)

        not_expected = [ f 
                         for f in originals
                         if f.name.endswith(f'.{UNKWN}') ]

        self.logger.info(f'{not_expected}')
        if len(not_expected) == 0:
            return False

        for ia_file in not_expected:
            orig_file = self.download(ia_file)
            new_file = self.fix_ext(orig_file, ia_file)
            new_file.unlink()
        
        
        working_dir = self.get_working_dir(item.identifier)
        working_dir.rmdir()
        return True



class DocConvertor(BaseProcess):
    def __init__(self, args):
        BaseProcess.__init__(self, args)
        self.logger = logging.getLogger('docconvertor')

        cred_file = args.gdrive_cred_file
        if cred_file is None:
            raise Exception('Gdrive credential file was not provided')

        if not Path(cred_file).exists():
            raise Exception(f'Gdrive credential file provided {cred_file} doesn\'t exist') 

        refresh_file = args.gdrive_refresh_file
        if refresh_file is None:
            raise Exception('Gdrive refresh token file location was not provided') 

        if not Path(refresh_file).exists():
            self.logger.warning(f'Gdrive refresh token file provided {refresh_file} doesn\'t exist.. you might be prompted to authorize') 

        self.gdriveobj = gdrive.GDriveConverter(cred_file, refresh_file)

    def convert_to_pdf(self, orig_file):
        orig_bytes = orig_file.read_bytes()
        pdf_bytes = self.gdriveobj.convert_to_pdf(orig_bytes)

        orig_name = str(orig_file)
        pdf_name = get_converted_name(orig_name)

        pdf_file = Path(pdf_name)
        pdf_file.write_bytes(pdf_bytes)

        return pdf_file

    def fix_ext(self, orig_file, ia_file):
        new_ext = ext_ops.get_file_extension(orig_file)
        orig_name = str(orig_file)
        new_name  = orig_name[:-len(UNKWN)] + new_ext

        new_file  = Path(new_name)
        orig_file.rename(new_file)

        self.upload(new_file)
        self.delete(ia_file)
        return new_file

    def process(self, item):
        files = item.get_files()
        originals = []
        all_names = set()
        for file in files:
            all_names.add(file.name)
            if file.source == 'original' and not \
               file.name.endswith('.xml') and \
               file.format not in ['Metadata', 'Item Tile']:
                originals.append(file)

        not_expected = [ f 
                         for f in originals
                         if not f.name.endswith('.pdf') and
                         get_converted_name(f.name) not in all_names ]

        self.logger.info(f'{not_expected}')
        if len(not_expected) == 0:
            return False

        for ia_file in not_expected:
            orig_file = self.download(ia_file)

            pdf_file = self.convert_to_pdf(orig_file)
            self.upload(pdf_file)
            pdf_file.unlink()
            orig_file.unlink()
        
        
        working_dir = self.get_working_dir(item.identifier)
        working_dir.rmdir()
        return True
        

class Reprocessor:
    def __init__(self, args):
        self.srcname = args.srcname
        self.datadir = args.datadir
        self.process = args.process
        self.ia_access_key = args.ia_access_key
        self.ia_secret_key = args.ia_secret_key
        
        self.logger = logging.getLogger('reprocessor')

        self.processor = self.get_processor(args)

        if self.processor is None:
            return
        
        self.id_list_file = args.id_list_file

    def get_processor(self, args):
        processor = None
        try:
            if self.process == 'convertdocs':
                processor = DocConvertor(args)
            elif self.process == 'fix-unkwn-extensions':
                processor = ExtensionFixer(args)
            elif self.process == 'check-extensions':
                processor = ExtensionChecker(args)
            elif self.process == 'delete-by-extension':
                processor = DeleterByExtension(args)
            else: # more to be added later
                self.logger.error(f'Unsupported process: {self.process}')
        except Exception:
            self.logger.error('Failed to initialize processor')

        return processor

    def get_iterator(self):
        if self.id_list_file is not None:
            return IdentifierFileIterator(self.id_list_file)

        prefix = get_prefix(self.srcname) 
        return ia.search_items(f'identifier:{prefix}*')


    def get_status_dir(self):
        return Path(self.datadir) / 'working' / self.process / self.srcname

    def get_done_file(self):
        return self.get_status_dir() / 'done.txt'

    def get_error_file(self):
        return self.get_status_dir() / 'error.txt'

    def get_upadated_file(self):
        return self.get_status_dir() / 'updated.txt'

    def load_doneset(self):
        doneset = set()

        done_file = self.get_done_file()

        if not done_file.exists():
            return doneset

        ids = done_file.read_text().split('\n')
        ids = [ i.strip() for i in ids if i.strip('\n') != '' ]

        doneset.update(ids)

        return doneset

    def append_to_file(delf, file, identifier):
        file.parent.mkdir(exist_ok=True, parents=True)
        
        with open(file, 'a') as f:
            f.write(identifier)
            f.write('\n')

    def mark_as_processed(self, identifier):
        done_file = self.get_done_file()
        self.append_to_file(done_file, identifier)

    def mark_as_error(self, identifier):
        error_file = self.get_error_file()
        self.append_to_file(error_file, identifier)

    def mark_as_updated(self, identifier):
        updated_file = self.get_upadated_file()
        self.append_to_file(updated_file, identifier)

    def run(self):
        count = 0
        processed_count = 0
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        self.get_upadated_file().unlink(missing_ok=True)
        self.get_error_file().unlink(missing_ok=True)

        doneset = self.load_doneset()

        self.logger.info(f'Already done: {len(doneset)}')

        iter = self.get_iterator()

        total_count = iter.num_found
        for result in iter:
            count += 1
            identifier = result.get('identifier', None)
            if identifier in doneset:
                skipped_count += 1
                if count >= total_count:
                    break
                continue

            item = ia.get_item(identifier)
            try:
                self.logger.info(f'processing {identifier=} - ' +
                                 f'{count=} {processed_count=} {updated_count=} ' +
                                 f'{error_count=} {skipped_count=} {total_count=}')
                updated = self.processor.process(item)
                if updated:
                    self.mark_as_updated(identifier)
                    updated_count += 1
                processed_count += 1
                self.mark_as_processed(identifier)
            except Exception as ex:
                self.logger.error(f'Unable to process item with {identifier=}, ex: {ex}')
                self.mark_as_error(identifier)
                error_count += 1

            # iterator breaks weirdly when there is more data than the intial count
            # so break out voluntarily
            if count >= total_count:
                break



if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Tool to convert docx/rtf files in IA to pdfs')

    parser.add_argument('-l', '--log-level', default='info', required=False,
                        choices=['debug', 'info', 'warning', 'error', 'critical'],
                        help='logging level')    

    parser.add_argument('-p', '--process', default='check-extensions',
                        choices=['convertdocs', 'fix-unkwn-extensions', 'check-extensions',
                                 'delete-by-extension'],
                        help='process to run')

    parser.add_argument('-s', '--source', dest='srcname', action='store',
                        required=True, choices=get_enabled_srcnames(),
                        help='source to process')

    parser.add_argument('-f', '--identifier-list-file', dest='id_list_file', action='store',
                        required=False, default=None,
                        help='file containing list of ids to reprocess')

    parser.add_argument('-d', '--data-dir', dest='datadir',
                        required=True, action='store', 
                        help='data-dir for storing files and status')

    parser.add_argument('-a', '--ia-access-key', dest='ia_access_key', action='store',
                        required=False, default=None,
                        help='access key for internet archive, only required for editing IA')

    parser.add_argument('-k', '--ia-secret-key', dest='ia_secret_key', action='store',
                        required=False, default=None,
                        help='secret key for internet archive, only required for editing IA')

    parser.add_argument('-c', '--gdrive-credentials-file', dest='gdrive_cred_file', action='store',
                        required=False, default=None,
                        help='credentials file for gdrive auth. "convertdocs" process specific')

    parser.add_argument('-r', '--gdrive-refresh-token-file', action='store',
                        dest='gdrive_refresh_file', required=False, default=None,
                        help='refresh token file for gdrive auth. "convertdocs" process specific')

    parser.add_argument('--ext-to-delete', required=False, default=None,
                        help='the extension of the files to delete, "delete-by-extension" specific')

    parser.add_argument('--size-to-delete', required=False, default=None,
                        help='min size of the files to delete, "delete-by-extension" specific')

    args = parser.parse_args()

    setup_logging(args.log_level)

    reprocessor = Reprocessor(args)

    if reprocessor.processor is None:
        sys.exit(1)

    reprocessor.run()
                


