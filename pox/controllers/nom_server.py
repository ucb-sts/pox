#!/usr/bin/env python
# Nom nom nom nom

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.lib.recoco import *
from pox.messenger.messenger import *

import sys
import signal
import socket

name = "nom_server"
log = core.getLogger(name)

class NomServer (EventMixin):
  """
  The Nom "database". Keeps a copy of the Nom in memory, as well as a list
  of all registered clients. When a client calls NomServer.put(),
  invalidates + updates the caches of all registered clients

  Visually,  NomClient's connect to the NomServer through
  the following interfaces:

  ==========================                            ==========================
  |    NomClient           |                            |    NomServer           |
  |                        |   any mutating operation   |                        |
  |                        |  -------------------->     |server.put(nom)         |
  |                        |                            |                        |
  |          client.       |                            |                        |
  |            update_nom()|    cache invalidation      |                        |
  |                        |   <-------------------     |                        |
  ==========================                            ==========================
  """
  
  # The set of components we depend on. These must be loaded before we can begin.
  _wantComponents = set(['topology'])
  
  def __init__(self):
    # Pre: core.messenger is registered
    # Wait for connections
    core.messenger.addListener(MessageReceived, self._handle_global_MessageReceived, weak=True)
    
    # client name -> TCPMessageConnection
    self.registered = {}
    
    # TODO: the following code is highly redundant with controller.rb
    self.topology = None
    if not core.listenToDependencies(self, self._wantComponents):
      # If dependencies aren't loaded, register event handlers for ComponentRegistered
      self.listenTo(core)
    else:
      self._finish_initialization() 
  
  def _handle_global_MessageReceived (self, event, msg):
    try:
      if 'nom_server_handshake' in msg:
        # It's for me! Store the connection object. Their name is the value
        event.con.read() # Consume the message
        event.claim()
        event.con.addListener(MessageReceived, self._handle_MessageReceived, weak=True)
        self.register_client(msg['nom_server_handshake'], event.con)
        log.debug("- started conversation with %s" % str(msg['nom_server_handshake']))
      else:
        log.debug("- ignoring")
    except:
      pass
    
  def _handle_MessageReceived (self, event, msg):
    if event.con.isReadable():
      r = event.con.read()
      log.debug("-%s" % str(r))
      if type(r) is not dict:
        log.warn("message was not a dict!")
        return
      
      if r.get("bye",False):
        log.debug("- goodbye!")
        event.con.close()
      if "get" in r:
        self.get(event.con)
      if "put" in r:
        self.put(r["put"]) 
    else:
      log.debug("- conversation finished")
  
  def _handle_ComponentRegistered (self, event):
    """ Checks whether the newly registered component is one of our dependencies """
    if core.listenToDependencies(self, self._wantComponents):
        self._finish_initialization() 

  def _finish_initialization(self):
    self.topology = core.components['topology'] 
      
  def register_client(self, client_name, connection):
    log.info("register %s" % client_name)
    self.registered[client_name] = connection

  def unregister_client(self, client):
    pass

  def get(self, conn):
    log.info("get")
    conn.send({"nom_update":self.topology})

  def put(self, val):
    log.info("put %s" % val)
    self.topology = val
    for client_name in self.registered.keys():
      log.info("invalidating/updating %s" % client_name)
      connection = self.registered[client_name]
      connection.send({"nom_update":self.topology})
      
          
def launch():
  import pox.messenger.messenger as messenger
  # TODO: don't assume localhost:7790 for emulation
  messenger.launch()
  from pox.core import core
  core.registerNew(NomServer)
  
  