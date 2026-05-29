#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""McuPilot 通用 RTT 二进制数据采集 — 三种模式, Numpy 降维, 零拷贝"""
import sys, os, time, glob, json, argparse, warnings
import yaml
import pylink
import numpy as np
from pathlib import Path

warnings.filterwarnings("ignore", category=RuntimeWarning)

NP_TYPE_MAP = {"u8":"u1","u16":"<u2","u32":"<u4","i8":"i1","i16":"<i2","i32":"<i4","f32":"<f4"}
DTYPE_MAP   = {"u8":"uint8","u16":"uint16","u32":"uint32","i8":"int8","i16":"int16","i32":"int32","f32":"float32"}


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


def _safe(val):
    try:
        v = float(val)
        return 0.0 if np.isnan(v) or np.isinf(v) else v
    except (ValueError, TypeError):
        return 0.0


def _stats(col, name):
    return {
        "name": name,
        "dtype": str(col.dtype),
        "min": _safe(np.nanmin(col)),
        "max": _safe(np.nanmax(col)),
        "mean": _safe(np.nanmean(col)),
        "variance": _safe(np.nanvar(col)),
    }


def rtt_capture(channel, duration_ms, mcu_device="Cortex-M4",
                format=None, count=1, aggregate=None, frame_size=None, fields=None):
    """三种模式: 简单流(format+count=1), 多通道流(format+count>1), 复杂帧(frame_size+fields)"""

    # ── 参数校验 ──
    if frame_size is not None and fields is not None:
        mode = "complex"
    elif format is not None:
        mode = "stream"
        elem_size = int(NP_TYPE_MAP[format][1])  # "<f4" → 4
        if frame_size is None:
            frame_size = elem_size * count
    else:
        return {"status": "error", "message": "缺少 format 或 frame_size+fields"}

    # ── J-Link 采集 ──
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
            jlink.connect(mcu_device, speed=4000)
        except Exception:
            jlink.connect("Cortex-M4", speed=4000)

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

        while True:
            trash = jlink.rtt_read(channel, 8192)
            if not trash:
                break

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

    frames_captured = len(raw_bytes) // frame_size
    if frames_captured == 0:
        return {"status": "success", "duration_ms": duration_ms, "frames_captured": 0, "columns": []}

    valid = raw_bytes[:frames_captured * frame_size]
    columns = []

    # ━━━ 模式 1: 简单流 (format + count=1) ━━━
    if mode == "stream" and count == 1:
        data = np.frombuffer(valid, dtype=NP_TYPE_MAP[format])
        columns.append(_stats(data, "stream"))

    # ━━━ 模式 2: 多通道流 (format + count>1) ━━━
    elif mode == "stream" and count > 1:
        flat = np.frombuffer(valid, dtype=NP_TYPE_MAP[format])
        matrix = flat.reshape(-1, count)

        if aggregate and aggregate != "none":
            agg_map = {"max": matrix.max, "min": matrix.min, "mean": matrix.mean, "sum": matrix.sum}
            agg_fn = agg_map.get(aggregate, matrix.max)
            col = agg_fn(axis=1)
            columns.append(_stats(col, f"agg_{aggregate}_{format}_x{count}"))
        else:
            for i in range(count):
                col = matrix[:, i]
                columns.append(_stats(col, f"ch{i}"))

    # ━━━ 模式 3: 复杂异构帧 ━━━
    elif mode == "complex":
        dtype_spec = {
            "names": [f["name"] for f in fields],
            "formats": [NP_TYPE_MAP[f["type"]] for f in fields],
            "offsets": [f["offset"] for f in fields],
            "itemsize": frame_size,
        }
        data = np.frombuffer(valid, dtype=dtype_spec)
        for f in fields:
            col = data[f["name"]]
            columns.append(_stats(col, f["name"]))

    return {"status": "success", "duration_ms": duration_ms, "frames_captured": frames_captured, "columns": columns}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument("--duration", type=int, default=500)
    parser.add_argument("--format", type=str, default=None)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--aggregate", type=str, default=None)
    parser.add_argument("--frame-size", type=int, default=None)
    parser.add_argument("--fields", type=str, default=None, help='JSON fields array')
    parser.add_argument("--config", default="project_config.yaml")
    args = parser.parse_args()

    mcu_device = "Cortex-M4"
    try:
        if Path(args.config).exists():
            with open(args.config, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
                mcu_device = cfg.get("hardware", {}).get("mcu", mcu_device)
    except Exception:
        pass

    fields = json.loads(args.fields) if args.fields else None

    result = rtt_capture(args.channel, args.duration, mcu_device=mcu_device,
                         format=args.format, count=args.count, aggregate=args.aggregate,
                         frame_size=args.frame_size, fields=fields)
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
