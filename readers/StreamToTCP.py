# Takes serial data and makes them available via TCP socket for COSMOS/OPENC3
# Copyright 2023 Jan T. Liphardt
# JTLiphardt@gmail.com
# No warranties, use at your own risk.

import serial
import serial.tools.list_ports as port_list
import socket
import struct
import re

HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 23200        # Port to listen on (non-privileged ports are > 1023)
GPS_ID = 'FthrWt04072'
Serial1 = '/dev/cu.usbserial-D201105P' # for the Featherweight GS
Serial2 = '/dev/cu.usbserial-2' # for the loRa receiver

def is_garbled(s):
    """ Returns True if string is a number. """
    try:
        float(s)
        return False
    except ValueError:
        return True

# def send_data(binary_data, conn):
#     try:
#         conn.sendall(binary_data)
#     except KeyboardInterrupt:
#         if conn:
#             conn.close()

def pack_EGG(data):

    #strip preceeding garbled data, if any
    location = data.index('E:')
    data = data[location + 2 : -3] # chop off the \n'

    print("\nParsing Egg:", data)

    # 285:{000>@1>#0000>~AB0000>?085>! 458>=>:-20:73:11\n'
    # 288:{000>@1>#0000>~AB0000>?085>! 458>=>:-21:74:10\n'
    # "{000>@1>#0000>~AB0000>?085>! 458>=>"
    parts = data.split(":")
    print("parts:", len(parts))
    if(len(parts) != 5):
        print("Eggtimer Packet too short or garbled:", data)
        return 0

    count  = int(parts[0])
    eggData = parts[1]
    rssi   = int(parts[2])
    # 3 = size    
    snr    = int(parts[4])

    agl = 0
    if "{" in eggData:
        i = data.index("{")
        agl = int(data[i+1:i+4])

    batt = 0.0
    if "?" in eggData:
        i = data.index("?")
        batt = float(data[i+1:i+4])/10.0

    phase = 0
    if "@" in eggData:
        i = data.index("@")
        phase = int(data[i+1])

    pyro = 100;
    if "~" in eggData:
        i = data.index("~")
        state = data[i+1:i+4]
        if state[0] == "-": pyro += 100;
        if state[0] == "A": pyro += 200;
        if state[0] == "1": pyro += 300;
        if state[1] == "-": pyro += 10;
        if state[1] == "B": pyro += 20;
        if state[1] == "2": pyro += 30;
        if state[2] == "-": pyro += 1;
        if state[2] == "C": pyro += 2;
        if state[2] == "2": pyro += 3;

    payload = struct.pack("iidiiiii", 15, count, batt, agl, phase, pyro, rssi, snr)
    print("Sending Type 15 C:", count, "BATT:", batt, "Alt:", agl, "Phase:", phase, "Pyro:", pyro, "RSSI:", rssi, "SNR:", snr)
    return payload

def pack_RAV(data):

    #strip preceeding garbled data, if any
    location = data.index('R:')
    data = data[location + 2: ] # chop off the \n

    # there may or may not be garbage at the end of this...
    # thee chars worth?
    data = data[0: -3] # chop off the \n

    print("\nParsing Raven:", data)

    parts = data.split(":")
    # print("parts:", len(parts))
    if(len(parts) != 11):
        print("Raven Packet too short or garbled:", data)
        return 0

    if any(is_garbled(p) for p in parts):
        # one or more numbers are corrupted
        print("Raven Corrupted:", data)
        return 0

    # New Raven Data: R:2864:-13:-75:7698:3:0:0

    count  = int(parts[0])
    time_s = float(parts[1])/10.0
    hg_1   = int(parts[2])
    pg_1   = int(parts[3])
    batt   = float(parts[4])/1000.0
    gy_1   = int(parts[5])
    vel    = int(parts[6])
    agl    = int(parts[7])

    rssi   = int(parts[8])
    # size    
    snr    = int(parts[10])

    payload = struct.pack("iiddiiiiiii", 14, count, time_s, batt, hg_1, pg_1, gy_1, vel, agl, rssi, snr)
    
    print("Sending Type 14 C:", count, "T:", time_s, "HG_1:", hg_1, "PG_1:", pg_1, "Batt:", batt, "gy_1:", gy_1)
    print("Sending Type 14 V:", vel, "AGL:", agl, "RSSI:", rssi, "SNR:", snr)
    
    return payload

# @ RX_NOMTK 202 0000 00 00 03:00:59.920 CRC_OK  Rx NomTrk FthrWt04072 
# PkRx 10636 PkTx 10959 RSSI -077 SNR +06 
# AckRx 10598 AckTx 10645 RSSI -085 SNR  +6 
# SF 10 frq 919000000 trk_B_V 3972   +0 C CRC: 5D9B

def pack_FW_TRK(data):

    #strip preceeding garbled data, if any
    location = data.index('RX_NOMTK')
    data = data[location + 8 : ]

    # clean up string in a conservative manner
    # since there may be errors in it
    data = data.strip()
    data = data.replace('\\r\\n\'', '')
    data = data.replace(':', '')
    data = data.replace('_', '')
    data = data.replace(GPS_ID, '')
    data = re.sub('[a-z]','',data)
    data = re.sub('[A-Z]','',data)

    # need to be careful since CRC hex is a mix of 
    # letters and numbers, generally, but not always

    # remove all runs of spaces
    remainder = " ".join(data.split())
    print("\nParsing T_Health:", remainder)

    # synthetic time since device turned on
    parts = remainder.split(" ")
    # print("parts:", len(parts))
    if(len(parts) < 17):
        #string is garbled
        return 0

    parts = parts[4 : 16]
    # print("parts:", parts)
    if any(is_garbled(p) for p in parts):
        # one or more numbers are corrupted
        return 0

    # construct the time
    hours   = float(parts[0][0:2])
    minutes = float(parts[0][2:4])
    seconds = float(parts[0][4:10])
    time_s = hours * 60 * 60 + minutes * 60 + seconds

    rssi_1 = int(parts[3])
    rssi_2 = int(parts[7])
    bat = float(parts[11])/1000.0

    payload = struct.pack("idiid", 13, time_s, rssi_1, rssi_2, bat)
    
    print("Sending Type 13 T:", time_s, "RSSI_1:", rssi_1, "RSSI_2:", rssi_2, "B:", bat)
    #print(payload)

    return payload

# GP_STAT 4157.924 Alt 000114 lt +XX.XXXXXX ln -XXX.XXXXX 
# Vel +0000 +069 +0000 
# Fix 3 # 21 14 10  5 
# 000_00_00 000_00_00 000_00_00 000_00_00 000_00_00 CRC: 7C9A

def pack_FW_GPS(data):

    #strip preceeding garbled data, if any
    location = data.index('GPS_STAT')
    data = data[location + 8 : ]

    # clean up string in a conservative manner
    # since there may be errors in it
    data = data.strip()
    data = data.replace('#', '')
    data = data.replace(':', '')
    data = data.replace('CRC_OK', '')
    data = data.replace('\\r\\n\'', '')
    data = data.replace('TRK', '')
    data = data.replace('Alt', '')
    data = data.replace('lt', '')
    data = data.replace('ln', '')
    data = data.replace('Vel', '')
    data = data.replace('Fix', '')
    data = data.replace(GPS_ID, '')
    data = data.replace('CRC', '')

    # remove all runs of spaces
    remainder = " ".join(data.split())
    print("\nParsing Tracker:", remainder)

    # synthetic time since device turned on
    parts = remainder.split(" ")
    # print("parts:", len(parts))
    if(len(parts) != 22):
        #string is garbled
        return 0

    parts = parts[4 : 16]
    # print("parts:", parts)
    if any(is_garbled(p) for p in parts):
        # one or more numbers are corrupted
        return 0

    hours   = float(parts[0][0:2])
    minutes = float(parts[0][2:4])
    seconds = float(parts[0][4:10])

    time_s = hours * 60 * 60 + minutes * 60 + seconds
    # print(time_s)

    # the actual parsing/packing, now that it's safe to do so
    altitude_ft = int(  parts[ 1])
    lat         = float(parts[ 2])
    lon         = float(parts[ 3])
    hv          = int(  parts[ 4])
    hdir        = int(  parts[ 5])
    vv          = int(  parts[ 6])
    fix         = int(  parts[ 7])
    satTotal    = int(  parts[ 8])
    sat24       = int(  parts[ 9])
    sat32       = int(  parts[10])
    sat40       = int(  parts[11])

    payload = struct.pack("ididdiiiiiiii", 12, time_s, altitude_ft, lat, lon, \
        hv, hdir, vv, fix, satTotal, sat24, sat32, sat40)
    
    print("Sending Type 12 T:", time_s, "lat:", lat, "lon:", lon, "alt:", altitude_ft)

    #print(payload)

    return payload

ports = list(port_list.comports())
for p in ports:
    print (p)

ser1 = serial.Serial(Serial1, baudrate=115200)
print (ser1.name)

ser2 = serial.Serial(Serial2, baudrate=115200)
print (ser2.name)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    conn, addr = s.accept()

    with conn:        
        print(f"Connected by {addr}")
        while True:
        
            # read all the serial data
            data1 = ser1.readline()
            # print (data1)
            
            data2 = ser2.readline()
            # print (data2)

            data = str(data1)

            if '@ GPS_STAT' in data:
                # either packet not for us
                # or packet had corrupted ID
                # or different type of packet
                if GPS_ID not in data:
                    continue
                if 'TRK' in data:
                    # ok, it's a tracking packet
                    binary_payload = pack_FW_GPS(data)
                    if binary_payload != 0:
                        conn.sendall(binary_payload)

            if '@ RX_NOMTK' in data:
                # either packet not for us
                # or packet had corrupted ID
                # or different type of packet
                if GPS_ID not in data:
                    continue
                binary_payload = pack_FW_TRK(data)
                if binary_payload != 0:
                    conn.sendall(binary_payload)

            data = str(data2)
            print(f"Data2: {data}")
            # there are three scenarios
            # Eggtimer only 
            # Raven only
            # Dual packet with data from both computers
            if data[6] == 'E':
                binary_payload = pack_EGG(data)
                if binary_payload != 0:
                    try:
                        conn.sendall(binary_payload)
                    except:
                        print(f"Lost connection to {addr}")
                        conn, addr = s.accept()

            if data[6] == 'R':
                if "E:" in data:
                    parts = data.split("E:")
                    data = parts[0]
                    dataEgg = parts[1]
                    print(f"Egg data: {dataEgg}")
                    binary_payload = pack_EGG("E:"+dataEgg)
                    if binary_payload != 0:
                        try:
                            conn.sendall(binary_payload)
                        except:
                            print(f"Lost connection to {addr}")
                            conn, addr = s.accept()

                binary_payload = pack_RAV(data)
                if binary_payload != 0:
                    try:
                        conn.sendall(binary_payload)
                    except:
                        print(f"Lost connection to {addr}")
                        conn, addr = s.accept()
