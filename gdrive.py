import io
import json
import string
import random
import logging

from httplib2 import Http
from oauth2client import file, client, tools
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

from utils import ext_ops

def get_random_string(n):
    res = ''.join(random.choices(string.ascii_uppercase +
                                 string.digits, k=n))

    return res

class GDriveConverter:
    def __init__(self, cred_file, refresh_token_file):
        self.service   = None
        self.logger    = logging.getLogger('gdrive.converter')
        self.cred_file = cred_file
        self.refresh_token_file = refresh_token_file

    def get_service(self):
        if self.service is not None:
            return self.service

        SCOPES = 'https://www.googleapis.com/auth/drive'

        store = file.Storage(self.refresh_token_file)
        creds = store.get()
        if not creds or creds.invalid:
            flow = client.flow_from_clientsecrets(self.cred_file, SCOPES)
            creds = tools.run_flow(flow, store)

        self.service = build('drive', 'v3', http=creds.authorize(Http()))

        return self.service

    def export_pdf(self, file_id):
        service = self.get_service()

        request = service.files()\
                         .export_media(
                             fileId   = file_id,
                             mimeType = "application/pdf"
                         )

        file = io.BytesIO()

        downloader = MediaIoBaseDownload(file, request)

        done = False
        while done is False:
            status, done = downloader.next_chunk()
            self.logger.debug(f"Download {int(status.progress() * 100)}.")
    
        return file.getvalue()

    def upload_file(self, content):
        service = self.get_service()

        mimetype = ext_ops.get_buffer_type(content)
        ext = ext_ops.get_extension(mimetype)
        if ext not in ['rtf', 'doc', 'xls']:
            raise Exception(f'Unexpected file extension: {ext=} {mimetype=}')

        fname = get_random_string(7) + '.' + ext

        file_metadata = {
            "name": fname,
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }

        iofile = io.BytesIO(content)
        media = MediaIoBaseUpload(iofile, mimetype=mimetype)

        file = (
            service.files()
                   .create(
                       fields = "id",
                       body   = file_metadata,
                       media_body = media,
                   )
                   .execute()
        )

        return file.get("id")


    def list_files(self):
        service = self.get_service()

        files = service.files()\
                       .list(fields = '*')\
                       .execute().get('files', [])

        print(json.dumps(files))

    def delete_file(self, file_id):
        service = self.get_service()

        # directly deleting doesn't work and I don't understand why
        #resp = service.files().delete(fileId=file_id, supportsAllDrives=True)
    
        change = {'trashed': True}
        service.files().update(fileId = file_id, body = change).execute()

        service.files().emptyTrash().execute()


    def convert_to_pdf(self, from_bytes):

        self.logger.info('uploading file')
        file_id = self.upload_file(from_bytes)

        self.logger.info('exporting file as pdf')
        pdf_content = self.export_pdf(file_id)

        self.logger.info('moving file to trash and emptying it')
        self.delete_file(file_id)

        return pdf_content
