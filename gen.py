#!/usr/bin/env python3
""

import os
import sys
import json
import time
import random
import hashlib
import hmac
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
APP_ID = 100067

OAUTH_REGISTER_URL    = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
OAUTH_TOKEN_URL       = "https://100067.connect.garena.com/oauth/guest/token/grant"
MAJOR_REGISTER_URL    = "https://loginbp.ppmainecoonghj.com/MajorRegister"
NEWBIE_URL            = "https://loginbp.ppmainecoonghj.com/ChooseNewbieChoice"
MAJOR_LOGIN_URL       = "https://loginbp.ppmainecoonghj.com/MajorLogin"
GENERATE_NICKNAME_URL = "https://loginbp.ppmainecoonghj.com/GenerateNickname"

GETLOGIN_HOST_IND   = "client.ind.freefiremobile.com"
GETLOGIN_HOST_OTHER = "clientbp.ggpolarbear.com"

ACCOUNTS_FILE = "accounts.json"
LOG_FILE      = "generator.log"

# Fixed value from working version — DO NOT randomize
X_GA_SV = "1789636317"


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGER
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(threadName)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")],
)
logger = logging.getLogger("ACCOUNT_GENERATOR")

file_lock = threading.Lock()
print_lock = threading.Lock()
log_lock  = threading.Lock()
stop_flag = threading.Event()


def L(level, msg, color=""):
    RST, C, G, Y, R, M, DIM = "\033[0m", "\033[96m", "\033[92m", "\033[93m", "\033[91m", "\033[95m", "\033[2m"
    colors = {"INFO": C, "OK": G, "STEP": M, "WARN": Y, "ERR": R, "DBG": DIM}
    c = color or colors.get(level, "")
    with log_lock:
        print(f"{c}[{level:^4}]{RST} {msg}", flush=True)
    logger.info(f"[{level}] {msg}")


def L_info(m):  L("INFO", m)
def L_ok(m):    L("OK",   m)
def L_step(m):  L("STEP", m)
def L_warn(m):  L("WARN", m)
def L_err(m):   L("ERR",  m)
def L_dbg(m):   L("DBG",  m)


def hex_dump(data: bytes, limit: int = 128, indent: str = "        "):
    if not data:
        return
    shown = data[:limit]
    for i in range(0, len(shown), 16):
        chunk = shown[i:i + 16]
        hx  = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{indent}{i:04x}  {hx:<47}  |{asc}|")
    if len(data) > limit:
        print(f"{indent}... ({len(data) - limit} more bytes)")


# ══════════════════════════════════════════════════════════════════════════════
#  USER-AGENT POOL (safe to randomize)
# ══════════════════════════════════════════════════════════════════════════════
MSDK_USER_AGENTS = [
    "GarenaMSDK/4.0.42(KB2003 ;Android 13;en;HK;app 2.130.1 2019118332;)",
    "GarenaMSDK/4.0.42(SM-G998B ;Android 14;en;IN;app 2.131.0 2019118527;)",
    "GarenaMSDK/4.0.42(CPH2095 ;Android 12;en;ID;app 2.129.1 2019118142;)",
    "GarenaMSDK/4.0.42(Redmi 2404ARN45A ;Android 13;en;IN;app 2.132.0 2019118721;)",
    "GarenaMSDK/4.0.42(Pixel 6 ;Android 14;en;US;app 2.131.1 2019118602;)",
    "GarenaMSDK/4.0.42(OnePlus 9 Pro ;Android 13;en;IN;app 2.132.2 2019118783;)",
    "GarenaMSDK/4.0.42(Xiaomi 13 Pro ;Android 14;en;ID;app 2.130.2 2019118441;)",
    "GarenaMSDK/4.0.42(realme RMX2189 ;Android 10;en;IN;app 2.130.0 2019118321;)",
]

UNITY_USER_AGENTS = [
    "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "UnityPlayer/2021.3.27f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "UnityPlayer/2020.3.45f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
]


def pick_msdk_ua():    return random.choice(MSDK_USER_AGENTS)
def pick_unity_ua():   return random.choice(UNITY_USER_AGENTS)


# ══════════════════════════════════════════════════════════════════════════════
#  INPUT
# ══════════════════════════════════════════════════════════════════════════════
def prompt_int(prompt: str, default: int, min_v: int = 1, max_v: int = 10**9) -> int:
    while True:
        try:
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print(); return default
        if not raw: return default
        if not raw.isdigit():
            print(f"  ✗ Enter a number between {min_v} and {max_v}")
            continue
        n = int(raw)
        if not (min_v <= n <= max_v):
            print(f"  ✗ Enter a number between {min_v} and {max_v}")
            continue
        return n


# ══════════════════════════════════════════════════════════════════════════════
#  PROTOBUF
# ══════════════════════════════════════════════════════════════════════════════
def write_varint(v: int) -> bytes:
    r = []
    while v > 127:
        r.append((v & 0x7F) | 0x80); v >>= 7
    r.append(v); return bytes(r)

def write_varint_field(fn, v): return write_varint((fn << 3) | 0) + write_varint(v)

def write_string_field(fn, v):
    b = v.encode("utf-8")
    return write_varint((fn << 3) | 2) + write_varint(len(b)) + b

def write_bytes_field(fn, v):
    return write_varint((fn << 3) | 2) + write_varint(len(v)) + v

def assemble_proto(fields) -> bytes:
    data = bytearray()
    for k, v in fields.items():
        if isinstance(v, int):
            data.extend(write_varint_field(k, v))
        elif isinstance(v, str):
            data.extend(write_string_field(k, v))
        elif isinstance(v, (bytes, bytearray)):
            data.extend(write_bytes_field(k, bytes(v)))
    return bytes(data)

def aes_encrypt(plain: bytes) -> bytes:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain, AES.block_size))

def aes_decrypt(ct: bytes) -> bytes:
    return unpad(AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(ct), AES.block_size)

def read_varint(data, offset):
    r, s = 0, 0
    while True:
        if offset >= len(data): raise IndexError("eof")
        b = data[offset]; r |= (b & 0x7F) << s; offset += 1
        if not (b & 0x80): break
        s += 7
    return r, offset

def parse_proto(data) -> dict:
    result, offset = {}, 0
    while offset < len(data):
        try:
            tag, offset = read_varint(data, offset)
        except Exception:
            break
        fn, wt = tag >> 3, tag & 0x7
        try:
            if wt == 0:
                v, offset = read_varint(data, offset)
                result[fn] = v
            elif wt == 2:
                ln, offset = read_varint(data, offset)
                v = data[offset:offset + ln]; offset += ln
                try: result[fn] = v.decode("utf-8")
                except: result[fn] = v.hex()
            elif wt == 1:
                result[fn] = data[offset:offset + 8].hex(); offset += 8
            elif wt == 5:
                result[fn] = data[offset:offset + 4].hex(); offset += 4
            else:
                break
        except Exception:
            break
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  XOR
# ══════════════════════════════════════════════════════════════════════════════
XOR_KEY = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
           0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]

def xor_open_id(open_id: str) -> bytes:
    b = open_id.encode("utf-8")
    return bytes(x ^ XOR_KEY[i % len(XOR_KEY)] for i, x in enumerate(b))


FIELD_22_HEX = (
    "474752450101010062020000a78910bd098e3ff2e4345d59a31db114ea088f37e32e65"
    "212ff96621793d9eb78720d0bf2ac95176569765247ada5eb01376b3b9931794a4946"
    "d76ef8890779f3f2129317e6e1cb2fdcf7b06247cea343b8d4f167eff85a2e1dfe99"
    "b4583a7e1a155dbe7f7f85cff3b223eb77222ec1228f3ee1ef6ce7f8ca24b00a554"
    "e497328812f8df74c82d519ae3e3ceab436eb145e8a517089a7cef6a4efb22214b2"
    "a4b19989b74807584afe5e52825e7ac60e19a596a9bf02d961de6a0ed2515ec6023"
    "fdb7684d9464b97b21c527ce61b6bee4ef30d20a1fa33a996952d44d44e44f2f86c"
    "768aaf2a7808ad60f91048dca0207961ba7c2555c48341b30190debc775edb2cee24"
    "4cf51fca3760ce4388be2db45e80b813b5beb9c784007b7762d7a1e428affc8a3a4"
    "cd76cbaef648a274297fde33233dccd3f272cb77f39a1affe0365a24954111f768f72"
    "0e77535af024bea2b2726c3bac992374755c3deacf09235e6865d456e651680d115a"
    "751a797225eaacdf9a513cf104526e1a32e5296e111a33ae581a63850837921df848"
    "9adfd41ea895b7cf3f5b2e45d538a6e4f032f590ccbb7daf5fa9c50adadee0799661"
    "4c3f957bda349e6c484fdf55970d1943ad7955a76671298b6d98b636b69ebde6bc94"
    "dbd93ac3393a6ae230130445b2d744189167854a5617be2393e7d8fbb5719a1b4754"
    "1ba466167e3e05a6c244f1301ee2035acf94dffc8adbde747d5cd85e35ead3acc372"
    "a59c4220e54bf63f9d80485f3de2518495c1d0f78c911d2da595911fd2a1989cf17"
    "cf3ded5f6c92dea64d675c555c11df92d6c517ca5d0d61a8962f43f76ec7e87596c"
    "8325ebf9ab0f8e6d2eca33c511ceac6980906ebd68c478665591dcecf788ec6ef34c"
    "fbe3fcc279c6147c5bf91cd43cdc9704236"
)


# ══════════════════════════════════════════════════════════════════════════════
#  API CALLS
# ══════════════════════════════════════════════════════════════════════════════
def generate_signature(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"))
    return hmac.new(CLIENT_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def register_guest(session, password, ua):
    L_step(f"register_guest → {OAUTH_REGISTER_URL}")
    L_info(f"  UA: {ua}")

    payload = {"app_id": APP_ID, "client_type": 2, "password": password, "source": 2}
    signature = generate_signature(payload)
    body = json.dumps(payload, separators=(",", ":"))
    L_dbg(f"  body: {body}")

    headers = {
        "User-Agent": ua,
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Signature {signature}",
    }

    t0 = time.time()
    resp = session.post(OAUTH_REGISTER_URL, data=body, headers=headers, timeout=15)
    dt = (time.time() - t0) * 1000
    L_info(f"  ← HTTP {resp.status_code}  ({dt:.0f} ms, {len(resp.content)} bytes)")

    if resp.status_code != 200:
        raise Exception(f"Register HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Register failed: {data}")

    uid = str(data["data"]["uid"])
    L_ok(f"  uid = {uid}")
    return uid


def get_token_legacy(session, uid, password, ua):
    L_step(f"get_token_legacy → {OAUTH_TOKEN_URL}")

    payload = {
        "uid": uid, "password": password,
        "response_type": "token", "client_type": "2",
        "client_secret": CLIENT_SECRET, "client_id": "100067",
    }
    headers = {
        "User-Agent": ua,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }

    t0 = time.time()
    resp = session.post(OAUTH_TOKEN_URL, data=payload, headers=headers, timeout=30)
    dt = (time.time() - t0) * 1000
    L_info(f"  ← HTTP {resp.status_code}  ({dt:.0f} ms, {len(resp.content)} bytes)")

    if resp.status_code != 200:
        raise Exception(f"Token HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    at, oid = data.get("access_token"), data.get("open_id")
    if not at or not oid:
        raise Exception(f"Token grant failed: {data}")

    L_ok(f"  open_id      = {oid}")
    L_ok(f"  access_token = {at[:40]}…")
    return at, oid


def generate_nickname(session, open_id):
    number = random.randint(10000, 99999)
    superscript = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    return str(number).translate(superscript) + "Rsglory"


def send_major_register(session, name, access_token, open_id, ua, dev=None):
    L_step(f"send_major_register → {MAJOR_REGISTER_URL}")
    L_info(f"  nickname: {name}")

    field14_bytes = xor_open_id(open_id)
    fields = {
        1: name, 2: access_token, 3: open_id,
        5: 102000007, 6: 4, 7: 1, 13: 1,
        14: field14_bytes,
        15: "en", 16: 2, 20: "2.133.8", 21: 1,
        22: bytes.fromhex(FIELD_22_HEX),
    }

    plain = assemble_proto(fields)
    encrypted = aes_encrypt(plain)
    L_dbg(f"  plain {len(plain)}B → encrypted {len(encrypted)}B")

    headers = {
        "Host": MAJOR_REGISTER_URL.split("/")[2],
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": X_GA_SV,
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Content-Length": str(len(encrypted)),
    }

    t0 = time.time()
    resp = session.post(MAJOR_REGISTER_URL, data=encrypted, headers=headers,
                        timeout=30, verify=False)
    dt = (time.time() - t0) * 1000
    L_info(f"  ← HTTP {resp.status_code}  ({dt:.0f} ms, {len(resp.content)} bytes)")

    if resp.status_code != 200:
        raise Exception(f"MajorRegister HTTP {resp.status_code}: {resp.text[:200]}")

    return parse_proto(resp.content)


def send_newbie_choice(session, account_id, choice=3, ua=None):
    L_step(f"send_newbie_choice → {NEWBIE_URL}")

    plain = assemble_proto({1: int(account_id), 2: 1, 3: int(choice)})
    encrypted = aes_encrypt(plain)

    headers = {
        "Host": "loginbp.ppmainecoonghj.com",
        "User-Agent": ua or "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": X_GA_SV,
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Content-Length": str(len(encrypted)),
    }

    t0 = time.time()
    resp = session.post(NEWBIE_URL, headers=headers, data=encrypted,
                        timeout=30, verify=False)
    dt = (time.time() - t0) * 1000
    L_info(f"  ← HTTP {resp.status_code}  ({dt:.0f} ms, {len(resp.content)} bytes)")

    if resp.status_code != 200:
        raise Exception(f"ChooseNewbieChoice HTTP {resp.status_code}")

    return resp


# ══════════════════════════════════════════════════════════════════════════════
#  MAJORLOGIN  —  MATCHES YOUR WORKING VERSION EXACTLY
# ══════════════════════════════════════════════════════════════════════════════
import random
import time

DEVICE_PROFILES = [
    {
        "os": "Android OS 10 / API-29 (QP1A.190711.020/1617006012)",
        "model": "realme RMX2189",
        "gpu": "PowerVR Rogue GE8320",
        "resolution": (1600, 720),
        "dpi": "320",
        "cpu": "ARM64 FP ASIMD AES | 2301 | 8",
        "renderer": "OpenGL ES 3.2 build 1.11@5425693",
        "language": "en",
    },
    {
        "os": "Android OS 11 / API-30",
        "model": "Redmi Note 10",
        "gpu": "Adreno (TM) 612",
        "resolution": (2400, 1080),
        "dpi": "440",
        "cpu": "ARM64 FP ASIMD AES | 2200 | 8",
        "renderer": "OpenGL ES 3.2",
        "language": "en",
    },
    {
        "os": "Android OS 12 / API-31",
        "model": "Samsung SM-A525F",
        "gpu": "Adreno (TM) 642L",
        "resolution": (2400, 1080),
        "dpi": "420",
        "cpu": "ARM64 FP ASIMD AES | 2300 | 8",
        "renderer": "OpenGL ES 3.2",
        "language": "en",
    },
    {
        "os": "Android OS 13 / API-33",
        "model": "V2312",
        "gpu": "Mali-G57",
        "resolution": (2400, 1080),
        "dpi": "440",
        "cpu": "ARM64 FP ASIMD AES | 2400 | 8",
        "renderer": "OpenGL ES 3.2",
        "language": "en",
    },
]
import random

IP_ADDRESSES = [
    "151.158.158.220",
    "151.158.158.221",
    "151.158.158.222",
    "151.158.158.223",
    "151.158.158.224",
    "151.158.158.225",
    "151.158.158.226",
    "151.158.158.227",
    "151.158.158.228",
    "151.158.158.229",
    "151.158.158.230",
    "151.158.158.231",
    "151.158.158.232",
    "151.158.158.233",
    "151.158.158.234",
    "151.158.158.235",
    "151.158.158.236",
    "151.158.158.237",
    "151.158.158.238",
    "151.158.158.239",
]

random_ip = random.choice(IP_ADDRESSES)

def build_major_login_payload(access_token, open_id, platform_type=4):
    return {
        3: time.strftime("%Y-%m-%d %H:%M:%S"),
        4: "free fire",
        5: 1,
        7: "2.133.9",
        8: "Android OS 10 / API-29 (QP1A.190711.020/1617006012)",
        9: "Handheld",
        10: "Vi India",
        11: "WIFI",
        12: 1600,
        13: 720,
        14: "320",
        15: "ARM64 FP ASIMD AES | 2301 | 8",
        16: 2799,
        17: "PowerVR Rogue GE8320",
        18: "OpenGL ES 3.2 build 1.11@5425693",
        19: "Google|9f7d6b8b-b10c-454a-852d-06332cd498eb",
        20: random_ip,
        21: "en",

        # Login-specific fields
        22: open_id,
        23: str(platform_type),

        24: "Handheld",
        25: "realme RMX2189",
        26: "TW",

        # Access token
        29: access_token,

        30: 1,
        41: "Vi India",
        42: "WIFI",
        57: "1ac4b80ecf0478a44203bf8fac6120f5",

        60: 19799,
        61: 2536,
        62: 5056,
        64: 2768,
        65: 19999,
        66: 2536,
        67: 19799,

        73: 1,
        74: "/data/app/com.dts.freefiremax-ShI7E0dK8p1IiZ785pvuVQ==/lib/arm64",
        76: 2,
        77: "38f4751a330688ab124c2c804cec90a5|/data/app/com.dts.freefiremax-ShI7E0dK8p1IiZ785pvuVQ==/base.apk",
        78: 2,
        79: 2,
        81: "64",
        83: "2019118527",

        86: "OpenGLES3",
        87: 3071,
        88: 4,

        92: 67920,
        93: "android_max",
        94: "KqsHT+UrR1HKqb6+1db+Ofei+NtZr2+hbiBo3yKDL8w+8E3S5qF2IgEEe1fFQFyHRzl4iyHjHp+QsfeLbjJ6+DidTiKxm0ak2uYYa6QR4nAUdlZR",
        95: 111107,
        96: '{"cur_rate":null,"support_etc2":true}',

        97: 1,
        98: 1,
        99: "4",
        100: "4",

        102: "",

        104: 83812,
        105: 1,
        106: "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|a4332cb1c1a84e51dd77441e4856ed5a",
        107: "1.9393e7b8e53e8aeb",
    }


def send_major_login(session, access_token, open_id, platform_type=4, ua=None):
    L_step(f"send_major_login → {MAJOR_LOGIN_URL}")
    L_info(f"  platform: {platform_type}")

    body = build_major_login_payload(access_token, open_id, platform_type)
    plain = assemble_proto(body)
    encrypted = aes_encrypt(plain)

    L_dbg(f"  plain {len(plain)}B → encrypted {len(encrypted)}B")
    L_dbg(f"  plaintext head:")
    hex_dump(plain, 64)

    headers = {
        "Host": "loginbp.ppmainecoonghj.com",
        "User-Agent": ua or "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": X_GA_SV,
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Content-Length": str(len(encrypted)),
    }

    t0 = time.time()
    resp = session.post(MAJOR_LOGIN_URL, data=encrypted, headers=headers,
                        timeout=30, verify=False)
    dt = (time.time() - t0) * 1000
    L_info(f"  ← HTTP {resp.status_code}  ({dt:.0f} ms, {len(resp.content)} bytes)")

    if resp.status_code != 200:
        L_err(f"  body: {resp.text[:200]}")
        raise Exception(f"MajorLogin HTTP {resp.status_code}: {resp.text[:200]}")

    PROTOBUF_OFFSET = 64
    if len(resp.content) <= PROTOBUF_OFFSET:
        raise Exception(f"MajorLogin response too short: {resp.content.hex()}")

    parsed = parse_proto(resp.content[PROTOBUF_OFFSET:])
    L_dbg(f"  parsed response fields: {list(parsed.keys())}")
    return parsed


# ══════════════════════════════════════════════════════════════════════════════
#  GETLOGINDATA
# ══════════════════════════════════════════════════════════════════════════════
def build_getlogindata_payload(jwt, open_id, platform, region="IND"):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    fields = {
        3: now, 4: "free fire", 5: 1, 7: "2.133.9",
        8: "Android OS 10 / API-29 (QP1A.190711.020/1617006012)",
        9: "Handheld", 10: "Vi India", 11: "WIFI",
        12: 1600, 13: 720, 14: "320",
        15: "ARM64 FP ASIMD AES | 2301 | 8", 16: 2799,
        17: "PowerVR Rogue GE8320",
        18: "OpenGL ES 3.2 build 1.11@5425693",
        19: "Google|9f7d6b8b-b10c-454a-852d-06332cd498eb",
        20: "151.158.158.220", 21: "en",
        22: open_id, 23: str(platform),
        24: "Handheld", 25: "realme RMX2189", 26: region.upper(),
        29: jwt, 30: 1,
        41: "Vi India", 42: "WIFI",
        57: "1ac4b80ecf0478a44203bf8fac6120f5",
        60: 19799, 61: 2536, 62: 5056, 64: 2768,
        65: 19999, 66: 2536, 67: 19799,
        73: 1,
        74: "/data/app/com.dts.freefiremax-ShI7E0dK8p1IiZ785pvuVQ==/lib/arm64",
        76: 2,
        77: "38f4751a330688ab124c2c804cec90a5|/data/app/com.dts.freefiremax-ShI7E0dK8p1IiZ785pvuVQ==/base.apk",
        78: 2, 79: 2, 81: "64", 83: "2019118527",
        86: "OpenGLES3", 87: 3071, 88: 4,
        92: 67920, 93: "android_max",
        94: "KqsHT+UrR1HKqb6+1db+Ofei+NtZr2+hbiBo3yKDL8w+8E3S5qF2IgEEe1fFQFyHRzl4iyHjHp+QsfeLbjJ6+DidTiKxm0ak2uYYa6QR4nAUdlZR",
        95: 111107,
        96: '{"cur_rate":null,"support_etc2":true}',
        97: 1, 98: 1, 99: "4", 100: "4", 102: "",
        104: 83812, 105: 1,
        106: "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|a4332cb1c1a84e51dd77441e4856ed5a",
        107: "1.9393e7b8e53e8aeb",
    }
    return assemble_proto(fields)


def send_getlogindata(session, jwt, open_id, platform_type="4", region="IND", ua=None):
    host = GETLOGIN_HOST_IND if region.upper() == "IND" else GETLOGIN_HOST_OTHER
    url = f"https://{host}/GetLoginData"
    L_step(f"send_getlogindata → {url}")
    L_info(f"  region: {region}  platform: {platform_type}")

    plain = build_getlogindata_payload(jwt, open_id, platform_type, region)
    encrypted = aes_encrypt(plain)

    headers = {
        "Host": host,
        "User-Agent": ua or "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": f"Bearer {jwt}",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55",
        "Content-Type": "application/octet-stream",
        "X-Unity-Version": "2022.3.47f1",
    }

    t0 = time.time()
    resp = session.post(url, headers=headers, data=encrypted,
                        verify=False, timeout=30)
    dt = (time.time() - t0) * 1000
    L_info(f"  ← HTTP {resp.status_code}  ({dt:.0f} ms, {len(resp.content)} bytes)")

    return resp.status_code, resp.content


def parse_getlogindata_response(data):
    p = parse_proto(data)
    return {
        "account_uid":     p.get(1, 0),
        "region":          p.get(3, ""),
        "account_name":    p.get(4, ""),
        "online_ip_port":  p.get(14, ""),
        "clan_id":         p.get(20, 0),
        "account_ip_port": p.get(32, ""),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  JSON I/O
# ══════════════════════════════════════════════════════════════════════════════
def load_json(path, default=None):
    if default is None: default = []
    if not os.path.exists(path): return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else default
    except Exception:
        return default


def save_account(account: dict) -> bool:
    if not isinstance(account, dict): return False
    if not account.get("uid") or not account.get("password"): return False
    with file_lock:
        data = load_json(ACCOUNTS_FILE)
        data.append(account)
        tmp = ACCOUNTS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, ACCOUNTS_FILE)
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  WORKER
# ══════════════════════════════════════════════════════════════════════════════
def create_one_account(worker_id: int, total: int, counters: dict):
    while not stop_flag.is_set():
        # Reserve exactly one account slot before doing network work.
        # success + active can never exceed the requested total.
        with file_lock:
            if counters["success"] >= total:
                return
            if counters["success"] + counters["active"] >= total:
                return
            counters["active"] += 1

        session = None
        account_succeeded = False
        try:
            session = requests.Session()
            session.verify = False

            # Per-account: ONLY User-Agents are randomized
            msdk_ua  = pick_msdk_ua()
            unity_ua = pick_unity_ua()

            with print_lock:
                print()
                print("═" * 70)
                L_step(f"WORKER #{worker_id} — new account start")
                print("═" * 70)
                L_info(f"  msdk_ua : {msdk_ua}")
                L_info(f"  unity_ua: {unity_ua}")

            # Password
            random_suffix = hashlib.sha256(os.urandom(16)).hexdigest()[:12].upper()
            password = f"Rsglory_{random_suffix}"
            L_info(f"  password: {password}")

            # STEP 1
            L_step("── STEP 1/7 · register_guest ──")
            uid = register_guest(session, password, msdk_ua)
            if not uid:
                raise RuntimeError("empty uid")

            # STEP 2
            L_step("── STEP 2/7 · get_token_legacy ──")
            access_token, open_id = get_token_legacy(session, uid, password, msdk_ua)

            # STEP 3 + 4
            L_step("── STEP 3/7 · MajorRegister ──")
            account_id = None
            nickname = "Unknown"
            for reg_attempt in range(1, 11):
                nickname = generate_nickname(session, open_id)
                L_info(f"  attempt {reg_attempt}/10 — nickname={nickname}")
                try:
                    reg_resp = send_major_register(session, nickname,
                                                   access_token, open_id, unity_ua)
                    account_id = reg_resp.get(3)
                    if account_id:
                        L_ok(f"  account_id = {account_id}")
                        break
                except Exception as e:
                    L_warn(f"  attempt failed: {e}")
                    if reg_attempt < 10: time.sleep(0.5)

            if not account_id:
                raise RuntimeError("MajorRegister failed: all nickname retries exhausted")

            # STEP 5
            L_step("── STEP 4/7 · send_newbie_choice ──")
            send_newbie_choice(session, account_id, choice=3, ua=unity_ua)

            # STEP 6
            L_step("── STEP 5/7 · send_major_login ──")
            login_resp = send_major_login(session, access_token, open_id,
                                          platform_type=4, ua=unity_ua)
            jwt = login_resp.get(8)
            if isinstance(jwt, bytes):
                jwt = jwt.decode("utf-8", errors="ignore")
            if not jwt:
                raise RuntimeError("MajorLogin failed: JWT missing")
            L_ok(f"  jwt = {jwt[:60]}…")

            # STEP 7
            L_step("── STEP 6/7 · send_getlogindata ──")
            status, content = send_getlogindata(session, jwt, open_id,
                                                platform_type="4",
                                                region="IND", ua=unity_ua)
            online_ip, chat_ip = None, None
            if status == 200:
                info = parse_getlogindata_response(content)
                online_ip = info.get("online_ip_port")
                chat_ip   = info.get("account_ip_port")
                L_ok(f"  online_ip_port = {online_ip}")
                L_ok(f"  chat_ip_port   = {chat_ip}")

            L_step("── STEP 7/7 · save account ──")
            account = {
                "uid": uid, "password": password, "nickname": nickname,
                "open_id": open_id, "access_token": access_token,
                "account_id": account_id, "jwt": jwt,
                "online_ip_port": online_ip, "chat_ip_port": chat_ip,
                "msdk_ua": msdk_ua, "unity_ua": unity_ua,
                "created_at": datetime.now().isoformat(),
            }

            if not save_account(account):
                raise RuntimeError("Account could not be saved")

            with file_lock:
                counters["success"] += 1
                counters["active"] -= 1
                account_succeeded = True
                done = counters["success"]

            with print_lock:
                print()
                print("╔" + "═" * 66 + "╗")
                print("║" + f"  ✅ ACCOUNT #{done}/{total} CREATED".ljust(66) + "║")
                print("╠" + "═" * 66 + "╣")
                print("║" + f"  Nickname : {nickname:<51}║")
                print("║" + f"  UID      : {uid:<51}║")
                print("║" + f"  Password : {password:<51}║")
                print("║" + f"  JWT      : {jwt[:51]:<51}║")
                print("╚" + "═" * 66 + "╝")
                print()

            if done >= total:
                L_ok(f"TARGET REACHED ({done}/{total}) — stopping")
                stop_flag.set()
                break

        except Exception as e:
            with file_lock:
                counters["active"] = max(0, counters["active"] - 1)
                counters["failed"] += 1
            L_err(f"WORKER #{worker_id} account failed: {e}")
            if stop_flag.is_set(): break
            time.sleep(2)
        finally:
            if session is not None:
                try: session.close()
                except Exception: pass


def generate_accounts(total: int, threads: int = 5, reset_existing: bool = False):
    """Generate accounts from the existing generator without using its CLI prompt."""
    global stop_flag
    total = max(1, int(total))
    threads = max(1, min(30, int(threads)))
    stop_flag.clear()

    if reset_existing:
        with file_lock:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    # IMPORTANT: reset_existing=True means the requested number is the FINAL
    # number of accounts in accounts.json.  The old implementation let every
    # worker start at once, so e.g. requesting 4 with 5 workers could create
    # 5+ accounts before the shared counter noticed the target was reached.
    counters = {"success": 0, "failed": 0, "active": 0}
    started = time.time()

    with ThreadPoolExecutor(max_workers=min(threads, total)) as executor:
        futures = []
        # Workers reserve an in-flight slot before creating an account.  This
        # guarantees: success + active <= total, so the generator can never
        # overshoot the requested count.
        for i in range(1, min(threads, total) + 1):
            futures.append(executor.submit(create_one_account, i, total, counters))

        try:
            while True:
                with file_lock:
                    done = counters["success"] >= total
                    no_active = counters["active"] == 0
                if done or (no_active and all(f.done() for f in futures)):
                    break
                time.sleep(0.25)
        finally:
            stop_flag.set()
            for f in futures:
                try:
                    f.result(timeout=5)
                except Exception:
                    pass

    # Keep the file exact when the caller asked for a fresh pool.  This is a
    # defensive trim only; normally the reservation logic above makes it a no-op.
    if reset_existing:
        with file_lock:
            data = load_json(ACCOUNTS_FILE)
            if len(data) > total:
                data = data[:total]
                with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

    return {
        "target": total,
        "created": counters["success"],
        "failed": counters["failed"],
        "elapsed": round(time.time() - started, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    global stop_flag
    stop_flag.clear()

    print()
    print("╔" + "═" * 66 + "╗")
    print("║" + "   RISHU Gen".center(66) + "║")
    print("╚" + "═" * 66 + "╝")
    print()

    print("┌─[ ⚙️  GENERATOR CONFIGURATION ]" + "─" * 34 + "┐")
    total   = prompt_int("│  🔢 Accounts to generate : ", default=10, min_v=1)
    threads = prompt_int("│  🧵 Worker threads       : ", default=5,  min_v=1, max_v=30)
    print("└" + "─" * 67 + "┘")
    print()

    print("  📌 MajorLogin fields: FIXED (matches working version)")
    print("  🎲 User-Agent: randomized across 8 MSDK + 4 Unity UAs")
    print(f"  📄 Log file : {LOG_FILE}")
    print()

    input("  ▶ Press ENTER to start generation... ")
    print()

    counters = {"success": 0, "failed": 0}
    start_time = time.time()

    try:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [
                executor.submit(create_one_account, i, total, counters)
                for i in range(1, threads + 1)
            ]
            while counters["success"] < total:
                time.sleep(0.5)
            stop_flag.set()
    except KeyboardInterrupt:
        print("\n  ⏹️  Stopped by user.")
        stop_flag.set()

    elapsed = time.time() - start_time
    print()
    print("═" * 50)
    print(f"  Total   : {total}")
    print(f"  Reached : {counters['success']}")
    print(f"  Time    : {elapsed:.1f}s")
    print("═" * 50)
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  ⏹️  Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception("FATAL: %s", e)
        sys.exit(1)