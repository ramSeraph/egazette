import sys
from pathlib import Path
from datetime import datetime, timedelta

usage = f'Usage: {sys.argv[0]} <from_date as DD-MM-YYYY> <to_date as DD-MM-YYYY> <output_dates_file> <split_size>'

if len(sys.argv) < 5:
    print(f'ERROR: expected 4 args got {len(sys.argv) - 1}')
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
    print('ERROR: to_date in unexpected format.. expected: DD-MM-YYYY')
    exit(1)

outfile = Path(sys.argv[3])

split_size = int(sys.argv[4])

print(from_date, to_date)
print(f'writing to {outfile}')

start_date = from_date
stop_date = None
with open(outfile, 'w') as f:
    done = False
    while True:
        stop_date = start_date + timedelta(days=split_size-1)
        if stop_date >= to_date:
            stop_date = to_date
            done = True

        start_str = start_date.strftime('%d-%m-%Y')
        stop_str  = stop_date.strftime('%d-%m-%Y')

        f.write(f'{start_str} {stop_str}\n')

        start_date = stop_date + timedelta(days=1)

        if done:
            break
