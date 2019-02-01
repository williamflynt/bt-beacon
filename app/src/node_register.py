import os
import sys

import requests
from bottle import route, run, template, request
from requests.exceptions import SSLError

try:
    from utility import get_pn_uuid
except ImportError:
    from app.src.utility import get_pn_uuid

INTERNAL_POST = "/getkeys"
NODE_ID = get_pn_uuid()
# POST_TO = "https://localhost:8000/nodes/register/{}".format(NODE_ID)
POST_TO = "https://demo.starlingiot.com/nodes/register/{}".format(NODE_ID)
FILE_DIR = os.path.dirname(os.path.abspath(__file__))


@route('/')
def index():
    return template(
        """
        <html>
        <head><title>Node Registration</title></head>
        <body>
        <div style="width: 400px;">
        
            <h1>Node Registration</h1>
            <hr/>
            
            <form action="{post_to}" method="post">
              <fieldset>
              <legend>Login Information: </legend>
              <input type="text" name="username" placeholder="Username" />
              <br />
              <input type="password" name="passwd" placeholder="Password" />
              <br/>
              <input type="submit" name="submit" value="Register Node" />
              </fieldset>
            </form>
        
        </div>
        
        </body>
        </html>
        """.format(post_to=INTERNAL_POST)
    )


@route(INTERNAL_POST, method="POST")
def getkeys():
    username = request.forms.get('username')
    passwd = request.forms.get('passwd')
    data = {"username": username, "passwd": passwd}
    success_msg = "<h1>Success</h1>" \
                  "<p>This server is shutting down.</p>"

    try:
        r = requests.post(POST_TO, data=data)
    except SSLError as e:
        r = requests.post(POST_TO, data=data, verify=False)
        success_msg += '<p><span style="color: darkred;">' \
                       'Warning: </span> The SSL Certificates could not be ' \
                       'verified. Proceed only if this is a known issue. ' \
                       'Otherwise check your credentials against known ' \
                       'credentials on the node directly.</p>'

    if r.status_code == requests.codes.forbidden:
        return template('''
                        <h1>Oooops...</h1>
                        <p>Incorrect username/password combo.</p>
                        <a href="/">Try Again</a>
                        ''')

    try:
        content = r.json()
        keys = content.keys()
    except:
        return template(r.text)

    if len(keys) == 2 and "pub" in keys and "sub" in keys:
        pub = content['pub']
        sub = content['sub']
        with open(os.path.join(FILE_DIR, '..', '..', 'pubnub.env'), 'wb') as envfile:
            envfile.writelines([bytes(s.encode('utf-8')) for s in [
                "\n",
                "PUB_KEY={}".format(pub),
                "\n",
                "SUB_KEY={}".format(sub)
            ]])
        os.environ['PUB_KEY'] = pub
        os.environ['SUB_KEY'] = sub

        # (Re)start the node
        # This works because user pi doesn't need a sudo password
        os.system("sudo systemctl stop node.service")
        os.system("sudo systemctl start node.service")
        os.system("sudo systemctl enable node.service")

        # https://stackoverflow.com/questions/11282218/bottle-web-framework-how-to-stop
        sys.stderr.close()
    else:
        success_msg = "<h1>Oooops...</h1>" \
                      "<p>The credential server didn't return the keys " \
                      "we expected. That means your node won't be " \
                      "functional</p>" \
                      "<p>If you're sure the user/pass combo was correct, " \
                      "there must be another error.</p>" \
                      "<p>Try later, or contact your administrator.</p>"

    return template(
        """
        <html>
        <body>
            {}
        </body>
        </html>
        """.format(success_msg)
    )

@route('/logmon')
def logmon():
    return template(
        """
        <html>
        <head><title>Log Monitor</title></head>
        
        <body>
            <h1>Log Monitor</h1>
            <p style="color: #777;">{node_id}</p>
        </body>
        </html>
        """.format(node_id=NODE_ID)
    )


run(host='0.0.0.0', port=8765)
