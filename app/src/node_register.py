import uuid

from bottle import route, run, template

# POST_TO = "https://flock.starlingiot.com/register/{}".format(str(uuid.getnode()))
POST_TO = "http://localhost:8000/{}".format(str(uuid.getnode()))


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
              <input type="password" name="password" placeholder="Password" />
              <br/>
              <input type="submit" name="submit" value="Register Node" />
              </fieldset>
            </form>
        
        </div>
        
        </body>
        </html>
        """.format(post_to=POST_TO)
    )


run(host='localhost', port=8765)
