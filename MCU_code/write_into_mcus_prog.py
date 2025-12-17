import serial
import time
import json
import sys
import os
from tqdm import tqdm

BAUD_RATE = 115200

## settings
try:
    com_port: str = sys.argv[1]
    mode: str = sys.argv[2] # either 'c' or 'w'
    mcu_id: str = sys.argv[3] # specify if needed for workers
except IndexError:
    print(f"Usage: python3 write_into_mcus_prog.py <PORT> <MODE> <ID>")
    sys.exit(1)

## init the serial port
try:
    ser: serial.Serial = serial.Serial(com_port, BAUD_RATE, timeout=1)
except Exception as e:
    print(f"Serial connection failed: {e}")
    sys.exit(1)



def wait_for_mcu_response(timeout=5) -> str | None:
    """
        Read MCU response
    """
    start = time.time()
    while True:
        if ser.in_waiting:
            line = ser.readline().decode().strip()
            if line:
                return line
        if time.time() - start > timeout:
            return None

def count_down(seconds: int, desc: str ="Waiting"):
    """
        Show the uploading progress
    """
    for _ in tqdm(range(seconds), desc=desc, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}s'):
        time.sleep(1)
        
def send_chunk(data_str: str):
    """ 
        Send the data chunk 
    """
    ser.write(data_str.encode())

## main logic
def process_coordinator(file_path: str):
    """ Process to upload the coordinator json file """
    print(f"Process Coordinator file: {file_path}")
    
    # 1. erase phase
    send_chunk('e')
    print(f"MCU: {wait_for_mcu_response()}")
    print(f"MCU: {wait_for_mcu_response()}")

    send_chunk('e')
    count_down(10, "Cleaning...")
    print(f"MCU: {wait_for_mcu_response()}")
    print(f"MCU: {wait_for_mcu_response()}")

    # 2. prepare to send data
    send_chunk('c')
    count_down(10, desc="Prepare to receive")
    print(f"MCU: {wait_for_mcu_response()}")
    print(f"MCU: {wait_for_mcu_response()}")

    # 3. read and send
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    for line in tqdm(lines, desc="Upload lines", unit="Line"):
        d = json.loads(line)
        mappings = d.get('mapping', [])

        if not mappings:
            break
        
        try:
            data = mappings[int(mcu_id)]
        except IndexError:
            continue

        # construct a data buffer to eliminate the times of calling write
        buffer = []
        # phases
        buffer.append(f"{len(data['count'])}!")
        # count
        for c in data['count']:
            buffer.append(f"{c}!")
        # map
        for m in data['map']:
            buffer.append(f"{' '.join(map(str, m))} !")
        # padding
        for p in data['padding_pos']:
            buffer.append(f"{len(p)} {' '.join(map(str, p))} !")    
        # end pos
        if not data['end_pos']:
            buffer.append("0!")
        else:
            buffer.append(f"{len(data['end_pos'])} ")
            for e in data['end_pos']:
                buffer.append(f"{' '.join(map(str, e))} ")
            buffer.append("!")
        # zero point
        buffer.append(f"{' '.join(map(str, data['zero_point']))} !")
        # scale
        buffer.append(f"{' '.join(map(str, data['scale']))} !")
        
        # send together
        full_packet = "".join(buffer)
        send_chunk(full_packet)
        send_chunk('!')
    send_chunk('!') # EOF
    print(f"MCU final response: {wait_for_mcu_response()}")
    

def process_worker(file_path: str):
    """ Process to upload the worker json file """
    print(f"Process Worker file: {file_path}")

    # 1. start
    send_chunk('s')
    count_down(10, desc="Prepare to receive")
    print(f"MCU: {wait_for_mcu_response()}")
    print(f"MCU: {wait_for_mcu_response()}")
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # 2. go through each layer/line
    for line in tqdm(lines, desc="Total lines", unit="line"):
        data = json.loads(line)
        weights = data.get('weights', [])

        for weight in tqdm(weights, desc="Upload weights", leave=False):
            buffer = []
            
            d = weight['data']
            data_str = " ".join(map(str, d))
            buffer.append(f"{len(d)} {data_str}!")
            buffer.append(f"{weight['bias']}!")
            buffer.append(f"{weight['which_kernel']}!")
            buffer.append(f"{weight['count']}!")

            if weight['start_pos_in']:
                sp = weight['start_pos_in']
                buffer.append(f"{sp[0]} {sp[1]} {sp[2]}!")
            else:
                buffer.append("!")


            # Info (Convolution / Linear)
            info = weight['info']
            if 'Convolution' in info:
                t = info['Convolution']
                # 预先格式化好，减少多次I/O
                buffer.append(f"C {t['o_pg']} {t['i_pg']} {t['s'][0]} {t['s'][1]} {t['k'][0]} {t['k'][1]} "
                              f"{t['i'][0]} {t['i'][1]} {t['i'][2]} {t['o'][0]} {t['o'][1]} {t['o'][2]}!")
            else:
                t = info['Linear']
                buffer.append(f"L {t['b_in']} {t['c_in']} {t['b_out']} {t['c_out']}!")

            
            # Zero points & Scale
            zp = weight['zero_points']
            buffer.append(f"{zp[0]} {zp[1]} {zp[2]} {weight['m']} {weight['s_out']}!")

            # --- 关键优化: 一次性发送整个 Block ---
            full_packet = "".join(buffer)
            send_chunk(full_packet)
        send_chunk('!') # line ends
    
    send_chunk('!') # EOF
    print(f"MCU final response: {wait_for_mcu_response()}")


if __name__ == "__main__":
    if mode == "c":
        target_file = "../pc_code/Simulation/Simu_q/Coordinator.json"
        if os.path.exists(target_file):   
            process_coordinator(target_file)
        else:
            print(f"Error: can't find the file {target_file}")
    else:
        target_file = f"../pc_code/Simulation/Simu_q/worker_{mcu_id}.json"
        if os.path.exists(target_file):
            process_worker(target_file)
        else:
            print(f"Error: can't find the file {target_file}")
    print(f"Upload finish")

        

