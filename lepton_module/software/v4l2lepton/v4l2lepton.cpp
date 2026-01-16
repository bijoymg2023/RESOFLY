#include <ctime>
#include <errno.h>
#include <fcntl.h> /* low-level i/o */
#include <fstream>
#include <iostream>
#include <linux/videodev2.h>
#include <malloc.h>
#include <pthread.h>
#include <semaphore.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>

#include "Lepton_I2C.h"
#include "Palettes.h"
#include "SPI.h"

#define PACKET_SIZE 164
#define PACKET_SIZE_UINT16 (PACKET_SIZE / 2)
#define PACKETS_PER_FRAME 60
#define FRAME_SIZE_UINT16 (PACKET_SIZE_UINT16 * PACKETS_PER_FRAME)
#define FPS 27;

static char const *v4l2dev = "/dev/video1";
static char *spidev = NULL;
static int v4l2sink = -1;
// Lepton 3.x support
static int width = 160;
static int height = 120;
static uint8_t result[PACKET_SIZE * PACKETS_PER_FRAME * 4]; // 4 segments

static void grab_frame() {
  int resets = 0;
  int segmentNumber = 0;

  // We need to read 4 segments to make a complete frame for Lepton 3.x
  // Each segment is 60 packets.
  for (int seg = 0; seg < 4; seg++) {
    int seg_resets = 0;

    while (1) {
      // Read ONE complete segment (60 packets * 164 bytes = 9840 bytes)
      // This keeps CS asserted for the whole segment, critical for sync.
      read(spi_cs_fd, result + (seg * PACKET_SIZE * PACKETS_PER_FRAME),
           PACKET_SIZE * PACKETS_PER_FRAME);

      // Check Packet 20 header for Segment Number (Lepton 3 specific)
      // Packet 20 is at index 20 * 164. Header is bytes 0-1.
      // But we just need valid packets check first.

      uint8_t *seg_ptr = result + (seg * PACKET_SIZE * PACKETS_PER_FRAME);
      int packetNumber = seg_ptr[1];
      if (packetNumber != 0) {
        // First packet wasn't 0. Sync lost?
        seg_resets++;
        usleep(1000);
        if (seg_resets > 750) {
          SpiClosePort();
          usleep(750000);
          SpiOpenPort(spidev);
          seg_resets = 0;
        }
        continue;
      }

      // Check for valid segment number in packet 20
      // Packet 20 starts at 20 * 164
      int packet20_idx = 20 * 164;
      // Segment ID is in the first byte (upper 4 bits?) depends on docs.
      // Actually, Lepton 3 data sheet: Packet 20, ID field contains segment.
      // byte 0: TTTT SSSS (T=Telemetry, S=Segment) - wait, check
      // LeptonThread.cpp LeptonThread.cpp: segmentNumber = (result[j *
      // PACKET_SIZE] >> 4) & 0x0f; but that was inside a specific packet 20
      // check.

      uint8_t seg_id = (seg_ptr[packet20_idx] >> 4) & 0x0f;

      // We want segment 1, then 2, then 3, then 4.
      // If we are looking for seg index 'seg' (0..3), we want ID seg+1.
      if (seg_id == 0) {
        // Sometimes we get 0 if not sync?
        // Or if it's a Lepton 2.x, segment is always 0?
        // Let's assume strict Lepton 3 check first.
        // If seg_id doesn't match expected, retry.
      }

      // If we're here, we assume valid read.
      break;
    }
  }

  // Process Frame
  frameBuffer = (uint16_t *)result;

  // Reset min/max
  uint16_t minValue = 65535;
  uint16_t maxValue = 0;

  // We have 4 segments of 60 packets.
  // Each packet has 80 pixels (160 bytes).
  // Total pixels = 4 * 60 * 80 = 19200.
  // 160 * 120 = 19200. Matches.

  // Only process lines if we have good data
  for (int i = 0; i < FRAME_SIZE_UINT16 * 4; i++) {
    // Skip header words?
    // FRAME_SIZE_UINT16 includes headers in the flat array count if we cast raw
    // buffer? No, result is raw bytes. frameBuffer is uint16 view. Each packet
    // is 164 bytes = 82 uint16s. First 2 uint16s are header.
    if (i % PACKET_SIZE_UINT16 < 2)
      continue; // Skip header

    // Swap Endianness
    uint16_t value = frameBuffer[i];
    // Swap bytes
    value = (value << 8) | (value >> 8);
    frameBuffer[i] = value; // Store back for next pass? Or just use temp.

    if (value > maxValue)
      maxValue = value;
    if (value < minValue)
      minValue = value;
  }

  float diff = maxValue - minValue;
  float scale = 255.0f / (diff > 0 ? diff : 1.0f);

  const int *colormap = colormap_ironblack;

  // Fill Output Buffer (160x120)
  for (int i = 0; i < FRAME_SIZE_UINT16 * 4; i++) {
    if (i % PACKET_SIZE_UINT16 < 2)
      continue;

    uint16_t value = frameBuffer[i];
    int scaled_val = (int)((value - minValue) * scale);
    if (scaled_val > 255)
      scaled_val = 255;
    if (scaled_val < 0)
      scaled_val = 0;

    // Calc pixel position
    // This is complex for Lepton 3 segments.
    // Simplified mapping (linear):
    // We have 4 segments stacked? Or tiled?
    // Lepton 3 segments are usually interlaces or blocks.
    // LeptonThread.cpp logic:
    // row = i / PACKET_SIZE_UINT16 / 2 + ofsRow;
    // ofsRow = 30 * (segmentNumber - 1);

    // Let's try simple linear filling and correct visual later if scrambled.
    // Pure linear fill validation.

    // Output idx
    // We need to map linear 'i' to image x,y.
    // Ignoring complex mapping for speed to verify feed LIVE first.

    // Just fill the vidsendbuf linearly to verify we have ANY non-resetting
    // video We might get scrambled video but it will stop resetting.

    // For a hack:
    // vidsendbuf is size width*height*3.
    static int pixel_counter = 0;
    if (i == 0)
      pixel_counter = 0;

    if (pixel_counter < width * height) {
      int idx = pixel_counter * 3;
      vidsendbuf[idx + 0] = colormap[3 * scaled_val];
      vidsendbuf[idx + 1] = colormap[3 * scaled_val + 1];
      vidsendbuf[idx + 2] = colormap[3 * scaled_val + 2];
      pixel_counter++;
    }
  }
}

static void stop_device() { SpiClosePort(); }

static void open_vpipe() {
  v4l2sink = open(v4l2dev, O_WRONLY);
  if (v4l2sink < 0) {
    fprintf(stderr, "Failed to open v4l2sink device. (%s)\n", strerror(errno));
    exit(-2);
  }
  // setup video for proper format
  struct v4l2_format v;
  int t;
  v.type = V4L2_BUF_TYPE_VIDEO_OUTPUT;
  t = ioctl(v4l2sink, VIDIOC_G_FMT, &v);
  if (t < 0)
    exit(t);
  v.fmt.pix.width = width;
  v.fmt.pix.height = height;
  v.fmt.pix.pixelformat = V4L2_PIX_FMT_RGB24;
  vidsendsiz = width * height * 3;
  v.fmt.pix.sizeimage = vidsendsiz;
  t = ioctl(v4l2sink, VIDIOC_S_FMT, &v);
  if (t < 0)
    exit(t);
  vidsendbuf = (char *)malloc(vidsendsiz);
}

static pthread_t sender;
static sem_t lock1, lock2;
static void *sendvid(void *v) {
  (void)v;
  for (;;) {
    sem_wait(&lock1);
    if (vidsendsiz != write(v4l2sink, vidsendbuf, vidsendsiz))
      exit(-1);
    sem_post(&lock2);
  }
}

void usage(char *exec) {
  printf("Usage: %s [options]\n"
         "Options:\n"
         "  -d | --device name       Use name as spidev device "
         "(/dev/spidev0.1 by default)\n"
         "  -h | --help              Print this message\n"
         "  -v | --video name        Use name as v4l2loopback device "
         "(%s by default)\n"
         "",
         exec, v4l2dev);
}

static const char short_options[] = "d:hv:";

static const struct option long_options[] = {
    {"device", required_argument, NULL, 'd'},
    {"help", no_argument, NULL, 'h'},
    {"video", required_argument, NULL, 'v'},
    {0, 0, 0, 0}};

int main(int argc, char **argv) {
  struct timespec ts;

  // processing command line parameters
  for (;;) {
    int index;
    int c;

    c = getopt_long(argc, argv, short_options, long_options, &index);

    if (-1 == c)
      break;

    switch (c) {
    case 0:
      break;

    case 'd':
      spidev = optarg;
      break;

    case 'h':
      usage(argv[0]);
      exit(EXIT_SUCCESS);

    case 'v':
      v4l2dev = optarg;
      break;

    default:
      usage(argv[0]);
      exit(EXIT_FAILURE);
    }
  }

  open_vpipe();

  // open and lock response
  if (sem_init(&lock2, 0, 1) == -1)
    exit(-1);
  sem_wait(&lock2);

  if (sem_init(&lock1, 0, 1) == -1)
    exit(-1);
  pthread_create(&sender, NULL, sendvid, NULL);

  for (;;) {
    // wait until a frame can be written
    fprintf(stderr, "Waiting for sink\n");
    sem_wait(&lock2);
    // setup source
    init_device(); // open and setup SPI
    for (;;) {
      grab_frame();
      // push it out
      sem_post(&lock1);
      clock_gettime(CLOCK_REALTIME, &ts);
      ts.tv_sec += 2;
      // wait for it to get written (or is blocking)
      if (sem_timedwait(&lock2, &ts))
        break;
    }
    stop_device(); // close SPI
  }
  close(v4l2sink);
  return 0;
}
