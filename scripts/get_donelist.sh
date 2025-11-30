#!/bin/bash

usage="USAGE: $0 <source> <from_date> <to_date> <output_file>"
src_name=$1
[[ $src_name == '' ]] && echo "ERROR: missing <source> argument" && echo $usage && exit 1

from_date=$2
[[ $from_date == '' ]] && echo "ERROR: missing <from_date> argument" && echo $usage && exit 1

to_date=$3
[[ $to_date == '' ]] && echo "ERROR: missing <to_date> argument" && echo $usage && exit 1

output_file=$4
[[ $output_file == '' ]] && echo "ERROR: missing <output_file> argument" && echo $usage && exit 1

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

rev_date() {
  echo "$1" | awk  'BEGIN{FS=OFS="-" }{print $3,$2,$1}'
}

from_date_rev=$(rev_date $from_date)
to_date_rev=$(rev_date $to_date)

echo "getting list of items with prefix from internet archive"
PREFIX_TO_REMOVE=''
if [[ ${TESTING-} == '1' ]]; then
  PREFIX_TO_REMOVE=$(uv run python -c "from srcs.datasrcs_info import TEST_PREFIX; print(TEST_PREFIX)")
  echo "need to remove prefix $PREFIX_TO_REMOVE"
fi

if [[ $PREFIX_TO_REMOVE != '' ]]; then
  uvx --from internetarchive ia search "identifier:${prefix}* AND date:[$from_date_rev TO $to_date_rev]" -i | sed "s/^${PREFIX_TO_REMOVE}//" > $output_file
  uvx --from internetarchive ia search "identifier:${prefix}* AND NOT date:*" -i | sed "s/^${PREFIX_TO_REMOVE}//" >> $output_file
else
  uvx --from internetarchive ia search "identifier:${prefix}* AND date:[$from_date_rev TO $to_date_rev]" -i > $output_file
  uvx --from internetarchive ia search "identifier:${prefix}* AND NOT date:*" -i >> $output_file
fi
