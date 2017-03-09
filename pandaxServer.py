from os import environ
import six
import requests
import json
# import Cookie

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

        # This is called during the initial WebSocket opening handshake.


    @inlineCallbacks
    def onChallenge(self, challenge):
        print("authentication challenge received")

    @inlineCallbacks
    def onJoin(self, details):
        print("session joined")
        print(details)

        results = []
        res = yield self.register(self)
        results.extend(res)

        for res in results:
            if isinstance(res, Failure):
                print("Failed to register procedure: {}".format(res.value))
            else:
                print("registration ID {}: {}".format(res.id, res.procedure))

    # @inlineCallbacks
    def onLeave(self, details):
        print("session left")

    # @inlineCallbacks
    def onDisconnect(self):
        print("transport disconnected")

    @wamp.register(u'call.rest.jsonrpc')
    def jsonrpc(self, url, method, params):
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

        self.publish(u'call.rest.jsonrpc', response)
        return response


if __name__ == '__main__':
    cert = crypto.load_certificate(
        crypto.FILETYPE_PEM,
        six.u(open('./probidder_fullchain.pem', 'r').read())
    )

    # tell Twisted to use just the one certificate we loaded to verify connections
    options = CertificateOptions(
        trustRoot=OpenSSLCertificateAuthorities([cert]),
    )

    runner = ApplicationRunner(
        environ.get("AUTOBAHN_DEMO_ROUTER", u"ws://127.0.0.1:8080/ws"),
        realm='realm1',
        # ssl=options,  # try removing this, but still use self-signed cert
    )

    runner.run(PandaX)
