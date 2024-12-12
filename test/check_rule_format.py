# -*- coding: utf-8 -*-
"""Test rule format."""
import json
from os import listdir, path
from typing import Optional

SOURCE_DIR: str = path.dirname(path.abspath(__file__))


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


def test_bool_trans():
    data: dict = load_json_file(
        path.join(
            SOURCE_DIR,
            '../custom_components/xiaomi_home/miot/specs/bool_trans.json'))
    assert data
    assert bool_trans(data)


def test_spec_filter():
    data: dict = load_json_file(
        path.join(
            SOURCE_DIR,
            '../custom_components/xiaomi_home/miot/specs/spec_filter.json'))
    assert data
    assert spec_filter(data)


def test_multi_lang():
    data: dict = load_json_file(
        path.join(
            SOURCE_DIR,
            '../custom_components/xiaomi_home/miot/specs/multi_lang.json'))
    assert data
    assert nested_3_dict_str_str(data)


def test_miot_i18n():
    i18n_path: str = path.join(
        SOURCE_DIR, '../custom_components/xiaomi_home/miot/i18n')
    for file_name in listdir(i18n_path):
        file_path: str = path.join(i18n_path, file_name)
        data: dict = load_json_file(file_path)
        assert data
        assert nested_3_dict_str_str(data)
