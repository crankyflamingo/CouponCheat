#VonsCouponCheater
#Grabs all available coupons and adds them to your Vons account.
#Saves having to do it manually via app/website.
#Author: crankyflamingo on Reddit.

import urllib2
import urllib
import io
import urlparse
import json
import socket
import urlparse
import re
import time
import random

#login details
#change this bit, the rest should work
username='your email address'
password='your password'

# Parse JSON and return a list of coupons not used yet
def GetListofCoupons(jsonobj, jsondealname, jsoncouponname):
    try:
        
        dictlist = jsonobj[jsondealname]
        offerlist = list()
    
        for member in dictlist:
            if member["status"] == "U":  # un-used on your account 
                offerlist.append(member[jsoncouponname])

        return offerlist  
    except:
        print "There was an error getting the data from the server. Exiting."
        exit()
               

# login to safeways terrible attempt at HTTP authentication (seriously, uri=realm=consumerPortal !??)
def LoginAndGetCookie():
    loginURL = "https://auth.safeway.com/opensso/identity/authenticate"
    loginbodydata = 'username='+urllib.quote_plus(username)+'&password='+urllib.quote_plus(password)
    
    # log in. They use a malformed http authentication. (should be uri=<blah>&realm=<blah>&user=<blah>...)
    fullURL = (loginURL + "?uri=realm%3DconsumerPortal" )

    req = urllib2.Request(fullURL)
    req.add_header('SWY_BANNER','Brand=VONS')
    req.add_header('SWY_VERSION','1.0')

    try:
        request = urllib2.urlopen(req, loginbodydata)
    except:
        print "Couldn't contact login site, exiting."
        exit()

    requestret = request.read().decode('utf-8')

    if not 'token.id' in requestret:        
        print 'error logging in to Vons site. Check credentials. Exiting.'
        exit()
            
    #extract cookie
    cookielist = requestret.split('=',1);
    cookiestring = cookielist.pop().split('\n',1).pop(0)

    return cookiestring

# the safeway site doesn't like standard JSON libraries (and you can't remove headers when using them)
# so I constructed them 1:1 the same as the app does it.
# makes call to safeway site
# retuns json string or error
def DoAndroidJSONCall(type, host, headers, bodydata):
    buffer = ""
    url = urlparse.urlparse(host)

    #construct GET or POST call
    if(type == 'GET'):
        sendbuf = "GET "+url.path+" HTTP/1.1\x0d\x0a"
    else:
        sendbuf = "POST "+url.path+" HTTP/1.1\x0d\x0a"
    
    #add headers
    for header in headers:
        sendbuf += (header + '\x0d\x0a')
    
    # add extra CRLF after headers
    sendbuf += '\x0d\x0a'   

    #add body data for POST
    sendbuf += bodydata
  
    #connect to site
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((url.netloc, 80))
        s.sendall(sendbuf)
    except:
        print "couldn't connect to site: ", url.path
        return "error: couldn't connect"

    #recv data
    while 1:
        # will throw timeout exception once no more data, breaking loop. 
        #Helps prevent hammering of their server.
        try:
            data = s.recv(4096) 
        except:
            break

         # this doesn't really do anything, but library examples use it
        if not data:
            break

        buffer += data

    s.close()
    
    # Attempt to parse JSON data if all went well, else return error string
    if 'HTTP/1.1 20' in buffer:     
        return GetJsonFromHTTP(buffer)
    elif 'HTTP/1.1 401' in buffer:
        return "error: unauthorised"
    else:
        return "error: malformed"

#throw away http headers, keep json stuff
#returns string of json
def GetJsonFromHTTP(rawhttpresponse):
    rawjson = ""    
    
    #deal with chunked http response
    #hooray for re
    rawjson = re.sub('\x0d\x0a\x30\x30......\x0d\x0a','',rawhttpresponse)   
    rawjson = rawjson.split('\x0d\x0a{',1).pop()
    rawjson = '{' + rawjson
    
    return str(rawjson)

#grabs all of the coupon ids not yet added to account
#returns a unique list of coupon ids
def GrabAllCoupons(globalcookie):
    # use cookie, API key to get all deals
    getpdoffersURL = "http://www.safeway.com/emmd/service/offer/pd"
    getmfgoffersURL = "http://www.safeway.com/emmd/service/offer/mfg"
    # todo. not many offers with this one, different format, timevs effort
    #url_get_ycs_offers = "http://www.safeway.com/J4UProgram1/services/program/YCS/offer/allocations"   
    
    offerURLs = [getpdoffersURL,getmfgoffersURL]

    getcouponsheaders = ['Content-Type: application/json', 'SWY_SSO_TOKEN: '+globalcookie, 'Cookie: swyConsumerDirectoryPro='+globalcookie,
                'SWY_BANNER: Brand=VONS', 'SWY_VERSION: 1.0', 'SWY_API_KEY: d0af2f73753a752d3968d0205ce88d94d353fabc.vons.j4u.android',
                'Host: www.safeway.com', 'Connection: Keep-Alive']

    # Get all our data into a list, or errors
    allthejson = list()
    for url in offerURLs:
        allthejson.append(DoAndroidJSONCall("GET", url, getcouponsheaders, ""))

    #turn it into json dicts if looks valid
    parsedjson = list();  
    for thejson in allthejson:
      if '{' == str(thejson[0:1]):
            parsedjson.append(json.loads(thejson))

    #extract out all coupons
    couponlist = list()
    for thejson in parsedjson:       
        if 'totalCount' in thejson:
            couponlist += GetListofCoupons(thejson, 'personalizedDeals', 'offerID')
        if 'resultCount' in thejson:
            couponlist += GetListofCoupons(thejson, 'manufacturerCoupons', 'couponID')

    #make unique, just in case, then return
    return list(set(couponlist))

#submits coupons to the site, adding them to the account
#returns list of remaining coupons to submit
def SubmitAllCoupons(couponlist, thecookie):
    #send 'em all to server, add to my card
    addcouponURL = "http://www.safeway.com/Clipping1/services/clip/offers"
    submitcouponsheaders = ['Cookie: swyConsumerDirectoryPro='+thecookie, 'SWY_SSO_TOKEN: '+thecookie, 
                'SWY_API_KEY: d0af2f73753a752d3968d0205ce88d94d353fabc.vons.j4u.android', 'Content-Type: application/json',
                'SWY_BANNER: Brand=VONS', 'SWY_VERSION: 1.0', 'Content-Length: xx', 'Host: www.safeway.com', 'Connection: Keep-Alive']
   
    for index, item in enumerate(couponlist):       
        
        #print "Submitting item ", item
        mydata = json.dumps({"offers":[item]})
        # remove space {"offers": ["1054884"]} isn't good -> {"offers":["1054884"]}
        mydata = re.sub(" ","",mydata)  
        submitcouponsheaders[6] = 'Content-Length: '+str(len(mydata))
            
        response = DoAndroidJSONCall("POST", addcouponURL, submitcouponsheaders, mydata)
       
        if('HTTP/1.1 401' in response):
            print "Logging in again due to bad server response... (Sent "+ str(index) + " this attempt of "+str(len(couponlist))+")... "
            # return remaining list upon error potential list overflow issue if on the last one already.
            return couponlist[index+1:len(couponlist)]    
        
        elif ('HTTP/1.1 20' not in response):
            print "Error submitting coupon: " + item

        if(index % 10 == 0):
            print "Submitted "+ str(index) + " so far ... of remaining " + str(len(couponlist))

    #return empty list once it's finished
    return list()

#main
print "Starting CouponCheat"

globalcookie = LoginAndGetCookie()

print "Logged in, obtained cookie, continuing ..."

couponlist = GrabAllCoupons(globalcookie)

print "Grabbed " + str(len(couponlist)) + " coupons from the site, adding to your account...\n"

#each time there is an error submitting the coupon, log in again and submit the remainder of the coupons
counter = 0
while len(couponlist) > 0:
    couponlist = SubmitAllCoupons(couponlist, LoginAndGetCookie())
    # sleep a bit, give server breather
    time.sleep(5)
    counter = counter + 1
    if counter > 9:
        print "Logged in 10 times to submit coupons, something isn't right... quitting"
        exit()
    
myinput = raw_input("Done! Press any key to continue")