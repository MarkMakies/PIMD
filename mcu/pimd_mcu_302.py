###############################################################################
# Pulse Induction Metal Detector, v3.01, coil v4
# Runs on RP2040 dev board
#
# Interfaces to a 32-bit oversampling ADC with 1024 down-sampling ADC (LTC2508-32)
# Takes 10k-40k samples per second
# Generates accurate pulse widths (5-50us) for the transmit coil
# Generates an accurate sample trigger (accuracy of 20ns)
# Provides a serial interface to a desktop for controlling:
#   - pulse width (PW)
#   - sample delay (SD)
#   - sample frequency
# Returns down-sampled voltage in uV at a rate of (sample frequency / 1024)
#
# v202 refactored using o3-mini
# v3.02 back to outputing uV - rearranged calc to ensure accuracy
#
###############################################################################

# pyright: reportMissingImports=false

import ubinascii 
import struct
import select
from sys import stdin
from utime import sleep_ms, sleep_us, ticks_ms
from machine import Pin, PWM, SPI, unique_id

# Print program title and board ID
print('Pulse Induction Metal Detector v3.02')
board_id = unique_id()
print('On RP2040 Waveshare RP2040-Zero Pico-like, ID: ' +
      ubinascii.hexlify(board_id).upper().decode())

# ---------------------------------------------------------------------------
# PWM Initialization for drive and sample coil pulses
# ---------------------------------------------------------------------------
drive_coil_pwm = PWM(Pin(4))  # Critical: same slice as sample coil
drive_coil_pwm.freq(10000)
drive_coil_pwm.duty_u16(0)

sample_coil_pwm = PWM(Pin(5))
sample_coil_pwm.freq(10000)

# ---------------------------------------------------------------------------
# ADC Interfaces
# ---------------------------------------------------------------------------
# ADC Raw 14-bit (SPI 0)
sckb_pin = Pin(2, Pin.OUT)
sdob_pin = Pin(0, Pin.IN)
busy_pin = Pin(15, Pin.IN)
adc_raw_spi = SPI(0, baudrate=10_000_000, sck=sckb_pin, miso=sdob_pin)

# ADC Filtered 32-bit (SPI 1)
scka_pin = Pin(10, Pin.OUT)
sdoa_pin = Pin(8, Pin.IN)
drl_pin = Pin(9, Pin.IN)
adc_filtered_spi = SPI(1, baudrate=10_000_000, sck=scka_pin, miso=sdoa_pin)

ltc2508_sel0 = Pin(12, Pin.OUT)

# Scaling factor for PWM duty cycle (2^16 counts over 1e6 microseconds)
PWM_SCALING_NUMERATOR = 2**16  # 65536
PWM_SCALING_DENOMINATOR_NS = 10**9  # 1_000_000_000 (since we're now using ns)

SAMPLE_PULSE_CORRECTION = 0.752   # Actual time between edges is 0.5us faster 

# ---------------------------------------------------------------------------
# ADC and signal reference settings
# ---------------------------------------------------------------------------
REFERENCE_VOLTAGE = 5       # Volts
ADC_RESOLUTION = 14         # Bits

# Raw SDOB word: 22-bit composite left-justified in the 4-byte SPI read.
# Top 14 bits (b31..b18) = signed differential code over +/-5V (10V span).
RAW_DIFF_SHIFT = 18
RAW_DIFF_MASK = 0x3FFF
RAW_FULL_SCALE_UV = 10_000_000

# ---------------------------------------------------------------------------
# Sample buffers and measurement variables
# ---------------------------------------------------------------------------
NUM_RAW_SAMPLES = 10
raw_samples = [0 for _ in range(NUM_RAW_SAMPLES)]
raw_median = 0

NUM_FILTERED_SAMPLES = 100
filtered_samples = [0 for _ in range(NUM_FILTERED_SAMPLES)]

ignore_first_few = 0
current_filtered_value: int = 0
current_raw_value = 0
base_time_ms = ticks_ms()

first_run = True
raw_in_progress = False
filtered_in_progress = False
drl_ready = False

group_delay = 10
group_delay_counter = group_delay

# ---------------------------------------------------------------------------
# Signal Parameters (default values)
# ---------------------------------------------------------------------------
pulse_width_us = 10     # in microseconds
sample_delay_us = 10    # in microseconds
sample_frequency_hz = 10000
down_sample = 256

# ---------------------------------------------------------------------------
# Operational State
# ---------------------------------------------------------------------------
state = 'ready'


def compute_pulse_duties(pulse_width_us, sample_delay_us, sample_frequency_hz):
    """
    Compute the drive/sample PWM duty values (duty_u16 counts) for the
    given pulse width, sample delay, and pulse frequency.
    """
    pulse_width_ns = int(pulse_width_us * 1000)
    sample_delay_ns = int((sample_delay_us + SAMPLE_PULSE_CORRECTION) * 1000)
    drive_duty = (pulse_width_ns * sample_frequency_hz * PWM_SCALING_NUMERATOR) // PWM_SCALING_DENOMINATOR_NS
    sample_duty = drive_duty + (sample_delay_ns * sample_frequency_hz * PWM_SCALING_NUMERATOR) // PWM_SCALING_DENOMINATOR_NS
    return drive_duty, sample_duty


def pulse_duties_valid(drive_duty, sample_duty):
    """
    Duties must fit duty_u16()'s 16-bit range, and the sample point must
    fall strictly after the drive pulse ends.
    """
    return 0 <= drive_duty <= 65535 and 0 <= sample_duty <= 65535 and sample_duty > drive_duty


def update_pulse_configuration():
    """
    Update PWM configurations for the drive and sample coils based on
    the current pulse width, sample delay, and frequency.
    """
    global group_delay_counter

    drive_duty, sample_duty = compute_pulse_duties(pulse_width_us, sample_delay_us, sample_frequency_hz)

    group_delay_counter = group_delay

    # Update frequencies and duty cycles
    drive_coil_pwm.freq(sample_frequency_hz)
    sample_coil_pwm.freq(sample_frequency_hz)

    drive_coil_pwm.duty_u16(drive_duty)
    sample_coil_pwm.duty_u16(sample_duty)

    # update down-sample factor
    ltc2508_sel0.value(down_sample == 1024) # only allowed values 256, 1024

def filtered_data_callback(pin):
    """
    Interrupt callback for filtered ADC data-ready (DRL falling edge).
    ISR-safe: only counts down the group-delay settle counter and sets a
    ready flag once it elapses. The SPI read happens in the main loop
    (acquire_filtered_data), not here.
    """
    global drl_ready, group_delay_counter

    if group_delay_counter == 0:
        # Disable further interrupts for this cycle
        pin.irq(handler=None)
        drl_ready = True
    else:
        group_delay_counter -= 1


def acquire_filtered_data():
    """
    Acquire one filtered ADC sample.
    Blocks until the group-delay settle period has elapsed and the ADC
    signals data-ready, then reads the result over SPI from the main
    loop. Also maintains a rolling buffer of the last NUM_FILTERED_SAMPLES
    samples.
    """
    global current_filtered_value, filtered_in_progress, filtered_samples, drl_ready

    filtered_in_progress = True
    drl_ready = False
    # Set up the interrupt on a falling edge from the ADC
    drl_pin.irq(trigger=Pin.IRQ_FALLING, handler=filtered_data_callback)
    while not drl_ready:
        sleep_ms(1)

    # Read 4 bytes from filtered ADC SPI (main-loop context, not the ISR)
    data_bytes = adc_filtered_spi.read(4)
    # Unpack as a big-endian 32-bit signed integer
    current_filtered_value = int(struct.unpack('>i', data_bytes)[0])
    filtered_in_progress = False

    # Maintain rolling buffer: remove oldest sample and add new sample.
    filtered_samples.pop(0)
    filtered_samples.append(current_filtered_value)


def calculate_standard_deviation(data):
    """
    Calculate and return the standard deviation of the list 'data'.
    """
    n = len(data)
    mean_value = sum(data) / n
    variance = sum((x - mean_value) ** 2 for x in data) / n
    return variance ** 0.5


def measurement_cycle():
    """
    Perform one measurement cycle:
      - Acquire a new filtered ADC sample.
      - Convert raw ADC values to microvolts.
      - Calculate the standard deviation of the filtered samples.
      - Print timing and measurement information.
    """
    global base_time_ms

    # Acquire one sample (blocking)
    acquire_filtered_data()

    # Convert filtered ADC value to microvolts
    # (Assuming ADC full scale corresponds to 2^31 counts for REF_VOLTAGE)
    #current_filtered_uV = int(current_filtered_value / 2**31 * REFERENCE_VOLTAGE * 1_000_000)
    current_filtered_uV = (current_filtered_value * 5_000_000) // (2**31)
        
    # Compute standard deviation and convert to microvolts

    #std_dev_uV = int(filtered_std_dev / 2**31 * REFERENCE_VOLTAGE * 1_000_000)
    filtered_std_dev = int(calculate_standard_deviation(filtered_samples)) 
    std_dev_uV = (filtered_std_dev * 5_000_000) // (2**31)

    elapsed_time = ticks_ms() - base_time_ms
    print(
        '*{time:d}, {current:d}, {std_dev:d}, {freq_kHz:1.1f}, {pulse:1.1f}, {delay:1.1f}, {down:d}'.format(
            time=elapsed_time,
            current=current_filtered_uV,
            std_dev=std_dev_uV,
            freq_kHz=sample_frequency_hz / 1000,
            pulse=pulse_width_us,
            delay=sample_delay_us,
            down=down_sample
    )
)


def read_raw_sample():
    """
    Read one raw sample from the no-latency ADC output (SDOB, SPI0).
    Extracts the signed 14-bit differential code from the top 14 bits of
    the 4-byte SPI word and returns it as a signed int.
    """
    data_bytes = adc_raw_spi.read(4)
    word = struct.unpack('>I', data_bytes)[0]
    raw14 = (word >> RAW_DIFF_SHIFT) & RAW_DIFF_MASK
    if raw14 & (RAW_DIFF_MASK // 2 + 1):
        raw14 -= RAW_DIFF_MASK + 1
    return raw14


def acquire_raw_average(x):
    """
    Boxcar-average x raw SDOB samples at the current (held) pulse_width /
    sample_delay. Reads are paced one per pulse period so each sample is an
    independent conversion. Returns (mean_uV, stddev_uV).
    """
    period_us = 1_000_000 // sample_frequency_hz
    samples = []
    for _ in range(x):
        samples.append(read_raw_sample())
        sleep_us(period_us)

    mean = sum(samples) / x
    variance = sum((s - mean) ** 2 for s in samples) / x
    mean_uV = int(mean * RAW_FULL_SCALE_UV / 2**14)
    std_uV = int((variance ** 0.5) * RAW_FULL_SCALE_UV / 2**14)
    return mean_uV, std_uV


def check_for_commands():
    """
    Check for incoming commands from the serial interface.
    Commands:
      - 'S' or 's': Start running measurements.
      - 'E' or 'e': Stop measurements.
      - '*' followed by parameters (Frequency, PulseWidth, SampleDelay):
            e.g., "*10,20,30" sets frequency (in kHz), pulse width, and sample delay.
      - 'A' or 'a' followed by a count: e.g. "A32" acquires 32 boxcar-averaged
            raw samples at the current pulse_width/sample_delay and replies
            with one 'R...' record.
    """
    global state, sample_frequency_hz, pulse_width_us, sample_delay_us, down_sample

    try:
        if serial_poll.poll(1):  # Non-blocking poll for input
            line = stdin.readline()  # Blocking read after poll indicates data
            cmd = line[0]
            if cmd in ('S', 's'):
                state = 'running'
                update_pulse_configuration()
            elif cmd in ('E', 'e'):
                state = 'stop'
            elif cmd == '*':
                # Expect comma-separated parameters: frequency (in kHz), pulse width, sample delay, down-sample factor
                parts = line[1:].split(',')
                new_frequency_hz = int(1000 * float(parts[0]))
                new_pulse_width_us = float(parts[1])
                new_sample_delay_us = float(parts[2])
                new_down_sample = int(parts[3])

                drive_duty, sample_duty = compute_pulse_duties(
                    new_pulse_width_us, new_sample_delay_us, new_frequency_hz)
                if pulse_duties_valid(drive_duty, sample_duty):
                    sample_frequency_hz = new_frequency_hz
                    pulse_width_us = new_pulse_width_us
                    sample_delay_us = new_sample_delay_us
                    down_sample = new_down_sample
                    update_pulse_configuration()
                else:
                    print('Command Input ERROR: rejected pulse config (drive_duty={0}, sample_duty={1})'.format(
                        drive_duty, sample_duty))
            elif cmd in ('A', 'a'):
                # Acquire x boxcar-averaged raw samples at the current pulse config
                try:
                    x = int(line[1:])
                except ValueError:
                    x = 0
                if not 1 <= x <= 1000:
                    print('Command Input ERROR: invalid average count (A{0})'.format(line[1:].strip()))
                else:
                    drive_duty, sample_duty = compute_pulse_duties(
                        pulse_width_us, sample_delay_us, sample_frequency_hz)
                    if not pulse_duties_valid(drive_duty, sample_duty):
                        print('Command Input ERROR: current pulse config invalid for acquisition '
                              '(drive_duty={0}, sample_duty={1})'.format(drive_duty, sample_duty))
                    else:
                        mean_uV, std_uV = acquire_raw_average(x)
                        elapsed_time = ticks_ms() - base_time_ms
                        record = 'R{0:d}, {1:d}, {2:d}, {3:d}, {4:1.1f}, {5:1.1f}, {6:1.1f}'.format(
                            elapsed_time, mean_uV, std_uV, x,
                            sample_frequency_hz / 1000, pulse_width_us, sample_delay_us)
                        print(record)
            else:
                print('Command Input ERROR')
    except Exception as e:
        print('Command Input EXCEPTION:', e)


def set_safe_state():
    """
    Put the system into a safe state: turn off drive coil and
    set sample coil to maximum duty cycle. Also disable interrupts.
    """
    drive_coil_pwm.duty_u16(0)
    sample_coil_pwm.duty_u16(2**16 - 1)
    drl_pin.irq(handler=None)
    print('SAFE: Drive OFF / Sampling OFF / Interrupts OFF')


# ---------------------------------------------------------------------------
# Main Program Loop
# ---------------------------------------------------------------------------
print('Ready')

serial_poll = select.poll()
serial_poll.register(stdin, select.POLLIN)

try:
    while True:
        check_for_commands()
        if state == 'running':
            measurement_cycle()
        elif state == 'stop':
            set_safe_state()
            state = 'ready'
except KeyboardInterrupt:
    print('\nTerminating')
    drive_coil_pwm.duty_u16(0)
finally:
    set_safe_state()
    print()
