import requests
import uuid

import bottle
from bottle import route, run, template, request

INTERNAL_POST = "/getkeys"
# POST_TO = "https://flock.starlingiot.com/register/{}".format(str(uuid.getnode()))
POST_TO = "http://localhost:8000/nodes/register/{}".format(str(uuid.getnode()))

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

    r = requests.post(POST_TO, data=data)
    content = r.json()
    keys = content.keys()

    if len(keys) == 2 and "pub" in keys and "sub" in keys:
        # Write to env / file / service
        # Start the node
        # Kill bottle (also do this check on startup)
        return template(
            """
            <html>
            <body>
            {}
            </body>
            </html>
            """.format(content)
        )


run(host='localhost', port=8765)
