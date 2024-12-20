# -*- coding: utf-8 -*-
"""Test rule format."""
import json
from os import listdir, path
from typing import Optional
import pytest
import yaml

ROOT_PATH: str = path.dirname(path.abspath(__file__))
TRANS_RELATIVE_PATH: str = path.join(
    ROOT_PATH, '../custom_components/xiaomi_home/translations')
MIOT_I18N_RELATIVE_PATH: str = path.join(
    ROOT_PATH, '../custom_components/xiaomi_home/miot/i18n')
SPEC_BOOL_TRANS_FILE = path.join(
    ROOT_PATH,
    '../custom_components/xiaomi_home/miot/specs/bool_trans.json')
SPEC_MULTI_LANG_FILE = path.join(
    ROOT_PATH,
    '../custom_components/xiaomi_home/miot/specs/multi_lang.json')
SPEC_FILTER_FILE = path.join(
    ROOT_PATH,
    '../custom_components/xiaomi_home/miot/specs/spec_filter.json')


def load_json_file(file_path: str) -> Optional[dict]:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(file_path, 'is not found.')
        return None
    except json.JSONDecodeError:
        print(file_path, 'is not a valid JSON file.')
        return None


def save_json_file(file_path: str, data: dict) -> None:
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def load_yaml_file(file_path: str) -> Optional[dict]:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(file_path, 'is not found.')
        return None
    except yaml.YAMLError:
        print(file_path, 'is not a valid YAML file.')
        return None


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
    if 'data' not in d or 'translate' not in d:
        return False
    if not dict_str_str(d['data']):
        return False
    if not nested_3_dict_str_str(d['translate']):
        return False
    default_trans: dict = d['translate'].pop('default')
    if not default_trans:
        print('default trans is empty')
        return False
    default_keys: set[str] = set(default_trans.keys())
    for key, trans in d['translate'].items():
        trans_keys: set[str] = set(trans.keys())
        if set(trans.keys()) != default_keys:
            print('bool trans inconsistent', key, default_keys, trans_keys)
            return False
    return True


def compare_dict_structure(dict1: dict, dict2: dict) -> bool:
    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        print('invalid type')
        return False
    if dict1.keys() != dict2.keys():
        print('inconsistent key values, ', dict1.keys(), dict2.keys())
        return False
    for key in dict1:
        if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
            if not compare_dict_structure(dict1[key], dict2[key]):
                print('inconsistent key values, dict, ', key)
                return False
        elif isinstance(dict1[key], list) and isinstance(dict2[key], list):
            if not all(
                    isinstance(i, type(j))
                    for i, j in zip(dict1[key], dict2[key])):
                print('inconsistent key values, list, ', key)
                return False
        elif not isinstance(dict1[key], type(dict2[key])):
            print('inconsistent key values, type, ', key)
            return False
    return True


def sort_bool_trans(file_path: str):
    trans_data: dict = load_json_file(file_path=file_path)
    trans_data['data'] = dict(sorted(trans_data['data'].items()))
    for key, trans in trans_data['translate'].items():
        trans_data['translate'][key] = dict(sorted(trans.items()))
    return trans_data


def sort_multi_lang(file_path: str):
    multi_lang: dict = load_json_file(file_path=file_path)
    multi_lang = dict(sorted(multi_lang.items()))
    for urn, trans in multi_lang.items():
        multi_lang[urn] = dict(sorted(trans.items()))
        for lang, spec in multi_lang[urn].items():
            multi_lang[urn][lang] = dict(sorted(spec.items()))
    return multi_lang


def sort_spec_filter(file_path: str):
    filter_data: dict = load_json_file(file_path=file_path)
    filter_data = dict(sorted(filter_data.items()))
    for urn, spec in filter_data.items():
        filter_data[urn] = dict(sorted(spec.items()))
    return filter_data


@pytest.mark.github
def test_bool_trans():
    data: dict = load_json_file(SPEC_BOOL_TRANS_FILE)
    assert data, f'load {SPEC_BOOL_TRANS_FILE} failed'
    assert bool_trans(data), f'{SPEC_BOOL_TRANS_FILE} format error'


@pytest.mark.github
def test_spec_filter():
    data: dict = load_json_file(SPEC_FILTER_FILE)
    assert data, f'load {SPEC_FILTER_FILE} failed'
    assert spec_filter(data), f'{SPEC_FILTER_FILE} format error'


@pytest.mark.github
def test_multi_lang():
    data: dict = load_json_file(SPEC_MULTI_LANG_FILE)
    assert data, f'load {SPEC_MULTI_LANG_FILE} failed'
    assert nested_3_dict_str_str(data), f'{SPEC_MULTI_LANG_FILE} format error'


@pytest.mark.github
def test_miot_i18n():
    for file_name in listdir(MIOT_I18N_RELATIVE_PATH):
        file_path: str = path.join(MIOT_I18N_RELATIVE_PATH, file_name)
        data: dict = load_json_file(file_path)
        assert data, f'load {file_path} failed'
        assert nested_3_dict_str_str(data), f'{file_path} format error'


@pytest.mark.github
def test_translations():
    for file_name in listdir(TRANS_RELATIVE_PATH):
        file_path: str = path.join(TRANS_RELATIVE_PATH, file_name)
        data: dict = load_json_file(file_path)
        assert data, f'load {file_path} failed'
        assert dict_str_dict(data), f'{file_path} format error'


@pytest.mark.github
def test_miot_lang_integrity():
    # pylint: disable=import-outside-toplevel
    from miot.const import INTEGRATION_LANGUAGES
    integration_lang_list: list[str] = [
        f'{key}.json' for key in list(INTEGRATION_LANGUAGES.keys())]
    translations_names: set[str] = set(listdir(TRANS_RELATIVE_PATH))
    assert len(translations_names) == len(integration_lang_list)
    assert translations_names == set(integration_lang_list)
    i18n_names: set[str] = set(listdir(MIOT_I18N_RELATIVE_PATH))
    assert len(i18n_names) == len(translations_names)
    assert i18n_names == translations_names
    bool_trans_data: set[str] = load_json_file(SPEC_BOOL_TRANS_FILE)
    bool_trans_names: set[str] = set(
        bool_trans_data['translate']['default'].keys())
    assert len(bool_trans_names) == len(translations_names)
    # Check translation files structure
    default_dict: dict = load_json_file(
        path.join(TRANS_RELATIVE_PATH, integration_lang_list[0]))
    for name in list(integration_lang_list)[1:]:
        compare_dict: dict = load_json_file(
            path.join(TRANS_RELATIVE_PATH, name))
        if not compare_dict_structure(default_dict, compare_dict):
            print('compare_dict_structure failed /translations, ', name)
            assert False
    # Check i18n files structure
    default_dict = load_json_file(
        path.join(MIOT_I18N_RELATIVE_PATH, integration_lang_list[0]))
    for name in list(integration_lang_list)[1:]:
        compare_dict: dict = load_json_file(
            path.join(MIOT_I18N_RELATIVE_PATH, name))
        if not compare_dict_structure(default_dict, compare_dict):
            print('compare_dict_structure failed /miot/i18n, ', name)
            assert False


@pytest.mark.github
def test_miot_data_sort():
    # pylint: disable=import-outside-toplevel
    from miot.const import INTEGRATION_LANGUAGES
    sort_langs: dict = dict(sorted(INTEGRATION_LANGUAGES.items()))
    assert list(INTEGRATION_LANGUAGES.keys()) == list(sort_langs.keys()), (
        'INTEGRATION_LANGUAGES not sorted, correct order\r\n'
        f'{list(sort_langs.keys())}')
    assert json.dumps(
        load_json_file(file_path=SPEC_BOOL_TRANS_FILE)) == json.dumps(
            sort_bool_trans(file_path=SPEC_BOOL_TRANS_FILE)), (
                f'{SPEC_BOOL_TRANS_FILE} not sorted, goto project root path'
                ' and run the following command sorting, ',
                'pytest -s -v -m update ./test/check_rule_format.py')
    assert json.dumps(
        load_json_file(file_path=SPEC_MULTI_LANG_FILE)) == json.dumps(
            sort_multi_lang(file_path=SPEC_MULTI_LANG_FILE)), (
                f'{SPEC_MULTI_LANG_FILE} not sorted, goto project root path'
                ' and run the following command sorting, ',
                'pytest -s -v -m update ./test/check_rule_format.py')
    assert json.dumps(
        load_json_file(file_path=SPEC_FILTER_FILE)) == json.dumps(
            sort_spec_filter(file_path=SPEC_FILTER_FILE)), (
                f'{SPEC_FILTER_FILE} not sorted, goto project root path'
                ' and run the following command sorting, ',
                'pytest -s -v -m update ./test/check_rule_format.py')


@pytest.mark.update
def test_sort_spec_data():
    sort_data: dict = sort_bool_trans(file_path=SPEC_BOOL_TRANS_FILE)
    save_json_file(file_path=SPEC_BOOL_TRANS_FILE, data=sort_data)
    print(SPEC_BOOL_TRANS_FILE, 'formatted.')
    sort_data = sort_multi_lang(file_path=SPEC_MULTI_LANG_FILE)
    save_json_file(file_path=SPEC_MULTI_LANG_FILE, data=sort_data)
    print(SPEC_MULTI_LANG_FILE, 'formatted.')
    sort_data = sort_spec_filter(file_path=SPEC_FILTER_FILE)
    save_json_file(file_path=SPEC_FILTER_FILE, data=sort_data)
    print(SPEC_FILTER_FILE, 'formatted.')
