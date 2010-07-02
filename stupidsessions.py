from flask import Flask, Session
from html5lib import HTMLParser, serialize
from html5lib.treebuilders.simpletree import Element
from werkzeug import url_quote_plus


_parser = HTMLParser()


class StupidSessionMixin(object):
    session_url_key = 'FLASKSESSION'
    session_url_rewrite_map = {
        'a':        ['href'],
        'img':      ['src'],
        'script':   ['src'],
        'link':     ['href']
    }

    def open_session(self, request):
        key = self.secret_key
        if key is not None:
            value = request.values.get(self.session_url_key, '')
            return Session.unserialize(value, key)

    def save_session(self, session, response):
        # we only support html
        if response.mimetype == 'text/html':
            response.data = self._inject_session(session, response.data)
        # handle redirects
        if 'location' in response.headers:
            response.headers['Location'] = self._rewrite_session_url(
                response.headers['location'], session.serialize())

    def _rewrite_session_url(self, url, sess):
        return '%s%s%s=%s' % (
            url,
            '?' in url and '&' or '?',
            self.session_url_key,
            url_quote_plus(sess)
        )

    def _inject_session(self, session, html):
        serialized = session.serialize()
        def _walk(node):
            for child in node.childNodes:
                _walk(child)
            if node.name in self.session_url_rewrite_map:
                for attr in self.session_url_rewrite_map[node.name]:
                    value = node.attributes.get(attr)
                    if value is None:
                        continue
                    new_value = self._rewrite_session_url(value, serialized)
                    node.attributes[attr] = new_value
            elif node.name == 'form':
                hidden = Element('input')
                hidden.attributes.update(
                    type='hidden',
                    name=self.session_url_key,
                    value=serialized
                )
                node.childNodes.append(hidden)
        tree = _parser.parse(html)
        _walk(tree)
        return serialize(tree)


class StupidSessionFlask(StupidSessionMixin, Flask):
    pass


def testapp():
    from flask import request, session, g, escape, redirect, url_for

    app = StupidSessionFlask(__name__)
    app.secret_key = 'testing'

    @app.before_request
    def pull_user():
        g.user = session.get('username')

    @app.route('/')
    def index():
        if g.user is not None:
            return '''
            <p>You are logged in as %s.
            <p><a href=/logout>Logout</a>
            ''' % escape(g.user)
        return 'You are not logged in. <a href=/login>Login</a>'

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            if username:
                session['username'] = username
                return redirect(url_for('index'))
        return '''
        <form action="" method=post>
            <p>Username:
            <input type=text name=username>
            <input type=submit value=Login>
        </form>
        '''

    @app.route('/logout')
    def logout():
        session['username'] = None
        return redirect(url_for('index'))

    return app


if __name__ == '__main__':
    app = testapp()
    app.run(debug=True)
