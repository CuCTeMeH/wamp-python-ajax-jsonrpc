from __future__ import print_function

from os import environ
import six
import requests
import json

from autobahn.twisted.util import sleep
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner, ApplicationSessionFactory
from autobahn import wamp

from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure
from twisted.internet._sslverify import OpenSSLCertificateAuthorities
from twisted.internet.ssl import CertificateOptions
from OpenSSL import crypto

class PandaX(ApplicationSession):
    def __init__(self, config=None):
        ApplicationSession.__init__(self, config)
        print("component created")

    def onConnect(self):
        print("transport connected")
        print(self.config.realm)
        self.join(self.config.realm)

    @inlineCallbacks
    def onChallenge(self, challenge):
        print("authentication challenge received")

    @inlineCallbacks
    def onJoin(self, details):
        print("session joined")
        print(details)

        def rest():
            return x + y

        def jsonrpc(url, method, params):
            print('url: ' + url)
            print('method: ' + method)
            print(params)

            headers = {'content-type': 'application/json'}

            # Example echo method
            payload = {
                "params": params,
                "jsonrpc": "2.0",
                "id": 0,
            }

            response = None

            if method == 'get':
                response = requests.get(
                    url, data=json.dumps(payload), headers=headers).json()
            elif method == 'post':
                response = requests.post(
                    url, data=json.dumps(payload), headers=headers).json()

            print('publishing to jsonrpc')
            self.publish(u'call.rest.jsonrpc', response)

        yield self.register(jsonrpc, u'call.rest.jsonrpc')
        yield self.register(rest, u'call.rest')

    @inlineCallbacks
    def onLeave(self, details):
        print("session left")

    @inlineCallbacks
    def onDisconnect(self):
        print("transport disconnected")


if __name__ == '__main__':
    runner = ApplicationRunner(
        environ.get("AUTOBAHN_DEMO_ROUTER", u"ws://127.0.0.1:8080/ws"),
        realm='crossbardemo'
    )

    runner.run(PandaX)
