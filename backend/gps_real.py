
import serial
import pynmea2
import time
import threading
from datetime import datetime

# NOTE: Requires 'pyserial' and 'pynmea2'
# pip install pyserial pynmea2

class GPSReader:
    def __init__(self, port='/dev/serial0', baudrate=9600):
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
        self.connected = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _read_loop(self):
        # U-blox7 usually runs at 9600 but can be configured to other rates
        baud_rates = [self.baudrate, 9600, 4800, 115200]
        
        while self.running:
            for baud in baud_rates:
                if not self.running:
                    break
                try:
                    with serial.Serial(self.port, baud, timeout=1) as ser:
                        print(f"[GPS] Successfully opened {self.port} at {baud} baud")
                        self.connected = True
                        while self.running:
                            try:
                                # Read line and decode
                                line = ser.readline().decode('ascii', errors='replace').strip()
                                
                                # Process NMEA sentences from U-blox7 (starts with $GP or $GN)
                                if line.startswith('$G'):
                                    try:
                                        msg = pynmea2.parse(line)
                                    except pynmea2.ParseError:
                                        continue # skip malformed lines typical in serial streams

                                    # Parse GPGGA/GNGGA (Fix Data - Location and Altitude)
                                    if type(msg).__name__ == 'GGA':
                                        if getattr(msg, 'lat', None) and getattr(msg, 'lon', None):
                                            self.current_data["latitude"] = msg.latitude
                                            self.current_data["longitude"] = msg.longitude
                                            self.current_data["altitude"] = float(msg.altitude) if getattr(msg, 'altitude', None) else 0.0
                                            self.current_data["accuracy"] = float(msg.horizontal_dil) * 5.0 if getattr(msg, 'horizontal_dil', None) else 10.0
                                            self.current_data["timestamp"] = datetime.utcnow()
                                            
                                    # Parse GPRMC/GNRMC (Recommended Minimum - Speed and Heading)
                                    elif type(msg).__name__ == 'RMC':
                                        if getattr(msg, 'lat', None) and getattr(msg, 'lon', None):
                                            self.current_data["latitude"] = msg.latitude
                                            self.current_data["longitude"] = msg.longitude
                                            self.current_data["timestamp"] = datetime.utcnow()
                                        if getattr(msg, 'spd_over_grnd', None):
                                            self.current_data["speed"] = float(msg.spd_over_grnd) * 1.852 # Knots to km/h
                                        if getattr(msg, 'true_course', None) and msg.true_course != '':
                                            self.current_data["heading"] = float(msg.true_course)

                            except Exception as e:
                                # Ignore transient read errors
                                pass
                                
                except serial.SerialException:
                    self.connected = False
                    # Serial port unavailable or disconnected
                    time.sleep(2) # Wait before trying next baud rate or repeating loop

    def get_data(self):
        data = self.current_data.copy()
        data["connected"] = self.connected
        return data

# Global instance pattern
# gps_reader = GPSReader()
# gps_reader.start()
