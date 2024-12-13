# -*- coding: utf-8 -*-
"""Unit test for miot_ev.py."""
import os
import pytest

# pylint: disable=import-outside-toplevel, disable=unused-argument


@pytest.mark.github
def test_mev_timer_and_fd():
    from miot.miot_ev import MIoTEventLoop, TimeoutHandle

    mev = MIoTEventLoop()
    assert mev
    event_fd: os.eventfd = os.eventfd(0, os.O_NONBLOCK)
    assert event_fd
    timer4: TimeoutHandle = None

    def event_handler(event_fd):
        value: int = os.eventfd_read(event_fd)
        if value == 1:
            mev.clear_timeout(timer4)
            print('cancel timer4')
        elif value == 2:
            print('event write twice in a row')
        elif value == 3:
            mev.set_read_handler(event_fd, None, None)
            os.close(event_fd)
            event_fd = None
            print('close event fd')

    def timer1_handler(event_fd):
        os.eventfd_write(event_fd, 1)

    def timer2_handler(event_fd):
        os.eventfd_write(event_fd, 1)
        os.eventfd_write(event_fd, 1)

    def timer3_handler(event_fd):
        os.eventfd_write(event_fd, 3)

    def timer4_handler(event_fd):
        raise ValueError('unreachable code')

    mev.set_read_handler(
        event_fd, event_handler, event_fd)

    mev.set_timeout(500, timer1_handler, event_fd)
    mev.set_timeout(1000, timer2_handler, event_fd)
    mev.set_timeout(1500, timer3_handler, event_fd)
    timer4 = mev.set_timeout(2000, timer4_handler, event_fd)

    mev.loop_forever()
    # Loop will exit when there are no timers or fd handlers.
    mev.loop_stop()
