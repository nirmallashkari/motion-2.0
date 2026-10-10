"""Windows account-bound credential recovery; never log plaintext secrets."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time


class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def valid(value):
    return bool(value) and len(value)<=512 and not any(c.isspace() for c in value) and not value.startswith('DEEPSEEK_API_KEY=')


def transform(value,decrypt=False):
    if os.name!='nt':raise ValueError('Credential recovery requires Windows DPAPI')
    buffer=ctypes.create_string_buffer(value);source=Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));result=Blob()
    entropy_buffer=ctypes.create_string_buffer(b'MOTION 2.0 DeepSeek credential v1')
    entropy=Blob(len(entropy_buffer.raw)-1,ctypes.cast(entropy_buffer,ctypes.POINTER(ctypes.c_ubyte)))
    function=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    if not function(ctypes.byref(source),None,ctypes.byref(entropy),None,None,1,ctypes.byref(result)):
        raise ValueError('Windows could not protect/recover the local credential')
    try:return ctypes.string_at(result.data,result.size)
    finally:
        ctypes.memset(result.data,0,result.size)
        ctypes.windll.kernel32.LocalFree.argtypes=[ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(ctypes.cast(result.data,ctypes.c_void_p))


def load(path):
    path=Path(path);backup=path.with_suffix('.dpapi')
    value=path.read_text(encoding='utf-8-sig').strip() if path.is_file() else ''
    managed=path.name=='deepseek_api_key.txt' and path.parent.name=='secrets'
    if not managed:return value
    if path.is_symlink() or backup.is_symlink():raise ValueError('Credential links are not allowed')
    if valid(value):
        if not backup.is_file() or transform(backup.read_bytes(),True).decode()!=value:
            temporary=backup.with_suffix('.dpapi.tmp');temporary.write_bytes(transform(value.encode()));temporary.replace(backup)
        state='text_valid_encrypted_backup_ready'
    elif not value and backup.is_file():
        value=transform(backup.read_bytes(),True).decode()
        if not valid(value):raise ValueError('Recovered credential is invalid')
        state='recovered_from_encrypted_backup'
    else:return value
    record=dict(status=state,checked_at_unix=time.time(),text_file_bytes=path.stat().st_size if path.is_file() else None,
        text_last_write_unix=path.stat().st_mtime if path.is_file() else None,protection='Windows DPAPI, current account')
    temporary=path.parent/'credential_status.tmp';temporary.write_text(json.dumps(record,indent=2),encoding='utf-8')
    temporary.replace(path.parent/'credential_status.json')
    return value
