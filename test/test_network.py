# -*- coding: utf-8 -*-
"""Unit test for miot_network.py."""
import pytest
import asyncio

# pylint: disable=import-outside-toplevel, unused-argument


@pytest.mark.asyncio
async def test_network_monitor_loop_async():
    from miot.miot_network import MIoTNetwork, InterfaceStatus, NetworkInfo
    miot_net = MIoTNetwork()

    async def on_network_status_changed(status: bool):
        print(f'on_network_status_changed, {status}')
    miot_net.sub_network_status(key='test', handler=on_network_status_changed)

    async def on_network_info_changed(
            status: InterfaceStatus, info: NetworkInfo):
        print(f'on_network_info_changed, {status}, {info}')
    miot_net.sub_network_info(key='test', handler=on_network_info_changed)

    await miot_net.init_async(3)
    await asyncio.sleep(3)
    print(f'net status: {miot_net.network_status}')
    print(f'net info: {miot_net.network_info}')
    await miot_net.deinit_async()
