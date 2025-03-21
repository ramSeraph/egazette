import sys
from pathlib import Path
from datetime import datetime, timedelta

usage = f'Usage: {sys.argv[0]} <from_date as DD-MM-YYYY> <to_date as DD-MM-YYYY> <output_dates_file>'

if len(sys.argv) < 4:
    print(f'ERROR: expected 3 args got {len(sys.argv) - 1}')
    print(usage)
    exit(1)

try:
    from_date = datetime.strptime(sys.argv[1], '%d-%m-%Y').date()
except Exception:
    print('ERROR: from_date in unexpected format.. expected: DD-MM-YYYY')
    exit(1)

try:
    to_date = datetime.strptime(sys.argv[2], '%d-%m-%Y').date()
except Exception:
    print('ERROR: from_date in unexpected format.. expected: DD-MM-YYYY')
    exit(1)

outfile = Path(sys.argv[3])

curr_date = from_date
print(from_date, to_date)
print(f'writing to {outfile}')
with open(outfile, 'w') as f:
    while curr_date <= to_date:
        f.write(curr_date.strftime('%d-%m-%Y'))
        f.write('\n')
        curr_date = curr_date + timedelta(days=1)
