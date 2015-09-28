#!/usr/bin/env python
 
import os
import sys
import time
import datetime
import requests
import urllib2
import json
import RPi.GPIO as GPIO
import rfmon_xively

from nrf24 import NRF24

# REMEMBER: OneWire is ALWAYS on Pin #4

# extract feed_id and api_key from environment variables
#FEED_ID = os.environ["FEED_ID"] or "1785749146"
#API_KEY = os.environ["API_KEY"] or "IjPjyGRBNX4215uvu7sAB86NBjCtklQByFAIb1VoJT2TUeXF"
#DEBUG = os.environ["DEBUG"] or true

##  RF Read Code
pipes = [[0xF0, 0xF0, 0xF0, 0xF0, 0xE1], [0xF0, 0xF0, 0xF0, 0xF0, 0xD1]]
CE_PIN_       = 18
IRQ_PIN_      = 23
RF_CHANNEL    = 76
PAYLOAD_SIZE  = 21

FEED_ID = "1785749146"
API_KEY = "IjPjyGRBNX4215uvu7sAB86NBjCtklQByFAIb1VoJT2TUeXF"
DEBUG = False
 
sensors = {}
sensors["C1"] = [ 600, ["RF1_Temp1", "Nathan"],  ["RF1_Temp2DHT", "Nathan2"], ["RF1_Humidity", "Humidity"] ]
sensors["C2"] = [ 600, ["RF2_Temp1", "Kitchen"], ["RF2_Temp2", "Aquarium"],   ["unused", "unused"] ]
sensors["D1"] = [ 600, ["GH_Temp", "GH Temperature"], ["GH_Humidity", "GH Humidity"], ["GH_Light", "GH Light"] ]

SLEEP_SECONDS = 1 

radio = NRF24()

def init_GPIO():
  GPIO.setmode(GPIO.BCM)

def initRadioReceive():
    radio.begin(0, 0, CE_PIN_, IRQ_PIN_)

    #radio.setDataRate(NRF24.BR_1MBPS)
    radio.setDataRate(NRF24.BR_250KBPS)
    radio.setPALevel(NRF24.PA_MAX)
    radio.setChannel(RF_CHANNEL)
    radio.setRetries(15,15)
    radio.setAutoAck(0)
    radio.setPayloadSize(PAYLOAD_SIZE)
    ##radio.enableDynamicPayloads()

    radio.openWritingPipe(pipes[0])
    radio.openReadingPipe(1, pipes[1])

    radio.startListening()
    radio.stopListening()
    radio.printDetails()
    print "-"*40

    radio.startListening()


def updateEMon(inTemp, outTemp):

    EMonAPIKey = '7c51f29723f0bdd78c15bd5fada20ac8'
    emonURL = 'http://emoncms.org/input/post.json?node=10&apikey=%s&json={IndoorTemp:%3.1f,OutdoorTemp:%3.1f}' % EMonAPIKey, inTemp, outTemp
    f = urllib2.urlopen(emonURL)
    json_string = f.read()
    print json_string


def parsePayload( recvBufferIn ):
    recv_string = ""
    for x in recvBufferIn:
        recv_string += chr(x)

    string_parts = recv_string.split(",")
    numtemps = len(string_parts) - 2
    ##print "[ParsePayload] Number of Temps found: [%d]" % numtemps

    node_   = string_parts[0]
    seq_ = string_parts[1] 
    
    temparray = []
    for x in range(2,numtemps+2):
        _temp = float(string_parts[x])/10
        temparray.append( _temp )

    return node_, seq_, temparray


# main program entry point - runs continuously updating our datastream with the
def run():

  init_GPIO()
  initRadioReceive()

  lastXivelyTime = {}

  while True:
    pipe = [1]
    while( radio.available(pipe, False) ):
        recv_buffer = []
        myDateTime = datetime.datetime.utcnow() 

        radio.read(recv_buffer)
        nodeID, seq, tempList = parsePayload( recv_buffer )
        numTemps = len(tempList)

        ##print "num temps=[%d]" % numTemps
        print "[", nodeID, "] ", seq, " - ", myDateTime, ":  ", tempList

        if( nodeID not in sensors ):
            print "No match found for Node {0}".format(nodeID)
            continue

        if( not nodeID in lastXivelyTime or (time.time() - lastXivelyTime[nodeID]) >= sensors[nodeID][0] ):
            for x in range(numTemps):
                if( tempList[x] < 900 ):
                    try:
                        rfmon_xively.xively_update( sensors[nodeID][x+1][0], sensors[nodeID][x+1][1], tempList[x], myDateTime ) 
                        lastXivelyTime[nodeID] = time.time()
                    except( requests.exceptions.ConnectionError, requests.HTTPError, urllib2.URLError) as e:
                      print "Error updating Xively with RF Data!!({0}): {1}".format(e.errno, e.strerror)

        # Update temp to EMon
        #updateEMon(deg_f, temp_f)

    radio.startListening()

    sys.stdout.flush()
    time.sleep(SLEEP_SECONDS)
 
try:
    run()
except KeyboardInterrupt:
    print "Keyboard Interrupt..."
finally:
    print "Exiting."
    GPIO.cleanup()

