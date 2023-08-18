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

def is_garbled(s):
    """ Returns True if string is a number. """
    try:
        float(s)
        return False
    except ValueError:
        return True

def pack_RAV(data):

    #strip preceeding garbled data, if any
    location = data.index('RAV')
    data = data[location + 3 : ]

    # clean up string in a conservative manner
    # since there may be errors in it
    data = data.strip()
    data = data.replace('#', '')
    data = data.replace('"', '')
    data = data.replace('\\n\'', '')
    data = data.replace(',', '')
    data = data.replace(':', '')
    data = data.replace('rssi ', '')
    data = data.replace('length ', '')
    data = data.replace('SNR ', '')
    print("\nParsing Raven:", data)

    # remove all runs of spaces
    remainder = " ".join(data.split())

    # synthetic time since device turned on
    parts = remainder.split(" ")
    # print("parts:", len(parts))
    if(len(parts) != 21):
        #string is garbled
        return 0

    parts.pop(17)

    if any(is_garbled(p) for p in parts):
        # one or more numbers are corrupted
        print("Raven Garbled:", remainder)
        return 0

    # construct the time
    hours   = float(parts[0][0:2])
    minutes = float(parts[0][2:4])
    seconds = float(parts[0][4:10])

    time_s = hours * 60 * 60 + minutes * 60 + seconds
    # print(time_s)

    hg_1 = int(parts[1])
    hg_2 = int(parts[2])
    hg_3 = int(parts[3])

    pg_1 = int(parts[4])
    pg_2 = int(parts[5])
    pg_3 = int(parts[6])

    un_1 = int(parts[7])
    un_2 = int(parts[8])
    batt = float(parts[9])/1000.0

    gy_1 = int(parts[10])
    gy_2 = int(parts[11])
    gy_3 = int(parts[12])

    ang_1 = int(parts[13])
    ang_2 = int(parts[14])
    vel   = int(parts[15])
    agl   = int(parts[16])

    #crc = parts[17][0:3]
    #counter = int(parts[17][4:])

    rssi =int(parts[17])

    #length = int(parts[18])
    
    snr =int(parts[19])

    payload = struct.pack("idiiiiiiiidiiiiii", 14, time_s, hg_1, hg_2, hg_3, pg_1, pg_2, pg_3, un_1, un_2, batt, ang_1, ang_2, vel, agl, rssi, snr)
    
    print("Sending Type 14 T:", time_s, "HG_1:", hg_1, "HG_2:", hg_2, "HG_3:", hg_3, "PG_1:", pg_1, "PG_2:", pg_2, "PG_3:", pg_3)
    print("Sending Type 14 UN_1:", un_1, "UN_2:", un_2, "Batt:", batt, "gy_1:", gy_1, "gy_2:", gy_2, "gy_3:", gy_3)
    print("Sending Type 14 ANG_1:", ang_1, "ANG_2:", ang_2, "vel:", vel, "agl:", agl, "RSSI:", rssi, "SNR:", snr)
    
    #print(payload)

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
    
    print("Sending Type 12 T:", time_s, "lat:", lat, "lon:", lon, "agl:", altitude_ft)

    #print(payload)

    return payload

ports = list(port_list.comports())
for p in ports:
    print (p)

ser1 = serial.Serial('/dev/cu.usbserial-D201105P', baudrate=115200)
print (ser1.name)

ser2 = serial.Serial('/dev/cu.usbserial-0001', baudrate=115200)
print (ser2.name)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
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

            if 'RAV' in data:
                binary_payload = pack_RAV(data)
                if binary_payload != 0:
                    conn.sendall(binary_payload)
