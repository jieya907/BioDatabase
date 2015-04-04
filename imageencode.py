__author__ = 'nich'
import os
import jinja2
import webapp2
from PIL import Image
import json
import cloudstorage as gcs
import time
from io import BytesIO
from imgurpython import ImgurClient

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape=True)

client_id = 'f01e2c9c566d815'
client_secret = '67dfcab0bf2aab5ff531d1514b01117aa0dd5967'

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

class Home(Handler):
    def get(self):
        self.render('home.html')

class Encode(Handler):
    """Create a file.

    The retry_params specified in the open call will override the default
    retry params for this particular file handle.

    Args:
      filename: filename.
    """
    def make_file(self, filename, img):
        write_retry_params = gcs.RetryParams(backoff_factor=1.1)
        gcs_file = gcs.open(filename, 'w', content_type='image/png', options={'x-goog-acl': 'public-read'},
                            retry_params=write_retry_params)
        img.save(gcs_file, 'png')
        gcs_file.close()

    def encode(self, img, msg):
        return img

    def post(self):
        if self.request.get('pic'):
            img = Image.open(BytesIO(self.request.get('pic')))
            msg = self.request.get('msg')
            resp = dict()
            if img and msg:
                filename = '/imageencrypt/' + str(int(round(time.time() * 1000))) + '.png'
                # Encodes the text into the image
                encoded = self.encode(img, msg)
                # Creates a file with the given name
                self.make_file(filename, encoded)
                link = 'http://storage.googleapis.com' + filename
                if self.request.get('down_link'):
                    resp['down_link'] = link
                #return webapp2.redirect('http://storage.googleapis.com' + filename)
                if self.request.get('imgur'):
                    client = ImgurClient(client_id, client_secret)
                    resp['imgur'] = client.upload_from_url(link)
                self.write(json.dumps(resp))

class Decode(Handler):
    def get_msg(self, url, i):
        return 'swag it ' + i

    def post(self):
        print 'hi'
        if self.request.get('urls'):
            print 'there'
            urls = json.loads(self.request.get('urls'))
            resp = dict()
            i = 0;
            for url in urls:
                splitUrl = url.split(".");
                if "png" in splitUrl[-1] or "jpg" in splitUrl[-1] or "jpeg" in splitUrl[-1]:
                #make sure url ends in .png or .jpg
                    resp[url] = self.get_msg(url, i)
                    i += 1
            print json.dumps(resp)
            self.write(json.dumps(resp))




application = webapp2.WSGIApplication([
    ('/', Home), ('/encode', Encode), ('/decode', Decode)
], debug=True)