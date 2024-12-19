# -*- coding: utf-8 -*-
"""Test rule format."""
import json
from os import listdir, path
from typing import Optional
import pytest
import yaml

SOURCE_PATH: str = path.dirname(path.abspath(__file__))
TRANS_RELATIVE_PATH: str = '../custom_components/xiaomi_home/translations'
MIOT_I18N_RELATIVE_PATH: str = '../custom_components/xiaomi_home/miot/i18n'


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


@pytest.mark.github
def test_bool_trans():
    data: dict = load_json_file(
        path.join(
            SOURCE_PATH,
            '../custom_components/xiaomi_home/miot/specs/bool_trans.json'))
    assert data
    assert bool_trans(data)


@pytest.mark.github
def test_spec_filter():
    data: dict = load_json_file(
        path.join(
            SOURCE_PATH,
            '../custom_components/xiaomi_home/miot/specs/spec_filter.json'))
    assert data
    assert spec_filter(data)


@pytest.mark.github
def test_multi_lang():
    data: dict = load_json_file(
        path.join(
            SOURCE_PATH,
            '../custom_components/xiaomi_home/miot/specs/multi_lang.json'))
    assert data
    assert nested_3_dict_str_str(data)


@pytest.mark.github
def test_miot_i18n():
    i18n_path: str = path.join(SOURCE_PATH, MIOT_I18N_RELATIVE_PATH)
    for file_name in listdir(i18n_path):
        file_path: str = path.join(i18n_path, file_name)
        data: dict = load_json_file(file_path)
        assert data
        assert nested_3_dict_str_str(data)


@pytest.mark.github
def test_translations():
    i18n_path: str = path.join(SOURCE_PATH, TRANS_RELATIVE_PATH)
    for file_name in listdir(i18n_path):
        file_path: str = path.join(i18n_path, file_name)
        data: dict = load_json_file(file_path)
        assert data
        assert dict_str_dict(data)


@pytest.mark.github
def test_miot_lang_integrity():
    # pylint: disable=import-outside-toplevel
    from miot.const import INTEGRATION_LANGUAGES
    integration_lang_list: list[str] = [
        f'{key}.json' for key in list(INTEGRATION_LANGUAGES.keys())]
    translations_names: set[str] = set(listdir(
        path.join(SOURCE_PATH, TRANS_RELATIVE_PATH)))
    assert len(translations_names) == len(integration_lang_list)
    assert translations_names == set(integration_lang_list)
    i18n_names: set[str] = set(listdir(
        path.join(SOURCE_PATH, MIOT_I18N_RELATIVE_PATH)))
    assert len(i18n_names) == len(translations_names)
    assert i18n_names == translations_names
    # Check translation files structure
    default_dict: dict = load_json_file(
        path.join(SOURCE_PATH, TRANS_RELATIVE_PATH, integration_lang_list[0]))
    for name in list(integration_lang_list)[1:]:
        compare_dict: dict = load_json_file(
            path.join(SOURCE_PATH, TRANS_RELATIVE_PATH, name))
        if not compare_dict_structure(default_dict, compare_dict):
            print('compare_dict_structure failed /translations, ', name)
            assert False
    # Check i18n files structure
    default_dict = load_json_file(
        path.join(
            SOURCE_PATH, MIOT_I18N_RELATIVE_PATH, integration_lang_list[0]))
    for name in list(integration_lang_list)[1:]:
        compare_dict: dict = load_json_file(
            path.join(SOURCE_PATH, MIOT_I18N_RELATIVE_PATH, name))
        if not compare_dict_structure(default_dict, compare_dict):
            print('compare_dict_structure failed /miot/i18n, ', name)
            assert False
