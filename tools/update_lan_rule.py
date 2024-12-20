""" Update LAN rule."""
# -*- coding: utf-8 -*-
# pylint: disable=relative-beyond-top-level
from os import path
from common import (
    http_get,
    load_yaml_file,
    save_yaml_file)


ROOT_PATH: str = path.dirname(path.abspath(__file__))
LAN_PROFILE_MODELS_FILE: str = path.join(
    ROOT_PATH,
    '../custom_components/xiaomi_home/miot/lan/profile_models.yaml')


SPECIAL_MODELS: list[str] = [
    # model2class-v2
    'chuangmi.camera.ipc007b', 'chuangmi.camera.ipc019b',
    'chuangmi.camera.ipc019e', 'chuangmi.camera.ipc020',
    'chuangmi.camera.v2', 'chuangmi.camera.v5',
    'chuangmi.camera.v6', 'chuangmi.camera.xiaobai',
    'chuangmi.radio.v1', 'chuangmi.radio.v2',
    'hith.foot_bath.q2', 'imou99.camera.tp2',
    'isa.camera.hl5', 'isa.camera.isc5',
    'jiqid.mistory.pro', 'jiqid.mistory.v1',
    'lumi.airrtc.tcpco2ecn01', 'lumi.airrtc.tcpecn02',
    'lumi.camera.gwagl01', 'miir.light.ir01',
    'miir.projector.ir01', 'miir.tv.hir01',
    'miir.tvbox.ir01', 'roome.bhf_light.yf6002',
    'smith.waterpuri.jnt600', 'viomi.fridge.u2',
    'xiaovv.camera.lamp', 'xiaovv.camera.ptz',
    'xiaovv.camera.xva3', 'xiaovv.camera.xvb4',
    'xiaovv.camera.xvsnowman', 'zdeer.ajh.a8',
    'zdeer.ajh.a9', 'zdeer.ajh.zda10',
    'zdeer.ajh.zda9', 'zdeer.ajh.zjy', 'zimi.clock.myk01',
    # specialModels
    'chuangmi.camera.ipc004b', 'chuangmi.camera.ipc009',
    'chuangmi.camera.ipc010', 'chuangmi.camera.ipc013',
    'chuangmi.camera.ipc013d', 'chuangmi.camera.ipc016',
    'chuangmi.camera.ipc017', 'chuangmi.camera.ipc019',
    'chuangmi.camera.ipc021', 'chuangmi.camera.v3',
    'chuangmi.camera.v4', 'isa.camera.df3',
    'isa.camera.hlc6', 'lumi.acpartner.v1',
    'lumi.acpartner.v2', 'lumi.acpartner.v3',
    'lumi.airrtc.tcpecn01', 'lumi.camera.aq1',
    'miir.aircondition.ir01', 'miir.aircondition.ir02',
    'miir.fan.ir01', 'miir.stb.ir01',
    'miir.tv.ir01', 'mijia.camera.v1',
    'mijia.camera.v3', 'roborock.sweeper.s5v2',
    'roborock.vacuum.c1', 'roborock.vacuum.e2',
    'roborock.vacuum.m1s', 'roborock.vacuum.s5',
    'rockrobo.vacuum.v1', 'xiaovv.camera.xvd5']


def update_profile_model(file_path: str):
    profile_rules: dict = http_get(
        url='https://miot-spec.org/instance/translate/models')
    if not profile_rules and 'models' not in profile_rules and not isinstance(
            profile_rules['models'], dict):
        raise ValueError('Failed to get profile rule')
    local_rules: dict = load_yaml_file(
        yaml_file=file_path) or {}
    for rule, ts in profile_rules['models'].items():
        if rule not in local_rules:
            local_rules[rule] = {'ts': ts}
        else:
            local_rules[rule]['ts'] = ts
    for mode in SPECIAL_MODELS:
        if mode not in local_rules:
            local_rules[mode] = {'ts': 1531108800}
        else:
            local_rules[mode]['ts'] = 1531108800
    local_rules = dict(sorted(local_rules.items()))
    save_yaml_file(
        yaml_file=file_path, data=local_rules)


update_profile_model(file_path=LAN_PROFILE_MODELS_FILE)
print('profile model list updated.')
