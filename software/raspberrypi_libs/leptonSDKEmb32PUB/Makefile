
# Generic Makefile for Lepton SDK on Linux/Raspberry Pi

MAKE=make
RM=rm
MKDIR=mkdir

ifndef CFG
CFG=Debug
endif

# Configuration: Debug
ifeq "$(CFG)" "Debug"
OUTDIR=Debug
OUTFILE=$(OUTDIR)/libLEPTON_SDK.a
CFLAGS=-g -fpermissive -Dlinux=1
endif

# Configuration: Release
ifeq "$(CFG)" "Release"
OUTDIR=Release
OUTFILE=$(OUTDIR)/libLEPTON_SDK.a
CFLAGS=-O2 -fpermissive -Dlinux=1
endif

# Common settings
CC=gcc
AR=ar

COMMON_OBJ=$(OUTDIR)/raspi_I2C.o $(OUTDIR)/crc16fast.o \
	$(OUTDIR)/LEPTON_AGC.o $(OUTDIR)/LEPTON_VID.o \
	$(OUTDIR)/LEPTON_I2C_Protocol.o $(OUTDIR)/LEPTON_I2C_Service.o \
	$(OUTDIR)/LEPTON_SDK.o $(OUTDIR)/LEPTON_SYS.o $(OUTDIR)/LEPTON_OEM.o

OBJ=$(COMMON_OBJ)

# Pattern rule
$(OUTDIR)/%.o : %.c
	$(CC) $(CFLAGS) -c -o $@ $<

# Build rules
all: $(OUTFILE)

$(OUTFILE): $(OUTDIR) $(OBJ)
	$(AR) rcs $@ $(OBJ)

$(OUTDIR):
	$(MKDIR) -p "$(OUTDIR)"

clean:
	$(RM) -f $(OUTFILE) $(OBJ)
	$(RM) -rf $(OUTDIR)

cleanall: clean
