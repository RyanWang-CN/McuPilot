#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""McuPilot 通用 RTT 二进制数据采集 (Channel 分离, 定长帧, 结构化统计)"""
import sys, os, time, glob, json, argparse
import yaml
import pylink
import numpy as np
from pathlib import Path

STRUCT_MAP = {"u8":"B","u16":"H","u32":"I","i8":"b","i16":"h","i32":"i","f32":"f"}
# fmt: off
NP_TYPE_MAP = {"u8":"u1","u16":"<u2","u32":"<u4","i8":"i1","i16":"<i2","i32":"<i4","f32":"<f4"}
# fmt: on

def find_jlink_dll():
    paths = [
        r"C:\Program Files\SEGGER\JLink*\JLink_x64.dll",
        r"C:\Program Files\SEGGER\JLink*\JLinkARM.dll",
        r"C:\Program Files (x86)\SEGGER\JLink*\JLinkARM.dll",
        r"C:\Keil_v5\ARM\Segger\JLinkARM.dll",
    ]
    for p in paths:
        m = glob.glob(p)
        if m:
            return max(m, key=os.path.getmtime)
    return None


def rtt_capture(channel, duration_ms, frame_size, fields):
    """抓取 channel 通道 frame_size 定长帧, 按 fields 偏移提取列后统计"""
    dll = find_jlink_dll()
    if not dll:
        return {"status": "error", "message": "J-Link DLL not found."}

    jlink = pylink.JLink(lib=pylink.Library(dllpath=dll))
    try:
        jlink.open()
    except Exception as e:
        return {"status": "error", "message": f"J-Link open failed: {e}"}

    raw_bytes = bytearray()
    try:
        jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
        try:
            jlink.connect("HC32F460KETA", speed=4000)
        except Exception:
            jlink.connect("Cortex-M0+", speed=4000)

        # Attach 模式，不复位，启动指定通道的 RTT
        for _ in range(40):
            try:
                try: jlink.rtt_stop()
                except Exception: pass
                jlink.rtt_start()
                jlink.rtt_read(0, 1)
                break
            except Exception:
                pass
            time.sleep(0.05)

        timeout_s = duration_ms / 1000.0
        start = time.time()
        while time.time() - start < timeout_s:
            try:
                chunk = jlink.rtt_read(channel, 4096)
                if chunk:
                    raw_bytes.extend(bytes(chunk))
            except Exception:
                pass
            time.sleep(0.002)
    except Exception as e:
        return {"status": "error", "message": f"RTT capture failed: {e}"}
    finally:
        try:
            jlink.rtt_stop()
            jlink.close()
        except Exception:
            pass

    # 定长切帧
    frames_captured = len(raw_bytes) // frame_size
    if frames_captured == 0:
        return {"status": "success", "duration_ms": duration_ms, "frames_captured": 0, "metrics": {}}

    valid = raw_bytes[:frames_captured * frame_size]

    # Numpy 结构化数组零拷贝解析
    dtype_spec = {
        "names": [f["name"] for f in fields],
        "formats": [NP_TYPE_MAP[f["type"]] for f in fields],
        "offsets": [f["offset"] for f in fields],
        "itemsize": frame_size,
    }
    data = np.frombuffer(valid, dtype=dtype_spec)

    metrics = {}
    for f in fields:
        col = data[f["name"]]
        metrics[f["name"]] = {
            "min": float(np.min(col)),
            "max": float(np.max(col)),
            "mean": float(np.mean(col)),
            "variance": float(np.var(col)),
        }

    return {"status": "success", "duration_ms": duration_ms, "frames_captured": frames_captured, "metrics": metrics}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument("--duration", type=int, default=500, help="采集时长(ms)")
    parser.add_argument("--frame-size", type=int, required=True, help="单帧字节数")
    parser.add_argument("--fields", type=str, required=True, help='JSON: [{"name":"v","offset":0,"type":"f32"}]')
    parser.add_argument("--config", default="project_config.yaml")
    args = parser.parse_args()

    # 读 YAML 获取 MCU 型号 (不传 fields 时不强依赖)
    fields = json.loads(args.fields)

    result = rtt_capture(args.channel, args.duration, args.frame_size, fields)
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
