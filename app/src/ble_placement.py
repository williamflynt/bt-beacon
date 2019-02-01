import os

from bottle import route, run, template, request

try:
    from utility import get_pn_uuid
except ImportError:
    from app.src.utility import get_pn_uuid

INTERNAL_POST = "/locate"
NODE_ID = get_pn_uuid()
POST_TO = "https://localhost:8765/locate"
FILE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIVATE_DIR = os.path.join(FILE_DIR, "..", "..", "venv", "bin", "activate")


@route('/')
def index():
    x = os.environ.get("NODE_X", "X")
    y = os.environ.get("NODE_Y", "Y")
    return template(
        f"""
        <html>
        <head><title>Node Registration</title></head>
        <body>
        <div style="width: 400px;">
        
            <h1>BLE Scanner Location</h1>
            <hr/>
            
            <form action="{INTERNAL_POST}" method="post">
              <fieldset>
              <legend>Raspberry Pi Relative Location: </legend>
              <input type="text" name="x" placeholder="{x}" />
              <br />
              <input type="text" name="y" placeholder="{y}" />
              <br/>
              <input type="submit" name="submit" value="Set Pi Location" />
              </fieldset>
            </form>
        
        </div>
        
        </body>
        </html>
        """
    )


@route(INTERNAL_POST, method="POST")
def set_pi_location():
    x = request.forms.get('x')
    y = request.forms.get('y')
    success_msg = "<h1>Success</h1>" \
                  "<p>This Raspberry Pi will use new coordinates on reboot.</p>"

    try:
        x = int(x)
        y = int(y)
        os.environ["NODE_X"] = x
        os.environ["NODE_Y"] = y
        with open(ACTIVATE_DIR, "w") as f:
            f.writelines([
                "\n", "\n", "# Set BLE scanner coordinates in meters",
                f"export NODE_X={x}", f"export NODE_X={y}", "\n", "\n"
            ])

    except Exception as e:
        return template(
            f"""
            <html>
            <body>
                <h3>Oops</h3>
                <p>{e}</p>
            </body>
            </html>
            """
        )

    return template(
        f"""
        <html>
        <body>
            {success_msg}
        </body>
        </html>
        """
    )


@route('/logmon')
def logmon():
    return template(
        f"""
        <html>
        <head><title>Log Monitor</title></head>
        
        <body>
            <h1>Log Monitor</h1>
            <p style="color: #777;">{NODE_ID}</p>
        </body>
        </html>
        """
    )


run(host='0.0.0.0', port=8765)
