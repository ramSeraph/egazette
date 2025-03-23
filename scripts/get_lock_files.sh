#!/bin/bash

set -e

USING_UV=${USING_UV:-0}

[[ ! -d .venv ]] || ( echo "ERROR: folder .venv already exists.. this script will modify it. Back it up and delete it before continuing" && exit 1 )

for file in sync iasync gvision tools all
do
    rm -rf .venv
    if [[ $USING_UV == 1 ]]; then
        uv venv
        uv pip install -r requirements/${file}.in
        uv pip freeze > requirements/${file}.txt
    else
        python -m venv .venv
        source .venv/bin/activate
        pip install -r requirements/${file}.in
        pip freeze > requirements/${file}.txt
        deactivate
    fi
done
rm -rf .venv
