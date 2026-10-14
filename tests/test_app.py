import unittest
from unittest.mock import patch

from app import (
    app,
    apply_windows_connected_names,
    find_connected_windows_match,
    normalize_bluetooth_address,
    remember_scan_names,
    resolve_address_name,
    resolve_connected_windows_name,
    resolve_device_name,
    sort_devices,
    state,
    usable_device_name,
)


class ScanHelpersTests(unittest.TestCase):
    def test_sort_devices_puts_strongest_rssi_first(self):
        devices = [
            {"address": "weak", "rssi": -80},
            {"address": "strong", "rssi": -45},
            {"address": "medium", "rssi": -60},
            {"address": "unavailable", "rssi": None},
        ]

        sorted_devices = sort_devices(devices)

        self.assertEqual(
            [device["address"] for device in sorted_devices],
            ["strong", "medium", "weak", "unavailable"],
        )

    def test_name_is_preserved_when_later_advertisement_has_no_name(self):
        existing_name = "Real advertised name"
        existing_source = "advertisement_data.local_name"

        name, source = resolve_device_name(
            advertised_name=None,
            device_name=None,
            existing_name=existing_name,
            existing_source=existing_source,
        )

        self.assertEqual(name, existing_name)
        self.assertEqual(source, existing_source)

    def test_name_is_preserved_across_scans_by_ble_address(self):
        address = "AA:BB:CC:DD:EE:FF"
        names_before_scan = state["known_names"].copy()
        try:
            state["known_names"][address] = {
                "name": "OnePlus Nord Buds 2r",
                "name_source": "advertisement_data.local_name",
            }

            name, source = resolve_address_name(
                address,
                advertised_name=None,
                device_name=None,
                existing={},
            )

            self.assertEqual(name, "OnePlus Nord Buds 2r")
            self.assertEqual(source, "advertisement_data.local_name")
        finally:
            state["known_names"] = names_before_scan

    def test_later_advertised_name_updates_address_cache(self):
        address = "AA:BB:CC:DD:EE:FF"
        names_before_scan = state["known_names"].copy()
        try:
            state["known_names"][address] = {
                "name": "Earlier real name",
                "name_source": "device.name",
            }

            name, source = resolve_address_name(
                address,
                advertised_name="OnePlus Nord Buds 2r",
                device_name=None,
                existing={},
            )

            self.assertEqual(name, "OnePlus Nord Buds 2r")
            self.assertEqual(source, "advertisement_data.local_name")
            self.assertEqual(
                state["known_names"][address]["name"],
                "OnePlus Nord Buds 2r",
            )
        finally:
            state["known_names"] = names_before_scan

    def test_retained_scan_names_can_repopulate_address_cache(self):
        address = "AA:BB:CC:DD:EE:FF"
        names_before_scan = state["known_names"].copy()
        try:
            state["known_names"].pop(address, None)
            remember_scan_names([
                {
                    "address": address,
                    "name": "OnePlus Nord Buds 2r",
                    "name_source": "advertisement_data.local_name",
                }
            ])

            name, source = resolve_address_name(address, None, None, existing={})

            self.assertEqual(name, "OnePlus Nord Buds 2r")
            self.assertEqual(source, "advertisement_data.local_name")
        finally:
            state["known_names"] = names_before_scan

    def test_generic_names_are_not_cached_or_displayed_as_real_names(self):
        address = "AA:BB:CC:DD:EE:FF"
        self.assertIsNone(usable_device_name("Unknown", address))
        self.assertIsNone(usable_device_name("Name unavailable", address))
        self.assertIsNone(usable_device_name(f"Bluetooth {address}", address))

    def test_generic_current_record_does_not_override_known_real_name(self):
        address = "AA:BB:CC:DD:EE:FF"
        names_before_scan = state["known_names"].copy()
        try:
            state["known_names"][address] = {
                "name": "OnePlus Nord Buds 2r",
                "name_source": "advertisement_data.local_name",
            }

            name, source = resolve_address_name(
                address,
                None,
                None,
                existing={"name": "Name unavailable", "name_source": "device.name"},
            )

            self.assertEqual(name, "OnePlus Nord Buds 2r")
            self.assertEqual(source, "advertisement_data.local_name")
        finally:
            state["known_names"] = names_before_scan

    def test_windows_connected_name_requires_exact_bluetooth_address_match(self):
        address = "AA:BB:CC:DD:EE:FF"
        windows_names = {"AABBCCDDEEFF": "Genuine Windows friendly name"}

        matched = resolve_connected_windows_name(
            address,
            windows_names,
        )
        mismatch = resolve_connected_windows_name(
            "AA:BB:CC:DD:EE:00",
            windows_names,
        )

        self.assertEqual(
            matched,
            ("Genuine Windows friendly name", "windows_connected"),
        )
        self.assertEqual(mismatch, (None, None))
        self.assertEqual(normalize_bluetooth_address(address), "AABBCCDDEEFF")
        self.assertEqual(normalize_bluetooth_address(0xAABBCCDDEEFF), "AABBCCDDEEFF")

    def test_windows_name_does_not_replace_a_ble_advertised_name(self):
        resolved = resolve_connected_windows_name(
            "AA:BB:CC:DD:EE:FF",
            {"AABBCCDDEEFF": "Windows cached name"},
            existing_name="Genuine advertised name",
            existing_source="advertisement_data.local_name",
        )

        self.assertEqual(
            resolved,
            ("Genuine advertised name", "advertisement_data.local_name"),
        )

    def test_windows_name_enriches_only_an_existing_exact_address_ble_row(self):
        address = "AA:BB:CC:DD:EE:FF"
        record = {
            "address": address,
            "name": None,
            "name_source": None,
            "rssi": -57,
            "rssi_history": [-62, -57],
            "last_seen": 1234.5,
        }
        with patch.dict(state, {"live_scan": {address: record}, "known_names": {}}):
            apply_windows_connected_names([
                {
                    "address": "AABBCCDDEEFF",
                    "name": "Genuine Windows friendly name",
                    "container_id": None,
                },
                {
                    "address": "001122334455",
                    "name": "Unobserved connected device",
                    "container_id": None,
                },
            ])

            self.assertEqual(len(state["live_scan"]), 1)
            self.assertEqual(
                state["live_scan"][address]["name"],
                "Genuine Windows friendly name",
            )
            self.assertEqual(state["live_scan"][address]["rssi"], -57)
            self.assertEqual(state["live_scan"][address]["rssi_history"], [-62, -57])
            self.assertEqual(state["live_scan"][address]["last_seen"], 1234.5)
            self.assertEqual(
                state["windows_connected_unmatched"],
                [{
                    "address": "001122334455",
                    "name": "Unobserved connected device",
                }],
            )

    def test_shared_valid_container_id_allows_windows_name_enrichment(self):
        address = "AA:BB:CC:DD:EE:FF"
        container_id = "c5b28f30-4219-4b57-b2fb-0fe39dd7e1c8"
        record = {
            "address": address,
            "name": None,
            "name_source": None,
            "rssi": -58,
            "rssi_history": [-62, -58],
            "last_seen": 1234.5,
        }
        connected = [{
            "address": "11:22:33:44:55:66",
            "name": "Genuine Windows friendly name",
            "container_id": container_id,
        }]
        with patch.dict(state, {
            "live_scan": {address: record},
            "known_names": {},
            "windows_connected_unmatched": [],
        }):
            apply_windows_connected_names(
                connected,
                {address: container_id.upper()},
            )

            self.assertEqual(
                state["live_scan"][address]["name"],
                "Genuine Windows friendly name",
            )
            self.assertEqual(state["live_scan"][address]["rssi"], -58)
            self.assertEqual(state["live_scan"][address]["rssi_history"], [-62, -58])
            self.assertEqual(state["live_scan"][address]["last_seen"], 1234.5)
            self.assertEqual(state["windows_connected_unmatched"], [])

    def test_shared_container_does_not_replace_a_genuine_ble_name(self):
        address = "AA:BB:CC:DD:EE:FF"
        container_id = "c5b28f30-4219-4b57-b2fb-0fe39dd7e1c8"
        record = {
            "address": address,
            "name": "BLE advertised name",
            "name_source": "advertisement_data.local_name",
            "rssi": -58,
            "rssi_history": [-62, -58],
            "last_seen": 1234.5,
        }
        with patch.dict(state, {
            "live_scan": {address: record},
            "known_names": {},
            "windows_connected_unmatched": [],
        }):
            apply_windows_connected_names(
                [{
                    "address": "11:22:33:44:55:66",
                    "name": "Windows friendly name",
                    "container_id": container_id,
                }],
                {address: container_id},
            )

            self.assertEqual(state["live_scan"][address]["name"], "BLE advertised name")

    def test_windows_name_is_not_applied_for_different_or_missing_container_id(self):
        address = "AA:BB:CC:DD:EE:FF"
        record = {
            "address": address,
            "name": None,
            "name_source": None,
            "rssi": -71,
            "rssi_history": [-74, -71],
            "last_seen": 1234.5,
        }
        connected = [{
            "address": "11:22:33:44:55:66",
            "name": "Windows friendly name",
            "container_id": "c5b28f30-4219-4b57-b2fb-0fe39dd7e1c8",
        }]
        with patch.dict(state, {
            "live_scan": {address: record},
            "known_names": {},
            "windows_connected_unmatched": [],
        }):
            apply_windows_connected_names(
                connected,
                {address: "088cb991-395d-48f8-a84f-839c240c11c0"},
            )

            self.assertIsNone(state["live_scan"][address]["name"])
            self.assertEqual(state["live_scan"][address]["rssi"], -71)
            self.assertEqual(state["live_scan"][address]["rssi_history"], [-74, -71])
            self.assertEqual(len(state["live_scan"]), 1)
            self.assertEqual(len(state["windows_connected_unmatched"]), 1)

    def test_ambiguous_shared_container_does_not_match(self):
        container_id = "c5b28f30-4219-4b57-b2fb-0fe39dd7e1c8"
        windows_records = [
            {"address": "11:22:33:44:55:66", "name": "First", "container_id": container_id},
            {"address": "22:33:44:55:66:77", "name": "Second", "container_id": container_id},
        ]

        match, reason = find_connected_windows_match(
            "AA:BB:CC:DD:EE:FF",
            container_id,
            windows_records,
        )

        self.assertIsNone(match)
        self.assertEqual(reason, "ambiguous_container_id")

    def test_generic_windows_name_cannot_enrich_ble_record(self):
        match, reason = find_connected_windows_match(
            "AA:BB:CC:DD:EE:FF",
            None,
            [{
                "address": "AA:BB:CC:DD:EE:FF",
                "name": "Bluetooth AA:BB:CC:DD:EE:FF",
                "container_id": None,
            }],
        )

        self.assertIsNone(match)
        self.assertEqual(reason, "container_unavailable")

    def test_scan_route_rejects_a_second_active_scan(self):
        with patch.dict(state, {"scanning": True}):
            response = app.test_client().post("/api/scan")

        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
