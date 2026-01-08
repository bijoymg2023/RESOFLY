# Raspberry Pi Video for FLIR Lepton

This application displays the thermal video feed from a FLIR Lepton module on a Raspberry Pi using Qt.
It supports **Lepton 2.x, 3.x, and 3.5**.

## Hardware Requirements
- Raspberry Pi (Any model with GPIO, tested on Pi 3/4/Zero)
- FLIR Lepton Module (2.x, 3.x, or 3.5)
- Breakout Board (e.g., PureThermal, or generic breakout) connected via SPI and I2C.

### Wiring (Generic Breakout)
| Lepton Pin | Raspberry Pi Pin | Function |
|------------|------------------|----------|
| GND        | GND              | Ground   |
| CS         | GPIO 8 (CE0)     | SPI CS0  |
| MISO       | GPIO 9 (MISO)    | SPI MISO |
| CLK        | GPIO 11 (SCLK)   | SPI CLK  |
| VIN        | 3.3V             | Power    |
| SDA        | GPIO 2 (SDA)     | I2C SDA  |
| SCL        | GPIO 3 (SCL)     | I2C SCL  |

> Note: Some instructions suggest CE1, but standard SPI0 usually uses CE0 or CE1. This code defaults to `/dev/spidev0.0` (CE0) or `/dev/spidev0.1` (CE1) depending on configuration. `SPI.cpp` defaults to checking both but usually expects CE0 or CE1. Ensure you enable SPI in raspi-config.

## Software Prerequisites

1. **Enable Interfaces**:
   Run `sudo raspi-config`
   - Interface Options -> SPI -> Enable
   - Interface Options -> I2C -> Enable

2. **Install Dependencies** (Qt5):
   ```bash
   sudo apt-get update
   sudo apt-get install qtbase5-dev qt5-qmake build-essential
   ```

## Build Instructions

1. Navigate to the directory:
   ```bash
   cd LeptonModule/software/raspberrypi_video
   ```

2. Compile:
   ```bash
   qmake
   make
   ```

   *Note: This will also compile the Lepton SDK in `../raspberrypi_libs`.*

3. Clean (if needed):
   ```bash
   make distclean
   ```

## Running the Application

### For FLIR Lepton 3.5 (or 3.x)
Lepton 3.x modules have a resolution of 160x120 and require a specific sync mode (`-tl 3`).

```bash
./raspberrypi_video -tl 3
```

### For FLIR Lepton 2.x
Lepton 2.x modules have a resolution of 80x60.

```bash
./raspberrypi_video
```

### Options
- `-tl 3`:  Select Lepton 3.x mode (Required for Lepton 3.5)
- `-ss 20`: Set SPI speed to 20MHz (Default). range 10-30.
- `-cm 1`:  Rainbow Colormap
- `-cm 2`:  Grayscale Colormap
- `-cm 3`:  IronBlack Colormap (Default)
- `-min 30000`: Force min scaling value (raw 14-bit value)
- `-max 32000`: Force max scaling value

### Troubleshooting
- **Black Screen / Red Square**: Ensure SPI wiring is correct and the Lepton is fully seated.
- **Garbled Image**: Try lowering SPI speed or checking connections.
- **Permission Errors**: You might need to add your user to `spi` and `i2c` groups, or run with `sudo` (not recommended for GUI apps usually, but sometimes necessary for direct hardware access unless udev rules are set).

```bash
sudo ./raspberrypi_video -tl 3
```
