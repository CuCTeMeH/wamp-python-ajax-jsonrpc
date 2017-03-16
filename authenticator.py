from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner, ApplicationSessionFactory
from autobahn import wamp
from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure
import requests
import json


class PandaXAuthenticator(ApplicationSession):
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

    @wamp.register(u'call.rest.authenticate')
    def authenticate(self, realm, authid, details):
        print("WAMP-CRA dynamic authenticator invoked: realm='{}', authid='{}'".format(realm, authid))
        # print(details)
        #
        cookies = details.get('transport', {}).get('http_headers_received', {}).get('cookie', {})
        response = self.get_auth_token()



        # pass the cookies to the auth server so that we can check if the user is authenticated. Then return the correct fucking thing and then be done with the auth shit thingy.


        # print(self)
        # check database for user session or make a rest call to the auth api with the request cookie so that we can be sure the user is logged in.
        # if(authid == 'joe'):
        return {
            # these are required:
            'secret': 'probid',  # the secret/password to be used
            'role': 'frontend'    # the auth role to be assigned when authentication succeeds
        }
        # else:
            # raise ApplicationError(u'call.rest.authenticate.no_such_user',
            #                        'could not authenticate session - no such user {}'.format(authid))
        # if authid in USERDB:
        # return a dictionary with authentication information ...
        #     return USERDB[authid]
        # else:
        #     raise ApplicationError(u'com.example.no_such_user', 'could not authenticate session - no such user {}'.format(authid))

    @staticmethod
    def get_auth_token():
        # headers = {'content-type': 'application/json'}
        # payload = {
        #     "jsonrpc": "2.0",
        #     "id": 0,
        # }
        #
        # response = requests.get('', data=json.dumps(payload), headers=headers, cookies=cookies).json()

        return 123123
