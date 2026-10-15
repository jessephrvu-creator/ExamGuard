# ExamGuard --- Preliminary BLE Test Results

## Purpose

These preliminary experiments explored Bluetooth Low Energy (BLE) device
discovery using the ExamGuard prototype. They do **not** establish
reliable identification of unauthorised devices or detection of
cheating.

## Test setup

-   **Prototype:** ExamGuard browser-based BLE scanning prototype
-   **Scan duration:** 15 seconds for the recorded example below
-   **Test devices:** Our own Bluetooth earbuds/headphones
-   **Conditions explored:** Earbuds inside the case with pairing mode
    off; earbuds outside the case and in pairing mode
-   **Environment:** Windows laptop with Bluetooth enabled
-   **Privacy:** Do not publish personal identifiers or sensitive device
    information.

## Observations available from the recorded notes

  -----------------------------------------------------------------------
  Observation                         Recorded information
  ----------------------------------- -----------------------------------
  Device counts                       Different runs reported 1, 2, and 3
                                      discovered BLE devices

  Example scan                        13 October 2026, 19:33:22

  Example scan duration               15 seconds

  Example scan result                 2 BLE devices discovered

  Names in the example output         `JODU52140792298` and
                                      `JODU52420747082`

  Matching to intended earbuds        Could not be reliably established
                                      from the scan output
  -----------------------------------------------------------------------

The available notes do not provide a complete run-by-run mapping of
every device condition to every result. Therefore, no condition-specific
detection rate or accuracy figure is reported.

## Interpretation

-   BLE discovery returned device observations in some test runs.
-   The number of discovered devices varied between runs.
-   Device names and BLE addresses do not, by themselves, prove the
    physical identity or owner of a device.
-   The experiments did not establish that every relevant device will be
    discovered.
-   A discovered BLE signal does not prove that a device is unauthorised
    or that cheating has occurred.

## Limitations

-   Device discovery may vary with advertising state, device behaviour,
    environment, and scanning conditions.
-   RSSI is a noisy signal-strength measurement, not an exact distance
    estimate.
-   Matching discovered BLE signals to a specific connected pair of
    earbuds remains unresolved.
-   The current observations are preliminary and are not a validated
    measure of accuracy, false-positive rate, or missed-detection rate.

## Next validation steps

If further testing is conducted, record each run separately with: 1.
Date and time. 2. Scan duration and software/platform setup. 3. Device
condition (for example, inside case / outside case; pairing mode on /
off). 4. Expected test device and whether it was discoverable under the
test setup. 5. Number of devices observed and relevant non-sensitive
output. 6. Whether the intended device could be matched, marked as
**confirmed**, **not matched**, or **inconclusive**.

Use only owned or explicitly authorised test devices. Keep personal
identifiers and credentials out of the public repository.

## Project status

ExamGuard is an **exploratory device-scanning prototype**. These
preliminary observations demonstrate BLE discovery under some
conditions, but do not demonstrate reliable identification of
unauthorised devices or cheating.
