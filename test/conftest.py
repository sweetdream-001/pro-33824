# -*- coding: utf-8 -*-
"""Pytest fixtures."""
import shutil
import pytest
from os import path, makedirs

TEST_ROOT_PATH: str = path.dirname(path.abspath(__file__))
TEST_LANG: str = 'zh-Hans'
TEST_UID: str = '123456789'
TEST_CLOUD_SERVER: str = 'cn'


@pytest.fixture(scope='session', autouse=True)
def load_py_file():
    # Copy py file to test folder
    file_list = [
        'common.py',
        'const.py',
        'miot_cloud.py',
        'miot_error.py',
        'miot_ev.py',
        'miot_i18n.py',
        'miot_lan.py',
        'miot_mdns.py',
        'miot_network.py',
        'miot_spec.py',
        'miot_storage.py']
    makedirs(path.join(TEST_ROOT_PATH, 'miot'), exist_ok=True)
    for file_name in file_list:
        shutil.copyfile(
            path.join(
                TEST_ROOT_PATH, '../custom_components/xiaomi_home/miot',
                file_name),
            path.join(TEST_ROOT_PATH, 'miot', file_name))
    print('\nloaded test py file, %s' % file_list)
    # Copy spec files to test folder
    shutil.copytree(
        src=path.join(
            TEST_ROOT_PATH, '../custom_components/xiaomi_home/miot/specs'),
        dst=path.join(TEST_ROOT_PATH, 'miot/specs'),
        dirs_exist_ok=True)
    print('\nloaded spec test folder, miot/specs')
    # Copy i18n files to test folder
    shutil.copytree(
        src=path.join(
            TEST_ROOT_PATH, '../custom_components/xiaomi_home/miot/i18n'),
        dst=path.join(TEST_ROOT_PATH, 'miot/i18n'),
        dirs_exist_ok=True)
    print('\nloaded i18n test folder, miot/i18n')
    yield
    # shutil.rmtree(path.join(TEST_ROOT_PATH, 'miot'))
    # print('\nremoved test file, %s', file_list)
    # shutil.rmtree(path.join(TEST_ROOT_PATH, 'miot/specs'))
    # print('\nremoved test folder, %s', 'miot/specs')
    # shutil.rmtree(path.join(TEST_ROOT_PATH, 'miot/i18n'))
    # print('\nremoved test folder, %s', 'miot/i18n')


@pytest.fixture(scope='session')
def test_root_path() -> str:
    return TEST_ROOT_PATH


@pytest.fixture(scope='session')
def test_cache_path() -> str:
    cache_path: str = path.join(TEST_ROOT_PATH, 'test_cache')
    makedirs(cache_path, exist_ok=True)
    return cache_path


@pytest.fixture(scope='session')
def test_lang() -> str:
    return TEST_LANG


@pytest.fixture(scope='session')
def test_uid() -> str:
    return TEST_UID


@pytest.fixture(scope='session')
def test_cloud_server() -> str:
    return TEST_CLOUD_SERVER
