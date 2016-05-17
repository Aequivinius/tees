#!/usr/bin/env python

# when calling command line, we call classify with different options
# can be called classify(input,model,output)

# input needs to be in interaction XML?

from jbjorne.Detectors.Preprocessor import Preprocessor
from jbjorne.train import workdir, getDetector, getSteps
import os
import gzip
from jbjorne.classify import classify , getModel

import xml.etree.ElementTree as ET
import json
import shutil

from flask import Flask, request , make_response , render_template

import tempfile

app = Flask(__name__)


@app.route('/tees_rest/', methods = ['GET','POST'])
def rest():
	"""Requests using curl -d supplying a 'text' argument"""
	
	if request.headers['Content-Type'] == 'application/json':
		if 'text' in request.get_json():
			try:
				result = mywrapper(request.get_json()['text'])
				return(result)
			except Exception as e:
				print(e)
				return("Error while processing request for '{}'.\n".format(request.get_json()['text']),500)
		return(400)
	
	if request.headers['Content-Type'] == 'application/x-www-form-urlencoded':
		if 'text' in request.form:
			try:
				result = mywrapper(request.form['text'])
				return(result)
			except Exception as e:
				print(e)
				return("Error while processing request for '{}'.\n".format(request.form['text']),500)
		return(400)
		
	return("Unsupported media type.",415)

def mywrapper(input_text):
	
	# could also use import uuid
	# tf = str(uuid.uuid4())
	tf = tempfile.NamedTemporaryFile(suffix=".txt")
		
	with open(tf.name,'w') as f:
		f.write(input_text)
		
	myclassify(tf.name,'output/' + tf.name)
	os.remove(tf.name)
	
	pa = None
	with gzip.open('output/{}-pred.xml.gz'.format(tf.name)) as f:
		# pa = tees_to_pubannotation(f.read())
		pa = tees_events_to_pubannotation(f.read())
	
	for f in os.listdir('output'):
		g = os.path.join('output',f)
		try:
			if os.path.isfile(g):
				os.remove(g)
			elif os.path.isdir(g):
				shutil.rmtree(g)
		except Exception as e:
			print(e)
	print(pa)
	return(pa)
	
def tees_events_to_pubannotation(input):
	root = ET.fromstring(input) # from parses directly into an Element
	text = root.find("document").get("text")
	
	# now, entities are denotations, and interactions are relations
		
	pre_json = { "text" : text }
	pre_json["denotations"] = list()
	pre_json["relations"] = list()
	
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
	
	for interaction in root.findall(".//interaction"):
		interaction_dict = dict()
		interaction_dict["id"] = interaction.get("id")
		interaction_dict["subj"] = interaction.get("e1")
		interaction_dict["obj"] = interaction.get("e2")
		interaction_dict["pred"] = interaction.get("type")
		
		pre_json["relations"].append(interaction_dict)		
	return(json.dumps(pre_json,sort_keys=True,indent=4))	
		

def tees_to_pubannotation(input):
	
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

def myclassify(input,output):
	
	# Define processing steps
	selector, detectorSteps, omitDetectorSteps = getSteps(None, None, ["PREPROCESS", "CLASSIFY"])
	
#	model = getModel(model)
#	preprocessor = Preprocessor()
	
	classifyInput = preprocessor.process(input, (output + "-preprocessed.xml.gz"), None, model, [], fromStep=detectorSteps["PREPROCESS"],omitSteps=["TEST","EVALUATE","EVALUATION"])
	
	
	detector.classify(classifyInput, model, output, fromStep=detectorSteps["CLASSIFY"],omitSteps=["TEST","EVALUATE","EVALUATION"])
	


model = getModel("GE11-test")
preprocessor = Preprocessor()
preprocessor.stepArgs("PARSE")["requireEntities"] = True
detector = getDetector(None, model)[0]()

if __name__=="__main__":
#	mywrapper("I saw the best minds of my generation destroyed by madness, starving hysterical naked, dragging themselves to the Negro streets at dawn looking for an angry fix.")

	app.run(debug=True)