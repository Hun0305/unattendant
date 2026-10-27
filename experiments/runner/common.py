"""실험 러너 공통: 경로, 모델 목록, 시스템 상태, 시작 조건, 측정 조건 기록 (docs/experiments.md 7·9절)."""
from __future__ import annotations

import fcntl
import json
import os
import platform
import subprocess
import time
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
EXP_DIR = Path(__file__).resolve().parents[1]  # experiments/
REPO = EXP_DIR.parent

# 경로는 환경 변수로 바꿀 수 있다 (시험용)
MODELS_TOML = Path(os.environ.get("EXP_MODELS_TOML", EXP_DIR / "models.toml"))
MODELS_DIR = Path(os.environ.get("EXP_MODELS_DIR", "~/models/gguf")).expanduser()
LLAMA_DIR = Path(os.environ.get("EXP_LLAMA_DIR", "~/opt/llama.cpp/v0.6.0")).expanduser()
RESULTS_DIR = Path(os.environ.get("EXP_RESULTS_DIR", EXP_DIR / "results"))
LOGS_DIR = Path(os.environ.get("EXP_LOGS_DIR", REPO / "logs"))  # git 제외

START_TEMP_MAX_C = float(os.environ.get("EXP_START_TEMP_MAX", "50"))  # 측정 시작 온도 상한 (5.2절)
TEMP_ABORT_C = float(os.environ.get("EXP_TEMP_ABORT", "80"))  # 실행 중 이 온도에 닿으면 멈춘다 (architecture.md 가드레일)
COOLDOWN_MAX_S = 600
MEM_MARGIN = 300 << 20  # MemAvailable ≥ MemoryMax + 300MB (7.2절)
LOAD1_MAX = 0.5
CYCLE_UNIT = "huninn-cycle.service"
VSCODE_MARKER = os.environ.get("EXP_VSCODE_MARKER", "/.vscode-server/").encode()  # 시험에서 바꾼다


def now() -> datetime:
    return datetime.now(KST)


def read(path: str | Path) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


# ── 모델 ─────────────────────────────────────────────

def load_models() -> dict[str, dict]:
    with MODELS_TOML.open("rb") as f:
        return {m["id"]: m for m in tomllib.load(f).get("model", [])}


def model_file(model_id: str, quant: str) -> tuple[dict, dict, Path]:
    """등록된 모델의 파일 항목과 경로. 없거나 크기가 다르면 ValueError."""
    models = load_models()
    if model_id not in models:
        raise ValueError(f"models.toml에 없는 모델: {model_id}")
    model = models[model_id]
    entry = next((f for f in model.get("file", []) if f["quant"] == quant), None)
    if entry is None:
        raise ValueError(f"{model_id}에 {quant} 파일이 없다")
    path = MODELS_DIR / entry["file"]
    if not path.exists() or path.stat().st_size != entry["size"]:
        raise ValueError(f"모델 파일이 없거나 크기가 다르다: {path} (fetch_models.py로 받는다)")
    return model, entry, path


# ── 시스템 상태 ──────────────────────────────────────

def temp_c() -> float | None:
    raw = read("/sys/class/thermal/thermal_zone0/temp")
    return round(int(raw) / 1000, 1) if raw and raw.isdigit() else None


def vcgencmd(*args: str) -> str | None:
    try:
        out = subprocess.run(["vcgencmd", *args], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def throttled() -> int | None:
    """get_throttled 값. 비트 0~3이 지금 상태(저전압, 클럭 제한, 스로틀링, 소프트 온도 제한)다."""
    out = vcgencmd("get_throttled")  # throttled=0x0
    try:
        return int(out.split("=", 1)[1], 16) if out else None
    except (IndexError, ValueError):
        return None


def arm_mhz() -> int | None:
    out = vcgencmd("measure_clock", "arm")  # frequency(48)=1800404352
    try:
        return round(int(out.split("=", 1)[1]) / 1e6) if out else None
    except (IndexError, ValueError):
        return None


def meminfo() -> dict[str, int]:
    """/proc/meminfo (바이트)."""
    out = {}
    for line in (read("/proc/meminfo") or "").splitlines():
        key, _, value = line.partition(":")
        parts = value.split()
        if parts and parts[0].isdigit():
            out[key] = int(parts[0]) * (1024 if parts[1:] == ["kB"] else 1)
    return out


def vmstat() -> dict[str, int]:
    out = {}
    for line in (read("/proc/vmstat") or "").splitlines():
        key, _, value = line.partition(" ")
        if value.isdigit():
            out[key] = int(value)
    return out


def cpu_ticks() -> tuple[int, int]:
    """/proc/stat 전체 CPU의 (바쁜 틱, 전체 틱). guest는 user에 이미 들어 있어 뺀다."""
    fields = [int(x) for x in (read("/proc/stat") or "cpu 0").splitlines()[0].split()[1:9]]
    fields += [0] * (8 - len(fields))
    total = sum(fields)
    idle = fields[3] + fields[4]  # idle + iowait
    return total - idle, total


def loadavg1() -> float:
    return float((read("/proc/loadavg") or "0").split()[0])


def own_cgroup() -> Path:
    for line in (read("/proc/self/cgroup") or "").splitlines():
        if line.startswith("0::"):
            return Path("/sys/fs/cgroup") / line[3:].lstrip("/")
    return Path("/sys/fs/cgroup")


def cgroup_value(cg: Path, name: str) -> int | None:
    raw = read(cg / name)
    return int(raw) if raw and raw.isdigit() else None  # "max"면 None


def cgroup_cpu_usec(cg: Path) -> int | None:
    for line in (read(cg / "cpu.stat") or "").splitlines():
        key, _, value = line.partition(" ")
        if key == "usage_usec":
            return int(value)
    return None


def vscode_pids() -> list[int]:
    """VS Code 원격 서버 프로세스. 연결을 끊어도 한동안 남을 수 있어 연결이 아니라 프로세스를 본다 (7.2절)."""
    pids, me = [], os.getpid()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == me:
            continue
        try:
            cmdline = (proc / "cmdline").read_bytes()
        except OSError:
            continue
        if VSCODE_MARKER in cmdline:
            pids.append(int(proc.name))
    return pids


def cycle_active() -> bool:
    try:
        out = subprocess.run(["systemctl", "is-active", CYCLE_UNIT], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.stdout.strip() in ("active", "activating", "deactivating", "reloading")


def start_problems(memory_max: int | None) -> list[str]:
    """시작 조건(7.2절) 중 안 맞는 것. 비어 있으면 시작해도 된다."""
    problems = []
    if pids := vscode_pids():
        problems.append(f"VS Code 서버 프로세스 {len(pids)}개")
    if cycle_active():
        problems.append("Huninn 사이클이 돌고 있다")
    available = meminfo().get("MemAvailable", 0)
    need = (memory_max or 0) + MEM_MARGIN
    if available < need:
        problems.append(f"MemAvailable {available >> 20}MB < 필요 {need >> 20}MB")
    if (load := loadavg1()) >= LOAD1_MAX:
        problems.append(f"1분 부하 평균 {load}")
    return problems


CYCLE_WAIT_MAX_S = 45 * 60


def wait_cycle() -> int:
    """Huninn 사이클이 끝날 때까지 기다린다(7.1절: 실험이 사이클에 양보한다). 기다린 초. 너무 길면 RuntimeError."""
    started = time.monotonic()
    while cycle_active():
        if time.monotonic() - started > CYCLE_WAIT_MAX_S:
            raise RuntimeError("Huninn 사이클이 45분 넘게 끝나지 않는다")
        time.sleep(30)
    return int(time.monotonic() - started)


def oom_kills(cg: Path) -> int:
    """이 cgroup에서 메모리 상한 때문에 죽은 프로세스 수 (memory.events)."""
    for line in (read(cg / "memory.events") or "").splitlines():
        key, _, value = line.partition(" ")
        if key == "oom_kill":
            return int(value)
    return 0


def evict_page_cache(path: Path) -> None:
    """파일을 페이지 캐시에서 비운다(권한 없이 된다). 다음 읽기가 SD카드에서 일어나 콜드 로드를 잴 수 있다."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)


def wait_cool(limit_c: float = START_TEMP_MAX_C, max_s: int = COOLDOWN_MAX_S) -> tuple[float | None, int]:
    """CPU가 limit_c 이하가 될 때까지 기다린다. (시작 온도, 기다린 초)."""
    started = time.monotonic()
    while True:
        t = temp_c()
        waited = int(time.monotonic() - started)
        if t is None or t <= limit_c or waited >= max_s:
            return t, waited
        time.sleep(5)


# ── 측정 조건 기록 ───────────────────────────────────

def _git(cwd: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def llama_info() -> dict:
    configure = read(LLAMA_DIR / "build-configure.log") or ""
    variant = next((line.split(":", 1)[1].strip() for line in configure.splitlines()
                    if "Adding CPU backend variant" in line), None)
    return {
        "dir": str(LLAMA_DIR),
        "tag": _git(LLAMA_DIR, "describe", "--tags", "--exact-match"),
        "commit": _git(LLAMA_DIR, "rev-parse", "HEAD"),
        "cpu_backend_flags": variant,  # 예: -mcpu=cortex-a72+crc+nodotprod+noi8mm+nosve+nosme
    }


def system_info() -> dict:
    cpuinfo = read("/proc/cpuinfo") or ""
    features = next((line.split(":", 1)[1].strip() for line in cpuinfo.splitlines() if line.startswith("Features")), None)
    os_release = dict(line.split("=", 1) for line in (read("/etc/os-release") or "").splitlines() if "=" in line)
    mem = meminfo()
    return {
        "board": (read("/proc/device-tree/model") or "").rstrip("\x00"),
        "cpu_features": features,
        "cpu_count": os.cpu_count(),
        "governor": read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
        "mem_total_mb": mem.get("MemTotal", 0) >> 20,
        "swap": [line.split()[0] for line in (read("/proc/swaps") or "").splitlines()[1:]],
        "kernel": platform.release(),
        "os": os_release.get("PRETTY_NAME", "").strip('"'),
        "python": platform.python_version(),
    }


def code_version() -> dict:
    """이 러너와 모델 목록의 버전. 커밋하지 않은 변경이 있으면 dirty."""
    paths = ["experiments/runner", "experiments/models.toml", "experiments/plans", "experiments/templates"]
    status = _git(REPO, "status", "--porcelain", "--", *paths)
    return {"commit": _git(REPO, "rev-parse", "HEAD"), "dirty": bool(status)}


# ── 기록 ─────────────────────────────────────────────

def log_event(event: str, **fields) -> None:
    """logs/experiments.jsonl(비공개)과 표준 출력(유닛이면 journal)에 남긴다."""
    record = {"at": now().isoformat(timespec="seconds"), "event": event, **fields}
    line = json.dumps(record, ensure_ascii=False)
    print(line, flush=True)
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with (LOGS_DIR / "experiments.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def acquire_lock():
    """실험은 한 번에 하나만 돈다 (7.1절). 잠금 파일 객체를 돌려주고, 이미 누가 잡고 있으면 None."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    lock = (LOGS_DIR / "exp-run.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return None
    return lock
