# -*- coding: utf-8 -*-
"""Windows DPAPI 数据保护封装: Cookie 凭证加密存储(仅当前 Windows 用户可解密)"""
import ctypes
from ctypes import wintypes


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _make_blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _blob_to_bytes(blob):
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob.pbData)


def protect(data: bytes) -> bytes:
    """DPAPI 加密"""
    in_blob = _make_blob(data)
    out_blob = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob), "DadealbitZhihuExporter", None, None, None, 0,
        ctypes.byref(out_blob))
    if not ok:
        raise OSError("CryptProtectData 调用失败")
    return _blob_to_bytes(out_blob)


def unprotect(data: bytes) -> bytes:
    """DPAPI 解密"""
    in_blob = _make_blob(data)
    out_blob = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0,
        ctypes.byref(out_blob))
    if not ok:
        raise OSError("CryptUnprotectData 调用失败")
    return _blob_to_bytes(out_blob)
