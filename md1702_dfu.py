#!/usr/bin/env python2
# -*- coding: utf-8 -*-


# Copyright 2010, 2011 Michael Ossmann
# Copyright 2015 Travis Goodspeed
# Copyright 2019 Pavel Moravec
#
# This file was based on md380-tools project file by Travis Goodsped,
# forked from Project Ubertooth as a DFU client for the TYT MD380 radio
# for Baofeng MD1702, an amateur dual-band radio for the DMR protocol.
# This script implements the poorly understood communication protocol
# unique to the MD1702.


from __future__ import print_function

import sys
import time

import usb.core
import os.path
import usb.core

from DM1702_DFU import DM1702_DFU, Versions
from DM1702_codeplug import DATA_map
from array import array

# The tricky thing is that *TWO* different applications all show up
# as this same VID/PID pair.
#
# 1. The run-time DFU interface.
# 2. The bootloader at 0x08000000
md1702_vendor = 0x0483
md1702_product = 0x5780

verbose_err = True

# flash_config = 0x08004000
# application = 0x08008000

# bootloader= 0x08000000
# ram_offset = 0x20000000
# bootloader_size   = 0x00004000

def hexdump(string):
    """God awful hex dump function for testing."""
    buf = ""
    i = 0
    for c in string:
        buf += "%02x" % c
        i += 1
        if i & 3 == 0:
            buf += " "
        if i & 0xf == 0:
            buf += "   "
        if i & 0x1f == 0:
            buf += "\n"

    print(buf)


def upload_config(dfu, filename):
    """Dumps the config block at 0x8004000."""
    block_size = 0x4000

    f = None
    if filename is not None:
        f = open(filename, 'wb')

    print("Dumping config.")
    try:
        data = dfu.upload(0, block_size)
        if f is not None:
            f.write(data)
        else:
            hexdump(data)

    finally:
        print("Done.")

def display_versions(dfu):
    """Dumps the version information from radio."""
    for i in [ 'FWVersion', 'RefDate', 'DataFormat', 'GPSFormat', 'CPSFormat' ] :
        print("%s= %s"  % (i + (' ' * (12-len(i))), dfu.to_str(dfu.verify(Versions[i]))))

    for i in [ 'Voices', 'HZKFont', 'Recordings', 'Settings', 'Logo', 'Unknown1' ]:
        start, end = dfu.verify_addrs(Versions[i])
        print("%s= 0x%06x - 0x%06x "  % (i+ (' ' * (12-len(i))), start, end ))
    dfu.enter_spi_usb_mode()
    print('DeviceID    = 0x%s' % dfu.hd(dfu.verify(Versions['DeviceID'])))

def upload_firmware(dfu, filename):
    """Dumps the firmware at 0x8008000."""
    fw_addr = 0x4000 #Block after config
    fw_size = 0xF8000

    f = None
    if filename is not None:
        f = open(filename, 'wb')

    print("Dumping firmware.")
    try:
        data = dfu.upload(fw_addr, fw_size)
        if f is not None:
            f.write(data)
        else:
            hexdump(data)

    finally:
        f.close()

def upload_all(dfu, filename, start=0, end=0xFFFFFF):
    """Dumps all SPI flash data, stores even partial results."""
    f = open(filename, 'wb')
    try:
        for part in range(start, end, dfu.sector_size):
            #print ("Part %06x end %06x" % (part,part+dfu.sector_size))
            data = dfu.upload_spi(part, dfu.sector_size, crop=False, silent=True)
            if f is not None:
                f.write(data)
                f.flush()
                sys.stdout.write('.')
                sys.stdout.flush()
            else:
                hexdump(data)
        sys.stdout.write('\n')
        sys.stdout.flush()
    finally:
        f.close()

def upload(dfu, filename, start=0, end=0xFFFFFF, crop=True):
    """Dumps the SPI flash data for given range."""
    f = open(filename, 'wb')
    try:
        data = dfu.upload_spi(start, end-start+1, crop=crop)
        if f is not None:
            f.write(data)
        else:
            hexdump(data)

    finally:
        f.close()

def upload_codeplug(dfu, filename, extra=False):
    """Dumps the SPI CODEPLUG data from SPI flash, searches in given range."""
    f = open(filename, 'wb')
    if f is None:
        sys.stderr.write("Writing to file %s failed, giving up\n" % filename)
        return
    try:
        buff = array('B', [])
        for addr in [0, 0x10, 0x20]:
            dx = dfu.verify(Versions['Custom'], 0xa, addr)
            buff += dx
            buff += array('B', [0] * (0x10 - len(dx)))
        sys.stdout.write('.')
        sys.stdout.flush()
        buff += array('B', [0] * (dfu.sector_size + 0x10 - len(buff)))
        buff += dfu.upload(0, 0x1000)
        buff = buff[:dfu.sector_size+0x110]
        buff += array('B', [0] * (2*dfu.sector_size - len(buff)))
        f.write(buff)
        f.flush()
        dfu.enter_spi_usb_mode()
        sector_map = dfu.get_cp_map()
        sys.stdout.write('+')
        sys.stdout.flush()
        done = []
        for idx in range(2,max(DATA_map)+1):
            if DATA_map[idx] is None:
                f.write(array('B', [0] * dfu.sector_size))
            elif DATA_map[idx] in sector_map:
                part = sector_map[DATA_map[idx]] * dfu.sector_size
                data = dfu.upload_spi(part, dfu.sector_size, crop=False, silent=True)
                sys.stdout.write('.')
                sys.stdout.flush()
                if data is None or len(data) != dfu.sector_size:
                    sys.stderr.write("Getting data block 0x%02x failed, giving up\n" % part/dfu.sector_size)
                    f.close()
                    os.remove(filename)
                    return
                f.write(data)
            else:
                sys.stderr.write("Data block with ID 0x%02x does not exist, giving up\n" % DATA_map[idx])
                f.close()
                os.remove(filename)
                return
            done.append(DATA_map[idx])
        if extra:
            #print(sector_map)
            for idx in sector_map:
                if idx not in done:
                    #print("Extra sector 0x%02x" % idx)
                    part = sector_map[idx] * dfu.sector_size
                    data = dfu.upload_spi(part, dfu.sector_size, crop=False, silent=True)
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    if data is not None and len(data) == dfu.sector_size:
                        f.write(data)
                    else:
                        sys.stderr.write("Skipping incomplete/missing data block 0x%02x for ID 0x%02x\n" % (sector_map[idx], idx))
            #    if DATA_map
        sys.stdout.write('\n')
        sys.stdout.flush()
    finally:
        f.close()

def download_codeplug(dfu, filename, calib=False):
    """Uploads the SPI CODEPLUG data to flash for given range."""
    f = open(filename, 'rb')
    if f is None:
        sys.stderr.write("Reading from data file %s failed, giving up\n" % filename)
        return
    try:
        data = array('B', f.read())
        if len(data) != (max(DATA_map)+1) * dfu.sector_size:
            print('According to the file size, this is not the official CPS DATA codeplug, aborting.')
            return
        dfu.enter_spi_usb_mode()
        sector_map = dfu.get_cp_map()
        for sec in range(2,max(DATA_map)+1):
          pos = (sec * dfu.sector_size) + 0xfff
          entry = data[pos]
          if sec in DATA_map:
              if DATA_map[sec] is None:
                continue
              elif DATA_map[sec] != entry:
                if sec == 0x4:
                    print('Sector 0x%02x mark does not match (0x%02x != 0x%02x), known CPS bug detected, fixing.' % (sec, DATA_map[sec], entry))
                    #Fix channel name string
                    data[pos-1] = 0x0
                    data[pos] = DATA_map[sec]
                else:
                    print('Sector 0x%02x mark does not match (0x%02x != 0x%02x), aborting.' % (sec, DATA_map[sec], entry))
                    return
              elif DATA_map[sec] not in sector_map:
                print("Data block with ID 0x%02x does not exist on device, aborting." % DATA_map[idx])
                return
              #else:
              #  print("Sector 0x%02x (0x%02x) OK" % (sec,entry))
          elif entry != 0x0:
              print('Sector mark for unlisted sector 0x%02x is not 0 (0x%02x), aborting.' % (sec, entry))
              return
        sys.stdout.write('+')
        sys.stdout.flush()

        for idx in range(2 if calib else 3 ,max(DATA_map)+1):
            if DATA_map[idx] is None:
                continue
            part = sector_map[DATA_map[idx]] * dfu.sector_size
            #print("Uploading data[0x%06x:0x%06x] to address 0x%06x length=0x%04x" % (idx*dfu.sector_size,(idx+1)*dfu.sector_size,part,dfu.sector_size))
            dfu.download_spi(part, data[idx*dfu.sector_size:(idx+1)*dfu.sector_size], dfu.sector_size, silent=True)
            sys.stdout.write('.')
            sys.stdout.flush()
        sys.stdout.write('\n')
        sys.stdout.flush()
    finally:
        f.close()


def download(dfu, data, start, end):
    """Writes the SPI flash data for given range."""
    if (end-start+1 < len(data)):
        raise RuntimeError('Uploaded data size %i is larger than maximum allowed size %i' % (len(data), end-start+1))
    dfu.download_spi(start, data, end-start+1)

def init_dfu(alt=0, dfu_mode=True):
    """Initializes the DFU switching to USB program mode."""
    dev = usb.core.find(idVendor=md1702_vendor, idProduct=md1702_product)

    if dev is None:
        raise RuntimeError('Device not found')

    dfu = DM1702_DFU(dev, alt)
    if dfu_mode:
        dev.default_timeout = 3000
        try:
            dfu.enter_dfu_mode()
        except usb.core.USBError as e:
            if len(e.args) > 0 and e.args[0] == 'Pipe error':
                raise RuntimeError('Failed to enter DFU mode. Is the device running in normal mode?')
            else:
                raise e
    else:
        dev.default_timeout = 5000
    return dfu


def usage():
    print("""
Usage: md1702-dfu <command> <arguments>

Write a codeplug to the radio. Supported file types: RAW (with writecp), DATA file (with write)
    md1702-dfu writecp <codeplug.raw>
    md1702-dfu write <codeplug.data>

Read a firmware and write it to a file.
    md1702-dfu readfw <firmware.bin>

Read a RAW codeplug and write it to a file (RAW with readcp, DATA CPS file with read)
    md1702-dfu readcp <codeplug.raw>
    md1702-dfu read <codeplug.data>

Read a DATA CPS file extended with extra sectors not found in DATA file (SMS, calls)
    md1702-dfu readall <codeplug_extra.raw>

Display device version information
    md1702-dfu versions

Read a voice data/HZK font/Boot image and write it to a file.
    md1702-dfu readvoice <voice.bin>
    md1702-dfu readfont <font.hzk>
    md1702-dfu readlogo <bootlogo.bin>

Write voice data/HZK font/Boot image and from a file (no checking of correct file type is done!).
    md1702-dfu writevoice <voice.bin>
    md1702-dfu writefont <font.hzk>
    md1702-dfu writelogo <bootlogo.bin>

Read a full SPI flash dump including a codeplug and write it to a file (very slow, ~1h)
    md1702-dfu readspi <spiflash.bin> [start [end]]
    # start/end are hexadecimal offsets

Dump the config block from Flash memory.
    md1702-dfu readcfg <cfg_filename.bin>

Set time and date on MD1702 to system time or specified time.
    md1702-dfu settime
    md1702-dfu settime "mm/dd/yyyy HH:MM:SS" (with quotes)

Reboot the device in normal mode.
    md1702-dfu reboot

Upgrade to new firmware:
    md1702-dfu upgrade <1702_v02_XYZ.bin>
""")


def main():
    try:
        if len(sys.argv) == 3:
            if sys.argv[1] == 'readcp':
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                print("Dumping RAW codeplug.")
                upload(dfu, sys.argv[2], dfu.cps_start, dfu.cps_end)

            elif sys.argv[1] in ['read', 'readall']:
                if sys.argv[1] == 'read' and sys.argv[2].split('.')[-1].lower() != "data":
                    usage()
                else:
                    dfu = init_dfu()
                    print("Dumping DATA CPS file.")
                    upload_codeplug(dfu, sys.argv[2], sys.argv[1] == 'readall')

            elif sys.argv[1] == 'readlogo':
                dfu = init_dfu()
                print("Dumping Boot logo raw image.")
                start, end = dfu.verify_addrs(Versions['Logo']) #logo offsets are not available in SPI_USB mode
                dfu.enter_spi_usb_mode()
                upload(dfu, sys.argv[2], start, end, crop=False)

            elif sys.argv[1] == 'readfont':
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                print("Dumping HZK font data.")
                start, end = dfu.verify_addrs(Versions['HZKFont'])
                upload(dfu, sys.argv[2], start, end)

            elif sys.argv[1] == 'readvoice':
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                print("Dumping Voice data.")
                start, end = dfu.verify_addrs(Versions['Voices'])
                upload(dfu, sys.argv[2], start, end)

            elif sys.argv[1] == 'readspi':
                print("Dumping 16MB of RAW SPI flash data, please be patient, it takes an hour.")
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                upload_all(dfu, sys.argv[2])
                print('Read complete')

            elif sys.argv[1] == 'readfw':
                dfu = init_dfu()
                upload_firmware(dfu, sys.argv[2])

            elif sys.argv[1] == 'readcfg':
                dfu = init_dfu()
                upload_config(dfu, sys.argv[2])

            elif sys.argv[1] == 'settime':
                dfu = init_dfu(dfu_mode=False)
                dfu.set_time(sys.argv[2])

            elif sys.argv[1] == 'writelogo':
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    dfu = init_dfu()
                    print("Setting Boot logo raw image.")
                    start, end = dfu.verify_addrs(Versions['Logo']) #logo offsets are not available in SPI_USB mode
                    dfu.enter_spi_usb_mode()
                    download(dfu, data, start, end)

            elif sys.argv[1] == 'writefont':
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    dfu = init_dfu()
                    dfu.enter_spi_usb_mode()
                    print("Setting HZK font data.")
                    start, end = dfu.verify_addrs(Versions['HZKFont'])
                    download(dfu, data, start, end)

            elif sys.argv[1] == 'writevoice':
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    dfu = init_dfu()
                    if data[:0x1000] == ('\xff' * 0x1000) and data[0x1016:0x101B] == '1.txt':
                        print('Stock voice data from MD, removing first 0x1000 bytes')
                        data = data[0x1000:]
                    dfu.enter_spi_usb_mode()
                    print("Setting Voice data.")
                    start, end = dfu.verify_addrs(Versions['Voices'])
                    download(dfu, data, start, end)

            elif sys.argv[1] in ['write', 'writecal'] and sys.argv[2].split('.')[-1].lower() == "data":
                dfu = init_dfu()
                print("Writing CPS DATA.")
                download_codeplug(dfu, sys.argv[2], sys.argv[1] == 'writecal')

            elif sys.argv[1] == 'writecp':
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    if len(data) == 0x3C000:
                        print('According to the size, this is official codeplug, use write command instead. Aborting.')
                        return
                    dfu = init_dfu()
                    dfu.enter_spi_usb_mode()
                    print("Writing RAW codeplug.")
                    download(dfu, data, dfu.cps_start, dfu.cps_end)

            elif sys.argv[1] == "upgrade":
                with open(sys.argv[2], 'rb') as f:
                    data = f.read()
                    dfu = init_dfu(dfu_mode=False)
                    dfu.enter_bootloader_mode()
                    dfu.set_timeout(60000)
                    dfu.download_fw(data, sys.argv[2])
            else:
                usage()

        elif len(sys.argv) == 2:
            if sys.argv[1] == 'settime':
                dfu = init_dfu(dfu_mode=False)
                dfu.set_time()

            elif sys.argv[1] == 'reboot':
                dfu = init_dfu()
                dfu.reboot()

            elif sys.argv[1] == 'versions':
                dfu = init_dfu()
                display_versions(dfu)

            elif sys.argv[1] == "upgrade_check":
                dfu = init_dfu(dfu_mode=False)
                dfu.enter_bootloader_mode()
                print ("Please turn off the radio now.")
            else:
                usage()

        elif len(sys.argv) in [4,5]:
            if sys.argv[1] == 'readspi':
                try:
                    start=int(sys.argv[3], 16)
                    end=int(sys.argv[4], 16) if len(sys.argv) == 5 else 0xffffff
                except:
                    usage()
                    exit(1)
                print("Dumping partial RAW SPI flash data from 0x%06x to 0x%06x, please be patient, it takes ~%.2f minutes." %\
                      (start, end, (end - start) * 0.0000032))
                dfu = init_dfu()
                dfu.enter_spi_usb_mode()
                upload_all(dfu, sys.argv[2],start, end)
                print('Read complete')

        else:
            usage()
    except (RuntimeError, Exception) as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        if verbose_err:
            print(exc_type, fname, exc_tb.tb_lineno)
        print(e)
        exit(1)

if __name__ == '__main__':
    main()
