
import spidev
import time
import sys

print("Opening SPI...")
try:
    spi = spidev.SpiDev()
    spi.open(0, 1)  # CS1 (CE1, Pin 26)
    spi.max_speed_hz = 5000000
    spi.mode = 0b11
    print("SPI interface opened.")
except Exception as e:
    print(f"FAILED to open SPI: {e}")
    sys.exit(1)

print("Attempting to read 10 bytes...")
try:
    data = spi.readbytes(10)
    print(f"Read data: {list(data)}")
    print("SUCCESS: Hardware is responding.")
except Exception as e:
    print(f"FAILED to read: {e}")
    sys.exit(1)
finally:
    spi.close()
