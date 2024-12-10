# -*- coding: utf-8 -*-
"""
Copyright (C) 2024 Xiaomi Corporation.

The ownership and intellectual property rights of Xiaomi Home Assistant
Integration and related Xiaomi cloud service API interface provided under this
license, including source code and object code (collectively, "Licensed Work"),
are owned by Xiaomi. Subject to the terms and conditions of this License, Xiaomi
hereby grants you a personal, limited, non-exclusive, non-transferable,
non-sublicensable, and royalty-free license to reproduce, use, modify, and
distribute the Licensed Work only for your use of Home Assistant for
non-commercial purposes. For the avoidance of doubt, Xiaomi does not authorize
you to use the Licensed Work for any other purpose, including but not limited
to use Licensed Work to develop applications (APP), Web services, and other
forms of software.

You may reproduce and distribute copies of the Licensed Work, with or without
modifications, whether in source or object form, provided that you must give
any other recipients of the Licensed Work a copy of this License and retain all
copyright and disclaimers.

Xiaomi provides the Licensed Work on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied, including, without
limitation, any warranties, undertakes, or conditions of TITLE, NO ERROR OR
OMISSION, CONTINUITY, RELIABILITY, NON-INFRINGEMENT, MERCHANTABILITY, or
FITNESS FOR A PARTICULAR PURPOSE. In any event, you are solely responsible
for any direct, indirect, special, incidental, or consequential damages or
losses arising from the use or inability to use the Licensed Work.

Xiaomi reserves all rights not expressly granted to you in this License.
Except for the rights expressly granted by Xiaomi under this License, Xiaomi
does not authorize you in any form to use the trademarks, copyrights, or other
forms of intellectual property rights of Xiaomi and its affiliates, including,
without limitation, without obtaining other written permission from Xiaomi, you
shall not use "Xiaomi", "Mijia" and other words related to Xiaomi or words that
may make the public associate with Xiaomi in any form to publicize or promote
the software or hardware devices that use the Licensed Work.

Xiaomi has the right to immediately terminate all your authorization under this
License in the event:
1. You assert patent invalidation, litigation, or other claims against patents
or other intellectual property rights of Xiaomi or its affiliates; or,
2. You make, have made, manufacture, sell, or offer to sell products that knock
off Xiaomi or its affiliates' products.

MIoT lan device control, only support MIoT SPEC-v2 WiFi devices.
"""


import json
import time
import asyncio
from dataclasses import dataclass
from enum import Enum, auto
import logging
import os
import queue
import random
import secrets
import socket
import struct
import threading
from typing import Callable, Optional, final
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

# pylint: disable=relative-beyond-top-level
from .miot_error import MIoTErrorCode
from .miot_ev import MIoTEventLoop, TimeoutHandle
from .miot_network import InterfaceStatus, MIoTNetwork, NetworkInfo
from .miot_mdns import MipsService, MipsServiceState
from .common import randomize_int, MIoTMatcher


_LOGGER = logging.getLogger(__name__)


class MIoTLanCmdType(Enum):
    """MIoT lan command."""
    DEINIT = 0
    CALL_API = auto()
    SUB_DEVICE_STATE = auto()
    UNSUB_DEVICE_STATE = auto()
    REG_BROADCAST = auto()
    UNREG_BROADCAST = auto()
    GET_DEV_LIST = auto()
    DEVICE_UPDATE = auto()
    DEVICE_DELETE = auto()
    NET_INFO_UPDATE = auto()
    NET_IFS_UPDATE = auto()
    OPTIONS_UPDATE = auto()


@dataclass
class MIoTLanCmd:
    """MIoT lan command."""
    type_: MIoTLanCmdType
    data: any


@dataclass
class MIoTLanCmdData:
    handler: Callable[[dict, any], None]
    handler_ctx: any
    timeout_ms: int


@dataclass
class MIoTLanGetDevListData(MIoTLanCmdData):
    ...


@dataclass
class MIoTLanCallApiData(MIoTLanCmdData):
    did: str
    msg: dict


class MIoTLanSendBroadcastData(MIoTLanCallApiData):
    ...


@dataclass
class MIoTLanUnregisterBroadcastData:
    key: str


@dataclass
class MIoTLanRegisterBroadcastData:
    key: str
    handler: Callable[[dict, any], None]
    handler_ctx: any


@dataclass
class MIoTLanUnsubDeviceState:
    key: str


@dataclass
class MIoTLanSubDeviceState:
    key: str
    handler: Callable[[str, dict, any], None]
    handler_ctx: any


@dataclass
class MIoTLanNetworkUpdateData:
    status: InterfaceStatus
    if_name: str


@dataclass
class MIoTLanRequestData:
    msg_id: int
    handler: Callable[[dict, any], None]
    handler_ctx: any
    timeout: TimeoutHandle


class MIoTLanDeviceState(Enum):
    FRESH = 0
    PING1 = auto()
    PING2 = auto()
    PING3 = auto()
    DEAD = auto()


class MIoTLanDevice:
    """MIoT lan device."""
    # pylint: disable=unused-argument
    OT_HEADER: int = 0x2131
    OT_HEADER_LEN: int = 32
    NETWORK_UNSTABLE_CNT_TH: int = 10
    NETWORK_UNSTABLE_TIME_TH: int = 120000
    NETWORK_UNSTABLE_RESUME_TH: int = 300
    FAST_PING_INTERVAL: int = 5000
    CONSTRUCT_STATE_PENDING: int = 15000
    KA_INTERVAL_MIN = 10000
    KA_INTERVAL_MAX = 50000

    did: str
    token: bytes
    cipher: Cipher
    ip: Optional[str]

    offset: int
    subscribed: bool
    sub_ts: int
    supported_wildcard_sub: bool

    _manager: any
    _if_name: Optional[str]
    _sub_locked: bool
    _state: MIoTLanDeviceState
    _online: bool
    _online_offline_history: list[dict[str, any]]
    _online_offline_timer: Optional[TimeoutHandle]

    _ka_timer: TimeoutHandle
    _ka_internal: int

    def __init__(
            self, manager: any,  did: str, token: str, ip: Optional[str] = None
    ) -> None:
        self._manager: MIoTLan = manager
        self.did = did
        self.token = bytes.fromhex(token)
        aes_key: bytes = self.__md5(self.token)
        aex_iv: bytes = self.__md5(aes_key + self.token)
        self.cipher = Cipher(
            algorithms.AES128(aes_key), modes.CBC(aex_iv), default_backend())
        self.ip = ip
        self.offset = 0
        self.subscribed = False
        self.sub_ts = 0
        self.supported_wildcard_sub = False
        self._if_name = None
        self._sub_locked = False
        self._state = MIoTLanDeviceState.DEAD
        self._online = False
        self._online_offline_history = []
        self._online_offline_timer = None

        def ka_init_handler(ctx: any) -> None:
            self._ka_internal = self.KA_INTERVAL_MIN
            self.__update_keep_alive(state=MIoTLanDeviceState.DEAD)
        self._ka_timer = self._manager.mev.set_timeout(
            randomize_int(self.CONSTRUCT_STATE_PENDING, 0.5),
            ka_init_handler, None)
        _LOGGER.debug('miot lan device add, %s', self.did)

    def keep_alive(self, ip: str, if_name: str) -> None:
        self.ip = ip
        if self._if_name != if_name:
            self._if_name = if_name
            _LOGGER.info(
                'device if_name change, %s, %s', self._if_name, self.did)
        self.__update_keep_alive(state=MIoTLanDeviceState.FRESH)

    @property
    def online(self) -> bool:
        return self._online

    @online.setter
    def online(self, online: bool) -> None:
        if self._online == online:
            return
        self._online = online
        self._manager.broadcast_device_state(
            did=self.did, state={
                'online': self._online, 'push_available': self.subscribed})

    @property
    def if_name(self) -> Optional[str]:
        return self._if_name

    def gen_packet(
        self, out_buffer: bytearray, clear_data: dict, did: str, offset: int
    ) -> int:
        clear_bytes = json.dumps(clear_data).encode('utf-8')
        padder = padding.PKCS7(algorithms.AES128.block_size).padder()
        padded_data = padder.update(clear_bytes) + padder.finalize()
        if len(padded_data) + self.OT_HEADER_LEN > len(out_buffer):
            raise ValueError('rpc too long')
        encryptor = self.cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        data_len: int = len(encrypted_data)+self.OT_HEADER_LEN
        out_buffer[:32] = struct.pack(
            '>HHQI16s', self.OT_HEADER, data_len, int(did), offset,
            self.token)
        out_buffer[32:data_len] = encrypted_data
        msg_md5: bytes = self.__md5(out_buffer[0:data_len])
        out_buffer[16:32] = msg_md5
        return data_len

    def decrypt_packet(self, encrypted_data: bytearray) -> dict:
        data_len: int = struct.unpack('>H', encrypted_data[2:4])[0]
        md5_orig: bytes = encrypted_data[16:32]
        encrypted_data[16:32] = self.token
        md5_calc: bytes = self.__md5(encrypted_data[0:data_len])
        if md5_orig != md5_calc:
            raise ValueError(f'invalid md5, {md5_orig}, {md5_calc}')
        decryptor = self.cipher.decryptor()
        decrypted_padded_data = decryptor.update(
            encrypted_data[32:data_len]) + decryptor.finalize()
        unpadder = padding.PKCS7(algorithms.AES128.block_size).unpadder()
        decrypted_data = unpadder.update(
            decrypted_padded_data) + unpadder.finalize()
        # Some device will add a redundant \0 at the end of JSON string
        decrypted_data = decrypted_data.rstrip(b'\x00')
        return json.loads(decrypted_data)

    def subscribe(self) -> None:
        if self._sub_locked:
            return
        self._sub_locked = True
        try:
            sub_ts: int = int(time.time())
            self._manager.send2device(
                did=self.did,
                msg={
                    'method': 'miIO.sub',
                    'params': {
                        'version': '2.0',
                        'did': self._manager.virtual_did,
                        'update_ts': sub_ts,
                        'sub_method': '.'
                    }
                },
                handler=self.__subscribe_handler,
                handler_ctx=sub_ts,
                timeout_ms=5000)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.error('subscribe device error, %s', err)

        self._sub_locked = False

    def unsubscribe(self) -> None:
        if not self.subscribed:
            return
        self._manager.send2device(
            did=self.did,
            msg={
                'method': 'miIO.unsub',
                'params': {
                    'version': '2.0',
                    'did': self._manager.virtual_did,
                    'update_ts': self.sub_ts or 0,
                    'sub_method': '.'
                }
            },
            handler=self.__unsubscribe_handler,
            timeout_ms=5000)
        self.subscribed = False
        self._manager.broadcast_device_state(
            did=self.did, state={
                'online': self._online, 'push_available': self.subscribed})

    def on_delete(self) -> None:
        if self._ka_timer:
            self._manager.mev.clear_timeout(self._ka_timer)
        if self._online_offline_timer:
            self._manager.mev.clear_timeout(self._online_offline_timer)
        self._manager = None
        self.cipher = None
        _LOGGER.debug('miot lan device delete, %s', self.did)

    def update_info(self, info: dict) -> None:
        if (
            'token' in info
            and len(info['token']) == 32
            and info['token'].upper() != self.token.hex().upper()
        ):
            # Update token
            self.token = bytes.fromhex(info['token'])
            aes_key: bytes = self.__md5(self.token)
            aex_iv: bytes = self.__md5(aes_key + self.token)
            self.cipher = Cipher(
                algorithms.AES128(aes_key),
                modes.CBC(aex_iv), default_backend())
            _LOGGER.debug('update token, %s', self.did)

    def __subscribe_handler(self, msg: dict, sub_ts: int) -> None:
        if (
            'result' not in msg
            or 'code' not in msg['result']
            or msg['result']['code'] != 0
        ):
            _LOGGER.error('subscribe device error, %s, %s', self.did, msg)
            return
        self.subscribed = True
        self.sub_ts = sub_ts
        self._manager.broadcast_device_state(
            did=self.did, state={
                'online': self._online, 'push_available': self.subscribed})
        _LOGGER.info('subscribe success, %s, %s', self._if_name, self.did)

    def __unsubscribe_handler(self, msg: dict, ctx: any) -> None:
        if (
            'result' not in msg
            or 'code' not in msg['result']
            or msg['result']['code'] != 0
        ):
            _LOGGER.error('unsubscribe device error, %s, %s', self.did, msg)
            return
        _LOGGER.info('unsubscribe success, %s, %s', self._if_name, self.did)

    def __update_keep_alive(self, state: MIoTLanDeviceState) -> None:
        last_state: MIoTLanDeviceState = self._state
        self._state = state
        if self._state != MIoTLanDeviceState.FRESH:
            _LOGGER.debug('device status, %s, %s', self.did, self._state)
        if self._ka_timer:
            self._manager.mev.clear_timeout(self._ka_timer)
            self._ka_timer = None
        match state:
            case MIoTLanDeviceState.FRESH:
                if last_state == MIoTLanDeviceState.DEAD:
                    self._ka_internal = self.KA_INTERVAL_MIN
                    self.__change_online(True)
                self._ka_timer = self._manager.mev.set_timeout(
                    self.__get_next_ka_timeout(), self.__update_keep_alive,
                    MIoTLanDeviceState.PING1)
            case (
                    MIoTLanDeviceState.PING1
                    | MIoTLanDeviceState.PING2
                    | MIoTLanDeviceState.PING3
            ):
                self._manager.ping(if_name=self._if_name, target_ip=self.ip)
                # Fast ping
                self._ka_timer = self._manager.mev.set_timeout(
                    self.FAST_PING_INTERVAL, self.__update_keep_alive,
                    MIoTLanDeviceState(state.value+1))
            case MIoTLanDeviceState.DEAD:
                if last_state == MIoTLanDeviceState.PING3:
                    self._ka_internal = self.KA_INTERVAL_MIN
                    self.__change_online(False)
            case _:
                _LOGGER.error('invalid state, %s', state)

    def __get_next_ka_timeout(self) -> int:
        self._ka_internal = min(self._ka_internal*2, self.KA_INTERVAL_MAX)
        return randomize_int(self._ka_internal, 0.1)

    def __change_online(self, online: bool) -> None:
        _LOGGER.info('change online, %s, %s', self.did, online)
        ts_now: int = int(time.time())
        self._online_offline_history.append({'ts': ts_now, 'online': online})
        if len(self._online_offline_history) > self.NETWORK_UNSTABLE_CNT_TH:
            self._online_offline_history.pop(0)
        if self._online_offline_timer:
            self._manager.mev.clear_timeout(self._online_offline_timer)
        if not online:
            self.online = False
        else:
            if (
                len(self._online_offline_history) < self.NETWORK_UNSTABLE_CNT_TH
                or (
                    ts_now - self._online_offline_history[0]['ts'] >
                    self.NETWORK_UNSTABLE_TIME_TH)
            ):
                self.online = True
            else:
                _LOGGER.info('unstable device detected, %s', self.did)
                self._online_offline_timer = self._manager.mev.set_timeout(
                    self.NETWORK_UNSTABLE_RESUME_TH,
                    self.__online_resume_handler, None)

    def __online_resume_handler(self, ctx: any) -> None:
        _LOGGER.info('unstable resume threshold past, %s', self.did)
        self.online = True

    def __md5(self, data: bytes) -> bytes:
        hasher = hashes.Hash(hashes.MD5(), default_backend())
        hasher.update(data)
        return hasher.finalize()


class MIoTLan:
    """MIoT lan device control."""
    # pylint: disable=unused-argument
    OT_HEADER: bytes = b'\x21\x31'
    OT_PORT: int = 54321
    OT_PROBE_LEN: int = 32
    OT_MSG_LEN: int = 1400
    OT_SUPPORT_WILDCARD_SUB: int = 0xFE

    OT_PROBE_INTERVAL_MIN: int = 5000
    OT_PROBE_INTERVAL_MAX: int = 45000

    _main_loop: asyncio.AbstractEventLoop
    _net_ifs: set[str]
    _network: MIoTNetwork
    _mips_service: MipsService
    _enable_subscribe: bool
    _lan_devices: dict[str, MIoTLanDevice]
    _virtual_did: str
    _probe_msg: bytes
    _write_buffer: bytearray
    _read_buffer: bytearray

    _mev: MIoTEventLoop
    _thread: threading.Thread
    _queue: queue.Queue
    _cmd_event_fd: os.eventfd

    _available_net_ifs: set[str]
    _broadcast_socks: dict[str, socket.socket]
    _local_port: Optional[int]
    _scan_timer: TimeoutHandle
    _last_scan_interval: Optional[int]
    _msg_id_counter: int
    _pending_requests: dict[int, MIoTLanRequestData]
    _device_msg_matcher: MIoTMatcher
    _device_state_sub_map: dict[str, MIoTLanSubDeviceState]
    _reply_msg_buffer: dict[str, TimeoutHandle]

    _lan_state_sub_map: dict[str, Callable[[bool], asyncio.Future]]
    _lan_ctrl_vote_map: dict[str, bool]

    _init_done: bool

    def __init__(
            self,
            net_ifs: list[str],
            network: MIoTNetwork,
            mips_service: MipsService,
            enable_subscribe: bool = False,
            virtual_did: Optional[int] = None,
            loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> None:
        if not network:
            raise ValueError('network is required')
        if not mips_service:
            raise ValueError('mips_service is required')
        self._main_loop = loop or asyncio.get_event_loop()
        self._net_ifs = set(net_ifs)
        self._network = network
        self._network.sub_network_info(
            key='miot_lan', handler=self.__on_network_info_change)
        self._mips_service = mips_service
        self._mips_service.sub_service_change(
            key='miot_lan', group_id='*',
            handler=self.__on_mips_service_change)
        self._enable_subscribe = enable_subscribe
        self._virtual_did = virtual_did or str(secrets.randbits(64))
        # Init socket probe message
        probe_bytes = bytearray(self.OT_PROBE_LEN)
        probe_bytes[:20] = (
            b'!1\x00\x20\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFFMDID')
        probe_bytes[20:28] = struct.pack('>Q', int(self._virtual_did))
        probe_bytes[28:32] = b'\x00\x00\x00\x00'
        self._probe_msg = bytes(probe_bytes)
        self._read_buffer = bytearray(self.OT_MSG_LEN)
        self._write_buffer = bytearray(self.OT_MSG_LEN)

        self._lan_devices = {}
        self._available_net_ifs = set()
        self._broadcast_socks = {}
        self._local_port = None
        self._scan_timer = None
        self._last_scan_interval = None
        self._msg_id_counter = int(random.random()*0x7FFFFFFF)
        self._pending_requests = {}
        self._device_msg_matcher = MIoTMatcher()
        self._device_state_sub_map = {}
        self._reply_msg_buffer = {}

        self._lan_state_sub_map = {}
        self._lan_ctrl_vote_map = {}

        self._init_done = False

        if (
            len(self._mips_service.get_services()) == 0
            and len(self._net_ifs) > 0
        ):
            _LOGGER.info('no central hub gateway service, init miot lan')
            self._main_loop.call_later(
                0, lambda: self._main_loop.create_task(
                    self.init_async()))

    @ property
    def virtual_did(self) -> str:
        return self._virtual_did

    @ property
    def mev(self) -> MIoTEventLoop:
        return self._mev

    @property
    def init_done(self) -> bool:
        return self._init_done

    async def init_async(self) -> None:
        if self._init_done:
            _LOGGER.info('miot lan already init')
            return
        if len(self._net_ifs) == 0:
            _LOGGER.info('no net_ifs')
            return
        if not any(self._lan_ctrl_vote_map.values()):
            _LOGGER.info('no vote for lan ctrl')
            return
        if len(self._mips_service.get_services()) > 0:
            _LOGGER.info('central hub gateway service exist')
            return
        for if_name in list(self._network.network_info.keys()):
            self._available_net_ifs.add(if_name)
        if len(self._available_net_ifs) == 0:
            _LOGGER.info('no available net_ifs')
            return
        if self._net_ifs.isdisjoint(self._available_net_ifs):
            _LOGGER.info('no valid net_ifs')
            return
        self._mev = MIoTEventLoop()
        self._queue = queue.Queue()
        self._cmd_event_fd = os.eventfd(0, os.O_NONBLOCK)
        self._mev.set_read_handler(
            self._cmd_event_fd, self.__cmd_read_handler, None)
        self._thread = threading.Thread(target=self.__lan_thread_handler)
        self._thread.name = 'miot_lan'
        self._thread.daemon = True
        self._thread.start()
        self._init_done = True
        for handler in list(self._lan_state_sub_map.values()):
            self._main_loop.create_task(handler(True))
        _LOGGER.info(
            'miot lan init, %s ,%s', self._net_ifs, self._available_net_ifs)

    async def deinit_async(self) -> None:
        if not self._init_done:
            _LOGGER.info('miot lan not init')
            return
        self._init_done = False
        self.__lan_send_cmd(MIoTLanCmdType.DEINIT, None)
        self._thread.join()

        self._lan_devices = {}
        self._broadcast_socks = {}
        self._local_port = None
        self._scan_timer = None
        self._last_scan_interval = None
        self._msg_id_counter = int(random.random()*0x7FFFFFFF)
        self._pending_requests = {}
        self._device_msg_matcher = MIoTMatcher()
        self._device_state_sub_map = {}
        self._reply_msg_buffer = {}
        for handler in list(self._lan_state_sub_map.values()):
            self._main_loop.create_task(handler(False))
        _LOGGER.info('miot lan deinit')

    async def update_net_ifs_async(self, net_ifs: list[str]) -> None:
        _LOGGER.info('update net_ifs, %s', net_ifs)
        if not isinstance(net_ifs, list):
            _LOGGER.error('invalid net_ifs, %s', net_ifs)
            return
        if len(net_ifs) == 0:
            # Deinit lan
            await self.deinit_async()
            self._net_ifs = set(net_ifs)
            return
        available_net_ifs = set()
        for if_name in list(self._network.network_info.keys()):
            available_net_ifs.add(if_name)
        if set(net_ifs).isdisjoint(available_net_ifs):
            _LOGGER.error('no valid net_ifs, %s', net_ifs)
            await self.deinit_async()
            self._net_ifs = set(net_ifs)
            self._available_net_ifs = available_net_ifs
            return
        if not self._init_done:
            self._net_ifs = set(net_ifs)
            await self.init_async()
            return
        self.__lan_send_cmd(
            cmd=MIoTLanCmdType.NET_IFS_UPDATE,
            data=net_ifs)

    async def vote_for_lan_ctrl_async(self, key: str, vote: bool) -> None:
        _LOGGER.info('vote for lan ctrl, %s, %s', key, vote)
        self._lan_ctrl_vote_map[key] = vote
        if not any(self._lan_ctrl_vote_map.values()):
            await self.deinit_async()
            return
        await self.init_async()

    async def update_subscribe_option(self, enable_subscribe: bool) -> None:
        _LOGGER.info('update subscribe option, %s', enable_subscribe)
        if not self._init_done:
            self._enable_subscribe = enable_subscribe
            return
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.OPTIONS_UPDATE,
            data={
                'enable_subscribe': enable_subscribe, })

    def update_devices(self, devices: dict[str, dict]) -> bool:
        _LOGGER.info('update devices, %s', devices)
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.DEVICE_UPDATE,
            data=devices)

    def delete_devices(self, devices: list[str]) -> bool:
        _LOGGER.info('delete devices, %s', devices)
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.DEVICE_DELETE,
            data=devices)

    def sub_lan_state(
        self, key: str, handler: Callable[[bool], asyncio.Future]
    ) -> None:
        self._lan_state_sub_map[key] = handler

    def unsub_lan_state(self, key: str) -> None:
        self._lan_state_sub_map.pop(key, None)

    @final
    def sub_device_state(
        self, key: str, handler: Callable[[str, dict, any], None],
        handler_ctx: any = None
    ) -> bool:
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.SUB_DEVICE_STATE,
            data=MIoTLanSubDeviceState(
                key=key, handler=handler, handler_ctx=handler_ctx))

    @final
    def unsub_device_state(self, key: str) -> bool:
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.UNSUB_DEVICE_STATE,
            data=MIoTLanUnsubDeviceState(key=key))

    @final
    def sub_prop(
        self, did: str, handler: Callable[[dict, any], None],
        siid: int = None, piid: int = None, handler_ctx: any = None
    ) -> bool:
        if not self._enable_subscribe:
            return False
        key = (
            f'{did}/p/'
            f'{"#" if siid is None or piid is None else f"{siid}/{piid}"}')
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.REG_BROADCAST,
            data=MIoTLanRegisterBroadcastData(
                key=key, handler=handler, handler_ctx=handler_ctx))

    @final
    def unsub_prop(self, did: str, siid: int = None, piid: int = None) -> bool:
        if not self._enable_subscribe:
            return False
        key = (
            f'{did}/p/'
            f'{"#" if siid is None or piid is None else f"{siid}/{piid}"}')
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.UNREG_BROADCAST,
            data=MIoTLanUnregisterBroadcastData(key=key))

    @final
    def sub_event(
        self, did: str, handler: Callable[[dict, any], None],
        siid: int = None, eiid: int = None, handler_ctx: any = None
    ) -> bool:
        if not self._enable_subscribe:
            return False
        key = (
            f'{did}/e/'
            f'{"#" if siid is None or eiid is None else f"{siid}/{eiid}"}')
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.REG_BROADCAST,
            data=MIoTLanRegisterBroadcastData(
                key=key, handler=handler, handler_ctx=handler_ctx))

    @final
    def unsub_event(self, did: str, siid: int = None, eiid: int = None) -> bool:
        if not self._enable_subscribe:
            return False
        key = (
            f'{did}/e/'
            f'{"#" if siid is None or eiid is None else f"{siid}/{eiid}"}')
        return self.__lan_send_cmd(
            cmd=MIoTLanCmdType.UNREG_BROADCAST,
            data=MIoTLanUnregisterBroadcastData(key=key))

    @final
    async def get_prop_async(
        self, did: str, siid: int, piid: int, timeout_ms: int = 10000
    ) -> any:
        result_obj = await self.__call_api_async(
            did=did, msg={
                'method': 'get_properties',
                'params': [{'did': did, 'siid': siid, 'piid': piid}]
            }, timeout_ms=timeout_ms)

        if (
            result_obj and 'result' in result_obj
            and len(result_obj['result']) == 1
            and 'did' in result_obj['result'][0]
            and result_obj['result'][0]['did'] == did
        ):
            return result_obj['result'][0].get('value', None)
        return None

    @final
    async def set_prop_async(
        self, did: str, siid: int, piid: int, value: any,
        timeout_ms: int = 10000
    ) -> dict:
        result_obj = await self.__call_api_async(
            did=did, msg={
                'method': 'set_properties',
                'params': [{
                    'did': did, 'siid': siid, 'piid': piid, 'value': value}]
            }, timeout_ms=timeout_ms)
        if result_obj:
            if (
                'result' in result_obj
                and len(result_obj['result']) == 1
                and 'did' in result_obj['result'][0]
                and result_obj['result'][0]['did'] == did
                and 'code' in result_obj['result'][0]
            ):
                return result_obj['result'][0]
            if 'code' in result_obj:
                return result_obj
        return {
            'code': MIoTErrorCode.CODE_INTERNAL_ERROR.value,
            'message': 'Invalid result'}

    @final
    async def action_async(
        self, did: str, siid: int, aiid: int, in_list: list,
        timeout_ms: int = 10000
    ) -> dict:
        result_obj = await self.__call_api_async(
            did=did, msg={
                'method': 'action',
                'params': {
                    'did': did, 'siid': siid, 'aiid': aiid, 'in': in_list}
            }, timeout_ms=timeout_ms)
        if result_obj:
            if 'result' in result_obj and 'code' in result_obj['result']:
                return result_obj['result']
            if 'code' in result_obj:
                return result_obj
        return {
            'code': MIoTErrorCode.CODE_INTERNAL_ERROR.value,
            'message': 'Invalid result'}

    @final
    async def get_dev_list_async(
        self, timeout_ms: int = 10000
    ) -> dict[str, dict]:
        if not self._init_done:
            return {}

        def get_device_list_handler(msg: dict, fut: asyncio.Future):
            self._main_loop.call_soon_threadsafe(
                fut.set_result, msg)

        fut: asyncio.Future = self._main_loop.create_future()
        if self.__lan_send_cmd(
            MIoTLanCmdType.GET_DEV_LIST,
            MIoTLanGetDevListData(
                handler=get_device_list_handler,
                handler_ctx=fut,
                timeout_ms=timeout_ms)):
            return await fut
        _LOGGER.error('get_dev_list_async error, send cmd failed')
        fut.set_result({})
        return await fut

    def ping(self, if_name: str, target_ip: str) -> None:
        if not target_ip:
            return
        self.__sendto(
            if_name=if_name, data=self._probe_msg, address=target_ip,
            port=self.OT_PORT)

    def send2device(
        self, did: str,
        msg: dict,
        handler: Optional[Callable[[dict, any], None]] = None,
        handler_ctx: any = None,
        timeout_ms: Optional[int] = None
    ) -> None:
        if timeout_ms and not handler:
            raise ValueError('handler is required when timeout_ms is set')
        device: MIoTLanDevice = self._lan_devices.get(did)
        if not device:
            raise ValueError('invalid device')
        if not device.cipher:
            raise ValueError('invalid device cipher')
        if not device.if_name:
            raise ValueError('invalid device if_name')
        if not device.ip:
            raise ValueError('invalid device ip')
        in_msg = {'id': self.__gen_msg_id(), **msg}
        msg_len = device.gen_packet(
            out_buffer=self._write_buffer,
            clear_data=in_msg,
            did=did,
            offset=int(time.time())-device.offset)

        return self.make_request(
            msg_id=in_msg['id'],
            msg=self._write_buffer[0: msg_len],
            if_name=device.if_name,
            ip=device.ip,
            handler=handler,
            handler_ctx=handler_ctx,
            timeout_ms=timeout_ms)

    def make_request(
        self,
        msg_id: int,
        msg: bytearray,
        if_name: str,
        ip: str,
        handler: Callable[[dict, any], None],
        handler_ctx: any = None,
        timeout_ms: Optional[int] = None
    ) -> None:
        def request_timeout_handler(req_data: MIoTLanRequestData):
            self._pending_requests.pop(req_data.msg_id, None)
            if req_data:
                req_data.handler({
                    'code': MIoTErrorCode.CODE_TIMEOUT.value,
                    'error': 'timeout'},
                    req_data.handler_ctx)

        timer: Optional[TimeoutHandle] = None
        request_data = MIoTLanRequestData(
            msg_id=msg_id,
            handler=handler,
            handler_ctx=handler_ctx,
            timeout=timer)
        if timeout_ms:
            timer = self._mev.set_timeout(
                timeout_ms, request_timeout_handler, request_data)
            request_data.timeout = timer
        self._pending_requests[msg_id] = request_data
        self.__sendto(if_name=if_name, data=msg, address=ip, port=self.OT_PORT)

    def broadcast_device_state(self, did: str, state: dict) -> None:
        for handler in self._device_state_sub_map.values():
            self._main_loop.call_soon_threadsafe(
                self._main_loop.create_task,
                handler.handler(did, state, handler.handler_ctx))

    def __gen_msg_id(self) -> int:
        if not self._msg_id_counter:
            self._msg_id_counter = int(random.random()*0x7FFFFFFF)
        self._msg_id_counter += 1
        if self._msg_id_counter > 0x80000000:
            self._msg_id_counter = 1
        return self._msg_id_counter

    def __lan_send_cmd(self, cmd: MIoTLanCmd, data: any) -> bool:
        try:
            self._queue.put(MIoTLanCmd(type_=cmd, data=data))
            os.eventfd_write(self._cmd_event_fd, 1)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.error('send cmd error, %s, %s', cmd, err)
        return False

    async def __call_api_async(
        self, did: str, msg: dict, timeout_ms: int = 10000
    ) -> dict:
        def call_api_handler(msg: dict, fut: asyncio.Future):
            self._main_loop.call_soon_threadsafe(
                fut.set_result, msg)

        fut: asyncio.Future = self._main_loop.create_future()
        if self.__lan_send_cmd(
                cmd=MIoTLanCmdType.CALL_API,
                data=MIoTLanCallApiData(
                    did=did,
                    msg=msg,
                    handler=call_api_handler,
                    handler_ctx=fut,
                    timeout_ms=timeout_ms)):
            return await fut

        fut.set_result({
            'code': MIoTErrorCode.CODE_UNAVAILABLE.value,
            'error': 'send cmd error'})
        return await fut

    def __lan_thread_handler(self) -> None:
        _LOGGER.info('miot lan thread start')
        self.__init_socket()
        # Create scan devices timer
        self._scan_timer = self._mev.set_timeout(
            int(3000*random.random()), self.__scan_devices, None)
        self._mev.loop_forever()
        _LOGGER.info('miot lan thread exit')

    def __cmd_read_handler(self, ctx: any) -> None:
        fd_value = os.eventfd_read(self._cmd_event_fd)
        if fd_value == 0:
            return
        while not self._queue.empty():
            mips_cmd: MIoTLanCmd = self._queue.get(block=False)
            if mips_cmd.type_ == MIoTLanCmdType.CALL_API:
                call_api_data: MIoTLanCallApiData = mips_cmd.data
                try:
                    self.send2device(
                        did=call_api_data.did,
                        msg={'from': 'ha.xiaomi_home', **call_api_data.msg},
                        handler=call_api_data.handler,
                        handler_ctx=call_api_data.handler_ctx,
                        timeout_ms=call_api_data.timeout_ms)
                except Exception as err:  # pylint: disable=broad-exception-caught
                    _LOGGER.error('send2device error, %s', err)
                    call_api_data.handler({
                        'code': MIoTErrorCode.CODE_INTERNAL_ERROR.value,
                        'error': str(err)},
                        call_api_data.handler_ctx)
            elif mips_cmd.type_ == MIoTLanCmdType.SUB_DEVICE_STATE:
                sub_data: MIoTLanSubDeviceState = mips_cmd.data
                self._device_state_sub_map[sub_data.key] = sub_data
            elif mips_cmd.type_ == MIoTLanCmdType.UNSUB_DEVICE_STATE:
                sub_data: MIoTLanUnsubDeviceState = mips_cmd.data
                self._device_state_sub_map.pop(sub_data.key, None)
            elif mips_cmd.type_ == MIoTLanCmdType.REG_BROADCAST:
                reg_data: MIoTLanRegisterBroadcastData = mips_cmd.data
                self._device_msg_matcher[reg_data.key] = reg_data
                _LOGGER.debug('lan register broadcast, %s', reg_data.key)
            elif mips_cmd.type_ == MIoTLanCmdType.UNREG_BROADCAST:
                unreg_data: MIoTLanUnregisterBroadcastData = mips_cmd.data
                if self._device_msg_matcher.get(topic=unreg_data.key):
                    del self._device_msg_matcher[unreg_data.key]
                _LOGGER.debug('lan unregister broadcast, %s', unreg_data.key)
            elif mips_cmd.type_ == MIoTLanCmdType.GET_DEV_LIST:
                get_dev_list_data: MIoTLanGetDevListData = mips_cmd.data
                dev_list = {
                    device.did: {
                        'online': device.online,
                        'push_available': device.subscribed
                    }
                    for device in self._lan_devices.values()
                    if device.online}
                get_dev_list_data.handler(
                    dev_list, get_dev_list_data.handler_ctx)
            elif mips_cmd.type_ == MIoTLanCmdType.DEVICE_UPDATE:
                devices: dict[str, dict] = mips_cmd.data
                for did, info in devices.items():
                    if did not in self._lan_devices:
                        if 'token' not in info:
                            _LOGGER.error(
                                'token not found, %s, %s', did, info)
                            continue
                        if len(info['token']) != 32:
                            _LOGGER.error(
                                'invalid device token, %s, %s', did, info)
                            continue
                        self._lan_devices[did] = MIoTLanDevice(
                            manager=self, did=did, token=info['token'],
                            ip=info.get('ip', None))
                    else:
                        self._lan_devices[did].update_info(info)
            elif mips_cmd.type_ == MIoTLanCmdType.DEVICE_DELETE:
                device_dids: list[str] = mips_cmd.data
                for did in device_dids:
                    lan_device = self._lan_devices.pop(did, None)
                    if not lan_device:
                        continue
                    lan_device.on_delete()
            elif mips_cmd.type_ == MIoTLanCmdType.NET_INFO_UPDATE:
                net_data: MIoTLanNetworkUpdateData = mips_cmd.data
                if net_data.status == InterfaceStatus.ADD:
                    self._available_net_ifs.add(net_data.if_name)
                    if net_data.if_name in self._net_ifs:
                        self.__create_socket(if_name=net_data.if_name)
                elif net_data.status == InterfaceStatus.REMOVE:
                    self._available_net_ifs.remove(net_data.if_name)
                    self.__destroy_socket(if_name=net_data.if_name)
            elif mips_cmd.type_ == MIoTLanCmdType.NET_IFS_UPDATE:
                net_ifs: list[str] = mips_cmd.data
                if self._net_ifs != set(net_ifs):
                    self._net_ifs = set(net_ifs)
                    for if_name in self._net_ifs:
                        self.__create_socket(if_name=if_name)
                    for if_name in list(self._broadcast_socks.keys()):
                        if if_name not in self._net_ifs:
                            self.__destroy_socket(if_name=if_name)
            elif mips_cmd.type_ == MIoTLanCmdType.OPTIONS_UPDATE:
                options: dict = mips_cmd.data
                if 'enable_subscribe' in options:
                    if options['enable_subscribe'] != self._enable_subscribe:
                        self._enable_subscribe = options['enable_subscribe']
                        if not self._enable_subscribe:
                            # Unsubscribe all
                            for device in self._lan_devices.values():
                                device.unsubscribe()
            elif mips_cmd.type_ == MIoTLanCmdType.DEINIT:
                # stop the thread
                if self._scan_timer:
                    self._mev.clear_timeout(self._scan_timer)
                    self._scan_timer = None
                for device in self._lan_devices.values():
                    device.on_delete()
                self._lan_devices.clear()
                for req_data in self._pending_requests.values():
                    self._mev.clear_timeout(req_data.timeout)
                self._pending_requests.clear()
                for timer in self._reply_msg_buffer.values():
                    self._mev.clear_timeout(timer)
                self._reply_msg_buffer.clear()
                self._device_msg_matcher = MIoTMatcher()
                self.__deinit_socket()
                self._mev.loop_stop()

    def __init_socket(self) -> None:
        self.__deinit_socket()
        for if_name in self._net_ifs:
            if if_name not in self._available_net_ifs:
                return
            self.__create_socket(if_name=if_name)

    def __create_socket(self, if_name: str) -> None:
        if if_name in self._broadcast_socks:
            _LOGGER.info('socket already created, %s', if_name)
            return
        # Create socket
        try:
            sock = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Set SO_BINDTODEVICE
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_BINDTODEVICE, if_name.encode())
            sock.bind(('', self._local_port or 0))
            self._mev.set_read_handler(
                sock.fileno(), self.__socket_read_handler, (if_name, sock))
            self._broadcast_socks[if_name] = sock
            self._local_port = self._local_port or sock.getsockname()[1]
            _LOGGER.info(
                'created socket, %s, %s', if_name, self._local_port)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.error('create socket error, %s, %s', if_name, err)

    def __deinit_socket(self) -> None:
        for if_name in list(self._broadcast_socks.keys()):
            self.__destroy_socket(if_name)
        self._broadcast_socks.clear()

    def __destroy_socket(self, if_name: str) -> None:
        sock = self._broadcast_socks.pop(if_name, None)
        if not sock:
            return
        self._mev.set_read_handler(sock.fileno(), None, None)
        sock.close()
        _LOGGER.info('destroyed socket, %s', if_name)

    def __socket_read_handler(self, ctx: tuple[str, socket.socket]) -> None:
        try:
            data_len, addr = ctx[1].recvfrom_into(
                self._read_buffer, self.OT_MSG_LEN, socket.MSG_DONTWAIT)
            if data_len < 0:
                # Socket error
                _LOGGER.error('socket read error, %s, %s', ctx[0], data_len)
                return
            if addr[1] != self.OT_PORT:
                # Not ot msg
                return
            self.__raw_message_handler(
                self._read_buffer[:data_len], data_len, addr[0], ctx[0])
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.error('socket read handler error, %s', err)

    def __raw_message_handler(
        self, data: bytearray, data_len: int, ip: str, if_name: str
    ) -> None:
        if data[:2] != self.OT_HEADER:
            return
        # Keep alive message
        did: str = str(struct.unpack('>Q', data[4:12])[0])
        device: MIoTLanDevice = self._lan_devices.get(did)
        if not device:
            return
        timestamp: int = struct.unpack('>I', data[12:16])[0]
        device.offset = int(time.time()) - timestamp
        # Keep alive if this is a probe
        if data_len == self.OT_PROBE_LEN or device.subscribed:
            device.keep_alive(ip=ip, if_name=if_name)
        # Manage device subscribe status
        if (
            self._enable_subscribe
            and data_len == self.OT_PROBE_LEN
            and data[16:20] == b'MSUB'
            and data[24:27] == b'PUB'
        ):
            device.supported_wildcard_sub = (
                int(data[28]) == self.OT_SUPPORT_WILDCARD_SUB)
            sub_ts = struct.unpack('>I', data[20:24])[0]
            sub_type = int(data[27])
            if (
                device.supported_wildcard_sub
                and sub_type in [0, 1, 4]
                and sub_ts != device.sub_ts
            ):
                device.subscribed = False
                device.subscribe()
        if data_len > self.OT_PROBE_LEN:
            # handle device message
            try:
                decrypted_data = device.decrypt_packet(data)
                self.__message_handler(did, decrypted_data)
            except Exception as err:   # pylint: disable=broad-exception-caught
                _LOGGER.error('decrypt packet error, %s, %s', did, err)
                return

    def __message_handler(self, did: str, msg: dict) -> None:
        if 'id' not in msg:
            _LOGGER.warning('invalid message, no id, %s, %s', did, msg)
            return
        # Reply
        req: MIoTLanRequestData = self._pending_requests.pop(msg['id'], None)
        if req:
            self._mev.clear_timeout(req.timeout)
            self._main_loop.call_soon_threadsafe(
                req.handler, msg, req.handler_ctx)
            return
        # Handle up link message
        if 'method' not in msg or 'params' not in msg:
            _LOGGER.debug(
                'invalid message, no method or params, %s, %s', did, msg)
            return
        # Filter dup message
        if self.__filter_dup_message(did, msg['id']):
            self.send2device(
                did=did, msg={'id': msg['id'], 'result': {'code': 0}})
            return
        _LOGGER.debug('lan message, %s, %s', did, msg)
        if msg['method'] == 'properties_changed':
            for param in msg['params']:
                if 'siid' not in param and 'piid' not in param:
                    _LOGGER.debug(
                        'invalid message, no siid or piid, %s, %s', did, msg)
                    continue
                key = f'{did}/p/{param["siid"]}/{param["piid"]}'
                subs: list[MIoTLanRegisterBroadcastData] = list(
                    self._device_msg_matcher.iter_match(key))
                for sub in subs:
                    self._main_loop.call_soon_threadsafe(
                        sub.handler, param, sub.handler_ctx)
        elif (
                msg['method'] == 'event_occured'
                and 'siid' in msg['params']
                and 'eiid' in msg['params']
        ):
            key = f'{did}/e/{msg["params"]["siid"]}/{msg["params"]["eiid"]}'
            subs: list[MIoTLanRegisterBroadcastData] = list(
                self._device_msg_matcher.iter_match(key))
            for sub in subs:
                self._main_loop.call_soon_threadsafe(
                    sub.handler, msg['params'], sub.handler_ctx)
        else:
            _LOGGER.debug(
                'invalid message, unknown method, %s, %s', did, msg)
        # Reply
        self.send2device(
            did=did, msg={'id': msg['id'], 'result': {'code': 0}})

    def __filter_dup_message(self, did: str, msg_id: int) -> bool:
        filter_id = f'{did}.{msg_id}'
        if filter_id in self._reply_msg_buffer:
            return True
        self._reply_msg_buffer[filter_id] = self._mev.set_timeout(
            5000,
            lambda filter_id: self._reply_msg_buffer.pop(filter_id, None),
            filter_id)

    def __sendto(
        self, if_name: str, data: bytes, address: str, port: int
    ) -> None:
        if address == '255.255.255.255':
            # Broadcast
            for if_n, sock in self._broadcast_socks.items():
                _LOGGER.debug('send broadcast, %s', if_n)
                sock.sendto(data, socket.MSG_DONTWAIT, (address, port))
        else:
            # Unicast
            sock = self._broadcast_socks.get(if_name, None)
            if not sock:
                _LOGGER.error('invalid socket, %s', if_name)
                return
            sock.sendto(data, socket.MSG_DONTWAIT, (address, port))

    def __scan_devices(self, ctx: any) -> None:
        if self._scan_timer:
            self._mev.clear_timeout(self._scan_timer)
        # Scan devices
        self.ping(if_name=None, target_ip='255.255.255.255')
        scan_time = self.__get_next_scan_time()
        self._scan_timer = self._mev.set_timeout(
            scan_time, self.__scan_devices, None)
        _LOGGER.debug('next scan time: %sms', scan_time)

    def __get_next_scan_time(self) -> int:
        if not self._last_scan_interval:
            self._last_scan_interval = self.OT_PROBE_INTERVAL_MIN
        self._last_scan_interval = min(
            self._last_scan_interval*2, self.OT_PROBE_INTERVAL_MAX)
        return self._last_scan_interval

    async def __on_network_info_change(
        self,
        status: InterfaceStatus,
        info: NetworkInfo
    ) -> None:
        _LOGGER.info(
            'on network info change, status: %s, info: %s', status, info)
        available_net_ifs = set()
        for if_name in list(self._network.network_info.keys()):
            available_net_ifs.add(if_name)
        if len(available_net_ifs) == 0:
            await self.deinit_async()
            self._available_net_ifs = available_net_ifs
            return
        if self._net_ifs.isdisjoint(available_net_ifs):
            _LOGGER.info('no valid net_ifs')
            await self.deinit_async()
            self._available_net_ifs = available_net_ifs
            return
        if not self._init_done:
            self._available_net_ifs = available_net_ifs
            await self.init_async()
            return
        self.__lan_send_cmd(
            MIoTLanCmdType.NET_INFO_UPDATE, MIoTLanNetworkUpdateData(
                status=status, if_name=info.name))

    async def __on_mips_service_change(
        self, group_id: str,  state: MipsServiceState, data: dict
    ) -> None:
        _LOGGER.info(
            'on mips service change, %s, %s, %s',  group_id, state, data)
        if len(self._mips_service.get_services()) > 0:
            _LOGGER.info('find central service, deinit miot lan')
            await self.deinit_async()
        else:
            _LOGGER.info('no central service, init miot lan')
            await self.init_async()
