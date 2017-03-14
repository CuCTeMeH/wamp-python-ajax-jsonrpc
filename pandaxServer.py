import requests
import json
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner, ApplicationSessionFactory
from autobahn.wamp.types import RegisterOptions
from twisted.internet.defer import inlineCallbacks


class PandaX(ApplicationSession):
    def __init__(self, config=None):
        ApplicationSession.__init__(self, config)

    def onConnect(self):
        self.join(self.config.realm)

    @inlineCallbacks
    def onJoin(self, details):
        yield self.register(self.jsonrpc, u"jsonrpc.", options=RegisterOptions(match=u"prefix", details_arg="details"))

    def jsonrpc(self, url, method, params, publish=True, details=None):
        print(details)
        procedure = details.procedure
        headers = {'content-type': 'application/json'}
        payload = {
            "params": params,
            "jsonrpc": "2.0",
            "id": 0,
        }
        response = None

        if method == 'get':
            response = requests.get(url, data=json.dumps(payload), headers=headers).json()
        elif method == 'post':
            response = requests.post(url, data=json.dumps(payload), headers=headers).json()

        if publish:
            self.publish(procedure, response)

        return response
