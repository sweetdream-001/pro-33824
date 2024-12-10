"""Check if conversion rules are valid.

The files to be checked are in the directory of ../miot/specs/
To run this script, PYTHONPATH must be set first.
See test_all.sh for the usage.

You can run all tests by running:
```
./test_all.sh
```
"""
import sys
import os
import json

def load_json(file_path: str) -> dict:
    """Load json file."""
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
        return data

def dict_str_str(d: dict) -> bool:
    """restricted format: dict[str, str]"""
    if not isinstance(d, dict):
        return False
    for k, v in d.items():
        if not isinstance(k, str) or not isinstance(v, str):
            return False
    return True

def dict_str_dict(d: dict) -> bool:
    """restricted format: dict[str, dict]"""
    if not isinstance(d, dict):
        return False
    for k, v in d.items():
        if not isinstance(k, str) or not isinstance(v, dict):
            return False
    return True

def nested_2_dict_str_str(d: dict) -> bool:
    """restricted format: dict[str, dict[str, str]]"""
    if not dict_str_dict(d):
        return False
    for v in d.values():
        if not dict_str_str(v):
            return False
    return True

def nested_3_dict_str_str(d: dict) -> bool:
    """restricted format: dict[str, dict[str, dict[str, str]]]"""
    if not dict_str_dict(d):
        return False
    for v in d.values():
        if not nested_2_dict_str_str(v):
            return False
    return True

def spec_filter(d: dict) -> bool:
    """restricted format: dict[str, dict[str, list<str>]]"""
    if not dict_str_dict(d):
        return False
    for value in d.values():
        for k, v in value.items():
            if not isinstance(k, str) or not isinstance(v, list):
                return False
            if not all(isinstance(i, str) for i in v):
                return False
    return True

def bool_trans(d: dict) -> bool:
    """dict[str,  dict[str, str] | dict[str, dict[str, str]] ]"""
    if not isinstance(d, dict):
        return False
    if "data" not in d or "translate" not in d:
        return False
    if not dict_str_str(d["data"]):
        return False
    if not nested_3_dict_str_str(d["translate"]):
        return False

    return True


def main():
    script_name = os.path.basename(__file__)

    source_dir = "../miot/specs"
    if not bool_trans(load_json(f"{source_dir}/bool_trans.json")):
        print(script_name, "bool_trans FAIL")
        sys.exit(1)
    if not nested_3_dict_str_str(load_json(f"{source_dir}/multi_lang.json")):
        print(script_name, "multi_lang FAIL")
        sys.exit(1)
    if not spec_filter(load_json(f"{source_dir}/spec_filter.json")):
        print(script_name, "spec_filter FAIL")
        sys.exit(1)

    source_dir = "../miot/i18n"
    if not nested_3_dict_str_str(load_json(f"{source_dir}/de.json")):
        print(script_name, "i18n de.json FAIL")
        sys.exit(1)
    if not nested_3_dict_str_str(load_json(f"{source_dir}/en.json")):
        print(script_name, "i18n en.json FAIL")
        sys.exit(1)
    if not nested_3_dict_str_str(load_json(f"{source_dir}/es.json")):
        print(script_name, "i18n es.json FAIL")
        sys.exit(1)
    if not nested_3_dict_str_str(load_json(f"{source_dir}/fr.json")):
        print(script_name, "i18n fr.json FAIL")
        sys.exit(1)
    if not nested_3_dict_str_str(load_json(f"{source_dir}/ja.json")):
        print(script_name, "i18n ja.json FAIL")
        sys.exit(1)
    if not nested_3_dict_str_str(load_json(f"{source_dir}/ru.json")):
        print(script_name, "i18n ru.json FAIL")
        sys.exit(1)
    if not nested_3_dict_str_str(load_json(f"{source_dir}/zh-Hans.json")):
        print(script_name, "i18n zh-Hans.json FAIL")
        sys.exit(1)
    if not nested_3_dict_str_str(load_json(f"{source_dir}/zh-Hant.json")):
        print(script_name, "i18n zh-Hant.json FAIL")
        sys.exit(1)

    print(script_name, "PASS")

if __name__ == "__main__":
    main()
