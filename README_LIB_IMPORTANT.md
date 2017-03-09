They need to fix it. I found the issue. They updated the cookiestore but not updated the protocol that uses it.

Basically in the cookiestore the cookie contains one extra param called 'authextra' here from their code:

        # when a cookie has been set, and the WAMP session
        # was successfully authenticated thereafter, the latter
        # auth info is store here
        'authid': None,
        'authrole': None,
        'authrealm': None,
        'authmethod': None,
        'authextra': None,
But the protocol.py on the def onConnect method (row 240 in version 17.2.1 latest for now) that gets the auth from cookiestore gets only 4, so the unpack function throws an error. The basic fix I can do is this:

    self._authid, self._authrole, self._authmethod, self._authrealm = self.factory._cookiestore.getAuth(self._cbtid)

This should look like this:

    self._authid, self._authrole, self._authmethod, self._authrealm, self._extra = self.factory._cookiestore.getAuth(self._cbtid)

This is a really quick workaround because below the code somewhere must use this extra parameter if you need to pass some extra stuff (this is optional however but...). If you dont need to pass some extra stuff this quick fix will do the job for you :)

file: crossbar/router/protocol.py row 240 onConnect method
https://github.com/crossbario/crossbar/issues/952

edit the lib on live if they didnt fix it already.