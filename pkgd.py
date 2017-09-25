#!/usr/bin/python

import os, sys
import signal, time, logging

# default settings for daemon 
WORKDIR = "/"
UMASK   = 0
MAXFD   = 1024	# default maximal file descriptors

if hasattr(os, "devnull"):
	REDIRECT_TO = os.devnull
else:
	REDIRECT_TO = "/dev/null"

def daemonize():
	if os.getppid() == 1:	# already a daemon
		return

	pid = os.fork()
	if pid > 0: os._exit(0)	# exit parent

	os.setsid()
	pid = os.fork()
	if pid > 0: os._exit(0)	# exit 1st child

	# now we're in the 2nd child
	os.chdir(WORKDIR)
	os.umask(UMASK)

	import resource
	maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
	if (maxfd == resource.RLIM_INFINITY):
		maxfd = MAXFD
	
	# close all existing file descriptors
	for fd in range(maxfd):
		try:
			os.close(fd)
		except OSError:
			pass
	
	os.open(REDIRECT_TO, os.O_RDWR)
	os.dup2(0, 1)
	os.dup2(0, 2)

	return 0
# end of daemonize

class ShouldQuit:
	pass

class ReloadSettings:
	pass

def signal_handler(signum, frame):
	if signum == signal.SIGTERM:
		raise ShouldQuit
	elif signum == signal.SIGHUP:
		raise ReloadSettings
# end of signal_handler

from logging import debug, info, warning, error, critical

import email, poplib, smtplib
from email.Header import decode_header

import re
p = re.compile(ur"""
	Package(?:\s*:\s*|\s+)NeonVM     # keyword
	(?:\s*:\s*|\s+)
	(?P<delivery_type>[A-Z]+)        # delivery-type
	\.
	(?P<locale>[A-Z]{2}-[A-Z]{2})    # locale
	(?P<audio>\s*\+\s*audio)?        # audio only
	""", re.IGNORECASE | re.VERBOSE)
def parseRequest(msg):
	# check mandatory header fields
	if not msg.has_key("Subject"): return None
	if not msg.has_key("From"): return None

	# parse the first subject header only
	s, enc = decode_header(msg.get_all("Subject")[0])[0]
	if not enc:
		s = unicode(s)
	else:
		s = unicode(s, enc)
	m = p.match(s)
	if not m: return None

	# normalize request
	gd = m.groupdict()
	delivery_type = gd["delivery_type"].upper()
	if delivery_type == "CANDC": delivery_type = "CandC"
	locale = gd["locale"].lower()
	locale = locale[:3] + locale[3:].upper()
	if gd.has_key("audio") and gd["audio"]:
		target = delivery_type + "." + locale + "+audio"
	else:
		target = delivery_type + "." + locale

	# normalize "From" entries
	fromlist = []
	for entry in msg.get_all("From", []):
		uentry = u""
		for partition, enc in decode_header(entry):
			if not enc:
				uentry += unicode(partition)
			else:
				uentry += unicode(partition, enc)
		fromlist.append(uentry)
			
	# normalize "Cc" entries
	cclist = []
	for entry in msg.get_all("Cc", []):
		uentry = u""
		for partition, enc in decode_header(entry):
			if not enc:
				uentry += unicode(partition)
			else:
				uentry += unicode(partition, enc)
		cclist.append(uentry)

	return (target, fromlist, cclist)
# end of parseRequest

def checkRequest(server, username, password):
	requests = []
	try:
		M = poplib.POP3(server)
		M.user(username)
		M.pass_(password)
		el = M.list()[1]
		for i in range(len(el)):
			lines = M.retr(i + 1)[1]
			msg = email.message_from_string("\r\n".join(lines))
			r = parseRequest(msg)
			if r:
				requests.append(r)
				M.dele(i + 1)
		M.quit()
	finally:
		return requests
# end of checkRequest

def load_settings():
	server = "sndserver"
	username = "test1"
	password = "abc123"
	interval = 60
	return (server, username, password, interval)
# end of load_settings

from email.mime.text import MIMEText
def handle_request(request):
	target, fromlist, cclist = request
	info("handling request: %s, From: %s Cc: %s" % \
			(target, ",".join(fromlist), ",".join(cclist)))
	outpath = "/audio/10354_NeonVoiceMail/Delivery/" + target.split("+")[0]
	toaddr = ",".join(fromlist)
	ccaddr = ",".join(cclist)
	msg = """Hello, 
Your requested for packaging %s has been received and processed. Please 
check %s for output files.

Thanks,
Packaging Agent""" % (target, outpath)
	msg = MIMEText(msg)
	msg["Subject"] = "Request for packaging " + target
	msg["From"] = "test1@appen.com.au"
	msg["To"] = toaddr
	msg["Cc"] = ccaddr
	try:
		S = smtplib.SMTP('sndserver')
		S.sendmail('test1@appen.com.au', toaddr, msg.as_string())
		S.quit()
	except:
		debug("error sending email notice")
	return
# end of handle_request

from handler import handle_request

def main():
	# setup logging facilities
	logging.basicConfig(level=logging.DEBUG, 
			format="%(asctime)s %(message)s",
			filename="/tmp/pkgd.log")
	debug("pkgd started")

	# install signal handlers
	signal.signal(signal.SIGHUP, signal_handler)
	signal.signal(signal.SIGTERM, signal_handler)
	signal.signal(signal.SIGCHLD, signal.SIG_IGN)
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	signal.signal(signal.SIGTTOU, signal.SIG_IGN)
	signal.signal(signal.SIGTTIN, signal.SIG_IGN)

	# load settings
	server, username, password, interval = load_settings()

	while True:
		try:
			info("checking for quests")
			requests = checkRequest(server, username, password)
			if not requests:
				info("no requests found")
			else:
				info("received %d request(s)" % len(requests))
				for r in requests: handle_request(r)
			debug("go to sleep")
			time.sleep(interval)
			debug("wake again")
		except ReloadSettings:
			info("received request to reload settings")
			server, username, password, interval = load_settings()
			continue
		except ShouldQuit:
			info("received request to quit")
			break
		except Exception, e:
			debug("caught unexpected error: %s" % e)
			break
	debug("exit")
	logging.shutdown()
# end of main

PIDFILE = "/tmp/pkgd.pid"	# should be "/var/run/pkgd.pid"

if __name__ == "__main__":
	try:
		daemonize()
	except OSError, e:
		print >>sys.stderr, e
		sys.exit(1)

	# check pid lock
	import fcntl
	lfd = os.open(PIDFILE, os.O_RDWR | os.O_CREAT, 0640)
	try:
		fcntl.lockf(lfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
	except IOError, e:
		# another instance is running
		os.close(lfd)
		sys.exit(0)
	
	# run program now
	try:
		os.write(lfd, "%d\n" % os.getpid())
		main()
	finally:	# always remove pid file at last
		os.close(lfd)
		os.remove(PIDFILE)
	sys.exit(os.EX_OK)
# end of main

