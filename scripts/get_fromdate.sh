#!/bin/bash

convert_to_short_date() {
  if [[ "$(uname)" == "Darwin" ]]; then
    date -j -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%d-%m-%Y
  else
    date -d "$1" +%d-%m-%Y
  fi
}

usage="USAGE: $0 <source> [<output_file>]"
src_name=$1
[[ $src_name == '' ]] && echo "ERROR: missing <source> argument" && echo $usage && exit 1

output_file=$2

set -Eeuo pipefail

echo "got source: $src_name"

echo "getting identifier prefix"
to_sandox_val='False'
if [[ ${TESTING-} == '1' ]]; then
  to_sandox_val='True'
fi
prefix=$(uv run python -c "from srcs.datasrcs_info import get_prefix; print(get_prefix('$src_name', to_sandbox=$to_sandox_val))")
echo "got prefix as: $prefix"
[[ $prefix != '' ]] || exit 1

echo "getting items with prefix from internet archive"
from_date_ia=$(uvx --from internetarchive ia search "identifier:${prefix}*" --sort 'date desc' -f date --parameters="page=1&rows=1" | jq -r .date)
if [[ $from_date_ia != '' ]]; then
  from_date=$(convert_to_short_date $from_date_ia)
  echo "got from date as : $from_date"
fi

if [[ ${from_date-} == '' ]]; then
  echo "getting from date from config"
  from_date=$(uv run python -c "from srcs.datasrcs_info import get_start_date; d = get_start_date('$src_name'); print('' if d is None else d.strftime('%d-%m-%Y'))")
  echo "got from date as: $from_date"
fi

[[ $from_date != '' ]] || exit 1

[[ $output_file == '' ]] && exit 0

echo "$from_date" > $output_file


