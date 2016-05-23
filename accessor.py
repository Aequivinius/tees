#!/usr/bin/env python

"""Runs a server using Flask which will listen to requests on /tees_rest/.
   Input text will be processed using TEES pipeline, and events found by
   TEES returned in PubAnnotate JSON"""

#######
# TO DO
#######

# The TEES pipeline is slow AF, and I think it's got to do
# with the fact that it tries to evaluate : BioNLP11GeniaTools.py
# will print a message in the end, which is not needed at all

# Ideally, we find a way to create a new process for every request
# so we don't get cross-talk

# Finally, we could look into asynchronous REST, since it takes
# some 40s per document

# here jbjorne refers to the directory containing TEES
# assumed to be in the same directory as this accessor.py
from jbjorne.Detectors.Preprocessor import Preprocessor
from jbjorne.train import getDetector, getSteps
from jbjorne.classify import getModel

from flask import Flask, request , make_response

from helpers import trunc

import os
import gzip
import xml.etree.ElementTree as ET
import json
import tempfile
import shutil

# initialise Flask in order to be able to deal
# with decorators such as @app.route below
app = Flask(__name__)

# listen to /tees_rest/ for requests
@app.route('/tees_rest/', methods = ['GET','POST'])
def rest():
	"""Requests using curl -d supplying a 'text' argument"""
	
	# 'text' can hide in two locations:
	# in request.form['text'] or in request.get_json()['text']
	if request.get_json() and 'text' in request.get_json():
		input = request.get_json()['text']
	elif request.form and 'text' in request.form:
		input = request.form['text']
	else:
		return("Could not find 'text' attribute to process.",400)
		
	# Check if input is ASCII
	try:
		input.decode('ascii')
	except UnicodeDecodeError:
		return("Currently, the pipeline can only process ASCII-encoded input",400)
	
	# call the pipeline
	try:
		result = input_to_response(input)
		return(result,200)
	except Exception as e:
		print(e)
		return("Error while processing request for '{}'.\n".format(trunc(input)),500)

#####################
# THE ACTUAL PIPELINE
#####################
def input_to_response(input):
	"""Prepares input for the TEES pipeline to read, runs the pipeline and returns JSON response."""
	
	# pipeline only accepts input as file, or I haven't
	# found a way to supply text directly yet, so we
	# write input to temporary file
	td = tempfile.mkdtemp()
	to = os.path.join(td,'output')
	ti = os.path.join(td,'input.txt')
	
	with open(ti,'wb+') as tf:
		tf.write(input)
		# because we're writing in binary mode for better cross-platformibility
		tf.seek(0) 
		tees_wrapper(ti,to)
	
	try:
		with gzip.open(str(to) + '-pred.xml.gz') as xml:
			json_ = xml_events_to_json(xml.read())
			response = json_to_response(json_)
			return(response)
	except Exception as e:
		print(e)
	
	finally:
		# clean up temporary folders & files
		shutil.rmtree(td)
	
def json_to_response(json_):
	"""Adds information to response headers to smoother running."""
	response = make_response(json_)

	# This is necessary to allow the REST be accessed from other domains
	response.headers['Access-Control-Allow-Origin'] = '*'

	response.headers['Content-Type'] = 'application/json'
	response.headers['Content-Length'] = len(json_)
	response.headers['X-Content-Type-Options'] = 'nosniff'
	response.headers['charset'] = 'ascii'
	return(response)

def xml_events_to_json(input):
	"""Extracts events from XML and rephrases them into JSON:
	   Entities are stored as denotations, interactions as relations."""

	root = ET.fromstring(input) # fromstring parses directly into an Element
	text = root.find("document").get("text")		
	pre_json = { "text" : text }
	pre_json["denotations"] = list()
	pre_json["relations"] = list()
	
	# for entities, the offset is stored on a per-sentence basis in the XML
	# thus we need to traverse sentence to sentence to recompute offsets
	# to be valid in the per-document view
	for sentence in root.findall(".//sentence"):
		sentence_offset = int(sentence.get("charOffset").split("-")[0])
		for entity in sentence.findall(".//entity"):
			entity_dict = dict()
			entity_dict["id"] = entity.get("id")
			
			start_span , end_span = entity.get("charOffset").split("-")
			start_span = int(start_span)
			end_span = int(end_span)
			entity_dict["span"] = { "begin" : sentence_offset+start_span , "end" : sentence_offset+end_span }
			
			entity_dict["obj"] = entity.get("type")
			
			pre_json["denotations"].append(entity_dict)
	
	# these are our relations
	for interaction in root.findall(".//interaction"):
		interaction_dict = dict()
		interaction_dict["id"] = interaction.get("id")
		interaction_dict["subj"] = interaction.get("e2")
		interaction_dict["obj"] = interaction.get("e1")

		# to make compatible with BioNLP 2016 GE-task,
		# we change 'A Theme B' to 'B themeOf A' etc.
		if interaction.get("type") in [ "Theme" , "theme" ]:
			interaction_dict["pred"] = "ThemeOf"
			
		elif interaction.get("type") in [ "Cause" , "cause" ]:
			interaction_dict["pred"] = "CauseOf"
			
		elif interaction.get("type") in [ "AtLoc" , "atLoc" , "ToLoc" , "toLoc" ]:
			interaction_dict["pred"] = "LocationOf"
			
		elif interaction.get("type") in [ "SiteParent" , "siteParent" ]:
			interaction_dict["pred"] = "PartOf"
				
		else:	
			interaction_dict["pred"] = interaction.get("type")
		
		pre_json["relations"].append(interaction_dict)
		
	# prettify before returning
	pretty_json = json.dumps(pre_json,sort_keys=True,indent=4)
	print(pretty_json)
	return(pretty_json)	
		

def xml_to_json(input):
	"""Exctracts PoS and parse information from XML"""
	root = ET.fromstring(input) # from parses directly into an Element
	text = root.find("document").get("text")
		
	pre_json = { "text" : text }
	pre_json["denotations"] = list()
	pre_json["relations"] = list()
	
	
	for token in root.findall(".//token"):
		token_dict = dict()
		token_dict["id"] = token.get("id")
		
		start_span , end_span = token.get("charOffset").split("-")
		token_dict["span"] = { "begin" : int(start_span) , "end" : int(end_span) }
		
		token_dict["obj"] = token.get("POS")
		
		pre_json["denotations"].append(token_dict)
	
	for dependency in root.findall(".//dependency"):
		relation_dict = dict()
		relation_dict["id"] = dependency.get("id")
		relation_dict["subj"] = dependency.get("t1")
		relation_dict["obj"] = dependency.get("t2")
		relation_dict["pred"] = dependency.get("type")
		
		pre_json["relations"].append(relation_dict)		
	return(json.dumps(pre_json,sort_keys=True,indent=4))

def tees_wrapper(input,output):
	"""Runs the TEES pipeline. Will read input text file, and write to output directory"""
	
	# Define processing steps
	selector, detectorSteps, omitDetectorSteps = getSteps(None, None, ["PREPROCESS", "CLASSIFY"])
	
	# The TEES documentation is very annoying, making it a big hassle and guessing game
	# Which arguments to supply where
	classifyInput = preprocessor.process(input, (output + "-preprocessed.xml.gz"), None, model, [], fromStep=detectorSteps["PREPROCESS"],omitSteps=["TEST","EVALUATE","EVALUATION"])
	
	detector.classify(classifyInput, model, output, fromStep=detectorSteps["CLASSIFY"],omitSteps=["TEST","EVALUATE","EVALUATION"])

# GLOBAL variables held in memory by the server
model = getModel("GE11")
preprocessor = Preprocessor()
preprocessor.stepArgs("PARSE")["requireEntities"] = True # this will speed up processing
detector = getDetector(None, model)[0]()

if __name__=="__main__":
	app.run(debug=True)