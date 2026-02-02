import spidev
import numpy as np
import cv2
import time

# Lepton specs
PACKET_SIZE = 164
PACKETS_PER_FRAME = 60
FRAME_WIDTH = 80
FRAME_HEIGHT = 60

spi = spidev.SpiDev()
spi.open(0, 0)                  # SPI0 CE0
spi.max_speed_hz = 20000000     # 20 MHz
spi.mode = 0b11

def get_frame():
    frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH), dtype=np.uint16)
    row = 0

    while row < FRAME_HEIGHT:
        packet = spi.readbytes(PACKET_SIZE)
        if packet[0] & 0x0F == 0x0F:
            continue  # discard invalid packet

        packet_row = packet[1]
        if packet_row != row:
            row = 0
            continue

        for col in range(FRAME_WIDTH):
            hi = packet[4 + col*2]
            lo = packet[5 + col*2]
            frame[row, col] = (hi << 8) | lo

        row += 1

    return frame

cv2.namedWindow("Thermal", cv2.WINDOW_NORMAL)

while True:
    raw = get_frame()

    # normalize for display
    img = cv2.normalize(raw, None, 0, 255, cv2.NORM_MINMAX)
    img = np.uint8(img)
    img = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)

    cv2.imshow("Thermal", img)

    if cv2.waitKey(1) & 0xFF == 27:
        break

spi.close()
cv2.destroyAllWindows()
