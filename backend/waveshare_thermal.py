"""
Waveshare 80x62 Thermal Camera HAT Driver
==========================================
Hardware driver for the Waveshare LWIR thermal camera.

Uses:
- I2C (smbus) for camera configuration
- SPI (spidev) for temperature data transfer
- GPIO for DATA_READY signal

Resolution: 80x62 pixels
Temperature Range: -20°C to 400°C
Frame Rate: ~5 FPS (hardware limited)
"""

import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

# Constants
FRAME_WIDTH = 80
FRAME_HEIGHT = 62
FRAME_PIXELS = FRAME_WIDTH * FRAME_HEIGHT

# I2C Configuration
I2C_BUS = 1
I2C_ADDR = 0x40

# GPIO Pin for DATA_READY
DATA_READY_PIN = 24


class WaveshareThermal:
    """
    Hardware driver for Waveshare 80x62 Thermal Camera HAT.
    
    Reads raw temperature data via SPI and converts to grayscale
    frame suitable for detection algorithms.
    """
    
    def __init__(self):
        self.available = False
        self.i2c = None
        self.spi = None
        self.crc_func = None
        self.last_frame = None
        self.min_temp = 20.0   # Expected min temp in scene (°C)
        self.max_temp = 40.0   # Expected max temp for humans (°C)
        
        self._init_hardware()
    
    def _init_hardware(self):
        """Initialize I2C, SPI, and GPIO interfaces."""
        try:
            import smbus2
            import spidev
            import crcmod
            
            # Initialize I2C for configuration
            self.i2c = smbus2.SMBus(I2C_BUS)
            
            # Initialize SPI for data transfer
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)  # Bus 0, Device 0
            self.spi.max_speed_hz = 20000000  # 20 MHz
            self.spi.mode = 0  # SPI Mode 0
            self.spi.bits_per_word = 8
            
            # CRC-16 for data validation
            self.crc_func = crcmod.mkCrcFun(0x18005, initCrc=0xFFFF, xorOut=0x0000)
            
            # Try to initialize GPIO for DATA_READY (optional)
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(DATA_READY_PIN, GPIO.IN)
                self.gpio_available = True
            except:
                self.gpio_available = False
                logger.warning("GPIO not available, using timing-based frame sync")
            
            # Configure camera (write initial register values)
            self._configure_camera()
            
            self.available = True
            logger.info("Waveshare 80x62 Thermal Camera initialized successfully")
            
        except ImportError as e:
            logger.warning(f"Waveshare Thermal HAT libraries not installed: {e}")
            logger.info("Install with: pip install smbus2 spidev crcmod RPi.GPIO")
        except Exception as e:
            logger.warning(f"Waveshare Thermal HAT initialization failed: {e}")
    
    def _configure_camera(self):
        """Configure camera registers via I2C."""
        try:
            # Basic configuration commands
            # These may need adjustment based on Waveshare documentation
            # Register 0x01: Enable continuous mode
            self.i2c.write_byte_data(I2C_ADDR, 0x01, 0x01)
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Camera I2C config failed: {e}")
    
    def _wait_for_data_ready(self, timeout=1.0):
        """Wait for DATA_READY signal or timeout."""
        if self.gpio_available:
            import RPi.GPIO as GPIO
            start = time.time()
            while time.time() - start < timeout:
                if GPIO.input(DATA_READY_PIN):
                    return True
                time.sleep(0.001)
            return False
        else:
            # Fallback: just wait a frame period (~200ms for 5fps)
            time.sleep(0.2)
            return True
    
    def _read_raw_frame(self):
        """
        Read raw temperature data from SPI.
        
        Returns: numpy array of shape (62, 80) with raw ADC values
        """
        if not self.available or self.spi is None:
            return None
        
        try:
            # Wait for frame to be ready
            if not self._wait_for_data_ready():
                return None
            
            # Each pixel is 2 bytes (16-bit temperature value)
            # Total: 80 * 62 * 2 = 9920 bytes + 2 bytes CRC = 9922 bytes
            bytes_to_read = FRAME_PIXELS * 2 + 2
            
            # Send dummy bytes to generate clock and receive data
            raw_bytes = self.spi.xfer2([0x00] * bytes_to_read)
            
            # Validate CRC (last 2 bytes)
            data_bytes = bytes(raw_bytes[:-2])
            received_crc = (raw_bytes[-2] << 8) | raw_bytes[-1]
            
            if self.crc_func:
                calculated_crc = self.crc_func(data_bytes)
                if calculated_crc != received_crc:
                    logger.debug("CRC mismatch, frame dropped")
                    return None
            
            # Convert to 16-bit array
            raw_data = np.frombuffer(data_bytes, dtype=np.uint16)
            
            # Reshape to frame dimensions
            frame = raw_data.reshape((FRAME_HEIGHT, FRAME_WIDTH))
            
            return frame
            
        except Exception as e:
            logger.error(f"SPI read error: {e}")
            return None
    
    def get_temperature_frame(self):
        """
        Get temperature frame in Celsius.
        
        Returns: numpy array of shape (62, 80) with temperature in °C
        """
        raw = self._read_raw_frame()
        if raw is None:
            return None
        
        # Convert raw ADC to temperature
        # Waveshare uses: Temp(°C) = raw_value / 100
        temp_frame = raw.astype(np.float32) / 100.0
        
        return temp_frame
    
    def get_frame(self):
        """
        Get grayscale frame normalized for detection.
        
        Returns: 8-bit grayscale numpy array (62, 80)
        """
        temp_frame = self.get_temperature_frame()
        if temp_frame is None:
            return self.last_frame  # Return cached frame if read fails
        
        # Dynamic range adjustment based on scene
        scene_min = max(self.min_temp, np.percentile(temp_frame, 5))
        scene_max = min(self.max_temp, np.percentile(temp_frame, 99))
        
        # Prevent division by zero
        if scene_max <= scene_min:
            scene_max = scene_min + 1.0
        
        # Normalize to 0-255
        normalized = (temp_frame - scene_min) / (scene_max - scene_min)
        normalized = np.clip(normalized, 0, 1)
        grayscale = (normalized * 255).astype(np.uint8)
        
        self.last_frame = grayscale
        return grayscale
    
    def get_max_temperature(self):
        """Get the maximum temperature in the current frame (°C)."""
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
            if self.spi:
                self.spi.close()
            if self.i2c:
                self.i2c.close()
            if self.gpio_available:
                import RPi.GPIO as GPIO
                GPIO.cleanup(DATA_READY_PIN)
        except:
            pass


# Singleton instance
_thermal_camera = None

def get_thermal_camera():
    """Get singleton thermal camera instance."""
    global _thermal_camera
    if _thermal_camera is None:
        _thermal_camera = WaveshareThermal()
    return _thermal_camera
