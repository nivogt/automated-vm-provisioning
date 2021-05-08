#!/usr/bin/env python

"""main.py: Listen to a rabbitmq queue and build a new vsphere vm given the received params"""

__author__      = "Nicolas VOGT"
__email__       = "nicolas.vogt@monext.net"
__copyright__   = "Copyright 2021, MONEXT" 

# generic
import argparse
import sys
import os
import json
import random
import string
import logging
import time

# rabbitmq specific
import pika
import signal

# packer specific
import packer

# vault specific
# import hvac

# Packer config vars
packerfile = 'packer/packerfile.json'
exc = []
packer_exec_path = '/usr/local/packer'

# set default variables
default = {
  "vsphere-datacenter": "DC1",
  "vsphere-cluster": "DEV_INT_R7/cluster1-6-archi",
  "vsphere-host": "esx1cl1-6-archi.dc1lan.local",
  "vsphere-datastore": "EMC_ESXCL1-6-ARCHI_DATASTORE_1",
  "vm-name": "CentOS8-Template",
  "folder": "ARCHI/PACKER",
  "vm-cpu-num": "1",
  "vm-mem-size": "1024",
  "vm-disk-size": "10240",
  "vm-network": "LAN DEV 97",
  "guest-os-type": "centos7_64Guest",
  "iso_url": "[EMC_ESXCL1-6-ARCHI_DATASTORE_1] isos/CentOS-8.3.2011-x86_64-minimal.iso",
  "server_ip" : "172.22.97.100",
  "server_gw" : "172.22.97.1",
  "server_mask" : "255.255.255.0",
  "dns_1" : "172.22.11.10",
  "dns_2" : "172.29.10.20"
}


#
# MAIN
#
if __name__ == '__main__':

  # define logger
  log = logging.getLogger()
  log.setLevel(logging.INFO)
  ch = logging.StreamHandler(sys.stdout)
  ch.setLevel(logging.INFO)
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')  
  ch.setFormatter(formatter)  
  log.addHandler(ch)  
  log.info('Logger configured')

  # update credentials
  params = dict()
  params.update({
    "vsphere-server" : os.environ['VSPHERE_SERVER'],
    "vsphere-user" : os.environ['VSPHERE_USER'],
    "vsphere-password" : os.environ['VSPHERE_PASSWORD']
  })
  
  # connect to RabbitMQ 
  log.info('Connect to RabbitMQ')
  try :
    credentials = pika.PlainCredentials(os.environ['QUEUE_USER'], os.environ['QUEUE_PASS'] )
    connection = pika.BlockingConnection(pika.ConnectionParameters(os.environ['QUEUE_SERVER'], os.environ['QUEUE_PORT'], '/', credentials ))
    channel = connection.channel()

  except Exception as e :
      log.error('Cannot copen connection to RabbitMQ : {}'.format(str(e)))
      sys.exit(-1)
  
  message_count = 0
  log.info('Start consuming {}'.format(os.environ['QUEUE_IN']))
  
  while True:
    
    method_frame, header_frame, body = channel.basic_get(os.environ['QUEUE_IN'])

    if not method_frame :
        log.info("listening to queue")
        time.sleep(15)
        continue
    
    else :

      # acknowledge the message
      log.info("new message received")
      channel.basic_ack(method_frame.delivery_tag)
      log.info(" -> message acknowledged")

      # load message
      message = json.loads(body.decode('UTF-8'))["message"]
      log.info("Message content : {}".format(json.dumps(message)))

      # override default parameters with provided values
      for key in [ "vsphere-datacenter", "vsphere-cluster",  "vsphere-host", "vsphere-datastore", "vm-name", "folder", "vm-cpu-num", "vm-mem-size", "vm-disk-size",  "guest-os-type", "vm-network", "iso_url" , "server_ip", "server_gw", "server_mask", "dns_1", "dns_2" ] :
        if key in message.keys() : 
          params[key] = message[key]
        else :
          params[key] = default[key]
      
      # generate a random password
      params["random-password"] = ''.join(random.choice(string.ascii_lowercase) for i in range(25))

      log.info("Preparing image")
      p = packer.Packer(packerfile, vars=params, exc=exc, exec_path=packer_exec_path)
      
      log.info("Building image")

      p.build(
          parallel=False, 
          debug=True, 
          force=False, 
          machine_readable=True
      )
      
      # reconnect to rabbitmq (the above traitement is way too long)
      try :
        connection = pika.BlockingConnection(pika.ConnectionParameters(os.environ['QUEUE_SERVER'], os.environ['QUEUE_PORT'], '/', credentials ))
        channel = connection.channel()

      except Exception as e :
          log.error('Cannot copen connection to RabbitMQ : {}'.format(str(e)))
          sys.exit(-1)
      
      channel.basic_publish(exchange='', routing_key=os.environ['QUEUE_OUT'], body=json.dumps(message))

  # Close the channel and the connection
  log.info("Closing properly")
  channel.close()
  connection.close()
