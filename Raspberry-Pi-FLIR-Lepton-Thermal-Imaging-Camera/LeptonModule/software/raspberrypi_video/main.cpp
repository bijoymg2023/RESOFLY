#include <QApplication>
#include <QMessageBox>
#include <QMutex>
#include <QThread>

#include <QColor>
#include <QLabel>
#include <QPushButton>
#include <QString>
#include <QtDebug>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <libgen.h>

#include "LeptonThread.h"
#include "MyLabel.h"

void printUsage(char *cmd) {
  char *cmdname = basename(cmd);
  printf("Usage: %s [OPTION]...\n"
         " -h      display this help and exit\n"
         " -cm x   select colormap\n"
         "           1 : rainbow\n"
         "           2 : grayscale\n"
         "           3 : ironblack [default]\n"
         " -tl x   select type of Lepton\n"
         "           2 : Lepton 2.x [default]\n"
         "           3 : Lepton 3.x\n"
         "               [for your reference] Please use nice command\n"
         "                 e.g. sudo nice -n 0 ./%s -tl 3\n"
         " -ss x   SPI bus speed [MHz] (10 - 30)\n"
         "           20 : 20MHz [default]\n"
         " -min x  override minimum value for scaling (0 - 65535)\n"
         "           [default] automatic scaling range adjustment\n"
         "           e.g. -min 30000\n"
         " -max x  override maximum value for scaling (0 - 65535)\n"
         "           [default] automatic scaling range adjustment\n"
         "           e.g. -max 32000\n"
         " -d x    log level (0-255)\n"
         "",
         cmdname, cmdname);
  return;
}

int main(int argc, char **argv) {
  int typeColormap = 3; // colormap_ironblack
  int typeLepton = 2;   // Lepton 2.x
  int spiSpeed = 20;    // SPI bus speed 20MHz
  int rangeMin = -1;    //
  int rangeMax = -1;    //
  int loglevel = 0;
  char targetIP[32] = "127.0.0.1"; // Default IP (Localhost)

  // Parse Arguments
  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "-h") == 0) {
      printUsage(argv[0]);
      printf(" -ip x   Destination IP (default: 127.0.0.1)\n");
      exit(0);
    } else if ((strcmp(argv[i], "-ip") == 0) && (i + 1 != argc)) {
      strncpy(targetIP, argv[i + 1], 31);
      i++;
    } else if (strcmp(argv[i], "-d") == 0) {
      int val = 3;
      if ((i + 1 != argc) && (strncmp(argv[i + 1], "-", 1) != 0)) {
        val = std::atoi(argv[i + 1]);
        i++;
      }
      if (0 <= val) {
        loglevel = val & 0xFF;
      }
    } else if ((strcmp(argv[i], "-cm") == 0) && (i + 1 != argc)) {
      int val = std::atoi(argv[i + 1]);
      if ((val == 1) || (val == 2)) {
        typeColormap = val;
        i++;
      }
    } else if ((strcmp(argv[i], "-tl") == 0) && (i + 1 != argc)) {
      int val = std::atoi(argv[i + 1]);
      if (val == 3) {
        typeLepton = val;
        i++;
      }
    } else if ((strcmp(argv[i], "-ss") == 0) && (i + 1 != argc)) {
      int val = std::atoi(argv[i + 1]);
      if ((10 <= val) && (val <= 30)) {
        spiSpeed = val;
        i++;
      }
    } else if ((strcmp(argv[i], "-min") == 0) && (i + 1 != argc)) {
      int val = std::atoi(argv[i + 1]);
      if ((0 <= val) && (val <= 65535)) {
        rangeMin = val;
        i++;
      }
    } else if ((strcmp(argv[i], "-max") == 0) && (i + 1 != argc)) {
      int val = std::atoi(argv[i + 1]);
      if ((0 <= val) && (val <= 65535)) {
        rangeMax = val;
        i++;
      }
    }
  }

  // Headless Application
  QCoreApplication a(argc, argv); // Changed from QApplication

  // create a thread to gather SPI data
  LeptonThread *thread = new LeptonThread();
  thread->setLogLevel(loglevel);
  thread->useColormap(typeColormap);
  thread->useLepton(typeLepton);
  thread->useSpiSpeedMhz(spiSpeed);
  thread->setAutomaticScalingRange();
  if (0 <= rangeMin)
    thread->useRangeMinValue(rangeMin);
  if (0 <= rangeMax)
    thread->useRangeMaxValue(rangeMax);

  // Note: No more signal connection to GUI labels

  thread->start();

  printf("RESOFLY Thermal Streamer Started (Headless)\n");
  printf("Streaming to 192.168.10.1:5005\n");

  return a.exec();
}
