"""
Waveshare 80x62 Thermal Camera HAT Driver
==========================================
Uses the official pysenxor library (MI48 chip) for proper SPI/I2C communication.

The MI48 chip protocol:
- I2C for register configuration (address 0x40)
- SPI for frame data transfer (row-by-row, 160 bytes per xfer)
- GPIO23 for hardware reset (nRESET)
- GPIO24 for DATA_READY signal
- GPIO7 for manual SPI chip select (CS)

Data format: 16-bit deci-Kelvin -> Celsius = value/10 - 273.15

Install pysenxor:
    cd ~/RESOFLY/backend
    wget https://files.waveshare.com/wiki/common/Thermal_Camera_Hat.zip
    unzip Thermal_Camera_Hat.zip
    cd pysenxor-master && pip install -e ./
"""

import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

# Constants
FRAME_WIDTH = 80
FRAME_HEIGHT = 62
FRAME_PIXELS = FRAME_WIDTH * FRAME_HEIGHT

# MI48 hardware constants
MI48_I2C_ADDRESS = 0x40
MI48_I2C_CHANNEL = 1
MI48_SPI_BUS = 0
MI48_SPI_CE = 0
MI48_SPI_MODE = 0b00
MI48_SPI_SPEED_HZ = 10000000  # 10 MHz (Safe/Stable speed)
MI48_SPI_XFER_SIZE = 160      # 1 row = 80 pixels x 2 bytes
MI48_SPI_CS_DELAY = 0.0005    # 500us delay

# GPIO pins (BCM numbering)
PIN_DATA_READY = "BCM24"
PIN_RESET = "BCM23"
PIN_SPI_CS = "BCM7"


class WaveshareThermal:
    """
    Hardware driver for Waveshare 80x62 Thermal Camera HAT (MI48 chip).
    Uses the official pysenxor/senxor library for correct SPI protocol.
    """

    def __init__(self):
        self.available = False
        self.mi48 = None
        self.spi_cs = None
        self.last_frame = None
        self.frame_count = 0
        self.min_temp = 15.0
        self.max_temp = 45.0
        
        # Error tracking for auto-reset
        self.consecutive_errors = 0
        self.last_reset_time = 0

        self._init_hardware()

    def _init_hardware(self):
        """Initialize MI48 camera using pysenxor library."""
        try:
            from smbus2 import SMBus
            from spidev import SpiDev
            from gpiozero import DigitalInputDevice, DigitalOutputDevice
            from senxor.mi48 import MI48
            from senxor.interfaces import SPI_Interface, I2C_Interface

            logger.info("Initializing MI48 thermal camera via pysenxor...")

            # I2C interface for register access
            i2c_bus = SMBus(MI48_I2C_CHANNEL)
            i2c = I2C_Interface(i2c_bus, MI48_I2C_ADDRESS)

            # SPI interface for frame data
            spi_dev = SpiDev(MI48_SPI_BUS, MI48_SPI_CE)
            spi = SPI_Interface(spi_dev, xfer_size=MI48_SPI_XFER_SIZE)
            spi.device.mode = MI48_SPI_MODE
            spi.device.max_speed_hz = MI48_SPI_SPEED_HZ
            spi.device.bits_per_word = 8
            spi.device.lsbfirst = False
            spi.device.cshigh = True
            spi.device.no_cs = True

            # Manual chip select (GPIO7)
            self.spi_cs = DigitalOutputDevice(PIN_SPI_CS, active_high=False, initial_value=False)

            # DATA_READY signal (GPIO24)
            # DigitalInputDevice uses edge detection which is broken on
            # Bookworm with the rpigpio fallback (lgpio .so is wrong Python ABI).
            # Try edge-detect first, fall back to simple GPIO polling.
            data_ready = None
            try:
                data_ready = DigitalInputDevice(PIN_DATA_READY, pull_up=False)
                logger.info("DATA_READY: edge-detect mode (fast)")
            except Exception as edge_err:
                logger.warning(f"Edge detection unavailable: {edge_err}")
                try:
                    import RPi.GPIO as _GPIO
                    _GPIO.setwarnings(False)
                    try:
                        _GPIO.setmode(_GPIO.BCM)
                    except ValueError:
                        pass  # already set by gpiozero for output pins
                    _GPIO.setup(24, _GPIO.IN)

                    class PollingDataReady:
                        """Polls GPIO24 state without edge detection."""
                        def wait_for_active(self, timeout=1.0):
                            deadline = time.time() + timeout
                            while time.time() < deadline:
                                if _GPIO.input(24):
                                    return True
                                time.sleep(0.002)  # 2ms poll = ~500Hz
                            return False

                        @property
                        def value(self):
                            return bool(_GPIO.input(24))

                    data_ready = PollingDataReady()
                    logger.info("DATA_READY: GPIO polling mode (no edge detection)")
                except Exception as poll_err:
                    logger.warning(f"GPIO polling also failed: {poll_err}")
                    logger.info("Will rely on I2C status register polling for frame timing")

            # Hardware reset (GPIO23)
            reset_pin = DigitalOutputDevice(PIN_RESET, active_high=False, initial_value=True)

            class ResetHandler:
                def __init__(self, pin):
                    self.pin = pin
                def __call__(self):
                    self.pin.on()
                    time.sleep(0.000035)
                    self.pin.off()
                    time.sleep(0.050)

            # Create MI48 instance (this triggers reset + powerup + bootup)
            self.mi48 = MI48(
                [i2c, spi],
                data_ready=data_ready,
                reset_handler=ResetHandler(reset_pin)
            )

            # Configure camera
            self.mi48.set_fps(5)  # 5 FPS for stable operation

            # Enable noise filters if firmware supports it
            try:
                fw_major = int(self.mi48.fw_version[0])
                if fw_major >= 2:
                    self.mi48.enable_filter(f1=True, f2=True, f3=False)
                    self.mi48.set_offset_corr(0.0)
                    logger.info(f"MI48 FW v{self.mi48.fw_version} - filters enabled")
            except Exception as e:
                logger.warning(f"Could not configure filters: {e}")

            # Start continuous streaming with header
            self.mi48.start(stream=True, with_header=True)

            self.available = True
            logger.info(
                f"Waveshare 80x62 Thermal Camera initialized successfully "
                f"(MI48, I2C=0x{MI48_I2C_ADDRESS:02X})"
            )

        except ImportError as e:
            logger.warning(f"Waveshare HAT libraries not installed: {e}")
            logger.info(
                "Install pysenxor: cd ~/RESOFLY/backend && "
                "wget https://files.waveshare.com/wiki/common/Thermal_Camera_Hat.zip && "
                "unzip Thermal_Camera_Hat.zip && cd pysenxor-master && pip install -e ./"
            )
            import traceback
            traceback.print_exc()

    def _reset_camera(self):
        """Hardware reset the camera (GPIO 23)."""
        now = time.time()
        if now - self.last_reset_time < 10.0:
            return  # Prevent reset loops (max 1 reset every 10s)
            
        logger.warning("TRIGGERING HARDWARE RESET (Glitch Recovery)...")
        self.last_reset_time = now
        self.consecutive_errors = 0
        
        try:
            # Re-initialize to trigger reset sequence
            if self.mi48:
                self.mi48.stop()
            self._init_hardware()
        except Exception as e:
            logger.error(f"Reset failed: {e}")

    def _read_frame(self):
        """
        Read one frame from the MI48 via SPI.

        Returns: tuple (temperature_celsius_array, header) or (None, None)
        """
        if not self.available or self.mi48 is None:
            return None, None

        try:
            # Wait for DATA_READY signal
            if hasattr(self.mi48, 'data_ready') and self.mi48.data_ready is not None:
                self.mi48.data_ready.wait_for_active(timeout=1.0)
            else:
                # Fallback: poll status register
                for _ in range(100):
                    status = self.mi48.get_status()
                    if status & 0x10:  # DATA_READY bit
                        break
                    time.sleep(0.01)

            # Assert chip select, read frame, deassert
            if self.spi_cs:
                self.spi_cs.on()
                time.sleep(MI48_SPI_CS_DELAY)

            data, header = self.mi48.read()

            if self.spi_cs:
                time.sleep(MI48_SPI_CS_DELAY)
                self.spi_cs.off()

            if data is None:
                return None, None

            return data, header

        except Exception as e:
            logger.error(f"MI48 read error: {e}")
            if self.spi_cs:
                self.spi_cs.off()
            return None, None

    def get_temperature_frame(self):
        """
        Get temperature frame in Celsius.

        Returns: numpy array of shape (62, 80) with temperature in degrees C
        """
        data, header = self._read_frame()
        if data is None:
            return None

        try:
            # pysenxor already converts deci-Kelvin to Celsius
            # data is float16 array, reshape to (62, 80)
            from senxor.utils import data_to_frame
            temp_frame = data_to_frame(data, self.mi48.fpa_shape)
            
            # --- FRAME VALIDATION (Glitch Suppression) ---
            # Smart check for "torn" frames (large black/zero regions)
            zero_count = np.count_nonzero(temp_frame == 0.0)
            total_pixels = temp_frame.size
            zero_ratio = zero_count / total_pixels
            
            if zero_ratio > 0.02: # >2% zeros (Very strict check)
                self.consecutive_errors += 1
                logger.warning(f"Glitch detected: {zero_ratio*100:.1f}% zeros (Bad Frame #{self.consecutive_errors})")
                
                # Auto-Reset if stuck in glitch state
                if self.consecutive_errors >= 5:
                    self._reset_camera()
                    
                # GHOST LAG FIX:
                # If we have too many bad frames (>2), stop showing the old one.
                # It's better to show nothing (or a black frame) than a "frozen" ghost.
                if self.consecutive_errors > 2:
                    return None
                    
                # Return last good frame (briefly) to prevent micro-flicker
                return self.last_frame if self.last_frame is not None else None
            
            # Reset error counter on good frame
            self.consecutive_errors = 0
            self.frame_count += 1
            return temp_frame.astype(np.float32)

        except Exception as e:
            logger.error(f"Frame parse error: {e}")
            self.consecutive_errors += 1
            return self.last_frame if self.last_frame is not None else None

    def get_frame(self):
        """
        Get grayscale frame normalized for detection.

        Returns: 8-bit grayscale numpy array (62, 80)
        """
        temp_frame = self.get_temperature_frame()
        if temp_frame is None:
            if self.last_frame is not None:
                return self.last_frame

            # Generate diagnostic test pattern
            logger.warning("No frame data - sending test pattern")
            pattern = np.zeros((FRAME_HEIGHT, FRAME_WIDTH), dtype=np.uint8)
            for y in range(FRAME_HEIGHT):
                for x in range(FRAME_WIDTH):
                    pattern[y, x] = int((x / FRAME_WIDTH) * 200 + (y / FRAME_HEIGHT) * 55)
            return pattern

        # ABSOLUTE TEMPERATURE SCALING (Fixes "Fake Heat" / Auto-Gain issues)
        # We lock the range to 15C - 45C.
        # <15C = 0 (Black/Blue)
        # >45C = 255 (White/Yellow)
        # This makes detection thresholds STABLE.
        
        scene_min = self.min_temp # 15.0
        scene_max = self.max_temp # 45.0

        normalized = (temp_frame - scene_min) / (scene_max - scene_min)
        normalized = np.clip(normalized, 0, 1)
        grayscale = (normalized * 255).astype(np.uint8)

        self.last_frame = grayscale
        return grayscale

    def get_max_temperature(self):
        """Get the maximum temperature in the current frame (deg C)."""
        temp = self.get_temperature_frame()
        if temp is not None:
            return float(np.max(temp))
        return None

    def is_available(self):
        """Check if camera is available."""
        return self.available

    def close(self):
        """Release hardware resources."""
        try:
            if self.mi48:
                self.mi48.stop()
            if self.spi_cs:
                self.spi_cs.off()
        except Exception:
            pass


# Singleton instance
_thermal_camera = None

def get_thermal_camera():
    """Get singleton thermal camera instance."""
    global _thermal_camera
    if _thermal_camera is None:
        _thermal_camera = WaveshareThermal()
    return _thermal_camera
