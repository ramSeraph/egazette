# egazette
Modules to be installed:

1. BeautifulSoup 4: https://www.crummy.com/software/BeautifulSoup/ https://pypi.org/project/beautifulsoup4/

2. python-magic  https://github.com/ahupp/python-magic https://pypi.org/project/python-magic/

3. pypdf2 https://github.com/mstamy2/PyPDF2 https://pypi.org/project/PyPDF2/

4. Pillow   https://pypi.org/project/Pillow/

5. tesseract https://github.com/tesseract-ocr/

6. zipfile: https://pypi.org/project/zipp/

7. For Google Translate API:
google-cloud-translate  https://pypi.org/project/google-cloud-translate/

8. For using OCR capabilities:
google-cloud-vision https://pypi.org/project/google-cloud-vision/

9) For Google Speech to text:
google-cloud-speech 	https://pypi.org/project/google-cloud-translate/
google-cloud-storage    https://pypi.org/project/google-cloud-storage/

10) internetarchive: https://pypi.org/project/internetarchive/

Usage:python sync.py   [-l level(critical, error, warn, info, debug)]

                       [-a (all_downloads)]

                       [-m (updateMeta)]

                       [-n (no aggregation of srcs by hostname)]

                       [-r (updateRaw)]

                       [-f logfile]

                       [-t fromdate (DD-MM-YYYY)] [-T todate (DD-MM-YYYY)] 


                       [-s central_weekly -s central_extraordinary -s central
                        -s states 
                        -s andhra -s andhraarchive 
                        -s bihar 
                        -s chattisgarh -s cgweekly -s cgextraordinary 
                        -s delhi -s delhi_weekly -s delhi_extraordinary
                        -s karnataka
                        -s maharashtra -s telangana   -s tamilnadu
                        -s jharkhand   -s odisha      -s madhyapradesh
                        -s punjab      -s uttarakhand -s himachal
                        -s haryana     -s kerala      -s haryanaarchive
                        -s stgeorge    -s himachal    -s keralalibrary
                       ]

                       [-D datadir]


The program will download gazettes from various egazette sites
and will place in a specified directory. Gazettes will be
placed into directories named by type and date. If fromdate or
todate is not specified then the default is your current date.

Google API translation:

usage: translate.py [-h] [-t INPUT_TYPE] -l INPUT_LANG -L OUTPUT_LANG -i
                    INPUT_FILE -o OUTPUT_FILE -k KEY_FILE -p PROJECT_ID
                    [-c IGNORE_CLASSES]

Using Google API to translate text

optional arguments:
  -h, --help            show this help message and exit
  -t INPUT_TYPE, --type INPUT_TYPE
                        type of input file(text/sbv/html)
  -l INPUT_LANG, --input_lang INPUT_LANG
                        Language of input text
                        (https://cloud.google.com/translate/docs/languages)
  -L OUTPUT_LANG        Language of output text
  -i INPUT_FILE, --infile INPUT_FILE
                        Input File
  -o OUTPUT_FILE, --outfile OUTPUT_FILE
                        Output file
  -k KEY_FILE, --key KEY_FILE
                        Google key file
  -p PROJECT_ID, --project PROJECT_ID
                        Project ID
  -c IGNORE_CLASSES, --ignoreclass IGNORE_CLASSES
                        HTML classes to be ignored for translation

