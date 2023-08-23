# Takes serial data and makes them available via TCP socket for COSMOS/OPENC3
# Copyright 2023 Jan T. Liphardt
# JTLiphardt@gmail.com
# No warranties, use at your own risk.

import serial
import serial.tools.list_ports as port_list
import socket
import struct
import re
import time

HOST    = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT    = 23200        # Port to listen on (non-privileged ports are > 1023)
GPS_ID  = 'FthrWt04072'
Serial1 = '/dev/cu.usbserial-D201105P' # for the Featherweight GS
Serial2 = '/dev/cu.usbserial-4' # for the loRa receiver

def is_garbled(s):
    """ Returns True if string is a number. """
    try:
        float(s)
        return False
    except ValueError:
        return True

# @ RX_NOMTK 202 0000 00 00 03:00:59.920 CRC_OK  Rx NomTrk FthrWt04072 
# PkRx 10636 PkTx 10959 RSSI -077 SNR +06 
# AckRx 10598 AckTx 10645 RSSI -085 SNR  +6 
# SF 10 frq 919000000 trk_B_V 3972   +0 C CRC: 5D9B

# b'@ RX_NOMTK 202 0000 00 00 00:50:02.583 CRC_OK  Rx NomTrk FthrWt04072 PkRx  2523 PkTx   777 RSSI -030 SNR +07 AckRx   761 AckTx  2524 RSSI -044 SNR  +5 SF 10 frq 919000000 trk_B_V 3873   +0 C CRC: 011D\r\n'
# T_Health Input:  202 0000 00 00 00:50:02.583 CRC_OK  Rx NomTrk FthrWt04072 PkRx  2523 PkTx   777 RSSI -030 SNR +07 AckRx   761 AckTx  2524 RSSI -044 SNR  +5 SF 10 frq 919000000 trk_B_V 3873   +0 C CRC: 011D\r\n'
# T_Health Parse: 202 0000 00 00 005002.583 2523 777 -030 +07 761 2524 -044 +5 10 919000000 3873 +0 011
# Sending Type 13 T: 3002.583 RSSI_1: -30 RSSI_2: -44 B: 3.873

def pack_FW_TRK(data):

    #strip preceeding garbled data, if any
    location = data.index('RX_NOMTK')
    data = data[location + 9 : ]
    # print("T_Health Input:", data)

    # clean up string in a conservative manner
    # since there may be errors in it
    data = data.strip()
    data = data.replace(':', '')
    data = data.replace('_', '')
    data = data.replace(GPS_ID, '')
    data = re.sub('[a-z]','',data)
    data = re.sub('[A-Z]','',data)

    # need to be careful since CRC hex is a mix of 
    # letters and numbers, generally, but not always

    # remove all runs of spaces
    remainder = " ".join(data.split())
    print("Parsing T_Health:", remainder)

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
    snr_1 = int(parts[4])
    rssi_2 = int(parts[7])
    snr_2 = int(parts[8])

    bat = float(parts[11])/1000.0

    payload = struct.pack("idiiiidc", 13, time_s, rssi_1, rssi_2, snr_1, snr_2, bat, b'\n')
    
    print("Sending Type 13 T:", time_s, "RSSI_1:", rssi_1, "RSSI_2:", rssi_2, "SNR_1:", snr_1, "SNR_2:", snr_2, "BATT:", bat)

    return payload

# # GP_STAT 4157.924 Alt 000114 lt +XX.XXXXXX ln -XXX.XXXXX 
# # Vel +0000 +069 +0000 
# # Fix 3 # 21 14 10  5 
# # 000_00_00 000_00_00 000_00_00 000_00_00 000_00_00 CRC: 7C9A

def pack_FW_GPS(data):

    #strip preceeding garbled data, if any
    location = data.index('GPS_STAT')
    data = data[location + 9 : ]

    # clean up string in a conservative manner
    # since there may be errors in it
    data = data.strip()
    data = data.replace(':', '')
    data = data.replace('_', '')
    data = data.replace('#', '')
    data = data.replace(GPS_ID, '')
    data = re.sub('[a-z]','',data)
    data = re.sub('[A-Z]','',data)

    # remove all runs of spaces
    remainder = " ".join(data.split())
    print("Parsing Tracker:", remainder)

    # synthetic time since device turned on
    parts = remainder.split(" ")
    # print("parts:", len(parts))
    if(len(parts) < 21):
        print("Tracker packet too short:", len(parts))
        return 0

    parts = parts[4 : 16]
    # print("parts:", parts)
    if any(is_garbled(p) for p in parts):
        # one or more numbers are corrupted
        print("Tracker data corrupted:", parts)
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

    payload = struct.pack("qdiddiiiiiiiic", 11, time_s, altitude_ft, lat, lon, \
        hv, hdir, vv, fix, satTotal, sat24, sat32, sat40, b'\n')
    
    # print(payload)

    print("Sending Type 11 T:", time_s, "lat:", lat, "lon:", lon, "alt:",\
     altitude_ft, "hv:", hv, "hdir:", hdir, "vv:", vv, "fix:", fix, "satTotal:", satTotal)

    return payload

def pack_EGG(data):

    #strip preceeding garbled data, if any
    location = data.index('E:')
    data = data[location + 2 :]
    data = data.replace('\\n\'', '')  # chop off the \n', if its there

    print("Parsing Egg:", data)

    # 285:{000>@1>#0000>~AB0000>?085>! 458>=>:-20:73:11\n'
    # 288:{000>@1>#0000>~AB0000>?085>! 458>=>:-21:74:10\n'
    # "{000>@1>#0000>~AB0000>?085>! 458>=>"
    parts = data.split(":")
    # print("parts:", len(parts))
    if(len(parts) < 5):
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

    batt = 0
    if "?" in eggData:
        i = data.index("?")
        batt = int(data[i+1:i+4])

    phase = 0
    if "@" in eggData:
        i = data.index("@")
        phase = int(data[i+1])

    pyro = 0;
    if "~" in eggData:
        i = data.index("~")
        state = data[i+1:i+4]
        if state[0] == "0": pyro += 100;
        if state[0] == "A": pyro += 200;
        if state[0] == "1": pyro += 300;
        if state[1] == "0": pyro +=  10;
        if state[1] == "B": pyro +=  20;
        if state[1] == "2": pyro +=  30;
        if state[2] == "0": pyro +=   1;
        if state[2] == "C": pyro +=   2;
        if state[2] == "3": pyro +=   3;

    payload = struct.pack("qqiiiiiic", 2, count, agl, phase, pyro, rssi, snr, batt, b'\n')

    #print(payload)
    print("Sending Type 2 C:", count, "Batt:", batt, "Alt:", agl, "Phase:", phase, "Pyro:", pyro, "RSSI:", rssi, "SNR:", snr)
    
    return payload

def pack_RAV(data):

    #strip preceeding garbled data, if any
    location = data.index('R:')
    data = data[location + 2: ]
    data = data.replace('\\n\'', '') # chop off the \n', if its there

    print("Parsing Raven:", data)

    parts = data.split(":")
    # print("parts:", len(parts))
    if(len(parts) < 11):
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

    payload = struct.pack("qqiiiiiiiiddc", 1, count, hg_1, pg_1, gy_1, vel, agl, rssi, snr, 0, time_s, batt, b'\n')

    print("Sending Type 1 C:", count, "HG_1:", hg_1, "PG_1:", pg_1,\
        "gy_1:", gy_1, "V:", vel, "AGL:", agl, "RSSI:", rssi, "SNR:",\
        snr, "T:", time_s, "Batt:", batt)
    
    return payload

def send_data(binary_data, conn):
    if binary_data == 0:
        return
    try:
        conn.sendall(binary_data)
    except KeyboardInterrupt:
        if conn:
            conn.close()

if __name__ == "__main__":
    
    ports = list(port_list.comports())
    print("Possible Serial ports:")
    for p in ports:
        if '-D2' in p.name: #featherweight prefix is D2?
            print("\t"+p.name)
        elif 'CP2102 USB to UART Bridge Controller' in p.description:
            print("\t"+p.name)

    print("")

    ser1 = None
    ser2 = None

    timestr = time.strftime("%Y%m%d-%H%M%S")
    logFileRaw = open(timestr+'_RAW.txt', 'w')
    #logFile.close()

    try:
        ser1 = serial.Serial(Serial1, baudrate=115200)
        print(f"Connected to {ser1.name}")
    except:
        print(f"Could not open {Serial1}")

    try:
        ser2 = serial.Serial(Serial2, baudrate=115200)
        print(f"Connected to {ser2.name}")
    except:
        print(f"Could not open {Serial2}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # prevents "address already in use""
        s.bind((HOST, PORT))
        s.listen()

        # waits for connection
        conn, addr = s.accept()
        print(f"Connected by {addr}")

        while True:

            if ser1 and ser1.isOpen():
                data1 = str(ser1.readline())
                
                logFileRaw.write(data1)
                logFileRaw.write("\n")

                data1 = data1.replace('\\n\'', '')  # chop off the \n', if its there
                data1 = data1.replace('\\r', '')    # chop off the \r', if its there

                if '@ GPS_STAT' in data1:
                    if GPS_ID not in data1: continue
                    if 'TRK' in data1: 
                        print(f"\nData1: {data1}")
                        send_data(pack_FW_GPS(data1), conn)

                if '@ RX_NOMTK' in data1:
                    if GPS_ID not in data1: continue
                    print(f"\nData1: {data1}")
                    send_data(pack_FW_TRK(data1), conn)

            if ser2 and ser2.isOpen():
                data2 = str(ser2.readline())

                logFileRaw.write(data2)
                logFileRaw.write("\n")

                data2 = data2.replace('\\n\'', '')  # chop off the \n', if it's there
                data2 = data2.replace('\\r', '')    # chop off the \r', if it's there

                if len(data2) < 7:
                    continue

                print(f"\nData2: {data2}")

                # there are three scenarios
                # Eggtimer only 
                # Raven only
                # Dual packet with data from both computers

                # eggtimer only
                if data2[6] == 'E': send_data(pack_EGG(data2), conn)

                # raven only OR dual packet
                if (data2[6] == 'R') and ("E:" in data2):
                    data2RXdata = data2[-10:]
                    # print(f"Tail: {data2RXdata}")
                    # print(f"BOTH: {data2}")
                    parts = data2.split("E:")
                    dataRav = parts[0]+data2RXdata
                    dataEgg = "E:"+parts[1]
                    # print(f"Rav data: {dataRav}")
                    # print(f"Egg data: {dataEgg}")
                    send_data(pack_RAV(dataRav), conn)
                    time.sleep(0.05)
                    send_data(pack_EGG(dataEgg), conn)
                elif (data2[6] == 'R'):
                    send_data(pack_RAV(data2), conn)
