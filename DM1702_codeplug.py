# -*- coding: utf-8 -*-

from __future__ import print_function


from struct import *
from array import array
from DM1702_contact import contacts, contact

DATA_map = {
#    0x00: 'FW_info',
#    0x01: 'Meta',
    0x02: 0x02, #Calibration
    0x03: 0x16, 0x04: 0x24, 0x05: 0x04, 0x06: 0x45, 0x07: 0x0b, 0x08: 0x11,
    0x09: 0x01, 0x0a: 0x0a, 0x0b: 0x13, 0x0c: 0x12, 0x0d: 0x03, 0x0e: 0x06,
    0x0f: 0x17, 0x10: 0x18, 0x11: 0x19, 0x12: 0x1a, 0x13: 0x1b, 0x14: 0x1c,
    0x15: 0x1d, 0x16: 0x1e, 0x17: 0x1f, 0x18: 0x20, 0x19: 0x21, 0x1a: 0x22,
    0x1b: 0x23, 0x1c: 0x25, 0x1d: 0x26, 0x1e: 0x27, 0x1f: 0x28, 0x20: 0x29,
    0x21: 0x2a, 0x22: 0x2b, 0x23: 0x2c, 0x24: None, 0x25: 0x3f, 0x26: 0x40,
    0x27: 0x41, 0x28: 0x42, 0x29: 0x43, 0x2a: 0x44, 0x2b: 0x46, 0x2c: 0x47,
    0x2d: 0x48, 0x2e: 0x49, 0x2f: 0x4a, 0x30: 0x4b, 0x31: 0x4c, 0x32: 0x4d,
    0x33: 0x4e, 0x34: 0x4f, 0x35: 0x50, 0x36: 0x51, 0x37: 0x52, 0x38: 0x53,
    0x39: 0x54, 0x3a: 0x55, 0x3b: 0x56
}