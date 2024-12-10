#!/bin/bash

set -e

# Get the script path.
script_path=$(dirname "$0")
# Change to the script path.
cd "$script_path"
# Set PYTHONPATH.
cd ..
export PYTHONPATH=`pwd`
echo "PYTHONPATH=$PYTHONPATH"
cd -

# Run the tests.
export source_dir="../miot/specs"
python3 json_format.py $source_dir/bool_trans.json
python3 json_format.py $source_dir/multi_lang.json
python3 json_format.py $source_dir/spec_filter.json
python3 json_format.py $source_dir/std_ex_actions.json
python3 json_format.py $source_dir/std_ex_devices.json
python3 json_format.py $source_dir/std_ex_events.json
python3 json_format.py $source_dir/std_ex_properties.json
python3 json_format.py $source_dir/std_ex_services.json
python3 json_format.py $source_dir/std_ex_values.json
export source_dir="../miot/i18n"
python3 json_format.py $source_dir/de.json
python3 json_format.py $source_dir/en.json
python3 json_format.py $source_dir/es.json
python3 json_format.py $source_dir/fr.json
python3 json_format.py $source_dir/ja.json
python3 json_format.py $source_dir/ru.json
python3 json_format.py $source_dir/zh-Hans.json
python3 json_format.py $source_dir/zh-Hant.json
python3 rule_format.py
