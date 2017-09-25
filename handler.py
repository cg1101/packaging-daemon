#!/usr/bin/python

import nis, email.utils
def getRecipientName(address):
	(realname, email_addr) = email.utils.parseaddr(address)
	if realname: return realname
	t = email_addr.split("@")
	login = t[0]
	if len(t) == 1 or t[1].endswith("appen.com.au"):
		try:
			entry = nis.match(login, 'passwd.byname')
			fullname = entry.split(":")[4]
			name = fullname.split(" ")[0]
		except:
			name = login
	else:
		name = login
	return name
# end of getRecipientName

class TaskException(Exception):
	pass

NEONVM_ROOT = "/home/appen/Projects/Neon/VM_Telephony/"
NEONVM_FAMILY = {
	"de-DE": { "path": "German", "subtype": ["TEST", "DEV"], "desc": "German", }, 
	"en-AU": { "path": "AustralianEnglish", "subtype": ["TEST", "DEV"], "desc": "Australian English", },
	"en-GB": { "path": "UKEnglish", "subtype": ["TEST", "DEV"], "desc": "UK English", },
	"en-US": { "path": "USEnglish", "subtype": ["TEST", "DEV"], "desc": "US English", },
	"es-ES": { "path": "Spanish", "subtype": ["TEST", "DEV"], "desc": "Spanish", },
	"es-MX": { "path": "MexicanSpanish", "subtype": ["TEST", "DEV"], "desc": "Mexican Spanish", },
	"fr-CA": { "path": "CanadianFrench", "subtype": ["TEST", "DEV"], "desc": "Canadian French", },
	"fr-FR": { "path": "French", "subtype": ["TEST", "DEV"], "desc": "French", },
	"it-IT": { "path": "Italian", "subtype": ["TEST", "DEV"], "desc": "Italian", },
	"ja-JP": { "path": "Japanese", "subtype": ["TEST", "DEV"], "desc": "Japanese", },
	"ko-KR": { "path": "Korean", "subtype": ["TEST", "DEV"], "desc": "Korean", },
	"nl-NL": { "path": "Dutch", "subtype": ["TEST", "DEV"], "desc": "Dutch", },
	"pt-BR": { "path": "BrazilianPortuguese", "subtype": ["TEST", "DEV"], "desc": "Brazilian Portuguese", },
	"sv-SE": { "path": "Swedish", "subtype": ["TEST", "DEV", "CandC"], "desc": "Swedish", },
	"zh-CN": { "path": "ChineseMandarin", "subtype": ["TEST", "DEV"], "desc": "China (PRC) - Mandarin", },
	"zh-TW": { "path": "MandarinTaiwan", "subtype": ["TEST", "DEV", "CandC"], "desc": "Chinese (Taiwan)", },
}

import os, sys
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
import email, smtplib
import subprocess

import logging
debug = logging.debug
info = logging.info
def handle_request(request):
	"""
	Handle NeonVM packaging request, send out notice on completion.
	"""
	target, fromlist, cclist = request
	info("handling request: %s, From: %s Cc: %s" % \
			(target, ",".join(fromlist), ",".join(cclist)))
	t = target.split("+")
	audio = (len(t) > 1 and t[1] == "audio")
	deliveryType, locale = t[0].split(".")
	
	success = False
	reason = ""
	try:
		if locale not in NEONVM_FAMILY:
			raise TaskException, t[0] + ": settings not found"

		settings = NEONVM_FAMILY[locale]
		if deliveryType not in settings["subtype"]:
			raise TaskException, deliveryType + ": not a valid " \
					"delivery type of " + settings["desc"] + "."
	
		inputPath = os.path.join(os.path.join(NEONVM_ROOT, 
				settings["path"]), "Packaging_" + deliveryType)
	
		demog = os.path.join(inputPath, "Demog_%s_%s.csv" % \
				(locale, deliveryType))
		master = os.path.join(inputPath, "MasterScript_%s_%s.txt" % \
				(locale, deliveryType))
		category = os.path.join(inputPath, "CategoryID_%s_%s.txt" % \
				(locale, deliveryType))
		txfiles = [j for j in [os.path.join(inputPath, i) for i in \
				os.listdir(inputPath) if i.lower().startswith("trans.")]\
				if os.path.isfile(j)]

		if not os.path.isfile(demog):
			raise TaskException, "cannot access demographics file: " \
					"'%s'" % demog
		if not os.path.isfile(master):
			raise TaskException, "cannot access master script: " \
					"'%s'" % master
		if not os.path.isfile(category):
			raise TaskException, "cannot access category map file: " \
					"'%s'" % category
		if not txfiles:
			raise TaskException, "no transcription files found in " \
					"'%s'" % inputPath
		args = ["/home/gcheng/work/NeonVM/pkgNeonVM.py", 
			"--locale", locale, 
			"--delivery-type", deliveryType, 
			"--outpath=/tmp", "--zip", demog, master, category, ]
		args.extend(txfiles)

		# call packer program
		debug("call packaging script:" + " ".join(args))
		#packer = subprocess.Popen(args, stderr=subprocess.PIPE)
		#errors = [i for i in packer.stderr]
		#result = packer.wait()
		#if result != 0:
		#	debug("failed")
		#	raise TaskException, "\n".join(errors)

		stdin, stdout, stderr = os.popen3(" ".join(args))
		errors = [i for i in stderr]
		if errors:
			debug("failed")
			raise TaskException, "\n".join(errors)

		# success
		debug("succeeded")
		success = True
	except TaskException, e:
		reason = e
	except OSError, e:
		debug(e.child_traceback)
		reason = "Internal error: %s" % e

	dat = {
		"recipient": getRecipientName(fromlist[0]), 
		"reason": reason, 
		"target":target, 
	}
	toaddr = ",".join(fromlist)
	ccaddr = ",".join(cclist)

	if success:
		# send success notice
		brief = MIMEText("""Hello, %(recipient)s, 

Your request for packaging %(target)s has been received and processed. 
Please find output in attachment.

Thanks,
Packaging Agent""" % dat)
		debug(brief)
		zipname = "%s.%s.zip" % (deliveryType, locale)
		zipfile = open(os.path.join("/tmp", zipname), "rb")
		zipdata = zipfile.read()
		zipfile.close()
		attachment = MIMEApplication(zipdata, "zip")
		attachment.add_header("Content-Disposition", "attachment", filename=zipname)

		msg = MIMEMultipart()
		msg.attach(brief)
		msg.attach(attachment)
	else:
		# send failure notice
		msg = MIMEText("""Hello, %(recipient)s, 

Processing of your request for packaging %(target)s has failed due to 
following reason(s):

%(reason)s

Please make corrections accordingly and try again.

Thanks,
Packaging Agent""" % dat)

	# send notice now
	msg["Subject"] = "Request for packaging " + target
	msg["From"] = "test1@appen.com.au"
	msg["To"] = toaddr
	msg["Cc"] = ccaddr

	#f = open("/tmp/mailnotice.txt", "w")
	#f.write(msg.as_string())
	#f.close()
	#print "Sending email to:", toaddr
	try:
		S = smtplib.SMTP('sndserver')
		S.sendmail('test1@appen.com.au', toaddr, msg.as_string())
		S.close()
	except e:
	#	print 'failed sending email', e
		debug("error sending email notice")
	pass
# end of handle_request

def main():
	logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

	# run a test
	target = raw_input("packaging target-> ")
	fromlist = raw_input("from list-> ").split(",")
	cclist = raw_input("cc list-> ").split(",")

	handle_request((target, fromlist, cclist))
# end of main

if __name__ == "__main__":
	main()
# end of program

