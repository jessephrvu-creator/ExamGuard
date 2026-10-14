# ExamGuard Browser Prototype

## Requirements
- Python 3.11+ (your current Python 3.13 may work if Bleak supports your platform)
- Windows with Bluetooth enabled
- VS Code (optional)

## Run locally
Open a terminal in this folder and run:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Then open http://127.0.0.1:5000 in Chrome or another browser. Keep the terminal open while using the app.

## Features
- 15-second Bluetooth Low Energy discovery
- RSSI signal-strength bands (initial thresholds for testing only)
- Signal filter
- CSV export of the selected filter
- Comparison between the latest two successful scans

## Important limitations
RSSI is a noisy signal-strength indicator, not an exact distance estimate. Thresholds need controlled calibration. BLE discovery only finds some advertisements and does not identify a person or prove misconduct. The local server is intended for the prototype on the same computer, not for public/network deployment.
