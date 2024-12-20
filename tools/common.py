# -*- coding: utf-8 -*-
"""Common functions."""
import json
import yaml
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def load_yaml_file(yaml_file: str) -> dict:
    with open(yaml_file, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)


def save_yaml_file(yaml_file: str, data: dict) -> None:
    with open(yaml_file, 'w', encoding='utf-8') as file:
        yaml.safe_dump(
            data=data, stream=file, allow_unicode=True)


def load_json_file(json_file: str) -> dict:
    with open(json_file, 'r', encoding='utf-8') as file:
        return json.load(file)


def save_json_file(json_file: str, data: dict) -> None:
    with open(json_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def http_get(
    url: str, params: dict = None, headers: dict = None
) -> dict:
    if params:
        encoded_params = urlencode(params)
        full_url = f'{url}?{encoded_params}'
    else:
        full_url = url
    request = Request(full_url, method='GET', headers=headers or {})
    content: bytes = None
    with urlopen(request) as response:
        content = response.read()
    return (
        json.loads(str(content, 'utf-8'))
        if content is not None else None)
