from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass

from pymavlink import mavutil


MAX_LOG_BYTES = int(os.getenv("MAVLINK_LOG_MAX_BYTES", str(200 * 1024 * 1024)))
LOG_DATA_CHUNK_SIZE = 90
LOG_REQUEST_WINDOW_SIZE = int(os.getenv("MAVLINK_LOG_REQUEST_WINDOW_BYTES", str(64 * 1024)))


class MavlinkImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class MavlinkLogEntry:
    id: int
    size: int
    time_utc: int
    num_logs: int
    last_log_num: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class DownloadedMavlinkLog:
    entry: MavlinkLogEntry
    payload: bytes


def _connect(connection: str, baud: int, timeout_s: float):
    master = mavutil.mavlink_connection(connection, baud=baud, autoreconnect=False)
    heartbeat = master.wait_heartbeat(timeout=timeout_s)
    if heartbeat is None:
        master.close()
        raise MavlinkImportError("MAVLink HEARTBEAT を受信できませんでした。接続先を確認してください。")
    return master


def _collect_log_entries(master, timeout_s: float) -> list[MavlinkLogEntry]:
    master.mav.log_request_list_send(master.target_system, master.target_component, 0, 0xFFFF)

    entries: dict[int, MavlinkLogEntry] = {}
    expected_count: int | None = None
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        message = master.recv_match(type="LOG_ENTRY", blocking=True, timeout=0.5)
        if message is None:
            continue

        entry = MavlinkLogEntry(
            id=int(message.id),
            size=int(message.size),
            time_utc=int(message.time_utc),
            num_logs=int(message.num_logs),
            last_log_num=int(message.last_log_num),
        )
        entries[entry.id] = entry
        expected_count = entry.num_logs
        if expected_count == 0:
            break
        if expected_count is not None and len(entries) >= expected_count:
            break

    if expected_count == 0:
        return []
    if not entries:
        raise MavlinkImportError("機体からログ一覧を取得できませんでした。")

    return sorted(entries.values(), key=lambda item: item.id, reverse=True)


def list_mavlink_logs(connection: str, baud: int = 115200, timeout_s: float = 10) -> list[MavlinkLogEntry]:
    master = _connect(connection, baud, timeout_s)
    try:
        return _collect_log_entries(master, timeout_s)
    finally:
        master.close()


def _select_log(entries: list[MavlinkLogEntry], log_id: int | None) -> MavlinkLogEntry:
    if not entries:
        raise MavlinkImportError("機体内に取得可能なログがありません。")

    if log_id is None:
        return entries[0]

    for entry in entries:
        if entry.id == log_id:
            return entry

    raise MavlinkImportError(f"ログID {log_id} が見つかりません。")


def _download_log_data(master, entry: MavlinkLogEntry, timeout_s: float) -> bytes:
    if entry.size <= 0:
        raise MavlinkImportError("ログサイズが0バイトのため取り込めません。")
    if entry.size > MAX_LOG_BYTES:
        raise MavlinkImportError(f"ログサイズが上限を超えています。上限: {MAX_LOG_BYTES} bytes")

    payload = bytearray(entry.size)
    offset = 0
    chunk_timeout_s = max(5.0, min(timeout_s, 30.0))
    window_size = max(LOG_DATA_CHUNK_SIZE, LOG_REQUEST_WINDOW_SIZE)

    try:
        while offset < entry.size:
            window_start = offset
            window_end = min(window_start + window_size, entry.size)
            requested = window_end - window_start
            received_offsets: set[int] = set()
            received_bytes = 0

            for _attempt in range(3):
                master.mav.log_request_data_send(
                    master.target_system,
                    master.target_component,
                    entry.id,
                    window_start,
                    requested,
                )
                deadline = time.monotonic() + chunk_timeout_s

                while time.monotonic() < deadline and received_bytes < requested:
                    message = master.recv_match(type="LOG_DATA", blocking=True, timeout=0.5)
                    if message is None:
                        continue
                    if int(message.id) != entry.id:
                        continue

                    message_offset = int(message.ofs)
                    if message_offset < window_start or message_offset >= window_end:
                        continue
                    if message_offset in received_offsets:
                        continue

                    count = min(int(message.count), len(message.data), window_end - message_offset)
                    if count <= 0:
                        continue

                    payload[message_offset : message_offset + count] = bytes(message.data[:count])
                    received_offsets.add(message_offset)
                    received_bytes += count

                if received_bytes >= requested:
                    break

            if received_bytes < requested:
                missing_offset = next(
                    (
                        candidate
                        for candidate in range(window_start, window_end, LOG_DATA_CHUNK_SIZE)
                        if candidate not in received_offsets
                    ),
                    window_start,
                )
                raise MavlinkImportError(f"ログデータの受信がタイムアウトしました。offset={missing_offset}")

            offset = window_end
    finally:
        try:
            master.mav.log_request_end_send(master.target_system, master.target_component)
        except Exception:
            pass

    return bytes(payload)


def download_mavlink_log(
    connection: str,
    baud: int = 115200,
    timeout_s: float = 10,
    log_id: int | None = None,
) -> DownloadedMavlinkLog:
    master = _connect(connection, baud, timeout_s)
    try:
        entries = _collect_log_entries(master, timeout_s)
        entry = _select_log(entries, log_id)
        payload = _download_log_data(master, entry, timeout_s)
        return DownloadedMavlinkLog(entry=entry, payload=payload)
    finally:
        master.close()
