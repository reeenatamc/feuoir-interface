"""Reads the input volume of any Core Audio device, not only the default input.

osascript only reports the volume of the default input. This asks Core Audio for the device by name, so a USB
sound card keeps its own volume in condiciones.json without becoming the default input. It only reads: nothing
here changes a setting of the Mac.
"""
import ctypes
import ctypes.util

_ca = ctypes.CDLL(ctypes.util.find_library("CoreAudio"))
_cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))


def _fourcc(s):
    return int.from_bytes(s.encode("ascii"), "big")


SYSTEM_OBJECT = 1
DEVICES = _fourcc("dev#")
NAME = _fourcc("lnam")
VOLUME_SCALAR = _fourcc("volm")
VOLUME_DB = _fourcc("vold")
SCOPE_GLOBAL = _fourcc("glob")
SCOPE_INPUT = _fourcc("inpt")
ELEMENT_MAIN = 0
UTF8 = 0x08000100


class _Address(ctypes.Structure):
    _fields_ = [("selector", ctypes.c_uint32), ("scope", ctypes.c_uint32), ("element", ctypes.c_uint32)]


_ca.AudioObjectHasProperty.argtypes = [ctypes.c_uint32, ctypes.POINTER(_Address)]
_ca.AudioObjectHasProperty.restype = ctypes.c_bool
_ca.AudioObjectGetPropertyDataSize.argtypes = [ctypes.c_uint32, ctypes.POINTER(_Address), ctypes.c_uint32,
                                               ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
_ca.AudioObjectGetPropertyData.argtypes = [ctypes.c_uint32, ctypes.POINTER(_Address), ctypes.c_uint32,
                                           ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
_cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
_cf.CFStringGetCString.restype = ctypes.c_bool
_cf.CFRelease.argtypes = [ctypes.c_void_p]


def _device_ids():
    addr = _Address(DEVICES, SCOPE_GLOBAL, ELEMENT_MAIN)
    size = ctypes.c_uint32(0)
    if _ca.AudioObjectGetPropertyDataSize(SYSTEM_OBJECT, ctypes.byref(addr), 0, None, ctypes.byref(size)):
        return []
    ids = (ctypes.c_uint32 * (size.value // 4))()
    if _ca.AudioObjectGetPropertyData(SYSTEM_OBJECT, ctypes.byref(addr), 0, None, ctypes.byref(size), ids):
        return []
    return list(ids)


def _device_name(device_id):
    addr = _Address(NAME, SCOPE_GLOBAL, ELEMENT_MAIN)
    ref = ctypes.c_void_p()
    size = ctypes.c_uint32(ctypes.sizeof(ref))
    if _ca.AudioObjectGetPropertyData(device_id, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.byref(ref)):
        return None
    buf = ctypes.create_string_buffer(512)
    ok = _cf.CFStringGetCString(ref, buf, len(buf), UTF8)
    _cf.CFRelease(ref)
    return buf.value.decode("utf-8") if ok else None


def _find(name):
    for device_id in _device_ids():
        if _device_name(device_id) == name:
            return device_id
    return None


def _input_value(device_id, selector):
    """Main element first; devices without it keep the volume per channel, and channel 1 is the one recorded."""
    for element in (ELEMENT_MAIN, 1):
        addr = _Address(selector, SCOPE_INPUT, element)
        if not _ca.AudioObjectHasProperty(device_id, ctypes.byref(addr)):
            continue
        value = ctypes.c_float()
        size = ctypes.c_uint32(ctypes.sizeof(value))
        if not _ca.AudioObjectGetPropertyData(device_id, ctypes.byref(addr), 0, None, ctypes.byref(size),
                                              ctypes.byref(value)):
            return value.value
    return None


def input_volume(name):
    """Input volume from 0 to 100, on the same scale as the Sound settings and osascript.

    None when no device has that name or the device has no input volume control.
    """
    device_id = _find(name)
    scalar = None if device_id is None else _input_value(device_id, VOLUME_SCALAR)
    return None if scalar is None else round(scalar * 100)


def input_gain_db(name):
    """The same setting in dB, as the device reports it. A volume of 0 can be a gain of 0 dB, not silence."""
    device_id = _find(name)
    db = None if device_id is None else _input_value(device_id, VOLUME_DB)
    return None if db is None else round(db, 2)
