__author__ = 'nich'
import os
import jinja2
import webapp2
from PIL import Image
import json
import cloudstorage as gcs
import time
from io import BytesIO
from itertools import izip_longest # for Python 2.x
import urllib

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape=True)

client_id = 'f01e2c9c566d815'
client_secret = '67dfcab0bf2aab5ff531d1514b01117aa0dd5967'
# must be divisible by 3
SECRET_KEY = '000010101000000110011100111110011100000111001001000110100101011101111000111001001'
SECRET_LENGTH = len(SECRET_KEY)


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

    def modify_value(self, position_in_message, binary_message, pix_map, i,j, colorType):
        current_pixel = pix_map[i, j]
        if position_in_message >= len(binary_message):
                return current_pixel[colorType]
        new_val = bin(current_pixel[colorType])
        new_val = list(new_val)
        new_val[-1] = binary_message[position_in_message]
        new_val = int("".join(new_val), 2)
        return new_val

    def encode(self, message, image, password="password"):
        if len(password)==0:
            password="password"
        binary_message = ''.join('{:08b}'.format(ord(c)) for c in password)
        binary_message += ''.join('{:08b}'.format(ord(c)) for c in message)
        binary_message += '00000000'
        binary_message = SECRET_KEY + '{:08b}'.format(len(password)*8)+ binary_message

        pix_map = image.load()
        position_in_message = 0
        length = len(binary_message)
        for i in range(image.size[0]):	   # for every pixel:
            for j in range(image.size[1]):
                newPix = []
                for k in range(0,3):
                    newPix.append(int(self.modify_value(position_in_message,binary_message, pix_map, i,j,k)))
                    position_in_message +=1
                pix_map[i,j]=tuple(newPix)
                if position_in_message >= length:
                    return

    def post(self):
        if self.request.get('pic'):
            img = Image.open(BytesIO(self.request.get('pic')))
            msg = self.request.get('msg')
            resp = dict()
            if img and msg:
                filename = '/imageencode/' + str(int(round(time.time() * 1000))) + '.png'
                # Encodes the text into the image
                print 'encoding'
                self.encode(msg, img)
                print 'just encoded'
                # Creates a file with the given name
                self.make_file(filename, img)
                link = 'http://storage.googleapis.com' + filename
                print link
                if self.request.get('down_link'):
                    resp['down_link'] = link
                #return webapp2.redirect('http://storage.googleapis.com' + filename)
                if self.request.get('link'):
                    resp['link'] = link
                self.write(json.dumps(resp))

class Decode(Handler):
    def grouper(self, n, iterable, padvalue=None):
        """grouper(3, 'abcdefg', 'x') --> ('a','b','c'), ('d','e','f'), ('g','x','x')"""
        return izip_longest(*[iter(iterable)]*n, fillvalue=padvalue)

    def compare_index(self, current_pixel, colorType, compare_index):
        val = bin(current_pixel[colorType])
        last_val = val[-1]
        if compare_index<SECRET_LENGTH and last_val != SECRET_KEY[compare_index]:
            return True

    def decode(self, image, passwords=[]):
        passwords.insert(0,"password")
        message = ""
        compare_index = 0
        pix_map = image.load()
        binCount=''
        passLength = 0
        password = ''
        passwordList=[]

        for i in range(image.size[0]):
            for j in range(image.size[1]):
                if compare_index ==SECRET_LENGTH+8+passLength:
                    break
                current_pixel = pix_map[i, j]
                for k in range(0,3):
                    if self.compare_index(current_pixel,k, compare_index):
                            return None
                    compare_index += 1
                    if compare_index > SECRET_LENGTH:
                        binCount += str(bin(current_pixel[k])[-1])
                        if compare_index == SECRET_LENGTH+8:
                            passLength=int(binCount,2)
                        elif compare_index > SECRET_LENGTH+8:
                            #password+= str(bin(current_pixel[k])[-1])
                            passwordList.append(str(bin(current_pixel[k])[-1]))
                            if compare_index == SECRET_LENGTH+8+passLength:
                                password = self.grouper(8,''.join(passwordList),0)
                                break
        asciiPassword = ''
        for byte in password:
            character = ''.join(byte)
            asciiPassword += str(unichr(int(character, 2)))
        binary_message = ""
        binary_message_list=[]
        if asciiPassword in passwords:
            for i in range(image.size[0]):
                for j in range(image.size[1]):
                        current_pixel = pix_map[i, j]
                        red_val = bin(current_pixel[0])
                        green_val = bin(current_pixel[1])
                        blue_val = bin(current_pixel[2])
                        last_red_bit = red_val[len(red_val) - 1]
                        last_green_bit = green_val[len(green_val) - 1]
                        last_blue_bit = blue_val[len(blue_val) - 1]
                        binary_message_list.append(last_red_bit)
                        binary_message_list.append(last_green_bit)
                        binary_message_list.append(last_blue_bit)
            del binary_message_list[0:81+passLength+8]
            binary_message = self.grouper(8, ''.join(binary_message_list), 0)
            for byte in binary_message:
                character = ''.join(byte)
                if character == '00000000':
                    return message
                else:
                    message += str(unichr(int(character, 2)))
        else:
            return None

    def url_to_img(self, url):
        handle = urllib.urlopen(url)
        return Image.open(BytesIO(bytearray(handle.read())))

    def post(self):
        if self.request.get('urls'):
            urls = json.loads(self.request.get('urls'))
            resp = dict()
            i = 0
            for url in urls:
                splitUrl = url.split(".")
                #make sure url ends in .png or .jpg
                if "png" in splitUrl[-1] or "jpg" in splitUrl[-1] or "jpeg" in splitUrl[-1]:
                    img = self.url_to_img(url)
                    resp[url] = self.decode(img)
                    i += 1
            print json.dumps(resp)
            self.write(json.dumps(resp))

        elif self.request.get('url'):
            img = self.url_to_img(self.request.get('url'))
            msg = self.decode(img, [self.request.get('key')])
            print msg
            self.write(json.dumps(msg))

        elif self.request.get('pic'):
            img = Image.open(BytesIO(self.request.get('pic')))
            msg = self.decode(img, [self.request.get('key')])
            self.write(msg)





application = webapp2.WSGIApplication([
    ('/', Home), ('/encode', Encode), ('/decode', Decode)
], debug=True)