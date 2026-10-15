# ExamGuard Browser Prototype

ExamGuard is an exploratory Bluetooth Low Energy (BLE) device-scanning and signal-monitoring prototype for investigating whether wireless-device observations could provide supplementary information in examination environments.

**GitHub repository:** https://github.com/jessephrvu-creator/ExamGuard

## Requirements

- Python 3.11 or later.
- Windows with Bluetooth enabled.
- Bluetooth hardware and authorised test devices.
- VS Code (optional).

Python and Bluetooth-library compatibility depends on the operating system, hardware, and installed dependencies.

## Run Locally

Open PowerShell or a terminal in the project folder and run:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in Chrome or another browser.

Keep the terminal open while using the application.

This local setup is intended for testing on the same computer, not public or network deployment.

## Implemented Features

- 15-second Bluetooth Low Energy discovery.
- RSSI-based signal-strength bands, using initial thresholds for testing.
- Filtering of displayed scan results.
- CSV export of results for the selected filter.
- Comparison between the latest two successful scans.

These features describe the current prototype. Their presence does not establish that every feature has been validated under all conditions.

## Preliminary Experiments and Observations

Preliminary BLE scanning experiments were conducted using our own Bluetooth devices under different conditions.

Recorded observations include:

- The number of discovered BLE devices varied between scans.
- Some discovered devices appeared with unknown or inconsistent names.
- One recorded 15-second scan discovered two BLE devices.
- Matching a discovered BLE signal to a specific connected pair of earbuds could not be reliably established.

These observations are limited to the conditions tested. They do not establish general detection accuracy or demonstrate that all relevant devices can be discovered.

## Device-Matching Limitation

Discovering a BLE advertisement does not reliably establish the physical identity or owner of the device that transmitted it.

In our experiments, we could not reliably match discovered BLE signals to the intended connected earbuds. This remains an unresolved limitation requiring further validation.

The prototype must therefore be treated as an exploratory device-scanning tool, not a reliable system for identifying unauthorised devices.

## Signal Strength and Filtering

Received Signal Strength Indicator (RSSI) provides a measurement of received signal strength. It is not an exact distance measurement.

Signal readings can vary because of distance, obstacles, device orientation, interference, and other environmental factors. The initial signal-strength thresholds are intended for experimentation and require controlled calibration before being used for any operational purpose.

Filtering and scan comparison help inspect observations; they do not independently establish device identity.

## Privacy, Safety, and Responsible Use

- Use only devices you own or are explicitly authorised to test.
- Avoid publishing personal identifiers, credentials, or sensitive device information.
- Treat discovered devices as observations requiring interpretation, not evidence of misconduct.
- Do not automatically accuse or penalise anyone based on a scan result.
- Any real-world use would require appropriate privacy safeguards, controlled validation, and human verification.

**A detected BLE signal does not prove cheating, identify the person carrying a device, or establish that a device is unauthorised.**

## Current Status and Future Validation

The current project is an exploratory software prototype with preliminary scanning experiments completed.

Further validation is needed to assess discovery consistency, missed detections, unexpected observations, and device matching under documented test conditions.

No claim of reliable unauthorised-device identification or cheating detection is made.

## Technologies

- Python
- Flask
- Bluetooth Low Energy scanning components specified in the project dependencies

Refer to `requirements.txt` and the source code for the exact installed libraries and implementation details.