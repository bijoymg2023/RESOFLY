
import serial
import pynmea2
import time
import threading
from datetime import datetime

# NOTE: Requires 'pyserial' and 'pynmea2'
# pip install pyserial pynmea2

class GPSReader:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.current_data = {
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0.0,
            "accuracy": 0.0, # HDOP * est
            "speed": 0.0,
            "heading": 0.0,
            "timestamp": datetime.utcnow()
        }
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _read_loop(self):
        try:
            with serial.Serial(self.port, self.baudrate, timeout=1) as ser:
                while self.running:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore')
                        if line.startswith('$G'):
                            msg = pynmea2.parse(line)
                            
                            # Parse GPGGA (Fix Data)
                            if isinstance(msg, pynmea2.types.talker.GGA):
                                if msg.lat and msg.lon:
                                    self.current_data["latitude"] = msg.latitude
                                    self.current_data["longitude"] = msg.longitude
                                    self.current_data["altitude"] = float(msg.altitude) if msg.altitude else 0.0
                                    # Very rough accuracy estimate based on HDOP
                                    self.current_data["accuracy"] = float(msg.horizontal_dil) * 5.0 if msg.horizontal_dil else 10.0
                                    self.current_data["timestamp"] = datetime.utcnow()

                            # Parse GPRMC (Recommended Minimum) - has speed/course
                            if isinstance(msg, pynmea2.types.talker.RMC):
                                if msg.spd_over_grnd:
                                    # Knots to km/h
                                    self.current_data["speed"] = float(msg.spd_over_grnd) * 1.852
                                if msg.true_course:
                                    self.current_data["heading"] = float(msg.true_course)

                    except pynmea2.ParseError:
                        continue
                    except Exception as e:
                        print(f"GPS Parse Error: {e}")
                        time.sleep(1)
        except serial.SerialException as e:
            print(f"Could not open serial port {self.port}: {e}")

    def get_data(self):
        return self.current_data

# Global instance pattern
# gps_reader = GPSReader()
# gps_reader.start()
