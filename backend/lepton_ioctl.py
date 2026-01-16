
import struct
import fcntl
import array
import ctypes
import time
import os

# IOCTL Constants for SPI
SPI_IOC_MESSAGE_1 = 0x40206b00 # This depends on struct size, usually works for 1 msg xfer on 32-bit (Pi)
# Actually, let's look up proper calculation or standard values
# _IOW(SPI_IOC_MAGIC, 0, char[SPI_MSGSIZE(1)])
# On Pi 32-bit:
# SPI_IOC_MESSAGE(1) is often 0x40206b00.
# Let's try to be safer by deriving it or using a known working block.

# Safe simple wrapper
class LeptonIOCTL:
    def __init__(self, spidev_path="/dev/spidev0.0"):
        self.fd = os.open(spidev_path, os.O_RDWR)
        
    def close(self):
        os.close(self.fd)

    def xfer2(self, tx_data):
        # Construct SPI transfer structure
        # struct spi_ioc_transfer {
        #   __u64 tx_buf;
        #   __u64 rx_buf;
        #   __u32 len;
        #   __u32 speed_hz;
        #   __u16 delay_usecs;
        #   __u8  bits_per_word;
        #   __u8  cs_change;
        #   __u32 pad;
        # };
        
        # Data buffers
        length = len(tx_data)
        rx_data = array.array('B', [0]*length)
        
        # Get addresses
        tx_addr, _ = (array.array('B', tx_data)).buffer_info() # Make sure to hold ref if we pass addr? 
        # Actually easier to use ctypes for the buffer to ensure it stays put
        
        TxBuf = (ctypes.c_ubyte * length)(*tx_data)
        RxBuf = (ctypes.c_ubyte * length)()
        
        tx_addr = ctypes.addressof(TxBuf)
        rx_addr = ctypes.addressof(RxBuf)
        
        # Structure format for 64-bit aligned struct (even on 32-bit systems spidev uses 64-bit pointers)
        # Q Q I I H B B I
        # Q = u64 (8), I = u32 (4), H = u16 (2), B = u8 (1)
        fmt = "QQIIHBB I" 
        # But wait, python 'I' is unsigned int (4). 
        # Total size: 8+8+4+4+2+1+1+4 = 32 bytes.
        
        # SPI_IOC_MESSAGE(1)
        # Magic 'k' (107), type 0. Size 32.
        # _IOW(107, 0, 32)
        # Dir(2 bits) | Size(14) | Type(8) | Nr(8)
        # Write (1) = 0x40000000.  (Depends on arch, usually 1 for _IOC_WRITE)
        # Size 32 = 0x20
        # Type 'k' = 0x6b
        # Nr 0 = 0x00
        # Result: 0x40206b00 (Assuming _IOC_WRITE is 1, _IOC_READ is 2. On many linux SPI is IOW)
        # Actually SPI_IOC_MESSAGE is _IOW.
        
        ioctl_arg = 0x40206b00 
        
        speed_hz = 16000000
        delay_usecs = 0
        bits_per_word = 8
        cs_change = 0
        
        transfer = struct.pack(fmt, tx_addr, rx_addr, length, speed_hz, delay_usecs, bits_per_word, cs_change, 0)
        
        try:
            fcntl.ioctl(self.fd, ioctl_arg, transfer)
            return bytearray(RxBuf)
        except OSError as e:
            # Fallback if ioctl calculation is wrong try 64-bit one?
            print(f"IOCTL Error: {e}")
            return None

if __name__ == "__main__":
    # Test
    try:
        spi = LeptonIOCTL()
        res = spi.xfer2([0]*39360) # Try big read
        if res and len(res) == 39360:
            print("SUCCESS: Read 39360 bytes!")
        else:
            print("FAILED")
        spi.close()
    except Exception as e:
        print(f"CRASH: {e}")
