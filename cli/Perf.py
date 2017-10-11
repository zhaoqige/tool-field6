#!/usr/bin/python3
"""
Re-write "perf_win.pl" to "Perf.py"
by Qige <qigezhao@gmail.com>, 2017.10.10-2017.10.11
"""

import re
import os
import sys
import time

import paramiko


# pre define
KPI_CACHE       = '/tmp/.perf.wls'
KPI_IFNAME      = 'wlan0'
THRPT_CACHE     = '/tmp/.perf.thrpt'
THRPT_IFNAME    = 'eth0'

# WMAC, SSID, BSSID, Signal, Noise, Bitrate
CMD_KPI_FMT = 'ifconfig %s | grep %s -A0 | awk \'{print $5}\'; ' + \
'iwinfo %s i | tr -s "\n" "|" > %s; ' + \
'cat %s | cut -d "|" -f 1 | awk \'{print $3}\'; ' + \
'cat %s | cut -d "|" -f 2 | awk \'{print $3}\'; ' + \
'cat %s | cut -d "|" -f 5 | awk \'{print $2}\'; ' + \
'cat %s | cut -d "|" -f 5 | awk \'{print $4}\'; ' + \
'cat %s | cut -d "|" -f 5 | awk \'{print $5}\'; ' + \
'cat %s | cut -d "|" -f 6 | awk \'{print $3}\'; '
CMD_KPI = CMD_KPI_FMT % (KPI_IFNAME, KPI_IFNAME, KPI_IFNAME, KPI_CACHE, 
                         KPI_CACHE, KPI_CACHE, KPI_CACHE, KPI_CACHE, KPI_CACHE, KPI_CACHE)

CMD_THRPT_FMT = "cat /proc/net/dev | grep %s | awk '{print $2,$10}'\n"
CMD_THRPT = CMD_THRPT_FMT % (THRPT_IFNAME)


# file read/write/close
def fileRead(conffile):
    try:
        fd = open(conffile, 'r')
        if fd:
            data = fd.readline()
            return data
        
        fd.close()
    
    except:
        return None

# application
def appVersion():
    print('ARNPerf v7.0 (https://github.com/zhaoqige/arnperf.git')
    print('---- by Qige <qigezhao@gmail.com> v7.0.101017-py ----')
    print('-----------------------------------------------------')

def appHelp():
    print('Usage: Perf.py [hostip] [logfile] [note] [locations]')


# priority: user cli assigned 
def appConfigLoad(host, logfile, note, location):
    print('-> loading config file ...')
    #return '192.168.1.24','d24fast.log','demo','BJOffice'
    noneArray = [None, None, None, None, None, None, None]
    rHost, rPort, rUser, rPasswd, rLogfile, rNote, rLocation = noneArray
    conf = fileRead('ARNPerf.conf')
    if (not conf is None):
        confList = conf.split(',')
        rHost, rPort, rUser, rPasswd = confList[0:4]
        rLogfile, rNote, rLocation = confList[4:7] # 0-6, but 7th not included
    
    # replace and decide right params
    if (not host is None):
        rHost = host
        
    if (not logfile is None):
        rLogfile = logfile
        
    if (not note is None):
        rNote = note
        
    if (not location is None):
        rLocation = location
        
    if (rHost is None):
        rHost = '192.168.1.24'
        rPort = 22
        rUser = 'root'
        rPasswd = 'root'
        rLogfile = 'd24fast.log'
        rNote = 'demo'
        rLocation = 'BJDev'
        
    return [rHost, rPort, rUser, rPasswd, rLogfile, rNote, rLocation]

def cliParams():
    print('-> reading user input ...')
    if len(sys.argv) >= 4:
        return sys.argv[1:5] # 1-4, but 5th not included
    
    return [None, None, None, None]


# Secure SHell
def SSHConnect(host, user, passwd, port):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, port, user, passwd)
        
    except:
        ssh.close()
        ssh = None
        print('error> failed to connect', host, 
                '(please check your input: ip, port, user, password)')
        
    return ssh

def SSHExec(ssh, cmd):
    # FIXME: if error?
    reply = None
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        reply = stdout.readlines()
        
    except:
        stdout = None
    
    return reply

def SSHClose(ssh):
    ssh.close()


def thrptFormat(val):
    return int(val) * 8

def thrptUnitMbps(bits):
    return "%.3f" % (bits / 1024 / 1024)

def thrptUnit(bits):
    if (bits > 1024 * 1024):
        return "%.3f Mbps" % (bits / 1024 / 1024)
    
    if (bits > 1024):
        return "%.3f Kbps" % (bits / 1024)
    
    if (bits < 1024):
        return "%.3f bps" % (bits)

# query & parse result
def ARNPerfQuery(ssh):
    kpi = None
    #print(CMD_THRPT)
    rxtxBytesReply = SSHExec(ssh, CMD_THRPT)
    rxtxBytes = re.split(r'[,\s\n\r\\\n\\\r]', rxtxBytesReply[0] \
                        if (not rxtxBytesReply is None) and len(rxtxBytesReply) >= 1 \
                        else '0,0')
    
    if len(rxtxBytes) >= 2:
        kpi = rxtxBytes[0:2]
    else:
        kpi = [0, 0]

    # re-check        
    if (kpi is None):
        kpi = [0, 0]
    
    #print(CMD_KPI)
    wlsRaw = ["00:00:00:00:00:00", "00:00:00:00:00:00", '-', 0, 0, 0]
    wlsRawReply = SSHExec(ssh, CMD_KPI)
    if (not wlsRawReply is None) and len(wlsRawReply) >= 1:
        del wlsRaw[:]
        for val in wlsRawReply:
            wlsRaw.extend([str(val).strip()])
    
    if len(wlsRaw) >= 7:
        kpi.extend(wlsRaw[0:7])
    
    return kpi


def ARNPerfFormat(perfRaw, gpsCrt, msTsLast, thrptLast):
    msTsNow = time.time()
    msElapsed = round(abs(msTsNow - msTsLast), 3)
    print(" ->", msElapsed, 'second(s) passed')
    
    if (not perfRaw is None) and len(perfRaw) >= 9:
        wmac, ssid, bssid, signal, noise1, noise2, br = perfRaw[2:9]
        
        if (signal != 'unknown'):
            intNoise = int(noise2)
            intSignal = int(signal)
        else:
            intNoise = int(noise1)
            intSignal = intNoise

        snr = intSignal - intNoise
        
        # default 20MHz, not 8MHz
        br8m = 0.00
        if (br != 'unknown'):
            br8m = float(br)/20*8
    
    if (not perfRaw is None) and len(perfRaw) >= 2:
        rxBytes, txBytes = perfRaw[0:2]
        intThrptLastRx = int(thrptLast[0])
        intThrptLastTx = int(thrptLast[1])
        if (intThrptLastRx + intThrptLastTx > 0):
            rxThrpt = (int(rxBytes) - int(thrptLast[0])) / msElapsed
            txThrpt = (int(txBytes) - int(thrptLast[1])) / msElapsed
        else:
            rxThrpt = 0
            txThrpt = 0
        
        fmtRxThrpt = thrptFormat(rxThrpt)
        fmtTxThrpt = thrptFormat(txThrpt)

    data = gpsCrt
    data.extend([fmtRxThrpt, fmtTxThrpt])
    data.extend([wmac, ssid, bssid, intSignal, intNoise, snr, br8m])
    return data

# display KPI
def ARNPerfPrint(arnData):
    if (not arnData is None) and len(arnData) >= 13:
        gpsLat, gpsLng, gpsSpeed, gpsHdg = arnData[0:4]
        rxThrpt, txThrpt = arnData[4:6]
        wmac, ssid, bssid, signal, noise, snr, br = arnData[6:13]
        
        # clear screen
        os.system("cls");
        print()
        print("                     ARNPerf CLI")
        print("        https://github.com/zhaoqige/arnperf.git")
        print(" -------- -------- -------- -------- -------- --------")        
        print("             MAC:", wmac if (wmac != '') else '00:00:00:00:00:00')
        print("            SSID:", ssid.strip('"') if (ssid != '') else '-')
        print("           BSSID:", bssid if (bssid != '') else '00:00:00:00:00:00')
        print("    Signal/Noise: %d/%d dBm, SNR = %d" % (signal, noise, snr))
        print("         Bitrate: %.3f Mbit/s" % (br));
        print()
        print("      Throughput: Rx = %s, Tx = %s" % (thrptUnit(rxThrpt), thrptUnit(txThrpt)))
        print()
        print(' -> GCJ-02: %.8f,%.8f, speed %.3f km/h, hdg %.1f' \
              % (float(gpsLat), float(gpsLng), float(gpsSpeed), float(gpsHdg)))


def ARNPerfLogEnvSave(confHost, confLogfile, confNote, confLocation):
    try:
        line = "+6w,config,%s,%s,%s\n" % (confHost, confNote, confLocation)
        fd = open(confLogfile, 'w')
        fd.write(line)
        fd.flush()
        
        print('-> save {LogEnv} to', confLogfile, ' <', confHost, confNote, confLocation)
        fd.close
        
    except:
        print('error> failed to save {LogEnv}')
    
def ARNPerfLogSave(logfile, arnData):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(' ====> log saved at', ts, '-', logfile)
    try:
        if (not arnData is None) and len(arnData) >= 13:
            gpsLat, gpsLng, gpsSpeed, gpsHdg = arnData[0:4]
            rxThrpt, txThrpt = arnData[4:6]
            wmac, ssid, bssid, signal, noise, snr, br = arnData[6:13]
            
            fd = open(logfile, 'a')
            if fd:
                # +6w,ts,wmac,lat,lng,signal,noise,rxthrpt,rxmcs,txthrpt,txmcs,speed,hdg
                record = "+6w,%s,%s,%.8f,%.8f,%d,%d,%s,%s,%s,%s,%.3f,%.1f\n" \
                            % (ts, wmac, float(gpsLat), float(gpsLng), int(signal), int(noise), \
                               thrptUnitMbps(rxThrpt), 'MCS -1', thrptUnitMbps(txThrpt), 'MCS -1', \
                               float(gpsSpeed), float(gpsHdg))
                fd.write(record)
                fd.flush()
            
            fd.close()
    except:
        print('error> save log failed at', ts, '-', logfile)


# read from exchange file
def GPSLocationRtRaw():
    gpsRaw = None
    gpsFile = 'gps.txt';
    
    fd = open(gpsFile, 'r')
    if (fd):
        gpsRawStr = fd.read(64)
        gpsRaw = str(gpsRawStr).split(',')
    
    fd.close()
    return gpsRaw

# return & validate GPS lat,lng
def GPSLocationRt():
    gpsRaw = GPSLocationRtRaw()
    if len(gpsRaw) >= 5:
        gpsValid = gpsRaw[0]
        if (gpsValid == 'A'):
            return gpsRaw[1:5]
        
    return [0,0,0,0]

# GPS fence
def GPSFenceBreach(pos1, pos2):
    #gpsFenceDistance = 0.0002 # about 10 meters
    gpsFenceDistance = 0.0001 # about 5 meters
    #gpsFenceDistance = 0.000001 # about 10 meters
    if (pos1 and pos2):
        p1lat = float(pos1[0])
        p1lng = float(pos1[1])
        p2lat = float(pos2[0])
        p2lng = float(pos2[1])
        
        gapLat = abs(p1lat - p2lat)
        gapLng = abs(p1lng - p2lng)
        if (gapLat + gapLng > gpsFenceDistance):
            return 1
        
    return 0


"""
Tasks:
    1. Query GPS;
    2. Setup GPS Fence;
        2.1. Query Device Performance;
        2.2. Parse into ARNPerf7 format;
        2.3. Save to log.
"""
def ARNPerfRecord(ssh, configPerfArray):
    msTsLast = time.time()
    thrptLast = [0, 0]
    gpsLast = [0, 0]

    if len(configPerfArray) >= 4:
        confHost, confLogfile, confNote, confLocation = configPerfArray[0:4]
    else:
        confHost        = '192.168.1.24'
        confLogfile     = 'default.log'
        confNote        = 'demo'
        confLocation    = 'BJDevQZ'
    
    # save environment
    ARNPerfLogEnvSave(confHost, confLogfile, confNote, confLocation)
    
    # query device performance, setup GPS fence
    while 1:
        perfRaw = ARNPerfQuery(ssh)
        gpsCrt = GPSLocationRt()
        arnData = ARNPerfFormat(perfRaw, gpsCrt, msTsLast, thrptLast)
        ARNPerfPrint(arnData)
        msTsLast = time.time()

        if (GPSFenceBreach(gpsCrt, gpsLast) > 0):
            ARNPerfLogSave(confLogfile, arnData)
        
        # save for next time
        gpsLast = gpsCrt
        if (not perfRaw is None) and len(perfRaw) >= 2:
            thrptLast = perfRaw[0:2]
        
        time.sleep(1)
    

"""
ARNPerf (GPS Fence triggered)
------------------
Usage: "Perf.py [hostip] [logfile] [note] [locations]"
------------------
by Qige <qigezhao@gmail.com>
2017.10.10-2017.10.11
"""
def ARNPerfRecorder():
    appVersion()
    
    print('> reading config (user input, config file) ...')
    host, logfile, note, location = cliParams()
    configArray = appConfigLoad(host, logfile, note, location)
    if len(configArray) >= 4:
        confHost, confPort, confUser, confPasswd = configArray[0:4]
        
    configPerfArray = None
    if len(configArray) >= 7:
        configPerfArray = [confHost]
        configPerfArray.extend(configArray[4:7])
    
    #confHost = '192.168.1.24' # DEBUG USE ONLY!
    connParam = '%s:%s@%s:%s' % (confUser, confPasswd, confHost, confPort)
    print('> init connection', connParam, '...')
    ssh = SSHConnect(confHost, 'root', 'root', 22)
    if (not ssh is None):
        ARNPerfRecord(ssh, configPerfArray)
        SSHClose(ssh)
    else:
        print('error> Device %s unreachable!'% (host))
        appHelp()


# start ARN Performance Recorder
ARNPerfRecorder()
