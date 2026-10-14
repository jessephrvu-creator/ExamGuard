
import asyncio
import csv
import io
import logging
import sys
import threading
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file
from bleak import BleakScanner

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

LOCK = threading.Lock()
NEAR_RSSI = -60
MEDIUM_RSSI = -75
HISTORY_LIMIT = 10

state = {
    "current_scan": [],
    "previous_scan": [],
    "current_scan_time": None,
    "previous_scan_time": None,
    "live_scan": {},
    "known_names": {},
    "windows_connected_unmatched": [],
    "windows_connected_checked_at": None,
    "windows_connected_status": "not_checked",
    "scanning": False,
    "last_error": None,
}

def norm_address(value):
    if isinstance(value, int):
        if value <= 0 or value > 0xFFFFFFFFFFFF:
            return None
        return f"{value:012X}"

    if not isinstance(value, str):
        return None

    value = value.replace(":", "").replace("-", "").strip().upper()

    if len(value) != 12 or any(c not in "0123456789ABCDEF" for c in value):
        return None

    return value


def norm_guid(value):
    try:
        return str(uuid.UUID(str(value))).casefold() if value else None
    except (ValueError, TypeError, AttributeError):
        return None


def clean_name(value, address=None):
    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value or value.casefold() in {
        "unknown",
        "unknown device",
        "name unavailable",
        "n/a",
    }:
        return None

    return value


def signal_band(rssi):
    if rssi is None:
        return "Unknown"
    if rssi >= NEAR_RSSI:
        return "Near / Strong"
    if rssi >= MEDIUM_RSSI:
        return "Medium"
    return "Far / Weak"


def remember_names(rows):
    for row in rows:
        address = norm_address(row.get("address"))
        name = clean_name(row.get("name"))

        if address and name:
            state["known_names"].setdefault(
                address,
                {
                    "name": name,
                    "name_source": row.get("name_source"),
                },
            )


def get_property_guid(properties):
    try:
        value = properties.get("System.Devices.Aep.ContainerId")

        if value is None:
            return None

        try:
            from winrt.windows.foundation import IPropertyValue
            value = value.as_(IPropertyValue).get_guid()
        except Exception:
            pass

        return norm_guid(value)

    except Exception:
        return None


async def windows_connected_devices():
    """Enumerate Windows-connected classic Bluetooth devices."""
    if sys.platform != "win32":
        return {"devices": [], "status": "unsupported"}

    try:
        from winrt.windows.devices.bluetooth import (
            BluetoothConnectionStatus,
            BluetoothDevice,
        )
        from winrt.windows.devices.enumeration import DeviceInformation

        selector = BluetoothDevice.get_device_selector_from_connection_status(
            BluetoothConnectionStatus.CONNECTED
        )

        infos = await asyncio.wait_for(
            DeviceInformation.find_all_async_aqs_filter_and_additional_properties(
                selector,
                ["System.Devices.Aep.ContainerId"],
            ),
            timeout=8,
        )

        results = []

        for info in infos:
            device = None

            try:
                device = await BluetoothDevice.from_id_async(info.id)

                if device is None:
                    continue

                address = norm_address(int(device.bluetooth_address))

                if not address:
                    continue

                results.append({
                    "address": address,
                    "name": clean_name(device.name) or clean_name(info.name),
                    "container_id": get_property_guid(info.properties),
                    "connection_status": "Connected",
                })

            except Exception as exc:
                app.logger.debug(
                    "Windows device skipped: %s", type(exc).__name__
                )

            finally:
                if device is not None:
                    try:
                        device.close()
                    except Exception:
                        pass

        return {"devices": results, "status": "success"}

    except asyncio.TimeoutError:
        return {"devices": [], "status": "timeout"}

    except Exception as exc:
        app.logger.warning(
            "Windows enumeration failed: %s", type(exc).__name__
        )
        return {"devices": [], "status": "failed"}


async def direct_windows_ble_scan(duration=15):
    """Read actual RSSI values from Windows BLE advertisements."""
    if sys.platform != "win32":
        return

    try:
        from winrt.windows.devices.bluetooth.advertisement import (
            BluetoothLEAdvertisementWatcher,
            BluetoothLEScanningMode,
        )
    except Exception as exc:
        app.logger.warning(
            "Native Windows BLE API unavailable: %s", type(exc).__name__
        )
        return

    watcher = BluetoothLEAdvertisementWatcher()
    watcher.scanning_mode = BluetoothLEScanningMode.ACTIVE
    loop = asyncio.get_running_loop()

    def on_received(sender, args):
        try:
            address = norm_address(int(args.bluetooth_address))
            if not address:
                return

            rssi = int(args.raw_signal_strength_in_dbm)
            if rssi <= -127:
                return

            try:
                name = clean_name(args.advertisement.local_name)
            except Exception:
                name = None

            now = datetime.now().timestamp()

            def update():
                with LOCK:
                    old = state["live_scan"].get(address, {})
                    final_name = name or old.get("name")
                    source = (
                        "Windows BLE advertisement"
                        if name
                        else old.get("name_source")
                    )

                    history = (
                        old.get("rssi_history", []) + [rssi]
                    )[-HISTORY_LIMIT:]

                    state["live_scan"][address] = {
                        **old,
                        "address": address,
                        "name": final_name,
                        "name_source": source,
                        "rssi": rssi,
                        "signal": signal_band(rssi),
                        "rssi_history": history,
                        "last_seen": now,
                        "last_rssi_time": now,
                        "connection_status": old.get(
                            "connection_status", "Detected"
                        ),
                    }

                    if final_name:
                        state["known_names"][address] = {
                            "name": final_name,
                            "name_source": source,
                        }

            loop.call_soon_threadsafe(update)

        except Exception as exc:
            app.logger.debug(
                "BLE advertisement ignored: %s", type(exc).__name__
            )

    watcher.received.add(on_received)

    try:
        watcher.start()
        await asyncio.sleep(duration)
    finally:
        try:
            watcher.stop()
        except Exception:
            pass

        try:
            watcher.received.remove(on_received)
        except Exception:
            pass


async def bleak_scan(duration=15):
    """Scan BLE advertisements and attempt Windows identifier resolution."""
    cache_tasks = {}
    attempted = set()

    async def resolve_name(address):
        if sys.platform != "win32":
            return

        device = None

        try:
            from winrt.windows.devices.bluetooth import BluetoothLEDevice
            from winrt.windows.devices.enumeration import DeviceInformation

            device = await BluetoothLEDevice.from_bluetooth_address_async(
                int(address, 16)
            )

            if device is None:
                app.logger.info(
                    "BLE %s: Windows returned no device record", address
                )
                return

            name = clean_name(device.name)
            container_id = None

            try:
                info = await DeviceInformation.create_from_id_async(
                    device.device_id,
                    ["System.Devices.Aep.ContainerId"],
                )

                if info is not None:
                    container_id = get_property_guid(info.properties)

            except Exception as exc:
                app.logger.info(
                    "BLE %s: container lookup failed (%s)",
                    address,
                    type(exc).__name__,
                )

            app.logger.info(
                "BLE %s: name=%r container_id=%r",
                address,
                name,
                container_id,
            )

            with LOCK:
                row = state["live_scan"].get(address)

                if row:
                    if name and not row.get("name"):
                        row["name"] = name
                        row["name_source"] = "Windows BLE device"

                    if container_id:
                        row["container_id"] = container_id

        except Exception as exc:
            app.logger.info(
                "BLE %s: Windows resolution failed (%s)",
                address,
                type(exc).__name__,
            )

        finally:
            if device is not None:
                try:
                    device.close()
                except Exception:
                    pass

    def detected(device, advertisement):
        address = norm_address(getattr(device, "address", None))

        if not address:
            return

        name = clean_name(getattr(advertisement, "local_name", None))
        source = "BLE advertisement" if name else None

        if not name:
            name = clean_name(getattr(device, "name", None))
            if name:
                source = "Bleak device name"

        try:
            rssi = int(advertisement.rssi)
        except (TypeError, ValueError, AttributeError):
            rssi = None

        now = datetime.now().timestamp()

        with LOCK:
            old = state["live_scan"].get(address, {})
            known = state["known_names"].get(address, {})

            name = name or old.get("name") or known.get("name")
            source = source or old.get("name_source") or known.get(
                "name_source"
            )

            history = old.get("rssi_history", [])[:]
            last_rssi_time = old.get("last_rssi_time")

            if rssi is not None:
                history = (history + [rssi])[-HISTORY_LIMIT:]
                last_rssi_time = now
            else:
                rssi = old.get("rssi")

            state["live_scan"][address] = {
                **old,
                "address": address,
                "name": name,
                "name_source": source,
                "rssi": rssi,
                "signal": signal_band(rssi),
                "rssi_history": history,
                "last_seen": now,
                "last_rssi_time": last_rssi_time,
                "connection_status": old.get(
                    "connection_status", "Detected"
                ),
            }

            if name:
                state["known_names"][address] = {
                    "name": name,
                    "name_source": source,
                }

            # Resolve all observed addresses, not only unnamed devices.
            if address not in attempted:
                attempted.add(address)
                cache_tasks[address] = asyncio.create_task(
                    resolve_name(address)
                )

    scanner = BleakScanner(
        detection_callback=detected,
        scanning_mode="active",
    )

    await scanner.start()

    try:
        await asyncio.sleep(duration)
    finally:
        await scanner.stop()

    if cache_tasks:
        await asyncio.gather(
            *cache_tasks.values(),
            return_exceptions=True,
        )


async def discover_devices():
    with LOCK:
        state["live_scan"] = {}

    windows_task = asyncio.create_task(windows_connected_devices())
    bleak_task = asyncio.create_task(bleak_scan(15))
    native_task = asyncio.create_task(direct_windows_ble_scan(15))

    await asyncio.gather(
        bleak_task,
        native_task,
        return_exceptions=True,
    )

    windows_result = await windows_task
    windows_devices = windows_result["devices"]

    with LOCK:
        matched_addresses = set()
        matched_container_ids = set()

        for address, row in state["live_scan"].items():
            key = norm_address(address)
            row_container = norm_guid(row.get("container_id"))

            matches = [
                item for item in windows_devices
                if norm_address(item.get("address")) == key
            ]

            if not matches and row_container:
                matches = [
                    item for item in windows_devices
                    if norm_guid(item.get("container_id")) == row_container
                ]

            # A single exact address or shared container ID is required.
            if len(matches) == 1:
                matched = matches[0]
                row["connection_status"] = "Connected"

                matched_address = norm_address(matched.get("address"))
                if matched_address:
                    matched_addresses.add(matched_address)

                matched_container = norm_guid(
                    matched.get("container_id")
                )
                if matched_container:
                    matched_container_ids.add(matched_container)

                if not row.get("name") and matched.get("name"):
                    row["name"] = matched["name"]
                    row["name_source"] = "Windows connected device"

        state["windows_connected_unmatched"] = [
            {
                "address": item["address"],
                "name": item.get("name") or "Name unavailable",
                "connection_status": "Connected",
                "rssi": None,
                "signal": "Unknown",
            }
            for item in windows_devices
            if norm_address(item["address"]) not in matched_addresses
            and not (
                norm_guid(item.get("container_id"))
                and norm_guid(item.get("container_id"))
                in matched_container_ids
            )
        ]

        state["windows_connected_status"] = windows_result["status"]
        state["windows_connected_checked_at"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        return sorted(
            [
                {
                    **row,
                    "rssi_history": row.get("rssi_history", [])[:],
                }
                for row in state["live_scan"].values()
            ],
            key=lambda row: (
                row.get("rssi") is None,
                -(row["rssi"] if row.get("rssi") is not None else -999),
            ),
        )


def scan_worker():
    try:
        results = asyncio.run(discover_devices())

        with LOCK:
            state["previous_scan"] = state["current_scan"][:]
            state["previous_scan_time"] = state["current_scan_time"]
            state["current_scan"] = results
            state["current_scan_time"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            state["last_error"] = None

    except Exception as exc:
        app.logger.exception("ExamGuard scan failed")

        with LOCK:
            state["last_error"] = str(exc)
            state["windows_connected_status"] = "failed"

    finally:
        with LOCK:
            state["scanning"] = False


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    with LOCK:
        now = datetime.now().timestamp()
        rows = (
            list(state["live_scan"].values())
            if state["scanning"]
            else state["current_scan"]
        )

        devices = []

        for row in rows:
            item = {
                **row,
                "rssi_history": row.get("rssi_history", [])[:],
            }
            last_rssi = item.get("last_rssi_time")
            item["rssi_stale"] = (
                last_rssi is None or now - last_rssi > 5
            )
            devices.append(item)

        return jsonify({
            "current_scan": devices,
            "previous_scan": state["previous_scan"],
            "current_scan_time": state["current_scan_time"],
            "previous_scan_time": state["previous_scan_time"],
            "scanning": state["scanning"],
            "last_error": state["last_error"],
            "thresholds": {
                "near": NEAR_RSSI,
                "medium": MEDIUM_RSSI,
            },
            "windows_connected_unmatched":
                state["windows_connected_unmatched"],
            "windows_connected_checked_at":
                state["windows_connected_checked_at"],
            "windows_connected_status":
                state["windows_connected_status"],
        })


@app.post("/api/scan")
def api_scan():
    with LOCK:
        if state["scanning"]:
            return jsonify({
                "ok": False,
                "message": "A scan is already running.",
            }), 409

        remember_names(state["current_scan"])
        state["scanning"] = True
        state["last_error"] = None
        state["live_scan"] = {}
        state["windows_connected_unmatched"] = []
        state["windows_connected_checked_at"] = None
        state["windows_connected_status"] = "checking"

    threading.Thread(target=scan_worker, daemon=True).start()

    return jsonify({
        "ok": True,
        "message": "15-second scan started.",
    })


@app.get("/api/compare")
def api_compare():
    with LOCK:
        previous = state["previous_scan"][:]
        current = state["current_scan"][:]
        previous_time = state["previous_scan_time"]
        current_time = state["current_scan_time"]

    old = {d["address"]: d for d in previous}
    new = {d["address"]: d for d in current}

    return jsonify({
        "previous_count": len(previous),
        "current_count": len(current),
        "previous_scan_time": previous_time,
        "current_scan_time": current_time,
        "common": [new[a] for a in sorted(set(old) & set(new))],
        "new": [new[a] for a in sorted(set(new) - set(old))],
        "not_observed": [old[a] for a in sorted(set(old) - set(new))],
        "note": "Not observed does not prove absent or cheating.",
    })


@app.get("/api/export.csv")
def api_export():
    with LOCK:
        devices = state["current_scan"][:]
        scan_time = state["current_scan_time"] or ""

    selected = request.args.get("signal", "All signals")

    filters = {
        "Near / Strong": lambda r: r is not None and r >= NEAR_RSSI,
        "Medium": lambda r: r is not None and MEDIUM_RSSI <= r < NEAR_RSSI,
        "Far / Weak": lambda r: r is not None and r < MEDIUM_RSSI,
        "Unknown RSSI": lambda r: r is None,
    }

    if selected in filters:
        devices = [
            d for d in devices
            if filters[selected](d.get("rssi"))
        ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Scan Time",
        "Device Name",
        "BLE Address",
        "Connection Status",
        "RSSI (dBm)",
        "Signal Band",
    ])

    for item in devices:
        writer.writerow([
            scan_time,
            item.get("name") or "",
            item.get("address"),
            item.get("connection_status", "Detected"),
            "" if item.get("rssi") is None else item["rssi"],
            item.get("signal", "Unknown"),
        ])

    memory = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    memory.seek(0)

    return send_file(
        memory,
        mimetype="text/csv",
        as_attachment=True,
        download_name="examguard_scan_results.csv",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
