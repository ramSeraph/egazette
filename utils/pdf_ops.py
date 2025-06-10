import pymupdf
from collections import defaultdict

def extract_links_from_pdf(fileobj):
    all_links = []

    doc = pymupdf.open(fileobj)
    for page in doc:
        links = [ link.get('file', None) for link in page.get_links() ]
        all_links.extend([ link for link in links if link is not None ])

    return all_links

def convert_to_image_pdf(file_bytes):
    outdoc = pymupdf.open()

    doc = pymupdf.open(stream=file_bytes, filetype='pdf')
    
    for page in doc:

        img_bytes = page.get_pixmap(alpha=False, dpi=300)\
                        .tobytes(output='jpg', jpg_quality=10)

        img           = pymupdf.open(stream=img_bytes, filetype='jpg')
        img_pdf_bytes = img.convert_to_pdf()
        img_rect      = img[0].rect

        img.close()

        img_pdf = pymupdf.open(stream=img_pdf_bytes, filetype='pdf')

        page = outdoc.new_page(width  = img_rect.width,
                               height = img_rect.height)

        page.show_pdf_page(img_rect, img_pdf, 0)

    return outdoc.tobytes()

def convert_to_image_pdf_file(inp_file, outp_file):
    with open(inp_file, 'rb') as f:
        file_bytes = f.read()

    pdf_bytes = convert_to_image_pdf(file_bytes)

    with open(outp_file, 'wb') as f:
        f.write(pdf_bytes)

def get_all_used_unembedded_fonts(file_bytes):
    page_fonts = defaultdict(list)
    processed_fonts = set()
        
    doc = pymupdf.open(stream=file_bytes, filetype='pdf')

    for page_num in range(doc.page_count):
        page = doc[page_num]
        
        text_dict = page.get_text("dict")
        
        page_font_names = set()
        
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line.get("spans", []):
                        font_name = span.get("font")
                        if font_name:
                            page_font_names.add(font_name)
        
        font_list = page.get_fonts(full=True)
        
        # Process each font used on this page
        for font_info in font_list:
            # 453, 'n/a', 'TrueType', 'Nudi01kBold', 'F1', 'WinAnsiEncoding', 0
            font_ref = font_info[0]
            font_name = font_info[3]
            
            if font_name in page_font_names:

                font_embedded = False
                try:
                    _a, _b, _c, content = doc.extract_font(font_ref)
                    if content is not None and len(content) > 0:
                        font_embedded = True
                except Exception as ex:
                    print(ex)
    
                if not font_embedded:
                    font_key = (font_name, page_num)
                    
                    if font_key not in processed_fonts:
                        page_fonts[page_num].append(font_name)
                        processed_fonts.add(font_key)
        
    doc.close()
    
    result = dict(sorted(page_fonts.items()))
            
    return result

if __name__ == '__main__':
    import sys
    from pathlib import Path
    pdf_bytes = convert_to_image_pdf(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_bytes(pdf_bytes)

