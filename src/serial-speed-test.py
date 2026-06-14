import serial
import time

# Set up serial port (update the port name as needed)
ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)  # Adjust to your port

prev_time = time.time()

print('Listening on', ser.port)

try:
    while True:
        line = ser.readline().decode('utf-8', errors='ignore').rstrip()
        if line:
            now = time.time()
            interval = (now - prev_time) * 1000  # Convert to ms
            prev_time = now

            print(f'Packet Size: {len(line)} chars | Interval: {interval:.2f} ms')
except KeyboardInterrupt:
    print('\nStopped')
    ser.close()
