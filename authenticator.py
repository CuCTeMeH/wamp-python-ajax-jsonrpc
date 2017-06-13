from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner, ApplicationSessionFactory
from autobahn import wamp
from autobahn.wamp.exception import ApplicationError
from twisted.internet.defer import inlineCallbacks
from twisted.python.failure import Failure
from http.cookies import SimpleCookie
import redis
import requests
import simplejson
import jwt
import time
import urllib


class PandaXAuthenticator(ApplicationSession):

    redis_jwt_key = 'jwt-python'

    @inlineCallbacks
    def onJoin(self, details):
        """
        Event on join where we register our wamp callbacks.

        :param details:
        :return:
        """
        results = []
        res = yield self.register(self)
        results.extend(res)

        for res in results:
            if isinstance(res, Failure):
                print("Failed to register procedure: {}".format(res.value))
            else:
                print("registration ID {}: {}".format(res.id, res.procedure))

    @wamp.register(u'call.rest.authenticate')
    def authenticate(self, realm, authid, details, recurse=True):
        """
        Authenticate method that sets ctbid cookie for further authentication not needed to ping the service each time a new request is made.
        
        :param realm: 
        :param authid: 
        :param details: 
        :param recurse: 
        :return: 
        """
        cookie = SimpleCookie()
        cookie.load(details.get('transport', {}).get('http_headers_received', {}).get('cookie', {}))

        # Even though SimpleCookie is dictionary-like, it internally uses a Morsel object
        # which is incompatible with requests. Manually construct a dictionary instead.
        cookies = {}
        r = redis.StrictRedis(host='localhost', port=6379, db=0)

        for key, morsel in cookie.items():
            if key == 'laravel_oauth_session':
                if r.exists(morsel.value):
                    morsel.value = r.get(morsel.value).decode("utf-8")
                else:
                    token = PandaXAuthenticator.get_auth_token()

                    headers = {
                        'content-type': 'application/json',
                        'Authorization': 'Bearer ' + token
                    }
                    payload = {
                        "cookie": urllib.parse.unquote(morsel.value)
                    }

                    response = requests.post('https://dev-auth.probidder.com/api/cookie/decrypt',
                                             data=simplejson.dumps(payload), headers=headers).json()

                    if response and 'error' in response:
                        if recurse is False:
                            raise ApplicationError(u'call.rest.error.authenticate',
                                                   'could not authenticate session')

                        r.delete(PandaXAuthenticator.redis_jwt_key)
                        return self.authenticate(realm=realm, authid=authid, details=details, recurse=False)

                    if response['status']:
                        r.set(morsel.value, response['cookie'])
                        morsel.value = response['cookie']

            cookies[key] = morsel.value

        user = self.is_logged_in(cookies)
        if user is False:
            raise ApplicationError(u'call.rest.error.authenticate.no_such_user',
                                   'could not authenticate session - no such user {}'.format(authid))

        if user['status'] and user['user']['username'] == authid:
            return {
                # these are required:
                'secret': str(user['user']['username']),  # the secret/password to be used
                'role': 'frontend'  # the auth role to be assigned when authentication succeeds
            }
        else:
            raise ApplicationError(u'call.rest.error.authenticate.no_such_user',
                                   'could not authenticate session - no such user {}'.format(authid))

    @staticmethod
    def get_auth_token():
        """
        Get the Auth token to be used for every request. Store the token until new one needs to be done.
        
        :return: 
        """
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        token = r.get(PandaXAuthenticator.redis_jwt_key)

        if token:
            return token.decode("utf-8")

        encoding_payload = {
            'aud': 'https://dev-auth.probidder.com',
            'exp': int(time.time() + 1000),
            'iat': int(time.time()),
            'sub': 'WS',
            'iss': 'ws'
        }

        pem_file = open("../../bearer/wamp_ws.key", 'r')
        key_string = pem_file.read()
        pem_file.close()

        encoded_key = jwt.encode(encoding_payload, algorithm='RS512', key=key_string)

        headers = {
            'content-type': 'application/json'
        }

        payload = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": encoded_key.decode("utf-8")
        }

        response = requests.post('https://dev-auth.probidder.com/api/oauth/token',
                                 data=simplejson.dumps(payload), headers=headers).json()

        if 'access_token' in response:
            r.set(PandaXAuthenticator.redis_jwt_key, response['access_token'])
            return response['access_token']

        raise ApplicationError(u'call.rest.error.no_access_token',
                               'No access token')

    @staticmethod
    def is_logged_in(cookies, recurse=True):
        """
        Check if user is logged in using the Auth REST service. Passing the user cookies and token.
        
        :param cookies: 
        :param recurse: 
        :return: 
        """
        token = PandaXAuthenticator.get_auth_token()

        print('COOKIES FOR REQUEST: ')
        print(cookies)
        print('COOKIES FOR REQUEST: ')

        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer ' + token
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
        }

        r = redis.StrictRedis(host='localhost', port=6379, db=0)

        try:
            response = requests.get('https://dev-auth.probidder.com/api/authenticate/check',
                                    data=simplejson.dumps(payload), headers=headers, cookies=cookies).json()
        except Exception as e:
            if recurse is False:
                return False
                # raise ApplicationError(u'call.rest.error.is_logged_in',
                #                        'could not authenticate session')

            r.delete(PandaXAuthenticator.redis_jwt_key)
            return PandaXAuthenticator.is_logged_in(cookies=cookies, recurse=False)

        if response and 'error' in response:
            if recurse is False:
                return False
                # raise ApplicationError(u'call.rest.error.is_logged_in',
                #                        'could not authenticate session')

            r.delete(PandaXAuthenticator.redis_jwt_key)
            return PandaXAuthenticator.is_logged_in(cookies=cookies, recurse=False)

        return response
