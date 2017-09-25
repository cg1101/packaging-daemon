#!/usr/bin/python

import email, poplib
from email.Header import decode_header

server = 'sndserver'
username = 'test1'
password = 'abc123'

import re
p = re.compile(ur"Package:\s*NeonVM.*", re.IGNORECASE)

def checkRequest():
	requests = []
	M = poplib.POP3(server)
	M.user(username)
	M.pass_(password)
	el = M.list()[1]
	for i in range(len(el)):
		lines = M.retr(i + 1)[1]
		msg = email.message_from_string("\r\n".join(lines))
		if not msg.has_key('Subject'): continue
		s, enc = decode_header(msg.get_all("Subject")[0])[0]
		if not enc:
			s = unicode(s)
		else:
			s = unicode(s, enc)
		# is is a request?
		if not p.match(s): continue
		# requester must be present in order to be processed
		if not msg.has_key('From'): continue
		# add to target list
		requests.append((s, msg.get_all('From'), msg.get_all('Cc'), ))
		M.dele(i + 1)
	M.quit()
	return requests
# end of checkRequest

def main():
	requests = checkRequest()
	for s, f, c in requests:
		print "Subject: " + s
		print "From:    " + ",".join(f)
		if c: print "Cc:      " + ",".join(c)
# end of main

if __name__ == "__main__":
	main()
# end of main

